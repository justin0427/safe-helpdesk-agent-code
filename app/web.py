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
from app.execution_budget import DEFAULT_RUN_TIME_BUDGET_SECONDS, MODEL_TIMEOUT_SECONDS
from app.demo_scenarios import (
    run_backend_authorization_demo,
    run_circuit_open_demo,
    run_context_compaction_demo,
    run_context_boundary_demo,
    run_document_authorization_demo,
    run_external_share_blocked_demo,
    run_rag_injection_demo,
    run_ticket_before_sop_demo,
    run_sop_timeout_fallback_demo,
    run_time_budget_demo,
    run_tool_catalog_scope_demo,
    run_tool_output_sanitization_demo,
    run_nemo_input_rails_demo,
    run_memory_boundary_demo,
    run_memory_governance_demo,
    run_memory_poisoning_demo,
    run_token_cost_budget_demo,
    run_runaway_loop_demo,
    run_sop_first_demo,
)
from app.retry_control import CircuitBreaker
from app.nemo_input_preview import inspect_input_preview
from app.model_settings import ModelSettings
from app.live_experiments import (
    LiveExperimentRunner,
    OpenAIExperimentModel,
    experiment_catalog,
)
from app.run_trace import AgentRunResult, RunTrace


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Safe Helpdesk Agent")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
SOP_CIRCUIT_BREAKER = CircuitBreaker()


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_000)


class LiveExperimentRequest(BaseModel):
    day: int = Field(ge=11, le=22)
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
    if scenario == "tool-catalog":
        return _scenario_page(run_tool_catalog_scope_demo().as_dict())
    if scenario == "tool-output":
        return _scenario_page(run_tool_output_sanitization_demo().as_dict())
    if scenario == "nemo-input-rails":
        return _scenario_page(run_nemo_input_rails_demo().as_dict())
    if scenario == "backend-authorization":
        return _scenario_page(run_backend_authorization_demo().as_dict())
    if scenario == "memory-boundary":
        return _scenario_page(run_memory_boundary_demo().as_dict())
    if scenario == "memory-governance":
        return _scenario_page(run_memory_governance_demo().as_dict())
    if scenario == "memory-poisoning":
        return _scenario_page(run_memory_poisoning_demo().as_dict())
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/runtime")
def runtime_status() -> dict[str, str | bool | None]:
    load_dotenv()
    settings = ModelSettings.from_env()
    return {
        "live_llm_ready": settings.is_ready,
        "model_name": settings.model_name,
        "provider": settings.provider_label,
        "deterministic_tests_ready": True,
    }


@app.get("/api/experiments")
def live_experiments() -> list[dict[str, object]]:
    return experiment_catalog()


@app.post("/api/experiments/run")
def run_live_experiment(request: LiveExperimentRequest) -> dict:
    load_dotenv()
    settings = ModelSettings.from_env()
    if not settings.is_ready:
        raise HTTPException(
            status_code=503,
            detail="請先在 .env 設定模型，才能執行 Live security experiment。",
        )
    assert settings.model_name is not None
    assert settings.api_key is not None
    runner = LiveExperimentRunner(
        OpenAIExperimentModel(
            model_name=settings.model_name,
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout_seconds=_float_env("MODEL_TIMEOUT_SECONDS", MODEL_TIMEOUT_SECONDS),
        )
    )
    return runner.run(request.day, request.message).as_dict()


@app.post("/api/run")
def run_agent(request: AgentRequest) -> dict:
    load_dotenv()
    settings = ModelSettings.from_env()
    if not settings.is_ready:
        raise HTTPException(
            status_code=503,
            detail="請在 .env 設定 MODEL_NAME 與模型憑證，或先使用下方本機示範。",
        )
    input_decision = inspect_input_preview(request.message)
    if not input_decision.allowed:
        trace = RunTrace()
        trace.add(
            kind="guardrail",
            name=f"configured_input_{input_decision.category}",
            status="blocked",
            detail=input_decision.public_message,
        )
        trace.add(
            kind="model",
            name="live_llm",
            status="skipped",
            detail="輸入在主要模型呼叫前被拒絕。",
        )
        return AgentRunResult(
            response=input_decision.public_message,
            trace=trace.as_list(),
            stopped=True,
        ).as_dict()
    try:
        agent = HelpdeskAgent(
            model_name=settings.model_name,
            model_api_key=settings.api_key,
            model_base_url=settings.base_url,
            model_timeout_seconds=_float_env(
                "MODEL_TIMEOUT_SECONDS",
                MODEL_TIMEOUT_SECONDS,
            ),
            requested_by="demo.user",
            input_price_per_million_usd=_decimal_env("MODEL_INPUT_PER_MILLION_USD"),
            output_price_per_million_usd=_decimal_env("MODEL_OUTPUT_PER_MILLION_USD"),
            max_cost_usd=_decimal_env("RUN_COST_BUDGET_USD"),
            max_elapsed_seconds=_float_env(
                "RUN_TIME_BUDGET_SECONDS",
                DEFAULT_RUN_TIME_BUDGET_SECONDS,
            ),
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


@app.post("/api/demos/tool-catalog")
def tool_catalog_demo() -> dict:
    return run_tool_catalog_scope_demo().as_dict()


@app.post("/api/demos/tool-output")
def tool_output_demo() -> dict:
    return run_tool_output_sanitization_demo().as_dict()


@app.post("/api/demos/nemo-input-rails")
def nemo_input_rails_demo() -> dict:
    return run_nemo_input_rails_demo().as_dict()


@app.post("/api/demos/backend-authorization")
def backend_authorization_demo() -> dict:
    return run_backend_authorization_demo().as_dict()


@app.post("/api/demos/memory-boundary")
def memory_boundary_demo() -> dict:
    return run_memory_boundary_demo().as_dict()


@app.post("/api/demos/memory-governance")
def memory_governance_demo() -> dict:
    return run_memory_governance_demo().as_dict()


@app.post("/api/demos/memory-poisoning")
def memory_poisoning_demo() -> dict:
    return run_memory_poisoning_demo().as_dict()


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


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name} 必須是數字") from error
    if parsed <= 0:
        raise ValueError(f"{name} 必須大於 0")
    return parsed


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
    status_class = "stopped" if result["stopped"] else "success"
    status_text = "已安全停止" if result["stopped"] else "完成"
    page = page.replace(
        '<p id="run-status" class="status">Ready</p>',
        f'<p id="run-status" class="status {status_class}">{status_text}</p>',
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
