"""Deterministic scenarios used by the page and regression tests."""

from decimal import Decimal

from app.context_boundaries import context_inventory
from app.execution_budget import BudgetLedger, BudgetLimits, TokenPrice
from app.helpdesk_workflow import HelpdeskWorkflow
from app.knowledge_base import DEFAULT_ARTICLES, KnowledgeBaseArticle, MockKnowledgeBase
from app.loop_control import DEFAULT_RECURSION_LIMIT, loop_limit_message
from app.retry_control import CircuitBreaker, RetryPolicy, ToolTimeoutError
from app.run_trace import AgentRunResult, RunTrace
from app.tickets import MockTicketStore
from app.tool_policy import EXTERNAL_SHARE_DEMO_POLICY, validate_tool_call


def run_sop_first_demo() -> AgentRunResult:
    trace = RunTrace()
    workflow = HelpdeskWorkflow(
        requested_by="demo.user",
        ticket_store=MockTicketStore(),
        knowledge_base=MockKnowledgeBase(),
        trace=trace,
        ticket_request_authorized=True,
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


def run_ticket_before_sop_demo() -> AgentRunResult:
    """Show the write tool refusing a request before the required read step."""
    trace = RunTrace()
    workflow = HelpdeskWorkflow(
        requested_by="demo.user",
        ticket_store=MockTicketStore(),
        knowledge_base=MockKnowledgeBase(),
        trace=trace,
        ticket_request_authorized=True,
    )
    trace.add(
        kind="tool",
        name="create_ticket",
        status="requested",
        detail="示範在尚未查詢 SOP 時直接要求建立工單。",
    )
    ticket = workflow.create_ticket(
        title="VPN 無法連線",
        description="尚未查詢 SOP 的開單請求。",
        priority="high",
    )
    assert ticket["status"] == "blocked"
    trace.add(
        kind="model",
        name="final_response",
        status="completed",
        detail="說明開單要求被後端流程規則拒絕。",
    )
    return AgentRunResult(
        response="尚未查詢 SOP，已拒絕建立 mock 工單。請先取得流程資料後再決定是否開單。",
        trace=trace.as_list(),
        stopped=True,
    )


def run_external_share_blocked_demo() -> AgentRunResult:
    """Show an outbound tool request stopping before any dispatch happens."""
    trace = RunTrace()
    arguments = {
        "recipient": "outside@example.invalid",
        "article_id": "SOP-VPN-001",
    }
    trace.add(
        kind="tool",
        name="share_sop_excerpt",
        status="requested",
        detail="示範嘗試將 mock SOP 摘要交給外部收件者。",
    )
    decision = validate_tool_call(
        "share_sop_excerpt",
        arguments,
        policy=EXTERNAL_SHARE_DEMO_POLICY,
    )
    assert not decision.allowed
    trace.add(
        kind="guardrail",
        name=decision.rule,
        status="blocked",
        detail=decision.detail,
    )
    trace.add(
        kind="tool",
        name="outbound_dispatch",
        status="skipped",
        detail="policy 拒絕後沒有執行任何對外發送 handler。",
    )
    return AgentRunResult(
        response="收件者不在 allowlist，已拒絕外寄 mock SOP；沒有發送任何資料。",
        trace=trace.as_list(),
        stopped=True,
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


class TimedOutSopSource:
    """A deterministic source that lets the UI demonstrate safe degradation."""

    def search(self, query: str) -> list[dict[str, str]]:
        raise ToolTimeoutError("mock SOP request exceeded its client timeout")


def run_sop_timeout_fallback_demo() -> AgentRunResult:
    """Show timeout retries falling back without creating a ticket."""
    trace = RunTrace()
    workflow = HelpdeskWorkflow(
        requested_by="demo.user",
        ticket_store=MockTicketStore(),
        knowledge_base=TimedOutSopSource(),  # type: ignore[arg-type]
        trace=trace,
        ticket_request_authorized=True,
        retry_wait=lambda _: None,
    )
    results = workflow.search_it_sop("VPN 連不上")
    ticket = workflow.create_ticket(
        title="VPN 無法連線",
        description="SOP 查詢逾時。",
        priority="high",
    )
    trace.add(
        kind="model",
        name="final_response",
        status="completed",
        detail="告知 SOP 暫時無法使用，沒有假裝已建立工單。",
    )
    return AgentRunResult(
        response=results[0]["content"],
        trace=trace.as_list(),
        ticket=None if ticket["status"] == "blocked" else ticket,
        stopped=True,
    )


def run_circuit_open_demo() -> AgentRunResult:
    """Show a later request failing fast after the SOP service stays unhealthy."""
    trace = RunTrace()
    circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30)

    def workflow() -> HelpdeskWorkflow:
        return HelpdeskWorkflow(
            requested_by="demo.user",
            ticket_store=MockTicketStore(),
            knowledge_base=TimedOutSopSource(),  # type: ignore[arg-type]
            trace=trace,
            ticket_request_authorized=False,
            retry_policy=RetryPolicy(max_attempts=2),
            retry_wait=lambda _: None,
            sop_circuit_breaker=circuit_breaker,
        )

    workflow().search_it_sop("VPN 連不上")
    results = workflow().search_it_sop("VPN 連不上")
    return AgentRunResult(
        response=(
            "SOP 服務連續逾時後已開啟 circuit breaker；第二次查詢直接降級，"
            "沒有再送出 SOP 請求，也沒有建立工單。"
        ),
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


def run_context_boundary_demo() -> AgentRunResult:
    """Show that a retrieved escalation recommendation cannot authorize a write."""
    trace = RunTrace()
    source = MockKnowledgeBase(
        articles=(
            DEFAULT_ARTICLES[0],
            KnowledgeBaseArticle(
                article_id="SOP-ESCALATION-001",
                title="VPN 升級建議",
                content="若 VPN 問題仍無法排除，可建立高優先級工單。",
            ),
        )
    )
    workflow = HelpdeskWorkflow(
        requested_by="demo.user",
        ticket_store=MockTicketStore(),
        knowledge_base=source,
        trace=trace,
        ticket_request_authorized=False,
    )
    initial_blocks = context_inventory(
        retrieved_documents=(),
        tool_result={"name": "search_it_sop"},
    )
    for block in initial_blocks[:2]:
        trace.add(
            kind="context",
            name=block.source,
            status=block.trust,
            detail=block.detail,
        )
    results = workflow.search_it_sop("VPN 連不上，請說明排障步驟。")
    for block in context_inventory(
        retrieved_documents=results,
        tool_result={"name": "search_it_sop"},
    )[2:]:
        trace.add(
            kind="context",
            name=block.source,
            status=block.trust,
            detail=block.detail,
        )
    ticket = workflow.create_ticket(
        title="VPN 無法連線",
        description="SOP 建議建立工單。",
        priority="high",
    )
    assert ticket["status"] == "blocked"
    trace.add(
        kind="guardrail",
        name="retrieved_recommendation",
        status="ignored",
        detail="SOP 的升級建議沒有取得使用者授權，也沒有建立 mock 工單。",
    )
    return AgentRunResult(
        response="已讀取 VPN SOP；SOP 的升級建議不能授權寫入，沒有建立 mock 工單。",
        trace=trace.as_list(),
        stopped=True,
    )
