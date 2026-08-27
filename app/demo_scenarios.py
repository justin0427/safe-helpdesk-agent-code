"""Deterministic scenarios used by the page and regression tests."""

from app.helpdesk_workflow import HelpdeskWorkflow
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
