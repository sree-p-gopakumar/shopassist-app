from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import services
from .agent import AgentConfigurationError, resolve_with_agent


app = FastAPI(
    title="ShopAssist AI API",
    version="2.0.0",
    description=(
        "A customer-support API with a shared policy layer, an Anthropic tool-calling "
        "workflow, and a reusable MCP tool server."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CustomerLookup(BaseModel):
    email: str = Field(examples=["alex@example.com"])


class OrderLookup(BaseModel):
    order_id: str = Field(examples=["ORD-12345678"])
    customer_id: str = Field(examples=["CUS-1001"])


class RefundCheck(OrderLookup):
    pass


class RefundRequest(RefundCheck):
    reason: str = Field(min_length=3, examples=["Item arrived damaged"])
    amount: float | None = Field(default=None, gt=0)


class EscalationRequest(BaseModel):
    customer_id: str = Field(examples=["CUS-1001"])
    reason: str = Field(min_length=3, examples=["Policy exception requested"])
    summary: str = Field(min_length=5, examples=["Customer reports a fault after the return window."])
    order_id: str | None = Field(default=None, examples=["ORD-87654321"])


class CaseRequest(BaseModel):
    """Deterministic workflow input retained for tests and integrations that do not use an LLM."""

    email: str = Field(examples=["alex@example.com"])
    order_id: str = Field(examples=["ORD-12345678"])
    issue: str = Field(examples=["damaged item"])


class ChatRequest(BaseModel):
    """A customer message for Claude's tool-calling workflow."""

    message: str = Field(min_length=3, max_length=4000, examples=[
        "My email is alex@example.com. Order ORD-12345678 arrived damaged. Please help."
    ])


def _raise_for_tool_error(result: dict) -> None:
    """Translate a shared service error to the HTTP convention used by the existing API."""
    if not result.get("isError"):
        return
    status = {"permission": 403, "validation": 422, "business": 422}.get(result["errorCategory"], 400)
    raise HTTPException(status_code=status, detail=result["customerMessage"])


@app.get("/api/health", tags=["System"])
def health() -> dict:
    return {"status": "ok", "service": "shopassist-api", "timestamp": datetime.now(timezone.utc)}


@app.post("/api/customers/lookup", tags=["Customer verification"])
def lookup_customer(payload: CustomerLookup) -> dict:
    return services.get_customer_by_email(payload.email)


@app.post("/api/orders/lookup", tags=["Order support"])
def lookup_order(payload: OrderLookup) -> dict:
    result = services.lookup_order_by_id(payload.order_id, payload.customer_id)
    _raise_for_tool_error(result)
    if not result.get("order"):
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/refunds/eligibility", tags=["Refunds"])
def check_refund_eligibility(payload: RefundCheck) -> dict:
    result = services.check_refund_eligibility(payload.order_id, payload.customer_id)
    _raise_for_tool_error(result)
    if not result.get("order_id"):
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/refunds", status_code=201, tags=["Refunds"])
def process_refund(payload: RefundRequest) -> dict:
    result = services.process_refund(payload.order_id, payload.customer_id, payload.reason, payload.amount)
    _raise_for_tool_error(result)
    if not result.get("refund"):
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/escalations", status_code=201, tags=["Escalations"])
def create_human_escalation(payload: EscalationRequest) -> dict:
    result = services.create_human_escalation(
        payload.customer_id, payload.reason, payload.summary, payload.order_id
    )
    _raise_for_tool_error(result)
    if not result.get("escalation"):
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/api/cases/resolve", tags=["Deterministic casework"])
def resolve_case(payload: CaseRequest) -> dict:
    """The original guided workflow; it does not require an LLM API key."""
    customer_result = services.get_customer_by_email(payload.email)
    steps: list[dict] = [{"tool": "get_customer_by_email", "status": "complete"}]
    customer = customer_result.get("customer")
    if not customer:
        return {
            "outcome": "needs_customer_details",
            "message": "No matching customer account was found.",
            "steps": steps,
        }

    order_result = services.lookup_order_by_id(payload.order_id, customer["customer_id"])
    if order_result.get("isError") or not order_result.get("order"):
        return {
            "outcome": "cannot_verify_order",
            "message": order_result.get("customerMessage", order_result.get("message")),
            "steps": steps,
        }
    order = order_result["order"]
    steps.append({"tool": "lookup_order_by_id", "status": "complete", "order_id": order["order_id"]})

    policy = services.check_refund_eligibility(order["order_id"], customer["customer_id"])
    steps.append({"tool": "check_refund_eligibility", "status": "complete", "eligible": policy["eligible"]})
    issue = payload.issue.strip().lower()

    if policy["eligible"] and issue in {"damaged item", "duplicate charge", "missing item", "wrong item"}:
        refund = services.process_refund(order["order_id"], customer["customer_id"], payload.issue)["refund"]
        steps.append({"tool": "process_refund", "status": "complete", "refund_id": refund["refund_id"]})
        return {
            "outcome": "refund_submitted",
            "message": "Your refund has been submitted.",
            "customer": customer,
            "order": order,
            "refund": refund,
            "steps": steps,
        }

    escalation = services.create_human_escalation(
        customer["customer_id"], "Policy review", f"Issue: {payload.issue}. {policy['reason']}", order["order_id"]
    )["escalation"]
    steps.append({"tool": "create_human_escalation", "status": "complete", "ticket_id": escalation["ticket_id"]})
    return {
        "outcome": "escalated",
        "message": "This case needs a support specialist.",
        "customer": customer,
        "order": order,
        "escalation": escalation,
        "steps": steps,
    }


@app.post("/api/chat", tags=["AI casework"])
def chat(payload: ChatRequest) -> dict:
    """Use Claude to decide which safe ShopAssist tools to call and draft the reply."""
    try:
        return resolve_with_agent(payload.message)
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
