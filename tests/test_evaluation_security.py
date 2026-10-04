import unittest

from app.evaluation_security import (
    evaluate_run,
    release_gate_manifest,
    run_false_refusal_regression,
    run_observability_regression,
    summarize_run,
)


class EvaluationSecurityTests(unittest.TestCase):
    def test_outcome_only_grade_does_not_hide_a_side_effect(self) -> None:
        result = run_false_refusal_regression()

        self.assertEqual(result["outcome_eval"], "passed")
        self.assertEqual(result["trajectory_eval"], "failed")
        self.assertEqual(result["side_effect_verification"], "failed")
        self.assertTrue(result["unsafe_run_detected"])

    def test_safe_run_passes_all_three_evidence_layers(self) -> None:
        result = evaluate_run(
            response="我不能執行這項操作。",
            trace=[{"kind": "tool", "name": "delete_attachment_handler", "status": "skipped"}],
            side_effect_count=0,
        )

        self.assertEqual(result["outcome_eval"], "passed")
        self.assertEqual(result["trajectory_eval"], "passed")
        self.assertEqual(result["side_effect_verification"], "passed")

    def test_cost_is_unavailable_without_explicit_rates(self) -> None:
        metrics = summarize_run([], input_tokens=100, output_tokens=20, latency_ms=50)

        self.assertIsNone(metrics.estimated_cost_usd)
        self.assertIsNone(metrics.guardrail_interception_rate)
        self.assertIsNone(metrics.tool_failure_rate)

    def test_failure_envelope_has_stable_metrics_and_regression_case(self) -> None:
        result = run_observability_regression()

        self.assertEqual(result["metrics"]["total_tokens"], 2_900)
        self.assertEqual(result["metrics"]["estimated_cost_usd"], 0.0034)
        self.assertEqual(result["metrics"]["retry_count"], 2)
        self.assertTrue(result["regression_case_generated"])

    def test_release_manifest_keeps_known_risks_visible(self) -> None:
        manifest = release_gate_manifest()

        self.assertEqual(manifest["gate_status"], "passed")
        self.assertIn("fixed_attack_corpus_is_not_exhaustive", manifest["known_risks"])
        self.assertIn("automatic_deployment_after_failed_gate", manifest["out_of_scope"])


if __name__ == "__main__":
    unittest.main()
