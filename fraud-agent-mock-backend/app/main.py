from __future__ import annotations

import secrets

from fastapi import FastAPI, HTTPException

from app import policy
from app.schemas import (
    ActionRequest,
    ActionResult,
    PolicyDecision,
    PolicyRequest,
    RiskContext,
    VerifyRequest,
    VerifyResponse,
)

app = FastAPI(
    title="Fraud Agent Mock Backend",
    description=(
        "Mocked verification, policy, and action-execution services for the "
        "Real-Time Fraud Intervention voice agent. The agent (or its ElevenLabs "
        "Tools) calls these; the model never executes an action directly — only "
        "the policy service authorizes one, and only a matching token unlocks it."
    ),
    version="1.0.0",
)

# In-memory record of "verified" customers for this mock, keyed by
# verification_id -> customer_id. A real system would hand back a signed
# assertion from the bank's own out-of-band channel; here it's simulated.
_VERIFICATIONS: dict[str, str] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    """Mocks the bank's approved out-of-band challenge flow.
    Deliberately takes an opaque challenge_response, not a PIN, password,
    or OTP — those never pass through this system at all, mirroring the
    canvas's guardrail. For this mock, any non-empty response verifies,
    UNLESS it is literally the string 'fail', which simulates a failed
    challenge for testing the escalation path.
    """
    if not payload.challenge_response or payload.challenge_response.lower() == "fail":
        return VerifyResponse(verified=False, verification_id="")

    verification_id = secrets.token_urlsafe(16)
    _VERIFICATIONS[verification_id] = payload.customer_id
    return VerifyResponse(verified=True, verification_id=verification_id)


@app.post("/policy/evaluate", response_model=PolicyDecision)
def policy_evaluate(payload: PolicyRequest) -> PolicyDecision:
    verified_customer_id = _VERIFICATIONS.get(payload.verification_id)
    verified = verified_customer_id == payload.customer_id
    return policy.evaluate(
        verified=verified,
        risk_context=payload.risk_context,
        evidence=payload.evidence,
        customer_id=payload.customer_id,
    )


@app.post("/actions/freeze_card", response_model=ActionResult)
def freeze_card(payload: ActionRequest) -> ActionResult:
    ok = policy.redeem_token(payload.customer_id, payload.action_token, "freeze_card")
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid, expired, or already-used action token.")
    return ActionResult(
        action="freeze_card",
        executed=True,
        detail=f"Card temporarily frozen for customer {payload.customer_id}.",
    )


@app.get("/mock/sample-risk-events")
def sample_risk_events() -> list[RiskContext]:
    """Example risk-context payloads matching the four demo scenarios in
    the canvas (Box L): a clean happy path, an OTP-disclosure escalation,
    an active-impersonation escalation, and a false alarm."""
    return [
        RiskContext(
            event_type="anomalous_payment",
            transaction_id="txn_001",
            amount=4800,
            merchant_or_payee="Unknown Merchant LLC",
            channel="ecommerce",
            device_change_detected=True,
            geo_anomaly_detected=True,
            risk_score=0.87,
            reason_codes=["new_device", "geo_mismatch", "high_amount"],
            customer_id="cust_001",
            preferred_language="en",
        ),
        RiskContext(
            event_type="suspicious_login",
            transaction_id="txn_002",
            amount=2300,
            merchant_or_payee="Retail Store",
            channel="pos",
            device_change_detected=False,
            geo_anomaly_detected=False,
            risk_score=0.62,
            reason_codes=["velocity_check"],
            customer_id="cust_002",
            preferred_language="ar",
        ),
    ]
