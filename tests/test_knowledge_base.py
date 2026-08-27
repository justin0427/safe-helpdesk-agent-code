import unittest

from app.knowledge_base import MockKnowledgeBase


class MockKnowledgeBaseTests(unittest.TestCase):
    def test_finds_the_vpn_sop(self) -> None:
        knowledge_base = MockKnowledgeBase()

        results = knowledge_base.search("VPN 連不上")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["article_id"], "SOP-001")

    def test_returns_no_match_for_an_unknown_query(self) -> None:
        knowledge_base = MockKnowledgeBase()

        self.assertEqual(knowledge_base.search("印表機"), [])
