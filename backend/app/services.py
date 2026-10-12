"""Domain operations shared by the HTTP API, LLM agent, and MCP server.

The fixture dictionaries stand in for an order database, payment provider, and ticketing
system. Keeping policy and authorization here means an LLM cannot bypass them.
"""

from __future__ import annotations

from uuid import uuid4

CUSTOMERS = {
    "alex@example.com": {
        "customer_id": "CUS-1001",
        "email": "alex@example.com",
        "name": "Alex Morgan",
        "account_status": "active",
    }
}

ORDERS = {
    "ORD-12345678": {
        "order_id": "ORD-12345678",
        "customer_id": "CUS-1001",
        "status": "delivered",
        "delivered_days_ago": 12,
        "total": 89.99,
        "currency": "USD",
        "item": "AeroFit wireless headphones",
    },
    "ORD-87654321": {
        "order_id": "ORD-87654321",
        "customer_id": "CUS-1001",
        "status": "delivered",
        "delivered_days_ago": 45,
        "total": 149.99,
        "currency": "USD",
        "item": "Commuter backpack",
    },
}


def tool_error(category: str, customer_message: str, developer_message: str) -> dict:
    """Return the consistent safe error shape used by every ShopAssist tool."""
    return {
        "isError": True,
        "errorCategory": category,
        "isRetryable": False,
        "customerMessage": customer_message,
        "developerMessage": developer_message,
    }


def get_customer_by_email(email: str) -> dict:
    """Find a customer profile from an email address."""
    customer = CUSTOMERS.get(email.strip().lower())
    if not customer:
        return {
            "isError": False,
            "customer": None,
            "message": "No customer found for this email address.",
        }
    return {"isError": False, "customer": customer.copy()}


def lookup_order_by_id(order_id: str, customer_id: str) -> dict:
    """Return an order only when it belongs to the verified customer."""
    normalized_order_id = order_id.strip().upper()
    if not normalized_order_id.startswith("ORD-"):
        return tool_error(
            "validation",
            "The order ID does not look valid. Please check the order number and try again.",
            "Order ID must start with ORD-.",
        )

    order = ORDERS.get(normalized_order_id)
    if not order:
        return {
            "isError": False,
            "order": None,
            "message": "No order found with this order ID.",
        }
    if order["customer_id"] != customer_id:
        return tool_error(
            "permission",
            "I can’t access this order with the current account information.",
            "Order does not belong to the verified customer.",
        )
    return {"isError": False, "order": order.copy()}


def check_refund_eligibility(order_id: str, customer_id: str) -> dict:
    """Apply the policy to an authoritative order record, not model-provided facts."""
    order_result = lookup_order_by_id(order_id, customer_id)
    if order_result["isError"] or not order_result.get("order"):
        return order_result

    order = order_result["order"]
    if order["status"] != "delivered":
        return {
            "isError": False,
            "eligible": False,
            "order_id": order["order_id"],
            "reason": "This order has not been delivered, so an automatic refund is unavailable.",
            "next_action": "create_human_escalation",
        }
    if order["delivered_days_ago"] > 30:
        return {
            "isError": False,
            "eligible": False,
            "order_id": order["order_id"],
            "reason": "This order is outside the standard 30-day return window.",
            "next_action": "create_human_escalation",
        }
    return {
        "isError": False,
        "eligible": True,
        "order_id": order["order_id"],
        "reason": "Order is within the 30-day return window.",
        "next_action": "process_refund",
    }


def process_refund(
    order_id: str, customer_id: str, reason: str, amount: float | None = None
) -> dict:
    """Submit a refund only after authorization and policy checks succeed."""
    order_result = lookup_order_by_id(order_id, customer_id)
    if order_result["isError"] or not order_result.get("order"):
        return order_result

    order = order_result["order"]
    policy = check_refund_eligibility(order_id, customer_id)
    if not policy.get("eligible"):
        return tool_error("business", policy.get("reason", "Refund is unavailable."), "Refund policy denied action.")

    refund_amount = order["total"] if amount is None else amount
    if refund_amount <= 0:
        return tool_error(
            "validation",
            "The refund amount must be greater than zero.",
            "Refund amount was less than or equal to zero.",
        )
    if refund_amount > order["total"]:
        return tool_error(
            "business",
            "The refund amount cannot exceed the order total.",
            "Requested amount exceeds the authoritative order total.",
        )

    return {
        "isError": False,
        "refund": {
            "refund_id": f"REF-{uuid4().hex[:8].upper()}",
            "order_id": order["order_id"],
            "amount": refund_amount,
            "currency": order["currency"],
            "status": "submitted",
            "reason": reason,
        },
    }


def create_human_escalation(
    customer_id: str, reason: str, summary: str, order_id: str | None = None
) -> dict:
    """Open a human-support ticket after verifying any supplied order."""
    if order_id:
        order_result = lookup_order_by_id(order_id, customer_id)
        if order_result["isError"] or not order_result.get("order"):
            return order_result
        order_id = order_result["order"]["order_id"]

    return {
        "isError": False,
        "escalation": {
            "ticket_id": f"TCK-{uuid4().hex[:6].upper()}",
            "customer_id": customer_id,
            "order_id": order_id,
            "reason": reason,
            "summary": summary,
            "status": "open",
            "queue": "retail-support",
        },
    }
