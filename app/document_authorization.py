"""Tenant and document ACL checks for the Day 14 retrieval demo."""

from dataclasses import dataclass
from typing import Literal, Sequence


AuthorizationRule = Literal["tenant_isolation", "document_acl", "document_authorized"]


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: frozenset[str]


@dataclass(frozen=True)
class SecuredDocument:
    article_id: str
    tenant_id: str
    allowed_roles: frozenset[str]
    title: str
    content: str
    source: str = "approved_sop"


@dataclass(frozen=True)
class AuthorizationDecision:
    article_id: str
    allowed: bool
    rule: AuthorizationRule
    detail: str


def authorize_document(
    principal: Principal,
    document: SecuredDocument,
) -> AuthorizationDecision:
    """Authorize one document from server-controlled identity and metadata."""
    if document.tenant_id != principal.tenant_id:
        return AuthorizationDecision(
            article_id=document.article_id,
            allowed=False,
            rule="tenant_isolation",
            detail=(
                f"{document.article_id} 屬於其他 tenant，"
                "未進入相似度搜尋或模型 context。"
            ),
        )

    if document.allowed_roles and principal.roles.isdisjoint(document.allowed_roles):
        return AuthorizationDecision(
            article_id=document.article_id,
            allowed=False,
            rule="document_acl",
            detail=(
                f"{document.article_id} 需要 {sorted(document.allowed_roles)} 角色，"
                "目前身分不得讀取。"
            ),
        )

    return AuthorizationDecision(
        article_id=document.article_id,
        allowed=True,
        rule="document_authorized",
        detail=f"{document.article_id} 通過 tenant 與文件 ACL 檢查。",
    )


def filter_authorized_documents(
    principal: Principal,
    documents: Sequence[SecuredDocument],
) -> tuple[list[SecuredDocument], list[AuthorizationDecision]]:
    decisions = [authorize_document(principal, document) for document in documents]
    allowed = [
        document
        for document, decision in zip(documents, decisions, strict=True)
        if decision.allowed
    ]
    return allowed, decisions


def retrieve_from_authorized_candidates(
    candidates: Sequence[SecuredDocument],
    query_terms: Sequence[str],
) -> list[SecuredDocument]:
    """Small deterministic stand-in for vector search over an authorized subset."""
    normalized_terms = tuple(term.casefold() for term in query_terms if term.strip())
    return [
        document
        for document in candidates
        if any(
            term in f"{document.title} {document.content}".casefold()
            for term in normalized_terms
        )
    ]
