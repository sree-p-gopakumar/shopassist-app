from fastapi.testclient import TestClient

from app.agent import execute_tool
from app.main import app


client = TestClient(app)


def test_damaged_item_within_policy_submits_refund():
    response = client.post("/api/cases/resolve", json={
        "email": "alex@example.com", "order_id": "ORD-12345678", "issue": "damaged item"
    })
    assert response.status_code == 200
    assert response.json()["outcome"] == "refund_submitted"


def test_out_of_policy_case_is_escalated():
    response = client.post("/api/cases/resolve", json={
        "email": "alex@example.com", "order_id": "ORD-87654321", "issue": "damaged item"
    })
    assert response.status_code == 200
    assert response.json()["outcome"] == "escalated"


def test_order_requires_verified_owner():
    response = client.post("/api/orders/lookup", json={"order_id": "ORD-12345678", "customer_id": "CUS-NOT-ALEX"})
    assert response.status_code == 403


def test_agent_tools_use_the_same_policy_layer():
    result = execute_tool("check_refund_eligibility", {
        "order_id": "ORD-87654321", "customer_id": "CUS-1001"
    })
    assert result == {
        "isError": False,
        "eligible": False,
        "order_id": "ORD-87654321",
        "reason": "This order is outside the standard 30-day return window.",
        "next_action": "create_human_escalation",
    }
