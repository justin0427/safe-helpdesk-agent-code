"""Deterministic retrieval checks for the indirect-injection demo."""

from dataclasses import dataclass, replace
import re
from typing import Literal, Mapping, Sequence


DocumentTrust = Literal["approved_reference", "untrusted_reference"]


_APPROVED_REFERENCE_SOURCES = frozenset({"approved_sop"})


_INSTRUCTION_PATTERNS = (
    re.compile(r"忽略.{0,16}(?:指令|規則)", re.IGNORECASE),
    re.compile(r"(?:立即|直接).{0,12}(?:呼叫|執行).{0,20}(?:工具|create_ticket)", re.IGNORECASE),
    re.compile(r"(?:system|developer)\s*(?:prompt|message)", re.IGNORECASE),
    re.compile(
        r"ignore.{0,32}(?:previous|prior|all).{0,20}(?:instructions?|rules?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:call|invoke|execute).{0,24}(?:tool|create_ticket)",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class RetrievalDecision:
    article_id: str
    allowed: bool
    trust: DocumentTrust
    rule: str
    detail: str


def inspect_retrieved_document(document: Mapping[str, str]) -> RetrievalDecision:
    """Classify one mock document before it becomes model-visible context."""
    article_id = str(document["article_id"])
    source = str(document.get("source", "unknown"))
    trust: DocumentTrust = (
        "approved_reference"
        if source in _APPROVED_REFERENCE_SOURCES
        else "untrusted_reference"
    )

    content = str(document.get("content", ""))
    if any(pattern.search(content) for pattern in _INSTRUCTION_PATTERNS):
        return RetrievalDecision(
            article_id=article_id,
            allowed=False,
            trust=trust,
            rule="indirect_prompt_injection",
            detail=(
                f"{article_id} 含有指令式內容，已在 retrieval boundary 隔離；"
                f"來源為 {source}，不送進模型 context。"
            ),
        )

    if trust != "approved_reference":
        return RetrievalDecision(
            article_id=article_id,
            allowed=False,
            trust="untrusted_reference",
            rule="document_trust",
            detail=f"{article_id} 尚未被核准為參考資料，已隔離於模型 context 之外。",
        )

    return RetrievalDecision(
        article_id=article_id,
        allowed=True,
        trust="approved_reference",
        rule="retrieval_boundary",
        detail=f"{article_id} 可作為參考資料，但不能授權工具或改寫系統規則。",
    )


def filter_retrieved_documents(
    documents: Sequence[Mapping[str, str]],
) -> tuple[list[Mapping[str, str]], list[RetrievalDecision]]:
    """Return model-visible reference data and an auditable decision for every chunk."""
    decisions = [inspect_retrieved_document(document) for document in documents]

    # A retrieval system may split one instruction across adjacent chunks. Check
    # approved chunks in pairs so a boundary does not become an easy bypass.
    for index in range(len(documents) - 1):
        if not decisions[index].allowed or not decisions[index + 1].allowed:
            continue
        combined = " ".join(
            (
                str(documents[index].get("content", "")),
                str(documents[index + 1].get("content", "")),
            )
        )
        if not any(pattern.search(combined) for pattern in _INSTRUCTION_PATTERNS):
            continue
        for affected_index in (index, index + 1):
            article_id = decisions[affected_index].article_id
            decisions[affected_index] = replace(
                decisions[affected_index],
                allowed=False,
                rule="cross_chunk_prompt_injection",
                detail=(
                    f"{article_id} 與相鄰 chunk 合併後形成指令式內容，"
                    "已一併隔離於模型 context 之外。"
                ),
            )

    allowed = [
        document
        for document, decision in zip(documents, decisions, strict=True)
        if decision.allowed
    ]
    return allowed, decisions
