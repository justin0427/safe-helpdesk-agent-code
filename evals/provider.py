"""Promptfoo provider for deterministic Helpdesk security regression cases."""

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.eval_target import run_security_case


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Run a local safety case without calling an external model."""
    case = context["vars"]["case"]
    result = run_security_case(case)
    return {"output": json.dumps(result, ensure_ascii=False)}
