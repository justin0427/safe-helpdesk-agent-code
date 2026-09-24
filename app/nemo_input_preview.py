"""No-key preview of the NeMo regex Input Rail configured for Day 18."""

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "guardrails" / "day18" / "config.yml"
)


@dataclass(frozen=True)
class InputRailDecision:
    allowed: bool
    category: str
    public_message: str


def load_input_patterns(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> tuple[re.Pattern[str], ...]:
    """Load the patterns used by NeMo's `regex check input` flow."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    input_config = config["rails"]["config"]["regex_detection"]["input"]
    flags = re.IGNORECASE if input_config.get("case_insensitive", False) else 0
    return tuple(re.compile(pattern, flags) for pattern in input_config["patterns"])


def inspect_input_preview(
    user_input: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> InputRailDecision:
    """Classify a regex match without returning the original sensitive input."""
    for pattern in load_input_patterns(config_path):
        match = pattern.search(user_input)
        if match is None:
            continue
        category = next(
            (name for name, value in match.groupdict().items() if value is not None),
            "policy",
        )
        messages = {
            "jailbreak": "輸入含有改寫系統規則的要求，已在模型呼叫前拒絕。",
            "pii": "輸入含有示範用個人資料，已在模型呼叫前拒絕。",
            "policy": "輸入超出 Helpdesk Agent 的允許範圍，已拒絕。",
        }
        return InputRailDecision(False, category, messages[category])
    return InputRailDecision(True, "allowed", "輸入未命中 Day 18 regex Input Rail。")
