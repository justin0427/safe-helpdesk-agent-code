"""Validate and minimize untrusted tool results before model exposure."""

from collections.abc import Mapping
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class OutputPolicyEvent:
    rule: str
    status: str
    detail: str


@dataclass(frozen=True)
class SanitizedToolOutput:
    model_visible: dict[str, str]
    events: tuple[OutputPolicyEvent, ...]


_SUCCESS_FIELDS = {
    "search_it_sop": frozenset({"status", "article_id", "title", "content"}),
}

_INSTRUCTION_PATTERNS = (
    re.compile(r"ignore.{0,32}(previous|prior|all).{0,20}(instructions?|rules?)", re.IGNORECASE),
    re.compile(r"忽略.{0,16}(前面|先前|所有).{0,16}(指令|規則)"),
    re.compile(r"(call|invoke|執行|呼叫).{0,24}(tool|工具|share_sop_excerpt)", re.IGNORECASE),
)

_SAFE_TOOL_ERRORS = {
    "search_it_sop": {
        "status": "unavailable",
        "error_code": "SOP_UNAVAILABLE",
        "message": "SOP 暫時無法查詢，請稍後再試。",
    }
}

_INVALID_OUTPUT = {
    "status": "invalid",
    "error_code": "INVALID_TOOL_OUTPUT",
    "message": "工具回傳格式不符合預期，已停止使用這份結果。",
}


def sanitize_tool_output(
    tool_name: str,
    raw_result: object,
) -> SanitizedToolOutput:
    """Fail closed for unknown shapes and replace raw errors with safe messages."""
    if not isinstance(raw_result, Mapping):
        return SanitizedToolOutput(
            model_visible=dict(_INVALID_OUTPUT),
            events=(
                OutputPolicyEvent("output_validation", "blocked", "工具結果不是可驗證的物件。"),
            ),
        )

    raw_values = " ".join(
        value for value in raw_result.values() if isinstance(value, str)
    )
    has_instruction = any(pattern.search(raw_values) for pattern in _INSTRUCTION_PATTERNS)

    if raw_result.get("status") == "error":
        expected_error_fields = frozenset({"status", "error_code", "message"})
        events: list[OutputPolicyEvent] = []
        if frozenset(raw_result) != expected_error_fields:
            events.append(
                OutputPolicyEvent(
                    "output_validation",
                    "filtered",
                    "錯誤結果含有未定義欄位，沒有轉交給模型。",
                )
            )
        else:
            events.append(
                OutputPolicyEvent("output_validation", "accepted", "錯誤結果欄位符合 schema。")
            )
        if has_instruction:
            events.append(
                OutputPolicyEvent(
                    "tool_result_instruction",
                    "quarantined",
                    "錯誤文字含有指令式內容，沒有轉交給模型。",
                )
            )
        events.append(
            OutputPolicyEvent(
                "error_detail_minimization",
                "applied",
                "原始訊息與除錯細節已換成固定的公開錯誤代碼。",
            )
        )
        safe_error = _SAFE_TOOL_ERRORS.get(tool_name, _INVALID_OUTPUT)
        return SanitizedToolOutput(dict(safe_error), tuple(events))

    expected_fields = _SUCCESS_FIELDS.get(tool_name)
    if expected_fields is None or frozenset(raw_result) != expected_fields:
        return SanitizedToolOutput(
            model_visible=dict(_INVALID_OUTPUT),
            events=(
                OutputPolicyEvent(
                    "output_validation",
                    "blocked",
                    "成功結果的欄位和預先定義的 schema 不一致。",
                ),
            ),
        )

    if raw_result.get("status") != "ok" or not all(
        isinstance(raw_result[field], str) and raw_result[field].strip()
        for field in expected_fields
    ):
        return SanitizedToolOutput(
            model_visible=dict(_INVALID_OUTPUT),
            events=(
                OutputPolicyEvent(
                    "output_validation",
                    "blocked",
                    "成功結果含有錯誤型別或空白欄位。",
                ),
            ),
        )

    if has_instruction:
        return SanitizedToolOutput(
            model_visible=dict(_INVALID_OUTPUT),
            events=(
                OutputPolicyEvent(
                    "tool_result_instruction",
                    "quarantined",
                    "工具結果含有指令式內容，沒有轉交給模型。",
                ),
            ),
        )

    return SanitizedToolOutput(
        model_visible={field: str(raw_result[field]) for field in sorted(expected_fields)},
        events=(
            OutputPolicyEvent("output_validation", "accepted", "工具結果符合輸出 schema。"),
        ),
    )
