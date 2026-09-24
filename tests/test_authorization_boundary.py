import unittest

from app.authorization_boundary import (
    MockTicketApi,
    Principal,
    TicketRecord,
    validate_agent_output,
)


class AuthorizationBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.principal = Principal(
            subject="operator-a",
            tenant_id="campus-a",
            roles=frozenset({"helpdesk_operator"}),
            scopes=frozenset({"tickets:close"}),
        )

    def test_cross_tenant_ticket_is_denied_after_scope_and_role_pass(self) -> None:
        ticket = TicketRecord(ticket_id="TICKET-B-002", tenant_id="campus-b")

        result = MockTicketApi().close_ticket(
            principal=self.principal,
            ticket=ticket,
        )

        self.assertEqual(result.http_status, 403)
        self.assertEqual(result.code, "OBJECT_FORBIDDEN")
        self.assertFalse(result.handler_called)
        self.assertEqual(ticket.status, "open")
        self.assertEqual(
            [(decision.rule, decision.allowed) for decision in result.authorization],
            [
                ("api_authentication", True),
                ("api_scope", True),
                ("rbac", True),
                ("resource_acl", False),
            ],
        )

    def test_same_tenant_ticket_can_be_closed(self) -> None:
        ticket = TicketRecord(ticket_id="TICKET-A-001", tenant_id="campus-a")

        result = MockTicketApi().close_ticket(
            principal=self.principal,
            ticket=ticket,
        )

        self.assertEqual(result.status, "closed")
        self.assertTrue(result.handler_called)
        self.assertEqual(ticket.status, "closed")

    def test_output_check_blocks_success_claim_after_api_denial(self) -> None:
        ticket = TicketRecord(ticket_id="TICKET-B-002", tenant_id="campus-b")
        api_result = MockTicketApi().close_ticket(
            principal=self.principal,
            ticket=ticket,
        )

        output = validate_agent_output("已關閉 TICKET-B-002。", api_result)

        self.assertFalse(output.allowed)
        self.assertIn("沒有操作", output.response)
        self.assertNotIn("已關閉", output.response)


if __name__ == "__main__":
    unittest.main()
