"""Task-scoped tool exposure for the Helpdesk Agent."""

from dataclasses import dataclass
from typing import Literal


ToolOperation = Literal["read", "write", "execute"]


@dataclass(frozen=True)
class CatalogTool:
    name: str
    description: str
    operation: ToolOperation
    capability: str


TOOL_CATALOG = (
    CatalogTool("search_it_sop", "Search approved IT SOP articles for troubleshooting steps.", "read", "sop_search"),
    CatalogTool("create_ticket", "Create one mock helpdesk ticket after SOP lookup.", "write", "ticket_create"),
    CatalogTool("search_vpn_sop", "Search VPN-specific troubleshooting articles.", "read", "sop_search"),
    CatalogTool("search_network_sop", "Search network troubleshooting articles.", "read", "sop_search"),
    CatalogTool("lookup_helpdesk_article", "Look up one helpdesk article by keywords.", "read", "sop_search"),
    CatalogTool("find_it_policy", "Find an IT policy related to a reported issue.", "read", "sop_search"),
    CatalogTool("list_ticket_templates", "List templates that can be used to create a ticket.", "read", "ticket_create"),
    CatalogTool("create_incident", "Create a mock incident record.", "write", "ticket_create"),
    CatalogTool("update_ticket", "Update fields on an existing ticket.", "write", "ticket_update"),
    CatalogTool("add_ticket_comment", "Add a comment to an existing ticket.", "write", "ticket_update"),
    CatalogTool("escalate_ticket", "Escalate a ticket to another queue.", "write", "ticket_update"),
    CatalogTool("close_ticket", "Close an existing ticket.", "write", "ticket_update"),
    CatalogTool("reset_password", "Reset an account password.", "execute", "account_admin"),
    CatalogTool("unlock_account", "Unlock a suspended user account.", "execute", "account_admin"),
    CatalogTool("disable_user", "Disable a user account.", "execute", "account_admin"),
    CatalogTool("send_notification", "Send a notification to a named destination.", "write", "outbound_send"),
    CatalogTool("send_email", "Send an email to a supplied recipient.", "write", "outbound_send"),
    CatalogTool("upload_attachment", "Upload a file to an external ticket.", "write", "external_upload"),
    CatalogTool("http_request", "Send an arbitrary HTTP request.", "execute", "open_ended"),
    CatalogTool("run_shell_command", "Run an arbitrary shell command.", "execute", "open_ended"),
)


HELPDESK_TRIAGE_TOOL_NAMES = frozenset({"search_it_sop", "create_ticket"})


def tools_for_helpdesk_triage() -> tuple[CatalogTool, ...]:
    """Return only the tools required by the current triage workflow."""
    return tuple(tool for tool in TOOL_CATALOG if tool.name in HELPDESK_TRIAGE_TOOL_NAMES)


def omitted_tool_names() -> tuple[str, ...]:
    """Return catalog entries intentionally hidden from the model for this task."""
    return tuple(tool.name for tool in TOOL_CATALOG if tool.name not in HELPDESK_TRIAGE_TOOL_NAMES)


def overlapping_capabilities() -> dict[str, tuple[str, ...]]:
    """List capabilities represented by more than one catalog entry."""
    by_capability: dict[str, list[str]] = {}
    for tool in TOOL_CATALOG:
        by_capability.setdefault(tool.capability, []).append(tool.name)
    return {
        capability: tuple(names)
        for capability, names in by_capability.items()
        if len(names) > 1
    }
