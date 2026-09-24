"""Small, explicit execution budgets for the local Agent demo."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
import time
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ToolCallRequest,
    hook_config,
)
from langchain.messages import AIMessage, ToolMessage
from typing_extensions import NotRequired


MAX_MODEL_CALLS = 3
MAX_TOOL_CALLS = 4
MODEL_TIMEOUT_SECONDS = 20
MAX_OUTPUT_TOKENS_PER_CALL = 600
DEFAULT_RUN_TIME_BUDGET_SECONDS = 45.0


@dataclass(frozen=True)
class TokenPrice:
    """Deployment-provided prices, expressed per one million tokens."""

    input_per_million_usd: Decimal
    output_per_million_usd: Decimal

    def estimate(self, *, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            Decimal(input_tokens) * self.input_per_million_usd
            + Decimal(output_tokens) * self.output_per_million_usd
        ) / Decimal(1_000_000)


@dataclass(frozen=True)
class BudgetLimits:
    max_elapsed_seconds: float = DEFAULT_RUN_TIME_BUDGET_SECONDS
    max_total_tokens: int = 3_000
    max_estimated_cost_usd: Decimal | None = None

    def __post_init__(self) -> None:
        if self.max_elapsed_seconds <= 0:
            raise ValueError("max_elapsed_seconds must be positive")
        if self.max_total_tokens <= 0:
            raise ValueError("max_total_tokens must be positive")
        if self.max_estimated_cost_usd is not None and self.max_estimated_cost_usd <= 0:
            raise ValueError("max_estimated_cost_usd must be positive")


@dataclass
class BudgetLedger:
    limits: BudgetLimits
    pricing: TokenPrice
    total_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0")

    def record_model_usage(self, *, input_tokens: int, output_tokens: int) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must not be negative")
        self.total_tokens += input_tokens + output_tokens
        self.estimated_cost_usd += self.pricing.estimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def exceeded_limit(self, *, elapsed_seconds: float) -> str | None:
        if elapsed_seconds > self.limits.max_elapsed_seconds:
            return "time_budget"
        if self.total_tokens > self.limits.max_total_tokens:
            return "token_budget"
        if (
            self.limits.max_estimated_cost_usd is not None
            and self.estimated_cost_usd > self.limits.max_estimated_cost_usd
        ):
            return "cost_budget"
        return None


class BudgetState(AgentState):
    budget_started_at: NotRequired[float]


class ExecutionBudgetMiddleware(AgentMiddleware[BudgetState]):
    """Stop before another model call when the run has spent its budget."""

    state_schema = BudgetState

    def __init__(
        self,
        *,
        limits: BudgetLimits,
        pricing: TokenPrice | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self.limits = limits
        self.pricing = pricing
        self.clock = clock

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: BudgetState, runtime: Any) -> dict[str, Any] | None:
        exceeded = self._exceeded_limit(state)
        if exceeded is None:
            return None
        return {
            "messages": [AIMessage(content=_budget_stop_message(exceeded))],
            "jump_to": "end",
        }

    def wrap_tool_call(self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], Any]) -> Any:
        exceeded = self._exceeded_limit(request.state)
        if exceeded is None:
            return handler(request)
        return ToolMessage(
            content=_budget_stop_message(exceeded),
            tool_call_id=request.tool_call["id"],
            status="error",
        )

    def _exceeded_limit(self, state: BudgetState) -> str | None:
        started_at = state.get("budget_started_at")
        if started_at is None:
            return None
        ledger = BudgetLedger(
            limits=self.limits,
            pricing=self.pricing or TokenPrice(Decimal("0"), Decimal("0")),
        )
        for message in state.get("messages", []):
            usage = getattr(message, "usage_metadata", None) or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                ledger.record_model_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
        return ledger.exceeded_limit(elapsed_seconds=self.clock() - started_at)


def _budget_stop_message(exceeded: str) -> str:
    messages = {
        "time_budget": "Agent 已達執行時間上限，停止後續 Agent 動作。",
        "token_budget": "Agent 已達 Token 上限，停止後續 Agent 動作。",
        "cost_budget": "Agent 已達成本上限，停止後續 Agent 動作。",
    }
    return messages[exceeded]
