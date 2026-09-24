import unittest

from app.demo_scenarios import run_tool_catalog_scope_demo
from app.tool_catalog import (
    HELPDESK_TRIAGE_TOOL_NAMES,
    TOOL_CATALOG,
    omitted_tool_names,
    overlapping_capabilities,
    tools_for_helpdesk_triage,
)


class ToolCatalogTests(unittest.TestCase):
    def test_demo_catalog_contains_twenty_distinct_tools(self) -> None:
        names = [tool.name for tool in TOOL_CATALOG]

        self.assertEqual(len(names), 20)
        self.assertEqual(len(set(names)), 20)

    def test_helpdesk_triage_exposes_only_two_required_tools(self) -> None:
        visible_names = frozenset(tool.name for tool in tools_for_helpdesk_triage())

        self.assertEqual(visible_names, HELPDESK_TRIAGE_TOOL_NAMES)

    def test_open_ended_and_account_admin_tools_are_not_model_visible(self) -> None:
        visible_names = {tool.name for tool in tools_for_helpdesk_triage()}

        self.assertTrue(
            {"reset_password", "http_request", "run_shell_command"}.isdisjoint(visible_names)
        )
        self.assertIn("reset_password", omitted_tool_names())

    def test_catalog_makes_overlapping_capabilities_visible(self) -> None:
        overlaps = overlapping_capabilities()

        self.assertGreater(len(overlaps["sop_search"]), 1)
        self.assertGreater(len(overlaps["ticket_create"]), 1)

    def test_demo_records_twenty_to_two_reduction(self) -> None:
        result = run_tool_catalog_scope_demo()

        self.assertIn("20 個候選工具", result.response)
        self.assertEqual(result.trace[2]["status"], "2_tools")
        self.assertEqual(len(result.trace[3]["data"]["omitted_tools"]), 18)
