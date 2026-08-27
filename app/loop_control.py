"""Bound the number of LangGraph super-steps per Agent invocation."""

DEFAULT_RECURSION_LIMIT = 6
MINIMUM_RECURSION_LIMIT = 3


def build_agent_config(recursion_limit: int = DEFAULT_RECURSION_LIMIT) -> dict[str, int]:
    if recursion_limit < MINIMUM_RECURSION_LIMIT:
        raise ValueError(f"recursion_limit must be at least {MINIMUM_RECURSION_LIMIT}")
    return {"recursion_limit": recursion_limit}


def loop_limit_message() -> str:
    return (
        "系統已停止本次處理，因為 Agent 超過允許的執行步數。"
        "結果可能不完整，請縮小問題後重試。"
    )
