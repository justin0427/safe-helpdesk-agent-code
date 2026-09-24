"""Backend authorization that remains authoritative after agent guardrails."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: frozenset[str]
    scopes: frozenset[str]
    authenticated: bool = True


@dataclass
class TicketRecord:
    ticket_id: str
    tenant_id: str
    status: str = "open"


@dataclass(frozen=True)
class AuthorizationDecision:
    rule: str
    allowed: bool
    detail: str


@dataclass(frozen=True)
class TicketApiResult:
    status: str
    http_status: int
    code: str
    public_message: str
    authorization: tuple[AuthorizationDecision, ...]
    handler_called: bool


@dataclass(frozen=True)
class OutputDecision:
    allowed: bool
    response: str
    detail: str


ROLE_PERMISSIONS = {
    "helpdesk_operator": frozenset({"ticket:read", "ticket:close"}),
    "helpdesk_requester": frozenset({"ticket:read", "ticket:create"}),
}


class MockTicketApi:
    """A resource server that enforces auth at the point of mutation."""

    def close_ticket(
        self,
        *,
        principal: Principal,
        ticket: TicketRecord,
    ) -> TicketApiResult:
        decisions: list[AuthorizationDecision] = []

        authenticated = principal.authenticated
        decisions.append(
            AuthorizationDecision(
                rule="api_authentication",
                allowed=authenticated,
                detail=(
                    "mock API 已從受信任身分內容取得呼叫者。"
                    if authenticated
                    else "mock API 無法驗證呼叫者身分。"
                ),
            )
        )
        if not authenticated:
            return _denied(401, "UNAUTHENTICATED", decisions)

        has_scope = "tickets:close" in principal.scopes
        decisions.append(
            AuthorizationDecision(
                rule="api_scope",
                allowed=has_scope,
                detail=(
                    "呼叫憑證含有 tickets:close scope。"
                    if has_scope
                    else "呼叫憑證缺少 tickets:close scope。"
                ),
            )
        )
        if not has_scope:
            return _denied(403, "INSUFFICIENT_SCOPE", decisions)

        permissions = set().union(
            *(ROLE_PERMISSIONS.get(role, frozenset()) for role in principal.roles)
        )
        role_allowed = "ticket:close" in permissions
        decisions.append(
            AuthorizationDecision(
                rule="rbac",
                allowed=role_allowed,
                detail=(
                    "helpdesk_operator 角色可以使用關閉工單功能。"
                    if role_allowed
                    else "目前角色不能使用關閉工單功能。"
                ),
            )
        )
        if not role_allowed:
            return _denied(403, "ROLE_FORBIDDEN", decisions)

        object_allowed = principal.tenant_id == ticket.tenant_id
        decisions.append(
            AuthorizationDecision(
                rule="resource_acl",
                allowed=object_allowed,
                detail=(
                    "呼叫者與工單屬於同一個 mock tenant。"
                    if object_allowed
                    else "工單屬於另一個 mock tenant，拒絕物件層操作。"
                ),
            )
        )
        if not object_allowed:
            return _denied(403, "OBJECT_FORBIDDEN", decisions)

        ticket.status = "closed"
        return TicketApiResult(
            status="closed",
            http_status=200,
            code="TICKET_CLOSED",
            public_message="mock 工單已關閉。",
            authorization=tuple(decisions),
            handler_called=True,
        )


def validate_agent_output(candidate: str, api_result: TicketApiResult) -> OutputDecision:
    """Prevent a final answer from contradicting the authoritative API result."""
    success_claims = ("已關閉", "成功關閉", "ticket closed")
    if api_result.status != "closed" and any(
        claim in candidate.lower() for claim in success_claims
    ):
        return OutputDecision(
            allowed=False,
            response=api_result.public_message,
            detail="候選回覆宣稱操作成功，但 mock API 回傳拒絕，已改用權威結果。",
        )
    return OutputDecision(
        allowed=True,
        response=candidate,
        detail="回覆與 mock API 的拒絕結果一致，可以回傳。",
    )


def _denied(
    http_status: int,
    code: str,
    decisions: list[AuthorizationDecision],
) -> TicketApiResult:
    return TicketApiResult(
        status="denied",
        http_status=http_status,
        code=code,
        public_message="你沒有操作這張 mock 工單的權限；工單沒有變更。",
        authorization=tuple(decisions),
        handler_called=False,
    )
