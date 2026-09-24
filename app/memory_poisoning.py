"""Origin and approval policy for durable Agent memory writes."""

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Literal

from app.memory_governance import MemoryOwner, contains_pii


MemorySource = Literal["user", "retrieval", "tool", "model"]
MemoryOutcome = Literal["allowed", "blocked", "pending"]

ALLOWED_DURABLE_MEMORY_KEYS = frozenset({"response_tone", "locale", "device_os"})

_INSTRUCTION_PATTERNS = (
    re.compile(r"忽略.{0,20}(?:規則|指令)", re.IGNORECASE),
    re.compile(r"(?:永遠|之後都|未來都).{0,24}(?:略過|跳過|不要).{0,20}(?:核准|確認)", re.IGNORECASE),
    re.compile(r"(?:always|future).{0,32}(?:skip|bypass).{0,20}(?:approval|confirmation)", re.IGNORECASE),
)


@dataclass(frozen=True)
class MemoryCandidate:
    owner: MemoryOwner
    key: str
    value: str
    source: MemorySource


@dataclass(frozen=True)
class MemoryPolicyDecision:
    outcome: MemoryOutcome
    rule: str
    detail: str
    approval_id: str | None = None


class ProtectedLongTermMemory:
    """Accepts only user-attributed, approved, allowlisted durable memories."""

    def __init__(self) -> None:
        self._pending: dict[str, MemoryCandidate] = {}
        self._records: dict[tuple[str, str, str], str] = {}

    def propose(self, candidate: MemoryCandidate) -> MemoryPolicyDecision:
        if candidate.source != "user":
            return MemoryPolicyDecision(
                "blocked",
                "untrusted_memory_source",
                "retrieval、tool 與 model 內容不能直接寫入長期記憶。",
            )
        if candidate.key not in ALLOWED_DURABLE_MEMORY_KEYS:
            return MemoryPolicyDecision(
                "blocked",
                "memory_key_allowlist",
                "這個欄位不在允許保存的長期記憶清單中。",
            )
        if contains_pii(candidate.value):
            return MemoryPolicyDecision(
                "blocked",
                "sensitive_memory_write",
                "候選內容包含 PII 或憑證，拒絕保存。",
            )
        if any(pattern.search(candidate.value) for pattern in _INSTRUCTION_PATTERNS):
            return MemoryPolicyDecision(
                "blocked",
                "instruction_like_memory",
                "候選內容看起來像持久化指令，拒絕保存。",
            )

        approval_id = _candidate_fingerprint(candidate)[:16]
        self._pending[approval_id] = candidate
        return MemoryPolicyDecision(
            "pending",
            "memory_approval_required",
            "長期記憶候選已建立，等待同一位使用者確認。",
            approval_id,
        )

    def confirm(self, *, approval_id: str, approver: MemoryOwner) -> MemoryPolicyDecision:
        candidate = self._pending.get(approval_id)
        if candidate is None:
            return MemoryPolicyDecision("blocked", "memory_approval_invalid", "核准不存在或已失效。")
        if candidate.owner != approver:
            return MemoryPolicyDecision(
                "blocked",
                "memory_approval_scope",
                "核准者與候選記憶的 tenant 或 user 不相符。",
            )

        self._records[(approver.tenant_id, approver.user_id, candidate.key)] = candidate.value
        del self._pending[approval_id]
        return MemoryPolicyDecision("allowed", "approved_memory_write", "核准後才寫入長期記憶。")

    def read(self, owner: MemoryOwner) -> dict[str, str]:
        return {
            key: value
            for (tenant_id, user_id, key), value in self._records.items()
            if (tenant_id, user_id) == (owner.tenant_id, owner.user_id)
        }


class NaiveLongTermMemory:
    """Deliberately vulnerable store used only to demonstrate persistence."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], str] = {}

    def write(self, candidate: MemoryCandidate) -> None:
        self._records[(candidate.owner.tenant_id, candidate.owner.user_id, candidate.key)] = candidate.value

    def read(self, owner: MemoryOwner) -> dict[str, str]:
        return {
            key: value
            for (tenant_id, user_id, key), value in self._records.items()
            if (tenant_id, user_id) == (owner.tenant_id, owner.user_id)
        }


def _candidate_fingerprint(candidate: MemoryCandidate) -> str:
    payload = "\x00".join(
        (
            candidate.owner.tenant_id,
            candidate.owner.user_id,
            candidate.key,
            candidate.value,
            candidate.source,
        )
    )
    return sha256(payload.encode()).hexdigest()
