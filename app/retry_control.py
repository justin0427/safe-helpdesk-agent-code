"""Bounded retries for failures that are safe to repeat."""

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Any, TypeVar

from app.run_trace import RunTrace


Result = TypeVar("Result")


class TransientToolError(RuntimeError):
    """A read-only operation that may succeed when repeated."""


class ToolTimeoutError(TransientToolError):
    """A tool client classified an expired request as retryable."""


class RetryBudgetExhausted(RuntimeError):
    """Raised after every permitted retry has failed."""


class CircuitOpenError(RuntimeError):
    """Raised when a known-unhealthy dependency should fail fast."""

    def __init__(
        self,
        operation_name: str,
        retry_after_seconds: float,
        *,
        reason: str = "cooldown",
    ) -> None:
        super().__init__(f"{operation_name} is unavailable; retry after {retry_after_seconds:g} seconds")
        self.retry_after_seconds = retry_after_seconds
        self.reason = reason


@dataclass
class CircuitBreaker:
    """A process-local circuit breaker for one external dependency."""

    failure_threshold: int = 2
    recovery_timeout_seconds: float = 30.0
    clock: Callable[[], float] = time.monotonic
    _consecutive_failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _half_open: bool = field(default=False, init=False)
    _lock: Any = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.recovery_timeout_seconds < 0:
            raise ValueError("recovery_timeout_seconds must not be negative")

    def before_request(self, operation_name: str) -> str:
        with self._lock:
            if self._half_open:
                raise CircuitOpenError(operation_name, 0, reason="probe_in_flight")
            if self._opened_at is None:
                return "closed"
            retry_after = self.recovery_timeout_seconds - (self.clock() - self._opened_at)
            if retry_after > 0:
                raise CircuitOpenError(operation_name, retry_after)
            self._opened_at = None
            self._half_open = True
            return "half_open"

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None
            self._half_open = False

    def record_failure(self) -> bool:
        with self._lock:
            if self._half_open:
                self._half_open = False
                self._opened_at = self.clock()
                return True
            self._consecutive_failures += 1
            if self._consecutive_failures < self.failure_threshold:
                return False
            self._opened_at = self.clock()
            return True


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must not be negative")

    def delay_after_failure(self, failed_attempt: int) -> float:
        if not 1 <= failed_attempt < self.max_attempts:
            raise ValueError("failed_attempt must have another attempt available")
        return min(
            self.initial_delay_seconds * (2 ** (failed_attempt - 1)),
            self.max_delay_seconds,
        )


DEFAULT_READ_ONLY_RETRY_POLICY = RetryPolicy()


def run_with_retry(
    operation: Callable[[], Result],
    *,
    operation_name: str,
    policy: RetryPolicy,
    trace: RunTrace,
    wait: Callable[[float], None] = time.sleep,
    circuit_breaker: CircuitBreaker | None = None,
) -> Result:
    """Retry only classified transient errors and only for read-only operations."""
    if circuit_breaker is not None:
        try:
            circuit_state = circuit_breaker.before_request(operation_name)
        except CircuitOpenError as error:
            trace.add(
                kind="guardrail",
                name="circuit_breaker",
                status="blocked",
                detail=(
                    "已有一個服務探測請求在執行，這次查詢直接降級，不再送出請求。"
                    if error.reason == "probe_in_flight"
                    else "相依服務仍在冷卻中，這次查詢直接降級，不再送出請求。"
                ),
                data={"retry_after_seconds": round(error.retry_after_seconds, 3)},
            )
            raise
        if circuit_state == "half_open":
            trace.add(
                kind="guardrail",
                name="circuit_breaker",
                status="probe",
                detail="冷卻時間結束，允許一次探測請求確認服務是否恢復。",
            )

    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = operation()
        except TransientToolError as error:
            trace.add(
                kind="tool",
                name=operation_name,
                status="failed",
                detail=f"唯讀查詢暫時失敗（第 {attempt}/{policy.max_attempts} 次）。",
                data={"attempt": attempt, "error_type": type(error).__name__},
            )
            if attempt == policy.max_attempts:
                trace.add(
                    kind="guardrail",
                    name="retry_budget",
                    status="stopped",
                    detail=f"已用完 {policy.max_attempts} 次嘗試，不再重送查詢。",
                    data={"attempts": attempt},
                )
                if circuit_breaker is not None and circuit_breaker.record_failure():
                    trace.add(
                        kind="guardrail",
                        name="circuit_breaker",
                        status="opened",
                        detail="相依服務持續失敗，暫停後續請求並等待冷卻時間。",
                        data={"failure_threshold": circuit_breaker.failure_threshold},
                    )
                raise RetryBudgetExhausted(operation_name) from error

            delay = policy.delay_after_failure(attempt)
            trace.add(
                kind="guardrail",
                name="retry_budget",
                status="scheduled",
                detail=(
                    f"只允許重試唯讀查詢；預計等待 {delay:g} 秒後進行"
                    f"第 {attempt + 1}/{policy.max_attempts} 次。"
                ),
                data={"next_attempt": attempt + 1, "delay_seconds": delay},
            )
            wait(delay)
        else:
            if circuit_breaker is not None:
                circuit_breaker.record_success()
            trace.add(
                kind="tool",
                name=operation_name,
                status="completed",
                detail=f"唯讀查詢在第 {attempt}/{policy.max_attempts} 次成功。",
                data={"attempt": attempt},
            )
            return result

    raise AssertionError("retry loop must either return or raise")
