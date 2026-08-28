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
