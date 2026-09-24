"""Server-side tool schemas and access checks for the Helpdesk Agent."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Literal


ToolOperation = Literal["read", "write", "execute"]


@dataclass(frozen=True)
class ToolSchema:
    name: str
    operation: ToolOperation
    required_arguments: frozenset[str]


@dataclass(frozen=True)
class ToolPolicy:
    registered_tools: frozenset[str]
    allowed_operations: frozenset[ToolOperation]
    recipient_allowlist: frozenset[str] = field(default_factory=frozenset)
    article_allowlist: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ToolDecision:
    allowed: bool
    rule: str
    detail: str


TOOL_SCHEMAS = {
    "search_it_sop": ToolSchema(
        name="search_it_sop",
        operation="read",
        required_arguments=frozenset({"query"}),
    ),
    "create_ticket": ToolSchema(
        name="create_ticket",
        operation="write",
        required_arguments=frozenset({"title", "description", "priority"}),
    ),
    "share_sop_excerpt": ToolSchema(
        name="share_sop_excerpt",
        operation="write",
        required_arguments=frozenset({"recipient", "article_id"}),
    ),
}

DEFAULT_AGENT_TOOL_POLICY = ToolPolicy(
    registered_tools=frozenset({"search_it_sop", "create_ticket"}),
    allowed_operations=frozenset({"read", "write"}),
)

READ_ONLY_HELPDESK_POLICY = ToolPolicy(
    registered_tools=frozenset({"search_it_sop"}),
    allowed_operations=frozenset({"read"}),
)

TICKET_WRITER_POLICY = ToolPolicy(
    registered_tools=frozenset({"create_ticket"}),
    allowed_operations=frozenset({"write"}),
)

EXTERNAL_SHARE_DEMO_POLICY = ToolPolicy(
    registered_tools=frozenset({"share_sop_excerpt"}),
    allowed_operations=frozenset({"write"}),
    recipient_allowlist=frozenset({"it-support@example.test"}),
    article_allowlist=frozenset({"SOP-VPN-001"}),
)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_tool_call(
    tool_name: str,
    arguments: Mapping[str, object],
    *,
    policy: ToolPolicy,
) -> ToolDecision:
    """Return the first rejected rule, or the final allow decision."""
    decisions = validate_tool_call_steps(tool_name, arguments, policy=policy)
    return next((decision for decision in decisions if not decision.allowed), decisions[-1])


def validate_tool_call_steps(
    tool_name: str,
    arguments: Mapping[str, object],
    *,
    policy: ToolPolicy,
) -> tuple[ToolDecision, ...]:
    """Evaluate each server-side gate in order for audit and testing."""
    decisions: list[ToolDecision] = []
    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None or tool_name not in policy.registered_tools:
        return (ToolDecision(False, "tool_allowlist", "這個工具沒有註冊給目前的 Agent。"),)
    decisions.append(ToolDecision(True, "tool_allowlist", "工具已註冊給目前的執行角色。"))

    if schema.operation not in policy.allowed_operations:
        decisions.append(
            ToolDecision(False, "operation_boundary", "目前的 Agent 不具備這種操作權限。")
        )
        return tuple(decisions)
    decisions.append(
        ToolDecision(True, "operation_boundary", f"允許 {schema.operation} 類型操作。")
    )

    argument_names = set(arguments)
    if argument_names != schema.required_arguments:
        decisions.append(
            ToolDecision(
                False,
                "tool_schema",
                "工具參數和預先定義的 schema 不一致。",
            )
        )
        return tuple(decisions)

    if not all(isinstance(value, str) and value.strip() for value in arguments.values()):
        decisions.append(ToolDecision(False, "tool_schema", "工具參數必須是非空白字串。"))
        return tuple(decisions)
    decisions.append(ToolDecision(True, "tool_schema", "參數名稱與非空白字串檢查通過。"))

    if tool_name == "create_ticket" and arguments["priority"] not in {"low", "medium", "high"}:
        decisions.append(
            ToolDecision(False, "priority_allowlist", "priority 不在允許值內。")
        )
        return tuple(decisions)

    if tool_name != "share_sop_excerpt":
        decisions.append(ToolDecision(True, "allowed", "工具名稱、操作類型與參數都符合 policy。"))
        return tuple(decisions)

    recipient = str(arguments["recipient"]).strip().lower()
    if not _EMAIL_PATTERN.fullmatch(recipient):
        decisions.append(ToolDecision(False, "recipient_format", "收件者格式不合法。"))
        return tuple(decisions)
    decisions.append(ToolDecision(True, "recipient_format", "收件者格式檢查通過。"))
    if recipient not in policy.recipient_allowlist:
        decisions.append(ToolDecision(False, "recipient_allowlist", "收件者不在允許名單內。"))
        return tuple(decisions)
    decisions.append(ToolDecision(True, "recipient_allowlist", "收件者在允許名單內。"))
    if str(arguments["article_id"]) not in policy.article_allowlist:
        decisions.append(ToolDecision(False, "article_allowlist", "這份 SOP 不允許外寄。"))
        return tuple(decisions)
    decisions.append(ToolDecision(True, "article_allowlist", "SOP 在允許外寄的範圍內。"))
    decisions.append(ToolDecision(True, "allowed", "工具名稱、收件者與 SOP 範圍都符合 policy。"))
    return tuple(decisions)
