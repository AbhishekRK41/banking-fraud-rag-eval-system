import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_full_happy_path_verify_evaluate_act():
    """The scenario Box L calls the 'clean happy path' demo: verified
    customer, unrecognized transaction, no other risk signals -> freeze,
    no escalation, and the token actually unlocks the action."""
    verify_resp = client.post("/verify", json={"customer_id": "cust_1", "challenge_response": "ok"})
    assert verify_resp.status_code == 200
    verification_id = verify_resp.json()["verification_id"]
    assert verify_resp.json()["verified"] is True

    policy_resp = client.post("/policy/evaluate", json={
        "customer_id": "cust_1",
        "verification_id": verification_id,
        "risk_context": {
            "event_type": "anomalous_payment",
            "risk_score": 0.8,
            "customer_id": "cust_1",
        },
        "evidence": {"transaction_recognized": False},
    })
    assert policy_resp.status_code == 200
    decision = policy_resp.json()
    assert decision["authorized_actions"] == ["freeze_card"]
    assert decision["requires_human_escalation"] is False
    token = decision["action_token"]
    assert token

    action_resp = client.post("/actions/freeze_card", json={"customer_id": "cust_1", "action_token": token})
    assert action_resp.status_code == 200
    assert action_resp.json()["executed"] is True


def test_failed_verification_blocks_the_whole_flow():
    verify_resp = client.post("/verify", json={"customer_id": "cust_2", "challenge_response": "fail"})
    assert verify_resp.json()["verified"] is False

    policy_resp = client.post("/policy/evaluate", json={
        "customer_id": "cust_2",
        "verification_id": verify_resp.json()["verification_id"],
        "risk_context": {"event_type": "anomalous_payment", "risk_score": 0.5, "customer_id": "cust_2"},
        "evidence": {"transaction_recognized": False},
    })
    decision = policy_resp.json()
    assert decision["authorized_actions"] == []
    assert decision["requires_human_escalation"] is True
    assert decision["action_token"] is None


def test_action_endpoint_rejects_forged_token():
    resp = client.post("/actions/freeze_card", json={"customer_id": "cust_3", "action_token": "not-a-real-token"})
    assert resp.status_code == 403


def test_action_endpoint_rejects_reused_token():
    verify_resp = client.post("/verify", json={"customer_id": "cust_4", "challenge_response": "ok"})
    verification_id = verify_resp.json()["verification_id"]

    policy_resp = client.post("/policy/evaluate", json={
        "customer_id": "cust_4",
        "verification_id": verification_id,
        "risk_context": {"event_type": "anomalous_payment", "risk_score": 0.9, "customer_id": "cust_4"},
        "evidence": {"otp_disclosed": True},
    })
    token = policy_resp.json()["action_token"]

    first = client.post("/actions/freeze_card", json={"customer_id": "cust_4", "action_token": token})
    assert first.status_code == 200

    second = client.post("/actions/freeze_card", json={"customer_id": "cust_4", "action_token": token})
    assert second.status_code == 403


def test_sample_risk_events_endpoint_returns_data():
    resp = client.get("/mock/sample-risk-events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 2
    assert all("customer_id" in e for e in events)
