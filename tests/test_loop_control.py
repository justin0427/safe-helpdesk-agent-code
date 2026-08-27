import unittest

from app.loop_control import build_agent_config, loop_limit_message


class LoopControlTests(unittest.TestCase):
    def test_builds_a_recursion_limit_config(self) -> None:
        self.assertEqual(build_agent_config(6), {"recursion_limit": 6})

    def test_rejects_an_impossibly_small_limit(self) -> None:
        with self.assertRaises(ValueError):
            build_agent_config(2)

    def test_returns_a_safe_stop_message(self) -> None:
        self.assertIn("停止", loop_limit_message())
