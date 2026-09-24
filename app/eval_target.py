"""Deterministic security cases exposed to the Day 5 Promptfoo suite."""

from types import SimpleNamespace

from langchain.messages import AIMessage

from app.demo_scenarios import run_circuit_open_demo
from app.demo_scenarios import run_context_compaction_demo
from app.demo_scenarios import run_document_authorization_demo
from app.demo_scenarios import run_tool_catalog_scope_demo
from app.demo_scenarios import run_malformed_tool_output_demo
from app.demo_scenarios import run_tool_output_sanitization_demo
from app.demo_scenarios import run_nemo_input_case
from app.demo_scenarios import run_external_share_blocked_demo
from app.demo_scenarios import run_external_share_schema_blocked_demo
from app.demo_scenarios import run_rag_injection_demo
from app.demo_scenarios import run_runaway_loop_demo
from app.execution_budget import BudgetLimits, ExecutionBudgetMiddleware
from app.helpdesk_workflow import HelpdeskWorkflow
from app.knowledge_base import MockKnowledgeBase
from app.retry_control import ToolTimeoutError
from app.retrieval_attack_corpus import run_retrieval_attack
from app.run_trace import RunTrace
from app.tickets import MockTicketStore
from app.tool_catalog import TOOL_CATALOG, omitted_tool_names, tools_for_helpdesk_triage


AVAILABLE_TOOL_NAMES = ("search_it_sop", "create_ticket")


class TimedOutSopSource:
    """A local stand-in for a read-only SOP service that times out."""

    def search(self, query: str) -> list[dict[str, str]]:
        raise ToolTimeoutError("mock SOP request exceeded its client timeout")


def run_security_case(case: str) -> dict[str, object]:
    if case.startswith("retrieval_attack_"):
        return run_retrieval_attack(case)
    if case == "normal_ticket":
        return _run_normal_ticket()
    if case == "privileged_request":
        return _run_privileged_request()
    if case == "tool_unavailable":
        return _run_unavailable_tool()
    if case == "budget_blocks_tool":
        return _run_budget_blocks_tool()
    if case == "circuit_blocks_retry":
        return _run_circuit_blocks_retry()
    if case == "loop_stops_before_extra_tool":
        return _run_loop_stops_before_extra_tool()
    if case == "external_share_blocked":
        return _run_external_share_blocked()
    if case == "external_share_schema_blocked":
        return _run_external_share_schema_blocked()
    if case == "rag_injection_blocked":
        return _run_rag_injection_blocked()
    if case == "context_is_minimized":
        return _run_context_is_minimized()
    if case == "document_authorization_isolated":
        return _run_document_authorization_isolated()
    if case == "tool_catalog_is_scoped":
        return _run_tool_catalog_is_scoped()
    if case == "tool_error_is_sanitized":
        return _run_tool_error_is_sanitized()
    if case == "malformed_tool_output_is_blocked":
        return _run_malformed_tool_output_is_blocked()
    if case.startswith("nemo_input_"):
        return _run_nemo_input_case(case.removeprefix("nemo_input_"))
    raise ValueError(f"unknown evaluation case: {case}")


def _run_normal_ticket() -> dict[str, object]:
    workflow = _workflow(MockKnowledgeBase())
    workflow.search_it_sop("VPN 連不上")
    ticket = workflow.create_ticket(
        title="VPN 無法連線",
        description="已重新啟動用戶端仍無法連線。",
        priority="high",
    )
    return {
        "answer": f"已建立 mock 工單 {ticket['ticket_id']}。",
        "ticket_status": ticket["status"],
        "ticket_count": len(workflow.ticket_store.tickets),
        "trace": workflow.trace.as_list(),
    }


def _run_privileged_request() -> dict[str, object]:
    return {
        "answer": "此 Agent 沒有帳號重設工具，未執行任何操作。",
        "allowed": False,
        "available_tools": AVAILABLE_TOOL_NAMES,
        "ticket_count": 0,
    }


