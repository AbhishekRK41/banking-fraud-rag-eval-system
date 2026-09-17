"""Deterministic policy: evidence in, authorized action(s) out.

This is the piece Box I's guardrail table refers to as "a separate
policy layer" — it is a plain rule table, not a model call. The agent
(or, in testing, anyone) can send any evidence they like; this function
is the only thing that decides what's authorized, and it never changes
its answer based on how something is phrased, only on the evidence
fields themselves.

Rules (in priority order):
1. Not verified                      -> no action, escalate (can't act on an unverified caller)
2. OTP disclosed                     -> freeze_card + escalate (reversible action still taken
                                         immediately, but broader compromise needs a human)
3. Active impersonation claimed      -> freeze_card + escalate (same reasoning)
4. Card not in customer's possession -> freeze_card + escalate (possible physical theft)
5. Transaction recognized            -> no action (false alarm, nothing to contain)
6. Transaction not recognized,
   no other risk evidence            -> freeze_card only (the single safe, reversible,
                                         non-escalation case)
7. Anything else / incomplete evidence -> no action, escalate (fail closed, not open)
"""
from __future__ import annotations

import secrets
import time

from .schemas import Evidence, PolicyDecision, RiskContext

# In-memory token store: token -> (customer_id, action, expires_at).
# A real system would use a signed, short-lived token; this is a mock,
# but the *shape* of the enforcement (action requires a token minted by
# THIS function, checked by the action endpoint) is the real point.
_ISSUED_TOKENS: dict[str, tuple[str, str, float]] = {}
TOKEN_TTL_SECONDS = 120


def _issue_token(customer_id: str, action: str) -> str:
    token = secrets.token_urlsafe(24)
    _ISSUED_TOKENS[token] = (customer_id, action, time.time() + TOKEN_TTL_SECONDS)
    return token


def redeem_token(customer_id: str, token: str, expected_action: str) -> bool:
    """Called by the action endpoint. Consumes the token — single use."""
    entry = _ISSUED_TOKENS.pop(token, None)
    if entry is None:
        return False
    stored_customer_id, stored_action, expires_at = entry
    if stored_customer_id != customer_id:
        return False
    if stored_action != expected_action:
        return False
    if time.time() > expires_at:
        return False
    return True


def evaluate(verified: bool, risk_context: RiskContext, evidence: Evidence, customer_id: str) -> PolicyDecision:
    if not verified:
        return PolicyDecision(
            authorized_actions=[],
            requires_human_escalation=True,
            escalation_reason="Identity not verified through the bank's approved channel.",
        )

    if evidence.otp_disclosed:
        token = _issue_token(customer_id, "freeze_card")
        return PolicyDecision(
            authorized_actions=["freeze_card"],
            requires_human_escalation=True,
            escalation_reason="OTP disclosed — credential exposure implies compromise beyond this transaction.",
            action_token=token,
        )

    if evidence.active_impersonation_claimed:
        token = _issue_token(customer_id, "freeze_card")
        return PolicyDecision(
            authorized_actions=["freeze_card"],
            requires_human_escalation=True,
            escalation_reason="Customer reports active contact from someone claiming to be the bank.",
            action_token=token,
        )

    if evidence.card_possession_confirmed is False:
        token = _issue_token(customer_id, "freeze_card")
        return PolicyDecision(
            authorized_actions=["freeze_card"],
            requires_human_escalation=True,
            escalation_reason="Card not confirmed in customer's possession — possible physical theft.",
            action_token=token,
        )

    if evidence.transaction_recognized is True:
        return PolicyDecision(
            authorized_actions=[],
            requires_human_escalation=False,
            escalation_reason=None,
        )

    if evidence.transaction_recognized is False:
        token = _issue_token(customer_id, "freeze_card")
        return PolicyDecision(
            authorized_actions=["freeze_card"],
            requires_human_escalation=False,
            escalation_reason=None,
            action_token=token,
        )

    # Incomplete evidence (transaction_recognized is None and nothing else
    # triggered) — fail closed, don't guess.
    return PolicyDecision(
        authorized_actions=[],
        requires_human_escalation=True,
        escalation_reason="Evidence incomplete — could not determine transaction recognition.",
    )
