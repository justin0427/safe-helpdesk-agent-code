"""Retention, access, deletion, and PII rules for durable user memory."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from uuid import uuid4


MAX_RETENTION_DAYS = 30

_PII_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)09\d{2}[- ]?\d{3}[- ]?\d{3}(?!\d)"),
    re.compile(r"(?:密碼|password|備用碼|api[_ -]?key)\s*[:：]?\s*\S+", re.IGNORECASE),
)


@dataclass(frozen=True)
class MemoryOwner:
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class GovernedMemoryRecord:
    record_id: str
    tenant_id: str
    user_id: str
    key: str
    value: str
    purpose: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class MemoryGovernanceDecision:
    allowed: bool
    rule: str
    detail: str


@dataclass(frozen=True)
class MemoryWriteResult:
    decision: MemoryGovernanceDecision
    record: GovernedMemoryRecord | None = None


class GovernedMemoryStore:
    """In-memory demo store with explicit ownership and lifecycle operations."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: dict[str, GovernedMemoryRecord] = {}

    def write(
        self,
        *,
        owner: MemoryOwner,
        key: str,
        value: str,
        purpose: str,
        retention_days: int,
        approved: bool,
    ) -> MemoryWriteResult:
        if contains_pii(value):
            return _blocked("pii_memory_write", "內容疑似包含 PII 或憑證，沒有寫入長期記憶。")
        if not approved:
            return _blocked("memory_consent_required", "長期記憶沒有取得明確核准，拒絕保存。")
        if retention_days <= 0:
            return _blocked("retention_policy", "保留期限必須大於 0 天。")

        effective_days = min(retention_days, MAX_RETENTION_DAYS)
        now = self._clock()
        record = GovernedMemoryRecord(
            record_id=f"MEM-{uuid4().hex[:8].upper()}",
            tenant_id=owner.tenant_id,
            user_id=owner.user_id,
            key=key,
            value=value.strip(),
            purpose=purpose,
            created_at=now,
            expires_at=now + timedelta(days=effective_days),
        )
        self._records[record.record_id] = record
        rule = "memory_retention_capped" if retention_days > MAX_RETENTION_DAYS else "memory_retention_set"
        return MemoryWriteResult(
            decision=MemoryGovernanceDecision(
                allowed=True,
                rule=rule,
                detail=f"記憶保留 {effective_days} 天，到期後不再提供給模型。",
            ),
            record=record,
        )

    def query(self, owner: MemoryOwner) -> tuple[GovernedMemoryRecord, ...]:
        self.purge_expired()
        return tuple(
            record
            for record in self._records.values()
            if record.tenant_id == owner.tenant_id and record.user_id == owner.user_id
        )

    def read_record(
        self,
        *,
        requester: MemoryOwner,
        record_id: str,
    ) -> tuple[GovernedMemoryRecord | None, MemoryGovernanceDecision]:
        self.purge_expired()
        record = self._records.get(record_id)
        if record is None:
            return None, MemoryGovernanceDecision(False, "memory_not_found", "找不到可讀取的記憶。")
        if (record.tenant_id, record.user_id) != (requester.tenant_id, requester.user_id):
            return None, MemoryGovernanceDecision(
                False,
                "user_memory_isolation",
                "tenant 或 user 不相符，拒絕讀取記憶。",
            )
        return record, MemoryGovernanceDecision(True, "user_memory_query", "使用者可查看自己的記憶。")

    def delete(self, *, requester: MemoryOwner, record_id: str) -> MemoryGovernanceDecision:
        record, decision = self.read_record(requester=requester, record_id=record_id)
        if record is None:
            return decision
        del self._records[record_id]
        return MemoryGovernanceDecision(True, "user_memory_delete", "使用者已刪除自己的記憶。")

    def purge_expired(self, now: datetime | None = None) -> int:
        current_time = now or self._clock()
        expired_ids = [
            record_id
            for record_id, record in self._records.items()
            if record.expires_at <= current_time
        ]
        for record_id in expired_ids:
            del self._records[record_id]
        return len(expired_ids)


def contains_pii(value: str) -> bool:
    return any(pattern.search(value) for pattern in _PII_PATTERNS)


def _blocked(rule: str, detail: str) -> MemoryWriteResult:
    return MemoryWriteResult(MemoryGovernanceDecision(False, rule, detail))
