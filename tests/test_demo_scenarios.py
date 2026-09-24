import unittest

from app.demo_scenarios import (
    run_circuit_open_demo,
    run_context_compaction_demo,
    run_context_boundary_demo,
    run_document_authorization_demo,
    run_external_share_blocked_demo,
    run_rag_injection_demo,
    run_sop_timeout_fallback_demo,
    run_ticket_before_sop_demo,
    run_time_budget_demo,
    run_token_cost_budget_demo,
    run_runaway_loop_demo,
    run_sop_first_demo,
)


class DemoScenarioTests(unittest.TestCase):
    def test_document_authorization_filters_tenant_acl_and_content(self) -> None:
        result = run_document_authorization_demo()

        self.assertTrue(result.stopped)
        self.assertIn("最後只有 1 份文件", result.response)
        self.assertIn("tenant_isolation", [event["name"] for event in result.trace])
        self.assertIn("document_acl", [event["name"] for event in result.trace])
        self.assertIn(
            "nemo_regex_retrieval_rail",
            [event["name"] for event in result.trace],
        )

    def test_context_compaction_keeps_relevant_history_and_drops_the_secret(self) -> None:
        result = run_context_compaction_demo()
        rendered = str(result.as_dict())

        self.assertTrue(result.stopped)
        self.assertIn("3 個 context blocks", result.response)
        self.assertNotIn("MOCK-948201", rendered)
        self.assertEqual(result.trace[-1]["status"], "3_blocks")

    def test_sop_first_demo_searches_before_creating_a_ticket(self) -> None:
        result = run_sop_first_demo()

        self.assertFalse(result.stopped)
        self.assertEqual(result.trace[0]["name"], "search_it_sop")
        self.assertEqual(result.trace[1]["name"], "create_ticket")
        self.assertEqual(result.ticket["status"], "created")

    def test_ticket_before_sop_demo_blocks_the_write(self) -> None:
        result = run_ticket_before_sop_demo()

        self.assertTrue(result.stopped)
        self.assertIsNone(result.ticket)
        self.assertIn("拒絕建立 mock 工單", result.response)
        self.assertEqual(
            [(event["name"], event["status"]) for event in result.trace],
            [
                ("create_ticket", "requested"),
                ("sop_first", "blocked"),
                ("final_response", "completed"),
            ],
        )

    def test_external_share_demo_stops_before_dispatch(self) -> None:
        result = run_external_share_blocked_demo()

        self.assertTrue(result.stopped)
        self.assertIn("沒有發送任何資料", result.response)
        self.assertEqual(
            [(event["name"], event["status"]) for event in result.trace],
            [
                ("share_sop_excerpt", "requested"),
                ("recipient_allowlist", "blocked"),
                ("outbound_dispatch", "skipped"),
            ],
        )

    def test_rag_injection_demo_quarantines_the_poisoned_document(self) -> None:
        result = run_rag_injection_demo()

        self.assertTrue(result.stopped)
        self.assertIsNone(result.ticket)
        self.assertIn("1 份指令式內容已隔離", result.response)
        self.assertIn(
            ("indirect_prompt_injection", "quarantined"),
            [(event["name"], event["status"]) for event in result.trace],
        )
        self.assertIn(
            ("explicit_user_ticket_request", "blocked"),
            [(event["name"], event["status"]) for event in result.trace],
        )

    def test_runaway_loop_demo_stops_after_the_budget(self) -> None:
        result = run_runaway_loop_demo(recursion_limit=4)

        self.assertTrue(result.stopped)
        self.assertEqual(len(result.trace), 5)
        self.assertEqual(result.trace[-1]["status"], "stopped")
        self.assertIn("停止", result.response)

    def test_stops_after_the_cost_budget_is_exceeded(self) -> None:
        result = run_token_cost_budget_demo()

        self.assertTrue(result.stopped)
        self.assertEqual(result.trace[-1]["name"], "cost_budget")
        self.assertEqual(result.trace[-2]["data"]["total_tokens"], 2_900)

    def test_stops_after_the_time_budget_is_exceeded(self) -> None:
        result = run_time_budget_demo()

        self.assertTrue(result.stopped)
        self.assertEqual(result.trace[-1]["name"], "time_budget")
        self.assertNotIn("create_ticket", [event["name"] for event in result.trace])

    def test_sop_timeout_degrades_without_creating_a_ticket(self) -> None:
        result = run_sop_timeout_fallback_demo()

        self.assertTrue(result.stopped)
        self.assertIsNone(result.ticket)
        self.assertIn("不會在無法查核流程時自動建立工單", result.response)
        self.assertIn("sop_unavailable", [event["name"] for event in result.trace])

    def test_circuit_demo_blocks_the_second_sop_request(self) -> None:
        result = run_circuit_open_demo()

        self.assertTrue(result.stopped)
        self.assertIn("沒有再送出 SOP 請求", result.response)
        self.assertEqual(
            len(
                [
                    event
                    for event in result.trace
                    if event["name"] == "search_it_sop" and event["status"] == "failed"
                ]
            ),
            2,
        )
        self.assertIn(
            "blocked",
            [
                event["status"]
                for event in result.trace
                if event["name"] == "circuit_breaker"
            ],
        )

    def test_context_demo_keeps_document_recommendation_as_data(self) -> None:
        result = run_context_boundary_demo()

        self.assertTrue(result.stopped)
        self.assertIn("沒有建立 mock 工單", result.response)
        self.assertEqual(
            [event["status"] for event in result.trace if event["kind"] == "context"],
            ["policy", "untrusted_data", "untrusted_data", "untrusted_data"],
        )
        self.assertIn(
            "explicit_user_ticket_request", [event["name"] for event in result.trace]
        )
        self.assertIn(
            "retrieved_recommendation", [event["name"] for event in result.trace]
        )
