"""The small, testable policy boundary shared by tools and demo scenarios."""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import time
from typing import Literal
from uuid import uuid4

from app.knowledge_base import MockKnowledgeBase
from app.retry_control import (
    CircuitBreaker,
    CircuitOpenError,
    DEFAULT_READ_ONLY_RETRY_POLICY,
    RetryBudgetExhausted,
    RetryPolicy,
    run_with_retry,
)
from app.retrieval_boundary import filter_retrieved_documents
from app.run_trace import RunTrace
from app.tickets import MockTicketStore


Priority = Literal["low", "medium", "high"]


@dataclass
class HelpdeskWorkflow:
    requested_by: str
    ticket_store: MockTicketStore
    knowledge_base: MockKnowledgeBase
    trace: RunTrace
    ticket_request_authorized: bool
    sop_checked: bool = False
    retry_policy: RetryPolicy = DEFAULT_READ_ONLY_RETRY_POLICY
    retry_wait: Callable[[float], None] = time.sleep
    sop_circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    execution_id: str = field(default_factory=lambda: uuid4().hex)

    def search_it_sop(self, query: str) -> list[dict[str, str]]:
        try:
            results = run_with_retry(
                lambda: self.knowledge_base.search(query),
                operation_name="search_it_sop",
                policy=self.retry_policy,
                trace=self.trace,
                wait=self.retry_wait,
                circuit_breaker=self.sop_circuit_breaker,
            )
        except (RetryBudgetExhausted, CircuitOpenError) as error:
            self.trace.add(
                kind="escalation",
                name="sop_service_outage",
                status="required",
                detail="SOP 服務無法使用，需由維運或人工確認後再處理。",
                data={"reason": type(error).__name__},
            )
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
                    "content": (
                        "請稍後再試；系統不會在無法查核流程時自動建立工單。"
                        "若服務持續異常，需由人工確認。"
                    ),
                }
            ]

        allowed_documents, decisions = filter_retrieved_documents(results)
        for decision in decisions:
            self.trace.add(
                kind="retrieval",
                name=decision.article_id,
                status=decision.trust,
                detail=f"已辨識文件來源與信任等級：{decision.trust}。",
            )
            self.trace.add(
                kind="guardrail",
                name=decision.rule,
                status="allowed" if decision.allowed else "quarantined",
                detail=decision.detail,
            )

        self.sop_checked = bool(allowed_documents)
        if not allowed_documents:
            self.trace.add(
                kind="fallback",
                name="retrieval_unavailable",
                status="degraded",
                detail="沒有通過 retrieval boundary 的 SOP，不允許後續寫入。",
            )
        return [dict(document) for document in allowed_documents]

    def create_ticket(
        self,
        *,
        title: str,
        description: str,
        priority: Priority,
    ) -> dict[str, str]:
        if not self.ticket_request_authorized:
            self.trace.add(
                kind="guardrail",
                name="explicit_user_ticket_request",
                status="blocked",
                detail="原始使用者請求沒有明確要求開工單，拒絕寫入操作。",
            )
            return {
                "status": "blocked",
                "reason": "The original user request did not authorize ticket creation.",
            }

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
