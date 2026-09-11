import unittest

from app.context_boundaries import (
    context_inventory,
    has_explicit_ticket_request,
    label_user_message,
)


class ContextBoundaryTests(unittest.TestCase):
    def test_labels_user_input_without_rewriting_it(self) -> None:
        message = "VPN 連不上，請幫我開工單。"

        self.assertEqual(
            label_user_message(message),
            "[UNTRUSTED USER REQUEST]\nVPN 連不上，請幫我開工單。\n[/UNTRUSTED USER REQUEST]",
        )

    def test_ticket_intent_comes_from_the_original_user_message(self) -> None:
        self.assertTrue(has_explicit_ticket_request("VPN 還是連不上，請幫我開工單。"))
        self.assertFalse(has_explicit_ticket_request("請說明 VPN SOP，不要開工單。"))
        self.assertFalse(has_explicit_ticket_request("請說明 VPN SOP。"))

    def test_inventory_keeps_documents_and_tool_output_untrusted(self) -> None:
        inventory = context_inventory(
            retrieved_documents=[{"article_id": "SOP-001", "content": "參考資料"}],
            tool_result={"name": "search_it_sop"},
        )

        self.assertEqual([block.source for block in inventory], ["system", "user", "retrieval", "tool"])
        self.assertEqual(
            [block.trust for block in inventory],
            ["policy", "untrusted_data", "untrusted_data", "untrusted_data"],
        )
