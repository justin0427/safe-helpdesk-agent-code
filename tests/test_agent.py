import unittest

from langchain_core.exceptions import ModelTimeoutError
from langchain_core.messages import AIMessage

from app.agent import HelpdeskAgent


class _TimeoutAgent:
    def invoke(self, *args, **kwargs):
        raise ModelTimeoutError("test timeout")


class _EmptyResponseAgent:
    def invoke(self, *args, **kwargs):
        return {"messages": [AIMessage(content="")]}


class HelpdeskAgentTests(unittest.TestCase):
    def _agent(self) -> HelpdeskAgent:
        return HelpdeskAgent(
            model_name="test-model",
            model_api_key="test-key",
            requested_by="test.user",
        )

    def test_model_timeout_stops_with_a_safe_message(self) -> None:
        agent = self._agent()
        agent.agent = _TimeoutAgent()

        result = agent.run_detailed("VPN 連不上，請查 SOP。")

        self.assertTrue(result.stopped)
        self.assertIn("逾時", result.response)
        self.assertEqual(result.trace[-1]["name"], "live_llm")
        self.assertEqual(result.trace[-1]["status"], "timed_out")

    def test_empty_model_output_uses_a_fixed_fallback(self) -> None:
        agent = self._agent()
        agent.agent = _EmptyResponseAgent()

        result = agent.run_detailed("VPN 連不上，請查 SOP。")

        self.assertFalse(result.stopped)
        self.assertIn("沒有產生可顯示的回覆", result.response)
        self.assertIn(
            ("empty_model_output", "degraded"),
            [(event["name"], event["status"]) for event in result.trace],
        )


if __name__ == "__main__":
    unittest.main()
