"""MCP adapter for the same domain services used by the ShopAssist HTTP API."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import services

mcp = FastMCP("ShopAssistMCP")


@mcp.tool()
def get_customer_by_email(email: str) -> dict:
    """Find a customer profile by email before accessing account or order data."""
    return services.get_customer_by_email(email)


@mcp.tool()
def lookup_order_by_id(order_id: str, customer_id: str) -> dict:
    """Retrieve an order only when you have a verified customer ID that owns it."""
    return services.lookup_order_by_id(order_id, customer_id)


@mcp.tool()
def check_refund_eligibility(order_id: str, customer_id: str) -> dict:
    """Apply the authoritative delivered-and-within-30-days refund policy."""
    return services.check_refund_eligibility(order_id, customer_id)


@mcp.tool()
def process_refund(order_id: str, customer_id: str, reason: str, amount: float | None = None) -> dict:
    """Submit a refund after customer verification and eligibility checks."""
    return services.process_refund(order_id, customer_id, reason, amount)


@mcp.tool()
def create_human_escalation(customer_id: str, reason: str, summary: str, order_id: str | None = None) -> dict:
    """Open a specialist ticket for a verified customer and optional verified order."""
    return services.create_human_escalation(customer_id, reason, summary, order_id)


if __name__ == "__main__":
    mcp.run()
