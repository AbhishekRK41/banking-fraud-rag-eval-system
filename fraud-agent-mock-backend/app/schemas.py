"""Request/response models for the three services the fraud agent talks to:
verification, policy evaluation, and action execution.

These schemas ARE the trust boundary described in the canvas (Box I):
the agent can only ever send what these models allow, and can only ever
receive what the policy service decides to return.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RiskContext(BaseModel):
    """What the bank's fraud engine would send when a signal fires.
    Richer than a bare customer ID + risk type — this is the payload
    Box F/H describe the fraud engine providing."""
    event_type: str = Field(..., examples=["suspicious_login", "anomalous_payment", "stolen_card_suspected"])
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "AED"
    merchant_or_payee: Optional[str] = None
    channel: Optional[str] = Field(None, examples=["pos", "ecommerce", "atm", "online_banking"])
    device_change_detected: bool = False
    geo_anomaly_detected: bool = False
    risk_score: float = Field(..., ge=0, le=1)
    reason_codes: list[str] = []
    customer_id: str
    preferred_language: Literal["en", "ar"] = "en"


class VerifyRequest(BaseModel):
    customer_id: str
    challenge_response: str  # opaque — represents whatever the bank's own
    # out-of-band channel returns; this service never sees or accepts a
    # PIN, password, or OTP itself, only a verification RESULT token from
    # the bank's own approved channel.


class VerifyResponse(BaseModel):
    verified: bool
    verification_id: str


class Evidence(BaseModel):
    """What the agent has established by the end of the conversation.
    This is the structured output Box F step 3 describes — the
    conversation compressed into fields the policy layer can reason
    about deterministically."""
    transaction_recognized: Optional[bool] = None
    otp_disclosed: bool = False
    active_impersonation_claimed: bool = False
    card_possession_confirmed: Optional[bool] = None


class PolicyRequest(BaseModel):
    customer_id: str
    verification_id: str
    risk_context: RiskContext
    evidence: Evidence


class PolicyDecision(BaseModel):
    authorized_actions: list[str]
    requires_human_escalation: bool
    escalation_reason: Optional[str] = None
    action_token: Optional[str] = None  # only present if an action was authorized;
    # /actions/{name} will not execute without a valid, matching token.


class ActionRequest(BaseModel):
    customer_id: str
    action_token: str


class ActionResult(BaseModel):
    action: str
    executed: bool
    detail: str
