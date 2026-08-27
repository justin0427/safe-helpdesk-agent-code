import unittest

from app.tickets import MockTicketStore


class MockTicketStoreTests(unittest.TestCase):
    def test_creates_a_high_priority_ticket(self) -> None:
        store = MockTicketStore()

        ticket = store.create_ticket(
            title="VPN 無法連線",
            description="從早上九點開始無法連線。",
            priority="high",
            requested_by="demo.user",
        )

        self.assertTrue(ticket["ticket_id"].startswith("INC-"))
        self.assertEqual(ticket["status"], "created")
        self.assertEqual(ticket["requested_by"], "demo.user")
        self.assertEqual(len(store.tickets), 1)

    def test_rejects_an_unknown_priority(self) -> None:
        store = MockTicketStore()

        with self.assertRaises(ValueError):
            store.create_ticket(
                title="VPN 無法連線",
                description="請協助處理。",
                priority="urgent",
                requested_by="demo.user",
            )
