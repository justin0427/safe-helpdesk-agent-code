"""The small, testable policy boundary shared by tools and demo scenarios."""

from dataclasses import dataclass
from typing import Literal

from app.knowledge_base import MockKnowledgeBase
from app.retry_control import DEFAULT_READ_ONLY_RETRY_POLICY, run_with_retry
from app.run_trace import RunTrace
from app.tickets import MockTicketStore


Priority = Literal["low", "medium", "high"]


@dataclass
class HelpdeskWorkflow:
    requested_by: str
    ticket_store: MockTicketStore
    knowledge_base: MockKnowledgeBase
    trace: RunTrace
    sop_checked: bool = False

    def search_it_sop(self, query: str) -> list[dict[str, str]]:
        results = run_with_retry(
            lambda: self.knowledge_base.search(query),
            operation_name="search_it_sop",
            policy=DEFAULT_READ_ONLY_RETRY_POLICY,
            trace=self.trace,
        )
        self.sop_checked = True
        return results

    def create_ticket(
        self,
        *,
        title: str,
        description: str,
        priority: Priority,
    ) -> dict[str, str]:
        if not self.sop_checked:
            self.trace.add(
                kind="guardrail",
                name="sop_first",
                status="blocked",
                detail="尚未查詢 SOP，拒絕建立工單。",
            )
            return {
                "status": "blocked",
                "reason": "Search the read-only SOP source before creating a ticket.",
            }

        ticket = self.ticket_store.create_ticket(
            title=title,
            description=description,
            priority=priority,
            requested_by=self.requested_by,
        )
        self.trace.add(
            kind="tool",
            name="create_ticket",
            status="completed",
            detail=f"已建立 {ticket['ticket_id']}。",
            data={"ticket_id": ticket["ticket_id"]},
        )
        return ticket
