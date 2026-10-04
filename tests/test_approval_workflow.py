import unittest
from datetime import datetime, timedelta, timezone

from app.approval_workflow import ApprovalWorkflow, IrreversibleOperation


class ApprovalWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 4, 8, 0, tzinfo=timezone.utc)
        self.workflow = ApprovalWorkflow(
            signing_key=b"day-25-test-signing-key",
            clock=lambda: self.now,
        )
        self.operation = IrreversibleOperation(
            action="delete_ticket_attachment",
            subject_id="student-25",
            ticket_id="TICKET-25",
            attachment_id="diagnostic.log",
            reason="測試資料清理",
        )

    def test_approval_is_bound_to_the_exact_operation_and_consumed_once(self) -> None:
        request = self.workflow.create(self.operation)

        result = self.workflow.approve_and_execute(
            request.approval_id,
            approved_by="demo.approver",
        )
        replay = self.workflow.approve_and_execute(
            request.approval_id,
            approved_by="demo.approver",
        )

        self.assertTrue(result.executed)
        self.assertEqual(result.request.status, "consumed")
        self.assertFalse(replay.executed)
        self.assertEqual(replay.decisions[0].outcome, "consumed")

    def test_changed_parameters_invalidate_the_approval(self) -> None:
        request = self.workflow.create(self.operation)
        changed = IrreversibleOperation(
            action=self.operation.action,
            subject_id=self.operation.subject_id,
            ticket_id=self.operation.ticket_id,
            attachment_id="different.log",
            reason=self.operation.reason,
        )

        result = self.workflow.approve_and_execute(
            request.approval_id,
            approved_by="demo.approver",
            operation_override=changed,
        )

        self.assertFalse(result.executed)
        self.assertIn(
            ("approval_scope", "blocked"),
            [(decision.rule, decision.outcome) for decision in result.decisions],
        )

    def test_timeout_skips_the_handler_and_requires_escalation(self) -> None:
        request = self.workflow.create(self.operation, ttl=timedelta(minutes=30))

        _, decisions = self.workflow.expire_and_escalate(
            request.approval_id,
            now=request.expires_at + timedelta(seconds=1),
        )

        events = [(decision.rule, decision.outcome) for decision in decisions]
        self.assertEqual(request.status, "escalated")
        self.assertIn(("approval_timeout", "expired"), events)
        self.assertIn(("irreversible_handler", "skipped"), events)
        self.assertIn(("approval_escalation", "required"), events)


if __name__ == "__main__":
    unittest.main()
