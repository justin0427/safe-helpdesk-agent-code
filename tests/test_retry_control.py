import unittest

from app.retry_control import (
    RetryBudgetExhausted,
    RetryPolicy,
    TransientToolError,
    run_with_retry,
)
from app.run_trace import RunTrace


class RetryControlTests(unittest.TestCase):
    def test_uses_exponential_backoff_within_the_configured_cap(self) -> None:
        policy = RetryPolicy(max_attempts=4, initial_delay_seconds=0.25, max_delay_seconds=0.5)

        self.assertEqual(policy.delay_after_failure(1), 0.25)
        self.assertEqual(policy.delay_after_failure(2), 0.5)
        self.assertEqual(policy.delay_after_failure(3), 0.5)

    def test_stops_after_the_retry_budget(self) -> None:
        trace = RunTrace()
        attempts = 0

        def always_unavailable() -> None:
            nonlocal attempts
            attempts += 1
            raise TransientToolError("temporary")

        with self.assertRaises(RetryBudgetExhausted):
            run_with_retry(
                always_unavailable,
                operation_name="read_only_lookup",
                policy=RetryPolicy(max_attempts=2),
                trace=trace,
                wait=lambda _: None,
            )

        self.assertEqual(attempts, 2)
        self.assertEqual(trace.as_list()[-1]["status"], "stopped")

    def test_does_not_retry_non_transient_errors(self) -> None:
        trace = RunTrace()
        attempts = 0

        def malformed_request() -> None:
            nonlocal attempts
            attempts += 1
            raise ValueError("bad request")

        with self.assertRaises(ValueError):
            run_with_retry(
                malformed_request,
                operation_name="read_only_lookup",
                policy=RetryPolicy(max_attempts=3),
                trace=trace,
                wait=lambda _: None,
            )

        self.assertEqual(attempts, 1)
        self.assertEqual(trace.as_list(), [])
