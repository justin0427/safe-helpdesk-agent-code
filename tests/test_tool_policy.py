import unittest

from app.agent import AGENT_TOOLS
from app.tool_policy import (
    DEFAULT_AGENT_TOOL_POLICY,
    EXTERNAL_SHARE_DEMO_POLICY,
    validate_tool_call,
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

    def test_outbound_tool_allows_only_the_scoped_mock_request(self) -> None:
        decision = validate_tool_call(
            "share_sop_excerpt",
            {"recipient": "it-support@example.test", "article_id": "SOP-VPN-001"},
            policy=EXTERNAL_SHARE_DEMO_POLICY,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule, "allowed")
