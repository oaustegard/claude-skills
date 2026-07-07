"""Tests for flowing control-flow primitives.

Coverage:
- v1.0 backward compat (existing DAG, retry, override, resume, detached)
- v1.1: when= conditional gate
- v1.1: validate= edge contract
- v1.1: retry_until= predicate loop
- Composition of new primitives
- v1.3: timeout_s enforcement, signature validation, clear_registry
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from flowing import task, Flow, StepState, clear_registry  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
