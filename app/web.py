"""Local web console for the Helpdesk Agent series demo."""

from pathlib import Path
from decimal import Decimal, InvalidOperation
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import HelpdeskAgent
from app.demo_scenarios import (
    run_sop_timeout_fallback_demo,
    run_time_budget_demo,
    run_token_cost_budget_demo,
    run_runaway_loop_demo,
    run_sop_first_demo,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Safe Helpdesk Agent")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_000)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/run")
def run_agent(request: AgentRequest) -> dict:
    load_dotenv()
    model_name = os.getenv("MODEL_NAME")
    if not os.getenv("OPENAI_API_KEY") or not model_name:
        raise HTTPException(
            status_code=503,
            detail="請在 .env 設定 OPENAI_API_KEY 和 MODEL_NAME，或先使用下方兩個本機示範。",
        )
    try:
        agent = HelpdeskAgent(
            model_name=model_name,
            requested_by="demo.user",
            input_price_per_million_usd=_decimal_env("MODEL_INPUT_PER_MILLION_USD"),
            output_price_per_million_usd=_decimal_env("MODEL_OUTPUT_PER_MILLION_USD"),
            max_cost_usd=_decimal_env("RUN_COST_BUDGET_USD"),
        )
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return agent.run_detailed(request.message).as_dict()


@app.post("/api/demos/sop-first")
def sop_first_demo() -> dict:
    return run_sop_first_demo().as_dict()


@app.post("/api/demos/runaway-loop")
def runaway_loop_demo() -> dict:
    return run_runaway_loop_demo().as_dict()


@app.post("/api/demos/sop-timeout")
def sop_timeout_demo() -> dict:
    return run_sop_timeout_fallback_demo().as_dict()


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
