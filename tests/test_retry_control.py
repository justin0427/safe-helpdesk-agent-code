import unittest

from app.retry_control import (
    CircuitBreaker,
    CircuitOpenError,
    RetryBudgetExhausted,
    RetryPolicy,
    ToolTimeoutError,
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

    def test_retries_a_timeout_only_within_the_retry_budget(self) -> None:
        trace = RunTrace()
        attempts = 0

        def always_times_out() -> None:
            nonlocal attempts
            attempts += 1
            raise ToolTimeoutError("timeout")

        with self.assertRaises(RetryBudgetExhausted):
            run_with_retry(
                always_times_out,
                operation_name="read_only_lookup",
                policy=RetryPolicy(max_attempts=2),
                trace=trace,
                wait=lambda _: None,
            )

        self.assertEqual(attempts, 2)
        self.assertEqual(trace.as_list()[-1]["status"], "stopped")

    def test_does_not_retry_errors_that_are_not_classified_as_transient(self) -> None:
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

    def test_recovers_after_a_transient_failure(self) -> None:
        trace = RunTrace()
        attempts = 0

        def succeeds_on_second_attempt() -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TransientToolError("temporary")
            return "ok"

        result = run_with_retry(
            succeeds_on_second_attempt,
            operation_name="read_only_lookup",
            policy=RetryPolicy(max_attempts=2),
            trace=trace,
            wait=lambda _: None,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(trace.as_list()[-1]["data"]["attempt"], 2)

    def test_opens_the_circuit_after_a_failed_retry_budget(self) -> None:
        trace = RunTrace()
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30)
        attempts = 0

        def always_times_out() -> None:
            nonlocal attempts
            attempts += 1
            raise ToolTimeoutError("timeout")

        with self.assertRaises(RetryBudgetExhausted):
            run_with_retry(
                always_times_out,
                operation_name="read_only_lookup",
                policy=RetryPolicy(max_attempts=2),
                trace=trace,
                wait=lambda _: None,
                circuit_breaker=circuit_breaker,
            )

        with self.assertRaises(CircuitOpenError):
            run_with_retry(
                always_times_out,
                operation_name="read_only_lookup",
                policy=RetryPolicy(max_attempts=2),
                trace=trace,
                wait=lambda _: None,
                circuit_breaker=circuit_breaker,
            )

        self.assertEqual(attempts, 2)
        self.assertEqual(trace.as_list()[-1]["status"], "blocked")

    def test_allows_a_successful_half_open_probe_after_cooldown(self) -> None:
        trace = RunTrace()
        now = [0.0]
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout_seconds=30,
            clock=lambda: now[0],
        )

        with self.assertRaises(RetryBudgetExhausted):
            run_with_retry(
                lambda: (_ for _ in ()).throw(ToolTimeoutError("timeout")),
                operation_name="read_only_lookup",
                policy=RetryPolicy(max_attempts=1),
                trace=trace,
                wait=lambda _: None,
                circuit_breaker=circuit_breaker,
            )

        now[0] = 31.0
        result = run_with_retry(
            lambda: "ok",
            operation_name="read_only_lookup",
            policy=RetryPolicy(max_attempts=1),
            trace=trace,
            wait=lambda _: None,
            circuit_breaker=circuit_breaker,
        )

        self.assertEqual(result, "ok")
        self.assertIn("probe", [event["status"] for event in trace.as_list()])

    def test_allows_only_one_half_open_probe_at_a_time(self) -> None:
        now = [0.0]
        circuit_breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout_seconds=30,
            clock=lambda: now[0],
        )
        circuit_breaker.record_failure()
        now[0] = 31.0

        self.assertEqual(circuit_breaker.before_request("read_only_lookup"), "half_open")
        with self.assertRaises(CircuitOpenError) as raised:
            circuit_breaker.before_request("read_only_lookup")

        self.assertEqual(raised.exception.reason, "probe_in_flight")
