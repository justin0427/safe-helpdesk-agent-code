"""Small session-memory boundary for the Day 20 demo."""

from dataclasses import dataclass
import re
from typing import Literal


MemoryKind = Literal["working", "preference"]

_SENSITIVE_PATTERNS = (
    re.compile(r"(?:password|passwd|密碼|備用碼)\s*[:：]?\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:sk|gho)_[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\bMOCK-\d{4,}\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class MemoryRecord:
    tenant_id: str
    session_id: str
    key: str
    value: str
    kind: MemoryKind


@dataclass(frozen=True)
class MemoryWriteDecision:
    allowed: bool
    rule: str
    detail: str


class SessionMemoryStore:
    """Stores approved values in memory and isolates them by tenant and session."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], MemoryRecord] = {}

    def write(self, record: MemoryRecord) -> MemoryWriteDecision:
        if any(pattern.search(record.value) for pattern in _SENSITIVE_PATTERNS):
            return MemoryWriteDecision(
                allowed=False,
                rule="sensitive_memory_write",
                detail="內容疑似包含密碼、備用碼或 token，拒絕寫入記憶。",
            )
        if record.kind == "preference":
            return MemoryWriteDecision(
                allowed=False,
                rule="persistent_memory_requires_approval",
                detail="跨回合偏好需要人工確認；本次沒有永久保存。",
            )
        self._records[(record.tenant_id, record.session_id, record.key)] = record
        return MemoryWriteDecision(
            allowed=True,
            rule="session_memory_write",
            detail="只寫入目前 tenant 與 session 的短期工作記憶。",
        )

    def read(self, *, tenant_id: str, session_id: str) -> tuple[MemoryRecord, ...]:
        return tuple(
            record
            for (record_tenant, record_session, _), record in self._records.items()
            if record_tenant == tenant_id and record_session == session_id
        )
