"""Structured, in-memory traces for one Helpdesk Agent run."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    kind: str
    name: str
    status: str
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


class RunTrace:
    """Collects the events that are safe to show in the local demo UI."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def add(
        self,
        *,
        kind: str,
        name: str,
        status: str,
        detail: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._events.append(
            TraceEvent(
                sequence=len(self._events) + 1,
                kind=kind,
                name=name,
                status=status,
                detail=detail,
                data=data or {},
            )
        )

    def as_list(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in self._events]


@dataclass(frozen=True)
class AgentRunResult:
    response: str
    trace: list[dict[str, Any]]
    ticket: dict[str, str] | None = None
    stopped: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
