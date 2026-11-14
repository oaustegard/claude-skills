"""Tests for flowing control-flow primitives.

Coverage:
- v1.0 backward compat (existing DAG, retry, override, resume, detached)
- v1.1: when= conditional gate
- v1.1: validate= edge contract
- v1.1: retry_until= predicate loop
- Composition of new primitives
- v1.3: timeout_s enforcement, signature validation, clear_registry
- v1.6: undo= compensation, snapshot()/restore(), ROLLED_BACK state
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from flowing import Flow, StepState, clear_registry, restore, snapshot, task


class TestBackwardCompat(unittest.TestCase):
    """v1.0 features must keep working unchanged."""

    def test_simple_chain(self):
        @task
        def a():
            return 1

        @task(depends_on=[a])
        def b(a):
            return a + 1

        @task(depends_on=[b])
        def c(b):
            return b * 10

        flow = Flow(c)
        flow.run()
        self.assertEqual(flow.value(c), 20)

    def test_retry_on_exception(self):
        calls = {"n": 0}

        @task(retry=2, retry_backoff_base_ms=1)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("nope")
            return "ok"

        flow = Flow(flaky)
        flow.run()
        self.assertEqual(flow.value(flaky), "ok")
        self.assertEqual(calls["n"], 3)

    def test_failure_propagates_skip(self):
        @task
        def fails():
            raise RuntimeError("boom")

        @task(depends_on=[fails])
        def downstream(fails):
            return fails + 1

        flow = Flow(downstream, fail_fast=False)
        flow.run()
        self.assertEqual(flow.results["fails"].state, StepState.FAILED)
        self.assertEqual(flow.results["downstream"].state, StepState.SKIPPED)

    def test_override_and_resume(self):
        calls = {"a": 0, "b": 0}

        @task
        def a():
            calls["a"] += 1
            return 5

        @task(depends_on=[a])
        def b(a):
            calls["b"] += 1
            if calls["b"] == 1:
                raise RuntimeError("first call fails")
            return a * 2

        flow = Flow(b)
        flow.run()
        self.assertEqual(flow.results["b"].state, StepState.FAILED)
        flow.resume()
        self.assertEqual(flow.value(b), 10)
        self.assertEqual(calls["a"], 1, "succeeded task should not re-run")


class TestWhenGate(unittest.TestCase):
    """when= conditional skip — falsy returns mark task SKIPPED."""

    def test_when_true_runs(self):
        @task
        def upstream():
            return {"ready": True}

        @task(depends_on=[upstream], when=lambda upstream: upstream["ready"])
        def gated(upstream):
            return "ran"

        flow = Flow(gated)
        flow.run()
        self.assertEqual(flow.results["gated"].state, StepState.SUCCEEDED)
        self.assertEqual(flow.value(gated), "ran")

    def test_when_false_skips(self):
        ran = {"flag": False}

        @task
        def upstream():
            return {"ready": False}

        @task(depends_on=[upstream], when=lambda upstream: upstream["ready"])
        def gated(upstream):
            ran["flag"] = True
            return "should not run"

        flow = Flow(gated)
        flow.run()
        self.assertEqual(flow.results["gated"].state, StepState.SKIPPED)
        self.assertFalse(ran["flag"], "task body must not execute when when() is False")

    def test_when_skip_propagates_to_dependents(self):
        @task
        def upstream():
            return {"ready": False}

        @task(depends_on=[upstream], when=lambda upstream: upstream["ready"])
        def middle(upstream):
            return "middle"

        @task(depends_on=[middle])
        def downstream(middle):
            return middle + " + downstream"

        flow = Flow(downstream)
        flow.run()
        self.assertEqual(flow.results["middle"].state, StepState.SKIPPED)
        self.assertEqual(flow.results["downstream"].state, StepState.SKIPPED)

    def test_when_raises_fails(self):
        @task
        def upstream():
            return {"ready": True}

        @task(depends_on=[upstream], when=lambda upstream: 1 / 0)
        def gated(upstream):
            return "unreachable"

        flow = Flow(gated, fail_fast=False)
        flow.run()
        self.assertEqual(flow.results["gated"].state, StepState.FAILED)
        self.assertIsInstance(flow.results["gated"].error, ZeroDivisionError)


class TestValidateGate(unittest.TestCase):
    """validate= edge contract — raise marks task FAILED with no retry."""

    def test_validate_passes(self):
        def must_be_dict(upstream):
            assert isinstance(upstream, dict), "upstream must be dict"

        @task
        def upstream():
            return {"k": "v"}

        @task(depends_on=[upstream], validate=must_be_dict)
        def consumer(upstream):
            return upstream["k"]

        flow = Flow(consumer)
        flow.run()
        self.assertEqual(flow.value(consumer), "v")

    def test_validate_fails_no_retry(self):
        body_calls = {"n": 0}

        def reject(upstream):
            raise ValueError(f"bad input: {upstream}")

        @task
        def upstream():
            return "wrong shape"

        @task(depends_on=[upstream], validate=reject, retry=5, retry_backoff_base_ms=1)
        def consumer(upstream):
            body_calls["n"] += 1
            return "should not run"

        flow = Flow(consumer, fail_fast=False)
        flow.run()
        self.assertEqual(flow.results["consumer"].state, StepState.FAILED)
        self.assertEqual(body_calls["n"], 0, "validate failure must not run task body")
        self.assertEqual(flow.results["consumer"].attempts, 0,
                         "validate failure must not consume retry budget")
        self.assertIsInstance(flow.results["consumer"].error, ValueError)


class TestRetryUntil(unittest.TestCase):
    """retry_until= predicate-driven loop — re-runs body until predicate(value) is True."""

    def test_retry_until_succeeds_after_n(self):
        calls = {"n": 0}

        @task(retry=5, retry_backoff_base_ms=1, retry_until=lambda v: v["valid"])
        def converging():
            calls["n"] += 1
            return {"valid": calls["n"] >= 3, "attempt": calls["n"]}

        flow = Flow(converging)
        flow.run()
        self.assertEqual(flow.results["converging"].state, StepState.SUCCEEDED)
        self.assertEqual(flow.value(converging)["attempt"], 3)
        self.assertEqual(flow.results["converging"].attempts, 3)

    def test_retry_until_exhausts(self):
        calls = {"n": 0}

        @task(retry=2, retry_backoff_base_ms=1, retry_until=lambda v: False)
        def never_satisfies():
            calls["n"] += 1
            return {"attempt": calls["n"]}

        flow = Flow(never_satisfies, fail_fast=False)
        flow.run()
        r = flow.results["never_satisfies"]
        self.assertEqual(r.state, StepState.FAILED)
        self.assertEqual(r.attempts, 3, "should consume full retry budget (1 + retry)")
        self.assertEqual(calls["n"], 3)
        # last value preserved on FAILED for diagnostics
        self.assertEqual(r.value, {"attempt": 3})

    def test_retry_until_first_attempt_pass(self):
        calls = {"n": 0}

        @task(retry=5, retry_backoff_base_ms=1, retry_until=lambda v: v == "ok")
        def immediate():
            calls["n"] += 1
            return "ok"

        flow = Flow(immediate)
        flow.run()
        self.assertEqual(flow.value(immediate), "ok")
        self.assertEqual(calls["n"], 1, "should not retry when predicate passes first time")

    def test_retry_until_predicate_raises(self):
        @task(retry=5, retry_backoff_base_ms=1, retry_until=lambda v: 1 / 0)
        def victim():
            return "value"

        flow = Flow(victim, fail_fast=False)
        flow.run()
        r = flow.results["victim"]
        self.assertEqual(r.state, StepState.FAILED)
        self.assertIsInstance(r.error, ZeroDivisionError)
        self.assertEqual(r.value, "value", "value preserved when predicate itself raises")


class TestComposition(unittest.TestCase):
    """The three primitives compose."""

    def test_when_then_validate_then_retry_until(self):
        # when=True -> proceed; validate passes; retry_until succeeds 2nd attempt
        body_calls = {"n": 0}

        @task
        def upstream():
            return {"go": True, "input": [1, 2, 3]}

        @task(
            depends_on=[upstream],
            when=lambda upstream: upstream["go"],
            validate=lambda upstream: (
                None if isinstance(upstream["input"], list)
                else (_ for _ in ()).throw(ValueError("bad input"))
            ),
            retry=3,
            retry_backoff_base_ms=1,
            retry_until=lambda v: v["good"],
        )
        def converging(upstream):
            body_calls["n"] += 1
            return {"good": body_calls["n"] >= 2, "n": body_calls["n"]}

        flow = Flow(converging)
        flow.run()
        self.assertEqual(flow.results["converging"].state, StepState.SUCCEEDED)
        self.assertEqual(flow.value(converging)["n"], 2)



class TestDetachedAutoDiscovery(unittest.TestCase):
    """v1.2: detached tasks whose deps are reachable from declared terminals
    should be auto-discovered and run, without needing to be passed as terminals.

    Regression: in v1.1.1, `Flow(assemble)` with a `store_memory(detached=True,
    depends_on=[assemble])` defined elsewhere would silently NOT run store_memory.
    The user had to know to pass it: `Flow(assemble, store_memory)`. The SKILL.md
    "Run in a final layer after the main DAG" implied auto-discovery.
    """

    def test_detached_downstream_of_terminal_auto_discovered(self):
        """Detached task whose dep IS the terminal should run automatically."""
        side_effects = []

        @task
        def main_step():
            return "result"

        @task(depends_on=[main_step], detached=True)
        def store(main_step):
            side_effects.append(("stored", main_step))
            return "stored"

        flow = Flow(main_step)  # NOTE: store NOT passed as terminal
        results = flow.run()

        self.assertEqual(results["main_step"].state, StepState.SUCCEEDED)
        self.assertIn("store", results)
        self.assertEqual(results["store"].state, StepState.SUCCEEDED)
        self.assertEqual(side_effects, [("stored", "result")])

    def test_detached_passed_as_terminal_still_works(self):
        """Backward compat: explicitly passing detached as terminal still works."""
        side_effects = []

        @task
        def main_step():
            return "result"

        @task(depends_on=[main_step], detached=True)
        def store(main_step):
            side_effects.append(main_step)

        flow = Flow(main_step, store)
        flow.run()
        self.assertEqual(side_effects, ["result"])

    def test_detached_chain_auto_discovered(self):
        """Detached-on-detached: if detachB depends on detachA depends on main,
        both should be auto-discovered when only main is the terminal."""
        order = []

        @task
        def main_step():
            order.append("main")
            return 1

        @task(depends_on=[main_step], detached=True)
        def detach_a(main_step):
            order.append("a")
            return main_step + 1

        @task(depends_on=[detach_a], detached=True)
        def detach_b(detach_a):
            order.append("b")
            return detach_a + 1

        flow = Flow(main_step)
        results = flow.run()

        self.assertEqual(results["main_step"].state, StepState.SUCCEEDED)
        self.assertEqual(results["detach_a"].state, StepState.SUCCEEDED)
        self.assertEqual(results["detach_b"].state, StepState.SUCCEEDED)
        self.assertEqual(order, ["main", "a", "b"])

    def test_unrelated_detached_not_picked_up(self):
        """Detached tasks whose deps are NOT reachable from terminals should
        NOT run — they belong to a different graph."""
        side_effects = []

        @task
        def graph_a_step():
            return "a"

        @task
        def graph_b_step():
            return "b"

        @task(depends_on=[graph_b_step], detached=True)
        def graph_b_side(graph_b_step):
            side_effects.append(graph_b_step)

        flow = Flow(graph_a_step)  # only graph A
        results = flow.run()

        self.assertEqual(results["graph_a_step"].state, StepState.SUCCEEDED)
        self.assertNotIn("graph_b_step", results)
        self.assertNotIn("graph_b_side", results)
        self.assertEqual(side_effects, [])

    def test_detached_failure_still_isolated(self):
        """Auto-discovered detached failure must still NOT trigger fail_fast
        and must land in flow.detached_failures (existing detached semantics)."""

        @task
        def main_step():
            return "ok"

        @task(depends_on=[main_step], detached=True)
        def flaky_side(main_step):
            raise RuntimeError("side-effect blew up")

        flow = Flow(main_step)
        results = flow.run()

        self.assertEqual(results["main_step"].state, StepState.SUCCEEDED)
        self.assertEqual(results["flaky_side"].state, StepState.FAILED)
        self.assertEqual(len(flow.detached_failures), 1)
        self.assertEqual(flow.detached_failures[0].name, "flaky_side")


class TestTimeout(unittest.TestCase):
    """timeout_s aborts a hung body and is retryable (v1.3)."""

    def test_timeout_fails_slow_task(self):
        @task(timeout_s=0.05)
        def slow():
            time.sleep(0.5)
            return "done"

        flow = Flow(slow, fail_fast=False)
        flow.run()
        r = flow.results["slow"]
        self.assertEqual(r.state, StepState.FAILED)
        self.assertIsInstance(r.error, TimeoutError)

    def test_timeout_consumes_retry_then_succeeds(self):
        calls = {"n": 0}

        @task(timeout_s=0.05, retry=2, retry_backoff_base_ms=1)
        def sometimes_slow():
            calls["n"] += 1
            if calls["n"] == 1:
                time.sleep(0.5)  # first attempt times out
            return calls["n"]

        flow = Flow(sometimes_slow)
        flow.run()
        self.assertEqual(flow.results["sometimes_slow"].state, StepState.SUCCEEDED)
        self.assertEqual(flow.value(sometimes_slow), 2)

    def test_no_timeout_runs_normally(self):
        @task
        def quick():
            return "ok"

        flow = Flow(quick)
        flow.run()
        self.assertEqual(flow.value(quick), "ok")


class TestSignatureValidation(unittest.TestCase):
    """Mismatched dep/parameter names are caught at graph-build time (v1.3)."""

    def test_mismatched_param_raises(self):
        @task
        def producer():
            return 1

        @task(depends_on=[producer])
        def consumer(wrong_name):
            return wrong_name + 1

        flow = Flow(consumer)
        with self.assertRaises(ValueError) as ctx:
            flow.run()
        msg = str(ctx.exception)
        self.assertIn("producer", msg)
        self.assertIn("consumer", msg)

    def test_kwargs_absorbs_any_dep(self):
        @task
        def producer():
            return 7

        @task(depends_on=[producer])
        def consumer(**kwargs):
            return kwargs["producer"]

        flow = Flow(consumer)
        flow.run()
        self.assertEqual(flow.value(consumer), 7)

    def test_name_override_matches_param(self):
        @task(name="aliased")
        def producer():
            return 3

        @task(depends_on=[producer])
        def consumer(aliased):
            return aliased * 2

        flow = Flow(consumer)
        flow.run()
        self.assertEqual(flow.value(consumer), 6)


class TestClearRegistry(unittest.TestCase):
    """clear_registry empties the module-level task registry (v1.3)."""

    def test_clear_registry_drops_detached_candidates(self):
        side_effects = []

        @task
        def shared():
            return 1

        @task(depends_on=[shared], detached=True)
        def stale_side(shared):
            side_effects.append("ran")

        # Without clearing, stale_side would auto-discover onto any later
        # flow built on `shared`. Clear it first.
        clear_registry()

        flow = Flow(shared)
        results = flow.run()
        self.assertEqual(results["shared"].state, StepState.SUCCEEDED)
        self.assertNotIn("stale_side", results)
        self.assertEqual(side_effects, [])

    def test_registry_empty_after_clear(self):
        @task
        def throwaway():
            return None

        clear_registry()
        from flowing import _TASK_REGISTRY
        self.assertEqual(_TASK_REGISTRY, [])


class TestContentAddressedJournal(unittest.TestCase):
    """Opt-in durable journal: cross-process replay + edit divergence."""

    def setUp(self):
        clear_registry()
        import tempfile
        self.jp = tempfile.mktemp(suffix=".jsonl")

    def tearDown(self):
        if os.path.exists(self.jp):
            os.unlink(self.jp)

    def _build(self, mult):
        clear_registry()
        calls = {"a": 0, "b": 0, "c": 0}

        @task
        def a():
            calls["a"] += 1
            return 10

        if mult == 2:
            @task(depends_on=[a], name="b")
            def b(a):
                calls["b"] += 1
                return a * 2
        else:
            @task(depends_on=[a], name="b")
            def b(a):
                calls["b"] += 1
                return a * 3

        @task(depends_on=[b], name="c")
        def c(b):
            calls["c"] += 1
            return b + 1

        return c, calls

    def test_no_journal_path_is_unchanged(self):
        c, calls = self._build(2)
        r = Flow(c).run()
        self.assertEqual(r["c"].value, 21)
        self.assertIsNone(r["c"].step_key)
        self.assertFalse(r["c"].cached)

    def test_replay_across_fresh_flow(self):
        c, calls = self._build(2)
        Flow(c, journal_path=self.jp).run()
        self.assertEqual((calls["a"], calls["b"], calls["c"]), (1, 1, 1))
        c2, calls2 = self._build(2)
        r2 = Flow(c2, journal_path=self.jp).run()
        self.assertEqual((calls2["a"], calls2["b"], calls2["c"]), (0, 0, 0))
        self.assertEqual(r2["c"].value, 21)
        self.assertTrue(r2["c"].cached and r2["a"].cached)

    def test_edit_diverges_and_cascades(self):
        c, _ = self._build(2)
        Flow(c, journal_path=self.jp).run()
        c3, calls3 = self._build(3)  # b's body edited
        r3 = Flow(c3, journal_path=self.jp).run()
        self.assertEqual(calls3["a"], 0)   # unchanged upstream cached
        self.assertEqual(calls3["b"], 1)   # edited task re-runs
        self.assertEqual(calls3["c"], 1)   # dependent cascades (chained key)
        self.assertEqual(r3["c"].value, 31)
        self.assertTrue(r3["a"].cached)
        self.assertFalse(r3["b"].cached or r3["c"].cached)

    def test_cosmetic_knob_does_not_bust_key(self):
        clear_registry()
        calls = {"x": 0}

        @task(retry=5, name="x")
        def x():
            calls["x"] += 1
            return 99

        Flow(x, journal_path=self.jp).run()
        clear_registry()

        @task(retry=0, name="x")  # knob changed, body identical
        def x2():
            calls["x"] += 1
            return 99

        Flow(x2, journal_path=self.jp).run()
        self.assertEqual(calls["x"], 1)

    def test_truncated_trailing_line_tolerated(self):
        c, _ = self._build(2)
        Flow(c, journal_path=self.jp).run()
        with open(self.jp, "a") as fh:
            fh.write('{"kind":"Completed","key":"v1:dead","nam')  # torn write
        c2, calls2 = self._build(2)
        r = Flow(c2, journal_path=self.jp).run()
        self.assertEqual((calls2["a"], calls2["b"], calls2["c"]), (0, 0, 0))
        self.assertEqual(r["c"].value, 21)


class TestRollback(unittest.TestCase):
    """v1.6: undo= runs in reverse completion order when the main DAG fails."""

    def setUp(self):
        clear_registry()
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.jp = os.path.join(self.dir, "run.jsonl")

    def _p(self, *parts):
        return os.path.join(self.dir, *parts)

    def _ship(self, tests_pass):
        """snapshot -> edit -> verify, the edit-then-test-then-restore recipe."""
        existing = self._p("tax.py")
        created = self._p("new", "deep", "invoice.py")
        with open(existing, "w") as fh:
            fh.write("def calculate_tax(x): ...\n")

        @task(undo=restore)
        def before():
            return snapshot([existing, created])

        @task(depends_on=[before])
        def edit(before):
            with open(existing, "w") as fh:
                fh.write("def compute_tax(x): ...\n")
            os.makedirs(os.path.dirname(created), exist_ok=True)
            with open(created, "w") as fh:
                fh.write("from tax import compute_tax\n")
            return 2

        @task(depends_on=[edit])
        def verify(edit):
            if not tests_pass:
                raise RuntimeError("ImportError: cannot import name 'calculate_tax'")
            return "ok"

        return verify, existing, created

    def test_failed_verify_restores_files_byte_exact(self):
        verify, existing, created = self._ship(tests_pass=False)
        flow = Flow(verify)
        r = flow.run()
        with open(existing) as fh:
            self.assertEqual(fh.read(), "def calculate_tax(x): ...\n")
        self.assertFalse(os.path.exists(created))
        self.assertFalse(os.path.exists(self._p("new")))  # created dirs removed
        self.assertEqual(r["before"].state, StepState.ROLLED_BACK)
        self.assertEqual(r["edit"].state, StepState.ROLLED_BACK)  # downstream of undone
        self.assertEqual(r["verify"].state, StepState.FAILED)
        self.assertIn("calculate_tax", str(r["verify"].error))
        self.assertEqual(flow.rollback_failures, [])

    def test_passing_verify_keeps_edits(self):
        verify, existing, created = self._ship(tests_pass=True)
        r = Flow(verify).run()
        with open(existing) as fh:
            self.assertEqual(fh.read(), "def compute_tax(x): ...\n")
        self.assertTrue(os.path.exists(created))
        self.assertEqual(r["before"].state, StepState.SUCCEEDED)

    def test_undo_runs_in_reverse_completion_order(self):
        order = []

        @task(undo=lambda v: order.append(v))
        def a():
            return "a"

        @task(depends_on=[a], undo=lambda v: order.append(v))
        def b(a):
            return "b"

        @task(depends_on=[b])
        def c(b):
            raise RuntimeError("boom")

        Flow(c).run()
        self.assertEqual(order, ["b", "a"])

    def test_undo_receives_task_value(self):
        got = []

        @task(undo=got.append)
        def a():
            return {"id": 42}

        @task(depends_on=[a])
        def b(a):
            raise RuntimeError("boom")

        Flow(b).run()
        self.assertEqual(got, [{"id": 42}])

    def test_no_failure_no_undo(self):
        calls = []

        @task(undo=calls.append)
        def a():
            return 1

        @task(depends_on=[a])
        def b(a):
            return a + 1

        r = Flow(b).run()
        self.assertEqual(calls, [])
        self.assertEqual(r["a"].state, StepState.SUCCEEDED)

    def test_failing_undo_recorded_and_walk_continues(self):
        order = []

        def bad_undo(v):
            raise OSError("disk gone")

        @task(undo=lambda v: order.append("a"))
        def a():
            return 1

        @task(depends_on=[a], undo=bad_undo)
        def b(a):
            return 2

        @task(depends_on=[b])
        def c(b):
            raise RuntimeError("boom")

        flow = Flow(c)
        r = flow.run()
        self.assertEqual(order, ["a"])  # a still undone after b's undo raised
        self.assertEqual(len(flow.rollback_failures), 1)
        self.assertEqual(flow.rollback_failures[0].name, "b")
        self.assertIsInstance(flow.rollback_failures[0].error, OSError)
        self.assertEqual(r["a"].state, StepState.ROLLED_BACK)
        # b's undo failed, so its effect is still in place. It is also
        # downstream of undone a, so it must re-run on resume: ROLLED_BACK.
        self.assertEqual(r["b"].state, StepState.ROLLED_BACK)

    def test_rollback_false_leaves_state(self):
        calls = []

        @task(undo=calls.append)
        def a():
            return 1

        @task(depends_on=[a])
        def b(a):
            raise RuntimeError("boom")

        r = Flow(b, rollback=False).run()
        self.assertEqual(calls, [])
        self.assertEqual(r["a"].state, StepState.SUCCEEDED)

    def test_independent_sibling_kept_and_resume_reruns_rolled_back(self):
        runs = {"fetch": 0, "prep": 0, "apply": 0}
        state = {"fail": True}

        @task
        def fetch():
            runs["fetch"] += 1
            return "data"

        @task(undo=lambda v: None)
        def prep():
            runs["prep"] += 1
            return "snap"

        @task(depends_on=[fetch, prep])
        def apply(fetch, prep):
            runs["apply"] += 1
            if state["fail"]:
                raise RuntimeError("boom")
            return "done"

        flow = Flow(apply)
        r = flow.run()
        self.assertEqual(r["fetch"].state, StepState.SUCCEEDED)  # not downstream of an undo
        self.assertEqual(r["prep"].state, StepState.ROLLED_BACK)
        state["fail"] = False
        r = flow.resume()
        self.assertEqual(r["apply"].state, StepState.SUCCEEDED)
        self.assertEqual(runs, {"fetch": 1, "prep": 2, "apply": 2})

    def test_detached_with_undo_rejected(self):
        @task
        def a():
            return 1

        with self.assertRaises(ValueError):
            @task(depends_on=[a], detached=True, undo=lambda v: None)
            def side(a):
                return a

    def test_detached_dependent_of_rolled_back_task_skips(self):
        fired = []

        @task(undo=lambda v: None)
        def a():
            return 1

        @task(depends_on=[a])
        def b(a):
            raise RuntimeError("boom")

        @task(depends_on=[a], detached=True)
        def announce(a):
            fired.append(a)

        r = Flow(b).run()
        self.assertEqual(fired, [])
        self.assertEqual(r["announce"].state, StepState.SKIPPED)

    def test_parallel_fail_fast_still_undoes_running_sibling(self):
        undone = []

        @task(undo=undone.append)
        def slow_ok():
            time.sleep(0.2)
            return "slow"

        @task
        def fast_fail():
            raise RuntimeError("boom")

        @task(depends_on=[slow_ok, fast_fail])
        def join(slow_ok, fast_fail):
            return 1

        r = Flow(join).run()
        self.assertEqual(undone, ["slow"])
        self.assertEqual(r["slow_ok"].state, StepState.ROLLED_BACK)

    def _journal_build(self, fail):
        calls = {"a": 0, "b": 0}

        @task(undo=lambda v: None)
        def a():
            calls["a"] += 1
            return 1

        @task(depends_on=[a])
        def b(a):
            calls["b"] += 1
            if fail:
                raise RuntimeError("boom")
            return a + 1

        return b, calls

    def test_journal_forgets_rolled_back_steps(self):
        b, calls = self._journal_build(fail=True)
        Flow(b, journal_path=self.jp).run()
        self.assertEqual(calls["a"], 1)
        b2, calls2 = self._journal_build(fail=False)
        r = Flow(b2, journal_path=self.jp).run()
        self.assertEqual(calls2["a"], 1)  # re-ran: its Completed was cancelled
        self.assertFalse(r["a"].cached)
        self.assertEqual(r["b"].value, 2)

    def test_cached_steps_are_not_undone(self):
        undone = []

        def build(fail):
            @task(undo=undone.append)
            def a():
                return "a"

            @task(depends_on=[a])
            def b(a):
                if fail:
                    raise RuntimeError("boom")
                return a

            return b

        Flow(build(False), journal_path=self.jp).run()
        r = Flow(build(True), journal_path=self.jp).run()
        self.assertTrue(r["a"].cached)
        self.assertEqual(undone, [])  # its effect belongs to the earlier run
        self.assertEqual(r["a"].state, StepState.SUCCEEDED)


class TestSnapshotRestore(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()

    def test_restore_reports_only_changed_paths(self):
        a = os.path.join(self.dir, "a.txt")
        b = os.path.join(self.dir, "b.txt")
        for p in (a, b):
            with open(p, "wb") as fh:
                fh.write(b"\x00orig\r\n")
        snap = snapshot([a, b])
        with open(a, "wb") as fh:
            fh.write(b"changed")
        self.assertEqual(restore(snap), [a])
        with open(a, "rb") as fh:
            self.assertEqual(fh.read(), b"\x00orig\r\n")

    def test_restore_recreates_deleted_file(self):
        a = os.path.join(self.dir, "a.txt")
        with open(a, "w") as fh:
            fh.write("x")
        snap = snapshot([a])
        os.remove(a)
        restore(snap)
        with open(a) as fh:
            self.assertEqual(fh.read(), "x")

    def test_restore_keeps_nonempty_created_dir(self):
        new = os.path.join(self.dir, "pkg", "mod.py")
        snap = snapshot([new])
        os.makedirs(os.path.dirname(new))
        with open(new, "w") as fh:
            fh.write("x")
        other = os.path.join(self.dir, "pkg", "other.py")
        with open(other, "w") as fh:
            fh.write("y")  # not in the snapshot; must survive
        restore(snap)
        self.assertFalse(os.path.exists(new))
        self.assertTrue(os.path.exists(other))


if __name__ == "__main__":
    unittest.main()
