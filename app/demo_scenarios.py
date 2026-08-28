"""Deterministic scenarios used by the page and regression tests."""

from app.helpdesk_workflow import HelpdeskWorkflow
from app.knowledge_base import MockKnowledgeBase
from app.loop_control import DEFAULT_RECURSION_LIMIT, loop_limit_message
from app.retry_control import (
    DEFAULT_READ_ONLY_RETRY_POLICY,
    RetryBudgetExhausted,
    TransientToolError,
    run_with_retry,
)
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


class IntermittentSopService:
    """A deterministic stand-in for a temporarily unavailable read-only service."""

    def __init__(self, *, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0
        self.knowledge_base = MockKnowledgeBase()

    def search(self, query: str) -> list[dict[str, str]]:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise TransientToolError("mock SOP service is temporarily unavailable")
        return self.knowledge_base.search(query)


def run_retry_success_demo() -> AgentRunResult:
    """Show a bounded retry for a read-only operation that later succeeds."""
    trace = RunTrace()
    service = IntermittentSopService(failures_before_success=2)
    results = run_with_retry(
        lambda: service.search("VPN 連不上"),
        operation_name="search_it_sop",
        policy=DEFAULT_READ_ONLY_RETRY_POLICY,
        trace=trace,
        wait=lambda _: None,
    )
    trace.add(
        kind="model",
        name="final_response",
        status="completed",
        detail="查詢成功後才整理回覆，沒有重送任何寫入操作。",
    )
    return AgentRunResult(
        response=f"第 3 次查詢成功，找到 {len(results)} 篇 SOP。未建立或重送任何工單。",
        trace=trace.as_list(),
    )


def run_retry_budget_demo() -> AgentRunResult:
    """Show that an unavailable read-only service stops at the retry budget."""
    trace = RunTrace()
    service = IntermittentSopService(
        failures_before_success=DEFAULT_READ_ONLY_RETRY_POLICY.max_attempts,
    )
    try:
        run_with_retry(
            lambda: service.search("VPN 連不上"),
            operation_name="search_it_sop",
            policy=DEFAULT_READ_ONLY_RETRY_POLICY,
            trace=trace,
            wait=lambda _: None,
        )
    except RetryBudgetExhausted:
        return AgentRunResult(
            response="SOP 服務暫時無法使用，已用完重試預算。未建立或重送任何工單。",
            trace=trace.as_list(),
            stopped=True,
        )
    raise AssertionError("the demo must exhaust its retry budget")
