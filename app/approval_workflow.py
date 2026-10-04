"""Server-side approval scope and lifecycle for irreversible mock actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from threading import RLock
from typing import Callable, Literal


ApprovalStatus = Literal[
    "pending",
    "approved",
    "consumed",
    "cancelled",
    "expired",
    "escalated",
]


@dataclass(frozen=True)
class IrreversibleOperation:
    action: str
    subject_id: str
    ticket_id: str
    attachment_id: str
    reason: str

    def canonical_payload(self) -> str:
        return json.dumps(
            {
                "action": self.action,
                "attachment_id": self.attachment_id,
                "reason": self.reason,
                "subject_id": self.subject_id,
                "ticket_id": self.ticket_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload().encode()).hexdigest()


@dataclass
class ApprovalRequest:
    approval_id: str
    operation: IrreversibleOperation
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus = "pending"
    approved_by: str | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    rule: str
    outcome: str
    detail: str


@dataclass(frozen=True)
class ApprovalExecution:
    executed: bool
    request: ApprovalRequest
    decisions: tuple[ApprovalDecision, ...]


class ApprovalWorkflow:
    """Keep approval state server-side and bind one token to one operation."""

    def __init__(
        self,
        *,
        signing_key: bytes | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._signing_key = signing_key or secrets.token_bytes(32)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._requests: dict[str, ApprovalRequest] = {}
        self._used_nonces: set[str] = set()
        self._deleted_attachments: set[tuple[str, str]] = set()
        self._lock = RLock()

    def create(
        self,
        operation: IrreversibleOperation,
        *,
        ttl: timedelta = timedelta(minutes=30),
    ) -> ApprovalRequest:
        now = self._clock()
        request = ApprovalRequest(
            approval_id=f"APR-{secrets.token_hex(6).upper()}",
            operation=operation,
            created_at=now,
            expires_at=now + ttl,
        )
        with self._lock:
            self._requests[request.approval_id] = request
        return request

    def preview(self, request: ApprovalRequest) -> dict[str, str | bool]:
        return {
            "approval_id": request.approval_id,
            "action": "永久刪除 mock 工單附件",
            "target": f"{request.operation.ticket_id} / {request.operation.attachment_id}",
            "effect": "附件內容將無法由此 demo 還原",
            "reason": request.operation.reason,
            "expires_at": request.expires_at.isoformat(),
            "irreversible": True,
            "status": request.status,
        }

    def approve_and_execute(
        self,
        approval_id: str,
        *,
        approved_by: str,
        operation_override: IrreversibleOperation | None = None,
    ) -> ApprovalExecution:
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                raise KeyError("approval request not found")
            now = self._clock()
            if request.status != "pending":
                return ApprovalExecution(
                    False,
                    request,
                    (
                        ApprovalDecision(False, "approval_state", request.status, "只有 pending request 可以核准。"),
                    ),
                )
            if now >= request.expires_at:
                request.status = "expired"
                return ApprovalExecution(
                    False,
                    request,
                    (
                        ApprovalDecision(False, "approval_expiry", "expired", "核准期限已過，未執行操作。"),
                    ),
                )

            request.status = "approved"
            request.approved_by = approved_by
            token = self._issue_token(request)
            operation = operation_override or request.operation
            return self._execute(request, operation, token, now)

    def cancel(self, approval_id: str) -> ApprovalRequest:
        with self._lock:
            request = self._requests[approval_id]
            if request.status == "pending":
                request.status = "cancelled"
            return request

    def expire_and_escalate(
        self,
        approval_id: str,
        *,
        now: datetime | None = None,
    ) -> tuple[ApprovalRequest, tuple[ApprovalDecision, ...]]:
        with self._lock:
            request = self._requests[approval_id]
            evaluated_at = now or self._clock()
            if request.status != "pending":
                return request, (
                    ApprovalDecision(False, "approval_state", request.status, "非 pending request 不會重新計時。"),
                )
            if evaluated_at < request.expires_at:
                return request, (
                    ApprovalDecision(False, "approval_timeout", "pending", "核准期限尚未到，危險操作保持暫停。"),
                )
            request.status = "expired"
            request.status = "escalated"
            return request, (
                ApprovalDecision(False, "approval_timeout", "expired", "等待超過 30 分鐘，原核准已失效。"),
                ApprovalDecision(False, "irreversible_handler", "skipped", "未取得有效核准，不執行不可逆操作。"),
                ApprovalDecision(True, "approval_escalation", "required", "建立人工追蹤事項，但不自動放行原操作。"),
            )

    def _issue_token(self, request: ApprovalRequest) -> str:
        payload = {
            "approval_id": request.approval_id,
            "operation_digest": request.operation.digest(),
            "expires_at": int(request.expires_at.timestamp()),
            "nonce": secrets.token_hex(12),
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self._signing_key, encoded, hashlib.sha256).hexdigest()
        return f"{encoded.hex()}.{signature}"

    def _execute(
        self,
        request: ApprovalRequest,
        operation: IrreversibleOperation,
        token: str,
        now: datetime,
    ) -> ApprovalExecution:
        payload, valid_signature = self._decode_token(token)
        decisions: list[ApprovalDecision] = [
            ApprovalDecision(True, "approval_token", "issued", "伺服器簽發一次性核准憑證，原始 token 不寫入 trace。"),
        ]
        if not valid_signature or payload is None:
            decisions.append(ApprovalDecision(False, "approval_token_integrity", "blocked", "核准憑證驗證失敗。"))
            return ApprovalExecution(False, request, tuple(decisions))
        if payload["approval_id"] != request.approval_id:
            decisions.append(ApprovalDecision(False, "approval_scope", "blocked", "核准憑證不屬於這筆 request。"))
            return ApprovalExecution(False, request, tuple(decisions))
        if payload["operation_digest"] != operation.digest():
            decisions.append(ApprovalDecision(False, "approval_scope", "blocked", "操作參數已改變，原核准不得沿用。"))
            return ApprovalExecution(False, request, tuple(decisions))
        if now.timestamp() >= payload["expires_at"]:
            request.status = "expired"
            decisions.append(ApprovalDecision(False, "approval_expiry", "expired", "核准憑證已過期。"))
            return ApprovalExecution(False, request, tuple(decisions))
        nonce = str(payload["nonce"])
        if nonce in self._used_nonces:
            decisions.append(ApprovalDecision(False, "approval_replay", "blocked", "一次性核准憑證不得重放。"))
            return ApprovalExecution(False, request, tuple(decisions))

        self._used_nonces.add(nonce)
        self._deleted_attachments.add((operation.ticket_id, operation.attachment_id))
        request.status = "consumed"
        decisions.extend(
            (
                ApprovalDecision(True, "approval_scope", "matched", "action、subject 與完整參數都符合預覽內容。"),
                ApprovalDecision(True, "approval_token", "consumed", "一次性核准憑證已消耗。"),
                ApprovalDecision(True, "irreversible_handler", "completed", "只刪除預覽中的 mock 附件。"),
            )
        )
        return ApprovalExecution(True, request, tuple(decisions))

    def _decode_token(self, token: str) -> tuple[dict[str, object] | None, bool]:
        try:
            encoded_hex, signature = token.split(".", maxsplit=1)
            encoded = bytes.fromhex(encoded_hex)
            expected = hmac.new(self._signing_key, encoded, hashlib.sha256).hexdigest()
            payload = json.loads(encoded)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None, False
        return payload, hmac.compare_digest(signature, expected)
