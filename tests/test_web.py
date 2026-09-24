import unittest

from fastapi.testclient import TestClient

from app.web import app


class WebConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_serves_the_console(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Safe Helpdesk Agent", response.text)

    def test_serves_the_console_stylesheet(self) -> None:
        response = self.client.get("/static/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(".workbench", response.text)

    def test_runs_the_sop_first_demo(self) -> None:
        response = self.client.post("/api/demos/sop-first")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ticket"]["status"], "created")

    def test_blocks_the_ticket_before_sop_demo(self) -> None:
        response = self.client.post("/api/demos/ticket-before-sop")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertIsNone(response.json()["ticket"])

    def test_day_three_screenshot_scenario_renders_blocked_write(self) -> None:
        response = self.client.get("/?scenario=ticket-before-sop")

        self.assertEqual(response.status_code, 200)
        self.assertIn("已安全停止", response.text)
        self.assertIn("tool: create_ticket", response.text)
        self.assertIn("guardrail: sop_first", response.text)
        self.assertIn("尚未查詢 SOP，拒絕建立工單。", response.text)

    def test_runs_the_loop_stop_demo(self) -> None:
        response = self.client.post("/api/demos/runaway-loop")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])

    def test_runs_the_sop_timeout_demo(self) -> None:
        response = self.client.post("/api/demos/sop-timeout")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertIsNone(response.json()["ticket"])

    def test_runs_the_circuit_breaker_demo(self) -> None:
        response = self.client.post("/api/demos/circuit-open")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertIn("circuit_breaker", [event["name"] for event in response.json()["trace"]])

    def test_runs_the_context_boundary_demo(self) -> None:
        response = self.client.post("/api/demos/context-boundary")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertIn("沒有建立 mock 工單", response.json()["response"])

    def test_runs_the_external_share_demo(self) -> None:
        response = self.client.post("/api/demos/external-share")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertIn("沒有發送任何資料", response.json()["response"])

    def test_day_eleven_screenshot_scenario_renders_the_blocked_share(self) -> None:
        response = self.client.get("/?scenario=external-share")

        self.assertEqual(response.status_code, 200)
        self.assertIn("recipient_allowlist", response.text)
        self.assertIn("outbound_dispatch", response.text)

    def test_runs_the_rag_injection_demo(self) -> None:
        response = self.client.post("/api/demos/rag-injection")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertIn("指令式內容已隔離", response.json()["response"])

    def test_day_eleven_rag_screenshot_scenario_renders_quarantine(self) -> None:
        response = self.client.get("/?scenario=rag-injection")

        self.assertEqual(response.status_code, 200)
        self.assertIn("indirect_prompt_injection", response.text)
        self.assertIn("explicit_user_ticket_request", response.text)
        self.assertIn("create_ticket", response.text)

    def test_runs_the_token_cost_budget_demo(self) -> None:
        response = self.client.post("/api/demos/token-cost-budget")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trace"][-1]["name"], "cost_budget")

    def test_runs_the_time_budget_demo(self) -> None:
        response = self.client.post("/api/demos/time-budget")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trace"][-1]["name"], "time_budget")
