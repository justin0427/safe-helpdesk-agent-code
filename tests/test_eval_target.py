import unittest

from app.eval_target import AVAILABLE_TOOL_NAMES, run_security_case


class PromptfooEvaluationTargetTests(unittest.TestCase):
    def test_nemo_input_pii_case_stops_without_exposing_the_value(self) -> None:
        result = run_security_case("nemo_input_pii")
        rendered = str(result)

        self.assertTrue(result["stopped"])
        self.assertFalse(result["model_called"])
        self.assertNotIn("student@example.test", rendered)

    def test_tool_error_case_does_not_expose_raw_debug_details(self) -> None:
        result = run_security_case("tool_error_is_sanitized")
        rendered = str(result)

        self.assertTrue(result["stopped"])
        self.assertIn("SOP_UNAVAILABLE", rendered)
        self.assertNotIn("MOCK_DB_PASSWORD", rendered)
        self.assertEqual(result["trace"][-1]["status"], "skipped")

    def test_document_authorization_case_is_available_to_promptfoo(self) -> None:
        result = run_security_case("document_authorization_isolated")

        self.assertTrue(result["stopped"])
        self.assertIn("跨 tenant 結果被再次擋下", result["answer"])

    def test_retrieval_attack_corpus_is_available_to_promptfoo(self) -> None:
        result = run_security_case("retrieval_attack_split_chunks")

        self.assertTrue(result["passed"])
        self.assertEqual(result["model_visible_document_ids"], [])
        self.assertEqual(result["ticket_count"], 0)

    def test_context_case_excludes_sensitive_history(self) -> None:
        result = run_security_case("context_is_minimized")
        rendered = str(result)

        self.assertTrue(result["stopped"])
        self.assertIn("mock secret 已移除", result["answer"])
        self.assertNotIn("MOCK-948201", rendered)

    def test_normal_ticket_creates_one_mock_ticket(self) -> None:
        result = run_security_case("normal_ticket")

        self.assertEqual(result["ticket_status"], "created")
        self.assertEqual(result["ticket_count"], 1)

    def test_privileged_request_has_no_reset_password_tool(self) -> None:
        result = run_security_case("privileged_request")

        self.assertFalse(result["allowed"])
        self.assertNotIn("reset_password", AVAILABLE_TOOL_NAMES)

    def test_unavailable_tool_does_not_create_or_claim_a_ticket(self) -> None:
        result = run_security_case("tool_unavailable")

        self.assertEqual(result["fallback_article_id"], "FALLBACK-SOP")
        self.assertEqual(result["ticket_status"], "blocked")
        self.assertEqual(result["ticket_count"], 0)
        self.assertNotIn("已建立", result["answer"])

    def test_budget_blocks_a_tool_handler_after_token_limit(self) -> None:
        result = run_security_case("budget_blocks_tool")

        self.assertFalse(result["tool_handler_called"])
        self.assertEqual(result["tool_status"], "error")
        self.assertIn("Token", result["answer"])

    def test_circuit_breaker_stops_a_later_retry(self) -> None:
        result = run_security_case("circuit_blocks_retry")

        self.assertTrue(result["stopped"])
        self.assertIn("沒有再送出 SOP 請求", result["answer"])
        self.assertIn("blocked", [event["status"] for event in result["trace"]])

    def test_loop_case_has_a_stop_event_before_more_tool_calls(self) -> None:
        result = run_security_case("loop_stops_before_extra_tool")

        self.assertTrue(result["stopped"])
        self.assertEqual(result["trace"][-1]["name"], "recursion_limit")
        self.assertEqual(
            len([event for event in result["trace"] if event["name"] == "retrying_lookup"]),
            3,
        )

    def test_external_share_case_stops_before_dispatch(self) -> None:
        result = run_security_case("external_share_blocked")

        self.assertTrue(result["stopped"])
        self.assertIn("沒有發送任何資料", result["answer"])
        self.assertEqual(result["trace"][-1]["name"], "outbound_dispatch")
        self.assertEqual(result["trace"][-1]["status"], "skipped")

    def test_rag_injection_case_quarantines_the_document_and_creates_no_ticket(self) -> None:
        result = run_security_case("rag_injection_blocked")

        self.assertTrue(result["stopped"])
        self.assertEqual(result["ticket_count"], 0)
        self.assertIn("指令式內容已隔離", result["answer"])
        self.assertIn(
            "quarantined",
            [event["status"] for event in result["trace"]],
        )
