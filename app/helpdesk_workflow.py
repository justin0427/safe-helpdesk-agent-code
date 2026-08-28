"""The small, testable policy boundary shared by tools and demo scenarios."""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import time
from typing import Literal
from uuid import uuid4

from app.knowledge_base import MockKnowledgeBase
from app.retry_control import (
    DEFAULT_READ_ONLY_RETRY_POLICY,
    RetryBudgetExhausted,
    RetryPolicy,
    run_with_retry,
)
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
    retry_policy: RetryPolicy = DEFAULT_READ_ONLY_RETRY_POLICY
    retry_wait: Callable[[float], None] = time.sleep
    execution_id: str = field(default_factory=lambda: uuid4().hex)

    def search_it_sop(self, query: str) -> list[dict[str, str]]:
        try:
            results = run_with_retry(
                lambda: self.knowledge_base.search(query),
                operation_name="search_it_sop",
                policy=self.retry_policy,
                trace=self.trace,
                wait=self.retry_wait,
            )
        except RetryBudgetExhausted:
            self.trace.add(
                kind="fallback",
                name="sop_unavailable",
                status="degraded",
                detail="SOP 暫時無法使用，保留問題描述，但不建立工單。",
            )
            return [
                {
                    "article_id": "FALLBACK-SOP",
                    "title": "SOP 暫時無法使用",
                    "content": "請稍後再試；系統不會在無法查核流程時自動建立工單。",
                }
            ]

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
            idempotency_key=self._ticket_idempotency_key(
                title=title,
                description=description,
                priority=priority,
            ),
        )
        self.trace.add(
            kind="tool",
            name="create_ticket",
            status=ticket["idempotency_status"],
            detail=(
                f"已建立 {ticket['ticket_id']}。"
                if ticket["idempotency_status"] == "created"
                else f"重複請求使用既有工單 {ticket['ticket_id']}。"
            ),
            data={
                "ticket_id": ticket["ticket_id"],
                "idempotency_status": ticket["idempotency_status"],
            },
        )
        return ticket

    def _ticket_idempotency_key(
        self,
        *,
        title: str,
        description: str,
        priority: Priority,
    ) -> str:
        payload = "\x00".join(
            (self.execution_id, self.requested_by, title.strip(), description.strip(), priority)
        )
        return sha256(payload.encode()).hexdigest()
