from decimal import Decimal
import unittest

from langchain.messages import AIMessage

from app.execution_budget import (
    BudgetLedger,
    BudgetLimits,
    ExecutionBudgetMiddleware,
    TokenPrice,
)


class ExecutionBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pricing = TokenPrice(
            input_per_million_usd=Decimal("1"),
            output_per_million_usd=Decimal("2"),
        )

    def test_tracks_tokens_and_a_deployment_provided_cost_estimate(self) -> None:
        ledger = BudgetLedger(limits=BudgetLimits(), pricing=self.pricing)

        ledger.record_model_usage(input_tokens=800, output_tokens=300)

        self.assertEqual(ledger.total_tokens, 1_100)
        self.assertEqual(ledger.estimated_cost_usd, Decimal("0.0014"))

    def test_identifies_the_time_budget_before_other_limits(self) -> None:
        ledger = BudgetLedger(limits=BudgetLimits(), pricing=self.pricing)

        self.assertEqual(ledger.exceeded_limit(elapsed_seconds=46), "time_budget")

    def test_identifies_the_cost_budget_after_usage_is_recorded(self) -> None:
        ledger = BudgetLedger(
            limits=BudgetLimits(max_estimated_cost_usd=Decimal("0.003")),
            pricing=self.pricing,
        )
        ledger.record_model_usage(input_tokens=1_500, output_tokens=1_000)

        self.assertEqual(ledger.exceeded_limit(elapsed_seconds=10), "cost_budget")

    def test_middleware_ends_before_another_model_call_after_token_limit(self) -> None:
        middleware = ExecutionBudgetMiddleware(
            limits=BudgetLimits(max_total_tokens=1_000),
            clock=lambda: 10.0,
        )
        message = AIMessage(
            content="done",
            usage_metadata={"input_tokens": 800, "output_tokens": 300, "total_tokens": 1_100},
        )

        update = middleware.before_model(
            {"messages": [message], "budget_started_at": 0.0},
            runtime=None,
        )

        self.assertEqual(update["jump_to"], "end")
        self.assertIn("Token", update["messages"][0].content)
