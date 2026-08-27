"""Local web console for the Helpdesk Agent series demo."""

from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import HelpdeskAgent
from app.demo_scenarios import run_runaway_loop_demo, run_sop_first_demo


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
    agent = HelpdeskAgent(model_name=model_name, requested_by="demo.user")
    return agent.run_detailed(request.message).as_dict()


@app.post("/api/demos/sop-first")
def sop_first_demo() -> dict:
    return run_sop_first_demo().as_dict()


@app.post("/api/demos/runaway-loop")
def runaway_loop_demo() -> dict:
    return run_runaway_loop_demo().as_dict()
