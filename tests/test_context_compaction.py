import unittest

from app.context_compaction import HistoryItem, prepare_history_context


class ContextCompactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.history = (
            HistoryItem("message-01", 1, "測試用 Windows 11 筆電。", "裝置是測試用 Windows 11 筆電。"),
            HistoryItem("message-02", 2, "Wi-Fi 問題已處理完成。"),
            HistoryItem("message-03", 3, "VPN 曾出現 E401，重新登入後暫時恢復。"),
            HistoryItem(
                "message-04",
                4,
                "測試帳號備用碼是 MOCK-948201。",
                sensitivity="secret",
            ),
            HistoryItem("message-05", 5, "印表機沒有紙，已自行補充。"),
            HistoryItem("message-06", 6, "現在 VPN 又出現 E401，只要排障步驟，不要開工單。"),
        )

    def test_keeps_the_current_turn(self) -> None:
        prepared = prepare_history_context(self.history, query_terms=("VPN", "E401"))

        self.assertEqual(prepared.model_context[-1].block_id, "message-06")
        self.assertEqual(prepared.model_context[-1].reason, "recent")

    def test_relevance_can_beat_a_more_recent_unrelated_message(self) -> None:
        prepared = prepare_history_context(self.history, query_terms=("VPN", "E401"))

        block_ids = [block.block_id for block in prepared.model_context]
        self.assertIn("message-03", block_ids)
        self.assertNotIn("message-05", block_ids)

    def test_sensitive_content_is_not_selected_or_summarized(self) -> None:
        prepared = prepare_history_context(self.history, query_terms=("VPN", "E401"))
        rendered = "\n".join(block.content for block in prepared.model_context)

        self.assertEqual(prepared.dropped_sensitive_ids, ("message-04",))
        self.assertNotIn("MOCK-948201", rendered)
        self.assertNotIn("message-04", prepared.summarized_ids)

    def test_compacts_safe_older_messages_into_one_block(self) -> None:
        prepared = prepare_history_context(self.history, query_terms=("VPN", "E401"))

        self.assertEqual(len(prepared.model_context), 3)
        self.assertEqual(prepared.model_context[0].block_id, "history-summary")
        self.assertEqual(
            prepared.summarized_ids,
            ("message-01",),
        )
        self.assertEqual(
            prepared.dropped_irrelevant_ids,
            ("message-02", "message-05"),
        )
