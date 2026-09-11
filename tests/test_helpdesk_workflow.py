import unittest

from app.helpdesk_workflow import HelpdeskWorkflow
from app.knowledge_base import MockKnowledgeBase
from app.retry_control import CircuitBreaker, RetryPolicy, ToolTimeoutError
from app.run_trace import RunTrace
from app.tickets import MockTicketStore


class HelpdeskWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = HelpdeskWorkflow(
            requested_by="demo.user",
            ticket_store=MockTicketStore(),
            knowledge_base=MockKnowledgeBase(),
            trace=RunTrace(),
        )

    def test_blocks_a_ticket_until_the_sop_was_checked(self) -> None:
        result = self.workflow.create_ticket(
            title="VPN 無法連線",
            description="請協助處理。",
            priority="high",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(self.workflow.ticket_store.tickets, [])
        self.assertEqual(self.workflow.trace.as_list()[-1]["name"], "sop_first")

    def test_creates_a_ticket_after_searching_the_sop(self) -> None:
        self.workflow.search_it_sop("VPN 連不上")
        ticket = self.workflow.create_ticket(
            title="VPN 無法連線",
            description="已重新啟動用戶端仍無法連線。",
            priority="high",
        )

        self.assertEqual(ticket["status"], "created")
        self.assertEqual(len(self.workflow.ticket_store.tickets), 1)
        self.assertEqual(
            [event["name"] for event in self.workflow.trace.as_list()],
            ["search_it_sop", "create_ticket"],
        )

    def test_uses_a_safe_fallback_when_sop_queries_time_out(self) -> None:
        class TimedOutKnowledgeBase:
            def search(self, query: str) -> list[dict[str, str]]:
                raise ToolTimeoutError("timeout")

        workflow = HelpdeskWorkflow(
            requested_by="demo.user",
            ticket_store=MockTicketStore(),
            knowledge_base=TimedOutKnowledgeBase(),  # type: ignore[arg-type]
            trace=RunTrace(),
            retry_policy=RetryPolicy(max_attempts=2),
            retry_wait=lambda _: None,
        )

        result = workflow.search_it_sop("VPN 連不上")
        ticket = workflow.create_ticket(
            title="VPN 無法連線",
            description="請協助處理。",
            priority="high",
        )

        self.assertEqual(result[0]["article_id"], "FALLBACK-SOP")
        self.assertEqual(ticket["status"], "blocked")
        self.assertEqual(workflow.trace.as_list()[-2]["name"], "sop_unavailable")
        self.assertEqual(workflow.ticket_store.tickets, [])

    def test_circuit_breaker_blocks_a_later_sop_request_without_calling_the_source(self) -> None:
        class TimedOutKnowledgeBase:
            calls = 0

            def search(self, query: str) -> list[dict[str, str]]:
                self.calls += 1
                raise ToolTimeoutError("timeout")

        source = TimedOutKnowledgeBase()
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30)
        trace = RunTrace()

        first = HelpdeskWorkflow(
            requested_by="demo.user",
            ticket_store=MockTicketStore(),
            knowledge_base=source,  # type: ignore[arg-type]
            trace=trace,
            retry_policy=RetryPolicy(max_attempts=1),
            retry_wait=lambda _: None,
            sop_circuit_breaker=circuit_breaker,
        )
        second = HelpdeskWorkflow(
            requested_by="demo.user",
            ticket_store=MockTicketStore(),
            knowledge_base=source,  # type: ignore[arg-type]
            trace=trace,
            retry_policy=RetryPolicy(max_attempts=1),
            retry_wait=lambda _: None,
            sop_circuit_breaker=circuit_breaker,
        )

        first.search_it_sop("VPN 連不上")
        result = second.search_it_sop("VPN 連不上")

        self.assertEqual(result[0]["article_id"], "FALLBACK-SOP")
        self.assertEqual(source.calls, 1)
        self.assertEqual(trace.as_list()[-3]["status"], "blocked")

    def test_deduplicates_an_identical_ticket_within_one_run(self) -> None:
        self.workflow.search_it_sop("VPN 連不上")
        first = self.workflow.create_ticket(
            title="VPN 無法連線",
            description="請協助處理。",
            priority="high",
        )
        second = self.workflow.create_ticket(
            title="VPN 無法連線",
            description="請協助處理。",
            priority="high",
        )

        self.assertEqual(first["ticket_id"], second["ticket_id"])
        self.assertEqual(second["idempotency_status"], "replayed")
        self.assertEqual(len(self.workflow.ticket_store.tickets), 1)
