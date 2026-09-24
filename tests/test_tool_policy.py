import unittest

from app.agent import AGENT_TOOLS
from app.tool_policy import (
    DEFAULT_AGENT_TOOL_POLICY,
    EXTERNAL_SHARE_DEMO_POLICY,
    READ_ONLY_HELPDESK_POLICY,
    TICKET_WRITER_POLICY,
    validate_tool_call,
    validate_tool_call_steps,
)


class ToolPolicyTests(unittest.TestCase):
    def test_agent_registration_matches_the_default_policy(self) -> None:
        self.assertEqual(
            frozenset(agent_tool.name for agent_tool in AGENT_TOOLS),
            DEFAULT_AGENT_TOOL_POLICY.registered_tools,
        )

    def test_default_agent_does_not_register_outbound_sharing(self) -> None:
        decision = validate_tool_call(
            "share_sop_excerpt",
            {"recipient": "it-support@example.test", "article_id": "SOP-VPN-001"},
            policy=DEFAULT_AGENT_TOOL_POLICY,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "tool_allowlist")

    def test_outbound_tool_rejects_an_extra_argument(self) -> None:
        decision = validate_tool_call(
            "share_sop_excerpt",
            {
                "recipient": "it-support@example.test",
                "article_id": "SOP-VPN-001",
                "include_all_articles": "true",
            },
            policy=EXTERNAL_SHARE_DEMO_POLICY,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "tool_schema")

    def test_outbound_tool_rejects_an_external_recipient(self) -> None:
        decision = validate_tool_call(
            "share_sop_excerpt",
            {"recipient": "outside@example.invalid", "article_id": "SOP-VPN-001"},
            policy=EXTERNAL_SHARE_DEMO_POLICY,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "recipient_allowlist")

    def test_outbound_validation_exposes_each_gate_in_order(self) -> None:
        decisions = validate_tool_call_steps(
            "share_sop_excerpt",
            {"recipient": "outside@example.invalid", "article_id": "SOP-VPN-001"},
            policy=EXTERNAL_SHARE_DEMO_POLICY,
        )

        self.assertEqual(
            [decision.rule for decision in decisions],
            [
                "tool_allowlist",
                "operation_boundary",
                "tool_schema",
                "recipient_format",
                "recipient_allowlist",
            ],
        )
        self.assertFalse(decisions[-1].allowed)

    def test_read_and_write_policies_register_different_tools(self) -> None:
        self.assertEqual(
            READ_ONLY_HELPDESK_POLICY.registered_tools,
            frozenset({"search_it_sop"}),
        )
        self.assertEqual(
            TICKET_WRITER_POLICY.registered_tools,
            frozenset({"create_ticket"}),
        )

    def test_ticket_priority_uses_an_allowlist(self) -> None:
        decision = validate_tool_call(
            "create_ticket",
            {"title": "VPN", "description": "VPN 連不上", "priority": "urgent"},
            policy=TICKET_WRITER_POLICY,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "priority_allowlist")

    def test_outbound_tool_allows_only_the_scoped_mock_request(self) -> None:
        decision = validate_tool_call(
            "share_sop_excerpt",
            {"recipient": "it-support@example.test", "article_id": "SOP-VPN-001"},
            policy=EXTERNAL_SHARE_DEMO_POLICY,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule, "allowed")