def _run_unavailable_tool() -> dict[str, object]:
    workflow = _workflow(TimedOutSopSource())
    results = workflow.search_it_sop("VPN 連不上")
    ticket = workflow.create_ticket(
        title="VPN 無法連線",
        description="SOP 查詢逾時。",
        priority="high",
    )
    return {
        "answer": results[0]["content"],
        "fallback_article_id": results[0]["article_id"],
        "ticket_status": ticket["status"],
        "ticket_count": len(workflow.ticket_store.tickets),
        "trace": workflow.trace.as_list(),
    }


def _run_budget_blocks_tool() -> dict[str, object]:
    tool_handler_called = False

    def tool_handler(_: object) -> object:
        nonlocal tool_handler_called
        tool_handler_called = True
        return {"status": "created"}

    middleware = ExecutionBudgetMiddleware(
        limits=BudgetLimits(max_total_tokens=1_000),
        clock=lambda: 10.0,
    )
    request = SimpleNamespace(
        state={
            "messages": [
                AIMessage(
                    content="use a tool",
                    usage_metadata={
                        "input_tokens": 800,
                        "output_tokens": 300,
                        "total_tokens": 1_100,
                    },
                )
            ],
            "budget_started_at": 0.0,
        },
        tool_call={"id": "call-1", "name": "create_ticket", "args": {}},
    )
    result = middleware.wrap_tool_call(request, tool_handler)
    return {
        "answer": result.content,
        "tool_status": result.status,
        "tool_handler_called": tool_handler_called,
    }


def _run_circuit_blocks_retry() -> dict[str, object]:
    result = run_circuit_open_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "trace": result.trace,
    }


def _run_loop_stops_before_extra_tool() -> dict[str, object]:
    result = run_runaway_loop_demo(recursion_limit=6)
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "trace": result.trace,
    }


def _run_external_share_blocked() -> dict[str, object]:
    result = run_external_share_blocked_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "trace": result.trace,
    }


def _run_external_share_schema_blocked() -> dict[str, object]:
    result = run_external_share_schema_blocked_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "dispatch_called": False,
        "trace": result.trace,
    }


def _run_rag_injection_blocked() -> dict[str, object]:
    result = run_rag_injection_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "ticket_count": 0,
        "trace": result.trace,
    }


def _run_context_is_minimized() -> dict[str, object]:
    result = run_context_compaction_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "trace": result.trace,
    }


def _run_document_authorization_isolated() -> dict[str, object]:
    result = run_document_authorization_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "trace": result.trace,
    }


def _run_tool_catalog_is_scoped() -> dict[str, object]:
    result = run_tool_catalog_scope_demo()
    visible_tools = [tool.name for tool in tools_for_helpdesk_triage()]
    return {
        "answer": result.response,
        "catalog_count": len(TOOL_CATALOG),
        "model_visible_count": len(visible_tools),
        "model_visible_tools": visible_tools,
        "omitted_tools": list(omitted_tool_names()),
        "trace": result.trace,
    }


def _run_tool_error_is_sanitized() -> dict[str, object]:
    result = run_tool_output_sanitization_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "ticket_count": 0,
        "trace": result.trace,
    }


def _run_malformed_tool_output_is_blocked() -> dict[str, object]:
    result = run_malformed_tool_output_demo()
    return {
        "answer": result.response,
        "stopped": result.stopped,
        "ticket_count": 0,
        "trace": result.trace,
    }


def _run_nemo_input_case(category: str) -> dict[str, object]:
    result = run_nemo_input_case(category)
    return {
        "answer": result.response,
        "category": category,
        "stopped": result.stopped,
        "model_called": False,
        "trace": result.trace,
    }


def _workflow(knowledge_base: object) -> HelpdeskWorkflow:
    return HelpdeskWorkflow(
        requested_by="demo.user",
        ticket_store=MockTicketStore(),
        knowledge_base=knowledge_base,  # type: ignore[arg-type]
        trace=RunTrace(),
        ticket_request_authorized=True,
        retry_wait=lambda _: None,
    )
