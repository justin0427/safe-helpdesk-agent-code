"""LangChain Helpdesk Agent with SOP-first tools and a bounded runtime."""

from dataclasses import dataclass
from typing import Literal, Optional

from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from app.helpdesk_workflow import HelpdeskWorkflow
from app.knowledge_base import MockKnowledgeBase
from app.loop_control import DEFAULT_RECURSION_LIMIT, build_agent_config, loop_limit_message
from app.run_trace import AgentRunResult, RunTrace
from app.tickets import MockTicketStore


SYSTEM_PROMPT = """
You are an internal IT Helpdesk Agent.

Search the read-only SOP source before deciding how to help. If the user asks
to open a ticket after the SOP has been checked, call create_ticket. Use the
tool result to tell the user the ticket number. Do not claim a ticket was
created unless the tool returned a successful result.
""".strip()


@dataclass
class HelpdeskContext:
    workflow: HelpdeskWorkflow


@tool
def search_it_sop(
    query: str,
    runtime: ToolRuntime[HelpdeskContext],
) -> list[dict[str, str]]:
    """Search read-only IT SOP articles before answering a procedural IT question."""
    return runtime.context.workflow.search_it_sop(query)


@tool
def create_ticket(
    title: str,
    description: str,
    priority: Literal["low", "medium", "high"],
    runtime: ToolRuntime[HelpdeskContext],
) -> dict[str, str]:
    """Create an IT support ticket when a user reports a technical problem."""
    return runtime.context.workflow.create_ticket(
        title=title,
        description=description,
        priority=priority,
    )


class HelpdeskAgent:
    def __init__(
        self,
        *,
        model_name: str,
        requested_by: str,
        ticket_store: Optional[MockTicketStore] = None,
        knowledge_base: Optional[MockKnowledgeBase] = None,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
    ) -> None:
        model = ChatOpenAI(model=model_name, temperature=0, timeout=30)
        self.requested_by = requested_by
        self.ticket_store = ticket_store or MockTicketStore()
        self.knowledge_base = knowledge_base or MockKnowledgeBase()
        self.agent_config = build_agent_config(recursion_limit)
        self.agent = create_agent(
            model=model,
            tools=[search_it_sop, create_ticket],
            context_schema=HelpdeskContext,
            system_prompt=SYSTEM_PROMPT,
        )

    def run(self, user_message: str) -> str:
        return self.run_detailed(user_message).response

    def run_detailed(self, user_message: str) -> AgentRunResult:
        trace = RunTrace()
        context = HelpdeskContext(
            workflow=HelpdeskWorkflow(
                requested_by=self.requested_by,
                ticket_store=self.ticket_store,
                knowledge_base=self.knowledge_base,
                trace=trace,
            )
        )
        try:
            result = self.agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config=self.agent_config,
                context=context,
            )
        except GraphRecursionError:
            trace.add(
                kind="guardrail",
                name="recursion_limit",
                status="stopped",
                detail="LangGraph 超過允許步數，已停止本次執行。",
            )
            return AgentRunResult(
                response=loop_limit_message(),
                trace=trace.as_list(),
                stopped=True,
            )

        response = _message_text(result["messages"][-1].content)
        trace.add(
            kind="model",
            name="final_response",
            status="completed",
            detail="模型已產生最終回覆。",
        )
        return AgentRunResult(response=response, trace=trace.as_list())


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return str(content)
