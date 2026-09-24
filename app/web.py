"""Local web console for the Helpdesk Agent series demo."""

from pathlib import Path
from decimal import Decimal, InvalidOperation
from html import escape
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import HelpdeskAgent
from app.demo_scenarios import (
    run_circuit_open_demo,
    run_context_compaction_demo,
    run_context_boundary_demo,
    run_document_authorization_demo,
    run_external_share_blocked_demo,
    run_rag_injection_demo,
    run_ticket_before_sop_demo,
    run_sop_timeout_fallback_demo,
    run_time_budget_demo,
    run_token_cost_budget_demo,
    run_runaway_loop_demo,
    run_sop_first_demo,
)
from app.retry_control import CircuitBreaker


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Safe Helpdesk Agent")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
SOP_CIRCUIT_BREAKER = CircuitBreaker()


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_000)


@app.get("/", include_in_schema=False, response_model=None)
def index(scenario: str | None = None) -> FileResponse | HTMLResponse:
    if scenario == "ticket-before-sop":
        return _scenario_page(run_ticket_before_sop_demo().as_dict())
    if scenario == "external-share":
        return _scenario_page(run_external_share_blocked_demo().as_dict())
    if scenario == "rag-injection":
        return _scenario_page(run_rag_injection_demo().as_dict())
    if scenario == "context-compaction":
        return _scenario_page(run_context_compaction_demo().as_dict())
    if scenario == "document-authorization":
        return _scenario_page(run_document_authorization_demo().as_dict())
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/run")
def run_agent(request: AgentRequest) -> dict:
    load_dotenv()
    model_name = os.getenv("MODEL_NAME")
    if not os.getenv("OPENAI_API_KEY") or not model_name:
        raise HTTPException(
            status_code=503,
            detail="請在 .env 設定 OPENAI_API_KEY 和 MODEL_NAME，或先使用下方本機示範。",
        )
    try:
        agent = HelpdeskAgent(
            model_name=model_name,
            requested_by="demo.user",
            input_price_per_million_usd=_decimal_env("MODEL_INPUT_PER_MILLION_USD"),
            output_price_per_million_usd=_decimal_env("MODEL_OUTPUT_PER_MILLION_USD"),
            max_cost_usd=_decimal_env("RUN_COST_BUDGET_USD"),
            sop_circuit_breaker=SOP_CIRCUIT_BREAKER,
        )
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return agent.run_detailed(request.message).as_dict()


@app.post("/api/demos/sop-first")
def sop_first_demo() -> dict:
    return run_sop_first_demo().as_dict()


@app.post("/api/demos/ticket-before-sop")
def ticket_before_sop_demo() -> dict:
    return run_ticket_before_sop_demo().as_dict()


@app.post("/api/demos/runaway-loop")
def runaway_loop_demo() -> dict:
    return run_runaway_loop_demo().as_dict()


@app.post("/api/demos/sop-timeout")
def sop_timeout_demo() -> dict:
    return run_sop_timeout_fallback_demo().as_dict()


@app.post("/api/demos/circuit-open")
def circuit_open_demo() -> dict:
    return run_circuit_open_demo().as_dict()


@app.post("/api/demos/context-boundary")
def context_boundary_demo() -> dict:
    return run_context_boundary_demo().as_dict()


@app.post("/api/demos/external-share")
def external_share_demo() -> dict:
    return run_external_share_blocked_demo().as_dict()


@app.post("/api/demos/rag-injection")
def rag_injection_demo() -> dict:
    return run_rag_injection_demo().as_dict()


@app.post("/api/demos/context-compaction")
def context_compaction_demo() -> dict:
    return run_context_compaction_demo().as_dict()


@app.post("/api/demos/document-authorization")
def document_authorization_demo() -> dict:
    return run_document_authorization_demo().as_dict()


@app.post("/api/demos/token-cost-budget")
def token_cost_budget_demo() -> dict:
    return run_token_cost_budget_demo().as_dict()


@app.post("/api/demos/time-budget")
def time_budget_demo() -> dict:
    return run_time_budget_demo().as_dict()


def _decimal_env(name: str) -> Decimal | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{name} 必須是十進位數字") from error


def _scenario_page(result: dict) -> HTMLResponse:
    """Render a deterministic scenario snapshot for documentation screenshots."""
    page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    trace_items = "".join(
        "<li><div>"
        f'<span class="trace-name">{escape(event["kind"])}: {escape(event["name"])}</span>'
        f'<span class="trace-detail">{escape(event["detail"])}</span>'
        "</div>"
        f'<span class="event-status {escape(event["status"])}">{escape(event["status"])}</span>'
        "</li>"
        for event in result["trace"]
    )
    page = page.replace(
        '<p id="run-status" class="status">Ready</p>',
        '<p id="run-status" class="status stopped">已安全停止</p>',
    )
    page = page.replace(
        '<p id="response" class="response">從左側輸入問題，或先執行其中一個安全示範。</p>',
        f'<p id="response" class="response">{escape(result["response"])}</p>',
    )
    page = page.replace(
        '<li class="empty-state">等待新的 Agent run。模型、工具與 guardrail 事件會依序出現在這裡。</li>',
        trace_items,
    )
    return HTMLResponse(page)
