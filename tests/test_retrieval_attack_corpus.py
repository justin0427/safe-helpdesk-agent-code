import unittest

from app.retrieval_attack_corpus import RETRIEVAL_ATTACK_CORPUS, run_retrieval_attack


class RetrievalAttackCorpusTests(unittest.TestCase):
    def test_every_attack_is_quarantined_before_tool_execution(self) -> None:
        self.assertEqual(len(RETRIEVAL_ATTACK_CORPUS), 4)

        for attack in RETRIEVAL_ATTACK_CORPUS:
            with self.subTest(case=attack.case_id):
                result = run_retrieval_attack(attack.case_id)
                self.assertTrue(result["passed"])
                self.assertEqual(result["model_visible_document_ids"], [])
                self.assertEqual(result["ticket_count"], 0)
                self.assertEqual(result["tool_outcome"], "skipped")
                self.assertEqual(result["trace"][-1]["name"], "create_ticket")
                self.assertEqual(result["trace"][-1]["status"], "skipped")
