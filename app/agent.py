"""LangChain Helpdesk Agent with SOP-first tools and a bounded runtime."""

from dataclasses import dataclass
from decimal import Decimal
import time
from typing import Literal, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.tools import ToolRuntime, tool
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError

from app.execution_budget import (
    BudgetLimits,
    ExecutionBudgetMiddleware,
    MAX_MODEL_CALLS,
    MAX_OUTPUT_TOKENS_PER_CALL,
    MAX_TOOL_CALLS,
    MODEL_TIMEOUT_SECONDS,
    TokenPrice,
)
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
        input_price_per_million_usd: Decimal | None = None,
        output_price_per_million_usd: Decimal | None = None,
        max_cost_usd: Decimal | None = None,
    ) -> None:
        model = ChatOpenAI(
            model=model_name,
            temperature=0,
            timeout=MODEL_TIMEOUT_SECONDS,
            max_tokens=MAX_OUTPUT_TOKENS_PER_CALL,
        )
        self.requested_by = requested_by
        self.ticket_store = ticket_store or MockTicketStore()
        self.knowledge_base = knowledge_base or MockKnowledgeBase()
        self.agent_config = build_agent_config(recursion_limit)
        self.budget_limits = BudgetLimits(max_estimated_cost_usd=max_cost_usd)
        self.token_price = _token_price(
            input_price_per_million_usd,
            output_price_per_million_usd,
        )
        if max_cost_usd is not None and self.token_price is None:
            raise ValueError("cost budget requires both input and output token prices")
        self.agent = create_agent(
            model=model,
            tools=[search_it_sop, create_ticket],
            context_schema=HelpdeskContext,
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                ExecutionBudgetMiddleware(
                    limits=self.budget_limits,
                    pricing=self.token_price,
                ),
                ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="end"),
                ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="end"),
            ],
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
                {
                    "messages": [{"role": "user", "content": user_message}],
                    "budget_started_at": time.monotonic(),
                },
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


def _token_price(
    input_price_per_million_usd: Decimal | None,
    output_price_per_million_usd: Decimal | None,
) -> TokenPrice | None:
    if input_price_per_million_usd is None and output_price_per_million_usd is None:
        return None
    if input_price_per_million_usd is None or output_price_per_million_usd is None:
        raise ValueError("both token prices must be configured together")
    return TokenPrice(input_price_per_million_usd, output_price_per_million_usd)
