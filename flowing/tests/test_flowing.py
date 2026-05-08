"""Tests for flowing v1.1 control-flow primitives.

Coverage:
- v1.0 backward compat (existing DAG, retry, override, resume, detached)
- v1.1: when= conditional gate
- v1.1: validate= edge contract
- v1.1: retry_until= predicate loop
- Composition of new primitives
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from flowing import task, Flow, StepState  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
