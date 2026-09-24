"""Deterministic context selection for the Day 12 demonstration."""

from dataclasses import dataclass
from typing import Literal, Sequence


Sensitivity = Literal["normal", "secret"]
SelectionReason = Literal["summary", "relevant", "recent"]


@dataclass(frozen=True)
class HistoryItem:
    message_id: str
    turn: int
    content: str
    safe_summary: str | None = None
    sensitivity: Sensitivity = "normal"


@dataclass(frozen=True)
class ModelContextBlock:
    block_id: str
    reason: SelectionReason
    content: str


@dataclass(frozen=True)
class PreparedContext:
    input_count: int
    model_context: tuple[ModelContextBlock, ...]
    dropped_sensitive_ids: tuple[str, ...]
    summarized_ids: tuple[str, ...]
    dropped_irrelevant_ids: tuple[str, ...]


def prepare_history_context(
    history: Sequence[HistoryItem],
    *,
    query_terms: Sequence[str],
    max_blocks: int = 3,
) -> PreparedContext:
    """Keep the current turn, prefer relevant history, and compact the rest."""
    if not history:
        raise ValueError("history cannot be empty")
    if max_blocks < 2:
        raise ValueError("max_blocks must leave room for recent and relevant context")

    sensitive = tuple(item for item in history if item.sensitivity == "secret")
    safe = [item for item in history if item.sensitivity == "normal"]
    if not safe:
        raise ValueError("history must contain at least one non-sensitive item")

    current = max(safe, key=lambda item: item.turn)
    older = [item for item in safe if item.message_id != current.message_id]
    normalized_terms = tuple(term.casefold() for term in query_terms if term.strip())

    def relevance(item: HistoryItem) -> tuple[int, int]:
        content = item.content.casefold()
        score = sum(term in content for term in normalized_terms)
        return score, item.turn

    relevant = [item for item in older if relevance(item)[0] > 0]
    relevant.sort(key=relevance, reverse=True)

    selected: list[ModelContextBlock] = []
    selected_ids: set[str] = {current.message_id}
    if relevant:
        best_match = relevant[0]
        selected_ids.add(best_match.message_id)
        selected.append(
            ModelContextBlock(
                block_id=best_match.message_id,
                reason="relevant",
                content=best_match.content,
            )
        )

    remaining = [item for item in older if item.message_id not in selected_ids]
    summary_items = [item for item in remaining if item.safe_summary]
    dropped_irrelevant = [item for item in remaining if not item.safe_summary]
    if summary_items and len(selected) < max_blocks - 1:
        selected.insert(
            0,
            ModelContextBlock(
                block_id="history-summary",
                reason="summary",
                content="較早紀錄：" + "；".join(item.safe_summary for item in summary_items),
            ),
        )

    selected.append(
        ModelContextBlock(
            block_id=current.message_id,
            reason="recent",
            content=current.content,
        )
    )

    return PreparedContext(
        input_count=len(history),
        model_context=tuple(selected[:max_blocks]),
        dropped_sensitive_ids=tuple(item.message_id for item in sensitive),
        summarized_ids=tuple(item.message_id for item in summary_items),
        dropped_irrelevant_ids=tuple(item.message_id for item in dropped_irrelevant),
    )
