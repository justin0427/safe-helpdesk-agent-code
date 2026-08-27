"""A local ticket store used instead of a real ITSM API in Day 2."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4


ALLOWED_PRIORITIES = {"low", "medium", "high"}


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    title: str
    description: str
    priority: str
    requested_by: str
    status: str
    created_at: str


class MockTicketStore:
    """Keeps tickets only in memory so the first demo cannot affect production."""

    def __init__(self) -> None:
        self.tickets: list[Ticket] = []

    def create_ticket(
        self,
        *,
        title: str,
        description: str,
        priority: str,
        requested_by: str,
    ) -> dict[str, str]:
        if priority not in ALLOWED_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(ALLOWED_PRIORITIES)}")

        ticket = Ticket(
            ticket_id=f"INC-{uuid4().hex[:8].upper()}",
            title=title.strip(),
            description=description.strip(),
            priority=priority,
            requested_by=requested_by,
            status="created",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.tickets.append(ticket)
        return asdict(ticket)
