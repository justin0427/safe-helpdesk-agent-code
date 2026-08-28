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

    def test_runs_the_loop_stop_demo(self) -> None:
        response = self.client.post("/api/demos/runaway-loop")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])

    def test_runs_the_token_cost_budget_demo(self) -> None:
        response = self.client.post("/api/demos/token-cost-budget")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trace"][-1]["name"], "cost_budget")

    def test_runs_the_time_budget_demo(self) -> None:
        response = self.client.post("/api/demos/time-budget")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trace"][-1]["name"], "time_budget")
