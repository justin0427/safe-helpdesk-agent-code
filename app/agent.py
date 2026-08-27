"""Day 2: the smallest useful tool-calling Helpdesk Agent."""

import json
from collections.abc import Callable
from typing import Any, Optional

from openai import OpenAI

from app.tickets import MockTicketStore


SYSTEM_PROMPT = """
You are an internal IT Helpdesk Agent.

When a user reports an IT problem and asks for help, call create_ticket.
Use the tool result to tell the user the ticket number. Do not claim a ticket
was created unless the tool returned a successful result.
""".strip()

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "create_ticket",
        "description": "Create an IT support ticket when a user reports a technical problem.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "A concise problem summary, no more than 20 Chinese characters.",
                },
                "description": {
                    "type": "string",
                    "description": "The full problem reported by the user.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "The ticket priority.",
                },
            },
            "required": ["title", "description", "priority"],
            "additionalProperties": False,
        },
    }
]


class HelpdeskAgent:
    def __init__(
        self,
        *,
        model_name: str,
        requested_by: str,
        ticket_store: Optional[MockTicketStore] = None,
        client: Optional[OpenAI] = None,
    ) -> None:
        self.model_name = model_name
        self.requested_by = requested_by
        self.ticket_store = ticket_store or MockTicketStore()
        self.client = client or OpenAI()

    def run(self, user_message: str) -> str:
        response = self.client.responses.create(
            model=self.model_name,
            instructions=SYSTEM_PROMPT,
            input=user_message,
            tools=TOOLS,
        )

        tool_outputs = []
        for item in response.output:
            if item.type != "function_call":
                continue

            tool_outputs.append(self._execute_tool_call(item.name, item.call_id, item.arguments))

        if not tool_outputs:
            return response.output_text

        final_response = self.client.responses.create(
            model=self.model_name,
            previous_response_id=response.id,
            input=tool_outputs,
        )
        return final_response.output_text

    def _execute_tool_call(self, name: str, call_id: str, arguments: str) -> dict[str, str]:
        # This allow-list is intentionally explicit. Later days turn it into a policy layer.
        if name != "create_ticket":
            raise ValueError(f"Tool is not allowed: {name}")

        args = json.loads(arguments)
        result = self.ticket_store.create_ticket(
            title=args["title"],
            description=args["description"],
            priority=args["priority"],
            requested_by=self.requested_by,
        )
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(result, ensure_ascii=False),
        }
