import unittest

from app.orchestration_security import (
    DelegationPrincipal,
    HandoffRequest,
    authorize_delegated_operation,
    issue_handoff_envelope,
    limit_parallel_workers,
)


class OrchestrationSecurityTests(unittest.TestCase):
    def test_parallel_plan_rejects_unknown_and_duplicate_workers(self) -> None:
        workers, decisions = limit_parallel_workers(
            ("vpn_specialist", "vpn_specialist", "unknown", "wifi_specialist"),
            max_workers=2,
        )

        self.assertEqual(workers, ("vpn_specialist", "wifi_specialist"))
        self.assertIn("duplicate_worker", [decision.rule for decision in decisions])
        self.assertIn("worker_allowlist", [decision.rule for decision in decisions])

    def test_parallel_plan_enforces_fan_out_budget(self) -> None:
        workers, decisions = limit_parallel_workers(
            ("vpn_specialist", "wifi_specialist"),
            max_workers=1,
        )

        self.assertEqual(workers, ("vpn_specialist",))
        self.assertIn(
            ("parallel_fanout_budget", "limited"),
            [(decision.rule, decision.outcome) for decision in decisions],
        )

    def test_handoff_scope_can_only_shrink(self) -> None:
        principal = DelegationPrincipal(
            tenant_id="campus-a",
            subject_id="student-24",
            actor_id="triage-agent",
            scopes=frozenset({"account.read", "password.reset"}),
        )
        request = HandoffRequest(
            target_agent="identity_specialist",
            task="檢查帳號並重設密碼",
            requested_scopes=frozenset({"account.read", "password.reset"}),
        )

        envelope, decisions = issue_handoff_envelope(
            run_id="RUN-24",
            principal=principal,
            request=request,
        )

        self.assertIsNotNone(envelope)
        assert envelope is not None
        self.assertEqual(envelope.effective_scopes, frozenset({"account.read"}))
        self.assertEqual(envelope.subject_id, principal.subject_id)
        self.assertEqual(envelope.actor_chain, ("triage-agent", "identity_specialist"))
        self.assertIn("reduced", [decision.outcome for decision in decisions])

    def test_sensitive_handoff_needs_scope_and_approval(self) -> None:
        principal = DelegationPrincipal(
            tenant_id="campus-a",
            subject_id="student-24",
            actor_id="triage-agent",
            scopes=frozenset({"account.read", "password.reset"}),
        )
        envelope, _ = issue_handoff_envelope(
            run_id="RUN-24",
            principal=principal,
            request=HandoffRequest(
                target_agent="identity_specialist",
                task="重設密碼",
                requested_scopes=frozenset({"password.reset"}),
            ),
        )
        assert envelope is not None

        allowed, decisions = authorize_delegated_operation(
            envelope,
            required_scope="password.reset",
            approved=False,
        )

        self.assertFalse(allowed)
        self.assertEqual(
            [(decision.rule, decision.outcome) for decision in decisions],
            [("delegated_scope", "blocked"), ("approval_gate", "pending")],
        )

    def test_unknown_handoff_target_is_rejected(self) -> None:
        envelope, decisions = issue_handoff_envelope(
            run_id="RUN-24",
            principal=DelegationPrincipal(
                tenant_id="campus-a",
                subject_id="student-24",
                actor_id="triage-agent",
                scopes=frozenset({"account.read"}),
            ),
            request=HandoffRequest(
                target_agent="unknown-agent",
                task="查詢帳號",
                requested_scopes=frozenset({"account.read"}),
            ),
        )

        self.assertIsNone(envelope)
        self.assertEqual(decisions[0].rule, "handoff_target_allowlist")


if __name__ == "__main__":
    unittest.main()
