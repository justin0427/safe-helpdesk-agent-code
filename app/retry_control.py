"""Bounded retries for transient, read-only tool failures."""

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import TypeVar

from app.run_trace import RunTrace


Result = TypeVar("Result")


class TransientToolError(RuntimeError):
    """A failure that may succeed when the same read-only request is retried."""


class RetryBudgetExhausted(RuntimeError):
    """Raised after every permitted retry has failed."""


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
) -> Result:
    """Retry only explicitly classified transient failures within a fixed budget."""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = operation()
        except TransientToolError as error:
            trace.add(
                kind="tool",
                name=operation_name,
                status="failed",
                detail=f"唯讀查詢暫時失敗（第 {attempt}/{policy.max_attempts} 次）。",
                data={"attempt": attempt},
            )
            if attempt == policy.max_attempts:
                trace.add(
                    kind="guardrail",
                    name="retry_budget",
                    status="stopped",
                    detail=f"已用完 {policy.max_attempts} 次嘗試，不再重送查詢。",
                    data={"attempts": attempt},
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
            trace.add(
                kind="tool",
                name=operation_name,
                status="completed",
                detail=f"唯讀查詢在第 {attempt}/{policy.max_attempts} 次成功。",
                data={"attempt": attempt},
            )
            return result

    raise AssertionError("retry loop must either return or raise")
