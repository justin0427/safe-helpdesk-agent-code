import unittest

from app.demo_scenarios import (
    run_retry_budget_demo,
    run_retry_success_demo,
    run_runaway_loop_demo,
    run_sop_first_demo,
)


class DemoScenarioTests(unittest.TestCase):
    def test_sop_first_demo_searches_before_creating_a_ticket(self) -> None:
        result = run_sop_first_demo()

        self.assertFalse(result.stopped)
        self.assertEqual(result.trace[0]["name"], "search_it_sop")
        self.assertEqual(result.trace[1]["name"], "create_ticket")
        self.assertEqual(result.ticket["status"], "created")

    def test_runaway_loop_demo_stops_after_the_budget(self) -> None:
        result = run_runaway_loop_demo(recursion_limit=4)

        self.assertTrue(result.stopped)
        self.assertEqual(len(result.trace), 5)
        self.assertEqual(result.trace[-1]["status"], "stopped")
        self.assertIn("停止", result.response)

    def test_retry_demo_stops_after_a_bounded_number_of_read_only_attempts(self) -> None:
        result = run_retry_budget_demo()

        self.assertTrue(result.stopped)
        self.assertEqual(result.trace[-1]["name"], "retry_budget")
        self.assertEqual(result.trace[-1]["status"], "stopped")
        self.assertNotIn("create_ticket", [event["name"] for event in result.trace])

    def test_retry_demo_recovers_without_repeating_a_write(self) -> None:
        result = run_retry_success_demo()

        self.assertFalse(result.stopped)
        self.assertEqual(result.trace[-2]["status"], "completed")
        self.assertEqual(result.trace[-2]["data"]["attempt"], 3)
        self.assertNotIn("create_ticket", [event["name"] for event in result.trace])
