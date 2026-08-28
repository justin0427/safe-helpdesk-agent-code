"""Deterministic scenarios used by the page and regression tests."""

from decimal import Decimal

from app.helpdesk_workflow import HelpdeskWorkflow
from app.execution_budget import BudgetLedger, BudgetLimits, TokenPrice
from app.knowledge_base import MockKnowledgeBase
from app.loop_control import DEFAULT_RECURSION_LIMIT, loop_limit_message
from app.run_trace import AgentRunResult, RunTrace
from app.tickets import MockTicketStore


def run_sop_first_demo() -> AgentRunResult:
    trace = RunTrace()
    workflow = HelpdeskWorkflow(
        requested_by="demo.user",
        ticket_store=MockTicketStore(),
        knowledge_base=MockKnowledgeBase(),
        trace=trace,
    )
    query = "VPN 連不上，已重新啟動用戶端，請幫我開一張高優先級工單。"
    results = workflow.search_it_sop(query)
    ticket = workflow.create_ticket(
        title="VPN 無法連線",
        description=query,
        priority="high",
    )
    trace.add(
        kind="model",
        name="final_response",
        status="completed",
        detail="先取得 SOP，再建立 mock 工單。",
    )
    return AgentRunResult(
        response=(
            f"已先查詢 SOP，並建立 {ticket['ticket_id']}。"
            "這是記憶體中的 mock 工單，不會連到真實 ITSM 系統。"
        ),
        trace=trace.as_list(),
        ticket=ticket,
    )


def run_runaway_loop_demo(
    recursion_limit: int = DEFAULT_RECURSION_LIMIT,
) -> AgentRunResult:
    """Simulate a retrying tool so the UI can show a deterministic safe stop."""
    trace = RunTrace()
    for step in range(1, recursion_limit + 1):
        kind = "model" if step % 2 else "tool"
        trace.add(
            kind=kind,
            name="retrying_lookup" if kind == "tool" else "choose_next_step",
            status="completed",
            detail="測試工具回傳暫時性錯誤，流程嘗試繼續。",
        )

    trace.add(
        kind="guardrail",
        name="recursion_limit",
        status="stopped",
        detail=f"已用完 {recursion_limit} 個示範步數，停止後續工具呼叫。",
    )
    return AgentRunResult(
        response=loop_limit_message(),
        trace=trace.as_list(),
        stopped=True,
    )


DEMO_TOKEN_PRICE = TokenPrice(
    input_per_million_usd=Decimal("1"),
    output_per_million_usd=Decimal("2"),
)


def _record_model_usage(
    trace: RunTrace,
    ledger: BudgetLedger,
    *,
    input_tokens: int,
    output_tokens: int,
    elapsed_seconds: float,
) -> str | None:
    ledger.record_model_usage(input_tokens=input_tokens, output_tokens=output_tokens)
    trace.add(
        kind="model",
        name="model_call",
        status="completed",
        detail=(
            f"累積 {ledger.total_tokens} tokens；示範估算成本 "
            f"${ledger.estimated_cost_usd:.4f}。"
        ),
        data={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": ledger.total_tokens,
            "estimated_cost_usd": str(ledger.estimated_cost_usd),
            "elapsed_seconds": elapsed_seconds,
        },
    )
    return ledger.exceeded_limit(elapsed_seconds=elapsed_seconds)


def run_token_cost_budget_demo() -> AgentRunResult:
    """Show a budget stopping the next action after measured model usage."""
    trace = RunTrace()
    ledger = BudgetLedger(
        limits=BudgetLimits(max_estimated_cost_usd=Decimal("0.003")),
        pricing=DEMO_TOKEN_PRICE,
    )
    _record_model_usage(
        trace,
        ledger,
        input_tokens=800,
        output_tokens=300,
        elapsed_seconds=9,
    )
    exceeded = _record_model_usage(
        trace,
        ledger,
        input_tokens=1_200,
        output_tokens=600,
        elapsed_seconds=21,
    )
    assert exceeded == "cost_budget"
    trace.add(
        kind="guardrail",
        name="cost_budget",
        status="stopped",
        detail="示範成本超過 $0.0030，停止下一次模型或工具呼叫。",
    )
    return AgentRunResult(
        response="已達成本預算，停止下一次 Agent 動作。這個示範沒有建立工單。",
        trace=trace.as_list(),
        stopped=True,
    )


def run_time_budget_demo() -> AgentRunResult:
    """Show a deadline stopping the next action before a write is attempted."""
    trace = RunTrace()
    ledger = BudgetLedger(
        limits=BudgetLimits(max_estimated_cost_usd=Decimal("0.003")),
        pricing=DEMO_TOKEN_PRICE,
    )
    exceeded = _record_model_usage(
        trace,
        ledger,
        input_tokens=600,
        output_tokens=150,
        elapsed_seconds=46,
    )
    assert exceeded == "time_budget"
    trace.add(
        kind="guardrail",
        name="time_budget",
        status="stopped",
        detail="示範執行時間超過 45 秒，停止下一次模型或工具呼叫。",
    )
    return AgentRunResult(
        response="已達時間預算，停止下一次 Agent 動作。這個示範沒有建立工單。",
        trace=trace.as_list(),
        stopped=True,
    )
