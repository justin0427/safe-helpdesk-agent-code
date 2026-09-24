"""Security boundaries for multi-agent fan-out and handoff demos."""

from dataclasses import dataclass
from typing import Iterable


MAX_PARALLEL_WORKERS = 2
KNOWN_WORKERS = frozenset({"vpn_specialist", "wifi_specialist"})
TARGET_AGENT_SCOPES = {
    "identity_specialist": frozenset({"account.read"}),
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    rule: str
    outcome: str
    detail: str


@dataclass(frozen=True)
class DelegationPrincipal:
    tenant_id: str
    subject_id: str
    actor_id: str
    scopes: frozenset[str]


@dataclass(frozen=True)
class HandoffRequest:
    target_agent: str
    task: str
    requested_scopes: frozenset[str]


@dataclass(frozen=True)
class HandoffEnvelope:
    run_id: str
    tenant_id: str
    subject_id: str
    actor_chain: tuple[str, ...]
    target_agent: str
    task: str
    effective_scopes: frozenset[str]


def limit_parallel_workers(
    requested_workers: Iterable[str],
    *,
    max_workers: int = MAX_PARALLEL_WORKERS,
) -> tuple[tuple[str, ...], tuple[PolicyDecision, ...]]:
    """Allow known, unique workers up to a fixed fan-out budget."""
    accepted: list[str] = []
    decisions: list[PolicyDecision] = []
    for worker_id in requested_workers:
        if worker_id not in KNOWN_WORKERS:
            decisions.append(
                PolicyDecision(False, "worker_allowlist", "blocked", "未知 worker，未加入執行計畫。")
            )
            continue
        if worker_id in accepted:
            decisions.append(
                PolicyDecision(False, "duplicate_worker", "blocked", "同一 worker 不會重複執行。")
            )
            continue
        if len(accepted) >= max_workers:
            decisions.append(
                PolicyDecision(False, "parallel_fanout_budget", "limited", "已達本次 worker 數量上限。")
            )
            continue
        accepted.append(worker_id)

    decisions.append(
        PolicyDecision(
            True,
            "parallel_fanout_budget",
            f"{len(accepted)}_workers",
            f"本次最多允許 {max_workers} 個唯一且已註冊的 worker。",
        )
    )
    return tuple(accepted), tuple(decisions)


def issue_handoff_envelope(
    *,
    run_id: str,
    principal: DelegationPrincipal,
    request: HandoffRequest,
) -> tuple[HandoffEnvelope | None, tuple[PolicyDecision, ...]]:
    """Build a server-owned delegation envelope without forwarding a parent token."""
    allowed_scopes = TARGET_AGENT_SCOPES.get(request.target_agent)
    if allowed_scopes is None:
        return None, (
            PolicyDecision(False, "handoff_target_allowlist", "blocked", "目標 Agent 不在允許名單內。"),
        )

    requested = request.requested_scopes
    effective = requested & principal.scopes & allowed_scopes
    scope_outcome = "allowed" if effective == requested else "reduced"
    envelope = HandoffEnvelope(
        run_id=run_id,
        tenant_id=principal.tenant_id,
        subject_id=principal.subject_id,
        actor_chain=(principal.actor_id, request.target_agent),
        target_agent=request.target_agent,
        task=request.task,
        effective_scopes=frozenset(effective),
    )
    return envelope, (
        PolicyDecision(
            True,
            "principal_propagation",
            "derived",
            "subject、tenant 與 actor chain 由伺服器端 principal 建立。",
        ),
        PolicyDecision(
            True,
            "delegation_scope",
            scope_outcome,
            "下游權限是請求、上游 scope 與目標 Agent allowlist 的交集。",
        ),
    )


def authorize_delegated_operation(
    envelope: HandoffEnvelope,
    *,
    required_scope: str,
    approved: bool,
) -> tuple[bool, tuple[PolicyDecision, ...]]:
    """Require both an effective scope and explicit approval for a sensitive action."""
    has_scope = required_scope in envelope.effective_scopes
    decisions = (
        PolicyDecision(
            has_scope,
            "delegated_scope",
            "allowed" if has_scope else "blocked",
            "handoff envelope 必須明確包含危險操作所需 scope。",
        ),
        PolicyDecision(
            approved,
            "approval_gate",
            "approved" if approved else "pending",
            "密碼重設需要獨立核准；handoff 本身不能代替核准。",
        ),
    )
    return has_scope and approved, decisions
