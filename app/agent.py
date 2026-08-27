"""Day 2: a minimal LangChain Helpdesk Agent with one mock tool."""

from dataclasses import dataclass
from typing import Literal, Optional

from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from app.knowledge_base import MockKnowledgeBase
from app.loop_control import DEFAULT_RECURSION_LIMIT, build_agent_config, loop_limit_message
from app.tickets import MockTicketStore


SYSTEM_PROMPT = """
You are an internal IT Helpdesk Agent.

When a user reports an IT problem and asks for help, call create_ticket.
Use the tool result to tell the user the ticket number. Do not claim a ticket
was created unless the tool returned a successful result.
""".strip()


@dataclass
class HelpdeskContext:
    requested_by: str
    ticket_store: MockTicketStore
    knowledge_base: MockKnowledgeBase


@tool
def search_it_sop(
    query: str,
    runtime: ToolRuntime[HelpdeskContext],
) -> list[dict[str, str]]:
    """Search read-only IT SOP articles before answering a procedural IT question."""
    return runtime.context.knowledge_base.search(query)


@tool
def create_ticket(
    title: str,
    description: str,
    priority: Literal["low", "medium", "high"],
    runtime: ToolRuntime[HelpdeskContext],
) -> dict[str, str]:
    """Create an IT support ticket when a user reports a technical problem."""
    return runtime.context.ticket_store.create_ticket(
        title=title,
        description=description,
        priority=priority,
        requested_by=runtime.context.requested_by,
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
        context = HelpdeskContext(
            requested_by=requested_by,
            ticket_store=ticket_store or MockTicketStore(),
            knowledge_base=knowledge_base or MockKnowledgeBase(),
        )
        model = ChatOpenAI(model=model_name, temperature=0, timeout=30)
        self.context = context
        self.agent_config = build_agent_config(recursion_limit)
        self.agent = create_agent(
            model=model,
            tools=[search_it_sop, create_ticket],
            context_schema=HelpdeskContext,
            system_prompt=SYSTEM_PROMPT,
        )

    def run(self, user_message: str) -> str:
        try:
            result = self.agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config=self.agent_config,
                context=self.context,
            )
        except GraphRecursionError:
            return loop_limit_message()
        return result["messages"][-1].text
