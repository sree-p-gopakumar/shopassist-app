"""Anthropic tool-calling loop for the ShopAssist web application."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from . import services

try:  # Lets the non-LLM API and its tests run before optional LLM dependencies are installed.
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - exercised only in an incomplete installation
    Anthropic = None  # type: ignore[assignment,misc]


SYSTEM_PROMPT = """You are ShopAssist, a careful e-commerce support assistant.

Use tools to establish facts; never invent customer, order, policy, or refund details.
For an order request, first find the customer from their email, then look up the order using
the returned customer_id, then check eligibility. Never issue a refund until the eligibility
tool reports eligible=true. For a policy exception, permission problem, or unsupported issue,
create a concise human escalation after the customer is identified. Explain the outcome in
plain language, without exposing developer messages or internal tool details. Ask a focused
question if the customer has not supplied enough information.
"""

TOOLS = [
    {
        "name": "get_customer_by_email",
        "description": "Find a customer by email. Use before accessing account or order data.",
        "input_schema": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    },
    {
        "name": "lookup_order_by_id",
        "description": "Retrieve an order only after obtaining a verified customer_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "customer_id": {"type": "string"},
            },
            "required": ["order_id", "customer_id"],
        },
    },
    {
        "name": "check_refund_eligibility",
        "description": "Apply the delivery and 30-day refund policy to a verified order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "customer_id": {"type": "string"},
            },
            "required": ["order_id", "customer_id"],
        },
    },
    {
        "name": "process_refund",
        "description": "Submit a refund. Use only after check_refund_eligibility says eligible=true.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "customer_id": {"type": "string"},
                "reason": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["order_id", "customer_id", "reason"],
        },
    },
    {
        "name": "create_human_escalation",
        "description": "Create a human support ticket for exceptions after customer verification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["customer_id", "reason", "summary"],
        },
    },
]

TOOL_FUNCTIONS: dict[str, Callable[..., dict]] = {
    "get_customer_by_email": services.get_customer_by_email,
    "lookup_order_by_id": services.lookup_order_by_id,
    "check_refund_eligibility": services.check_refund_eligibility,
    "process_refund": services.process_refund,
    "create_human_escalation": services.create_human_escalation,
}


class AgentConfigurationError(RuntimeError):
    """A safe configuration error that the HTTP layer can present to an operator."""


def execute_tool(name: str, tool_input: dict[str, Any]) -> dict:
    """Dispatch an LLM tool request without allowing an exception to escape as a tool result."""
    function = TOOL_FUNCTIONS.get(name)
    if not function:
        return services.tool_error("validation", "That support action is unavailable.", f"Unknown tool: {name}")
    try:
        return function(**tool_input)
    except (TypeError, ValueError) as exc:
        return services.tool_error("validation", "Some case details need to be corrected.", str(exc))


def _trace_step(tool: str, result: dict) -> tuple[dict, dict | None]:
    """Keep the browser audit trail useful without returning internal error messages."""
    if result.get("isError"):
        return {"tool": tool, "status": "blocked", "detail": result["customerMessage"]}, None
    if result.get("refund"):
        refund = result["refund"]
        return {"tool": tool, "status": "complete", "detail": f"Refund {refund['refund_id']} submitted."}, {"refund": refund}
    if result.get("escalation"):
        ticket = result["escalation"]
        return {"tool": tool, "status": "complete", "detail": f"Ticket {ticket['ticket_id']} opened."}, {"escalation": ticket}
    if result.get("eligible") is False:
        return {"tool": tool, "status": "complete", "detail": result["reason"]}, None
    return {"tool": tool, "status": "complete", "detail": result.get("message", "Completed.")}, None


def _load_configuration() -> tuple[Any, str]:
    # The course keeps its API key in the repository root. Environment variables still win.
    root_env = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(root_env)
    if Anthropic is None:
        raise AgentConfigurationError("Install the backend dependencies to enable the LLM workflow.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AgentConfigurationError("Set ANTHROPIC_API_KEY in .env before using the AI workflow.")
    return Anthropic(), os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def resolve_with_agent(customer_message: str, max_turns: int = 8) -> dict:
    """Run Claude's tool-use loop and return a customer response plus a safe audit trace."""
    client, model = _load_configuration()
    messages: list[dict[str, Any]] = [{"role": "user", "content": customer_message}]
    steps: list[dict] = []
    action: dict[str, Any] = {}

    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=900,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = execute_tool(block.name, block.input)
            step, new_action = _trace_step(block.name, result)
            steps.append(step)
            if new_action:
                action = new_action
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                    "is_error": result.get("isError", False),
                }
            )

        if not tool_results:
            text = "".join(block.text for block in response.content if block.type == "text").strip()
            return {"message": text or "I’m ready to help with your order.", "steps": steps, **action}
        messages.append({"role": "user", "content": tool_results})

    raise AgentConfigurationError("The support workflow took too many steps. Please try again.")
