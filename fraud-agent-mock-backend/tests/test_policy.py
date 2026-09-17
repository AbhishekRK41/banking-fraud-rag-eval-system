import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.policy import evaluate, redeem_token
from app.schemas import Evidence, RiskContext

BASE_RISK = RiskContext(
    event_type="anomalous_payment",
    risk_score=0.8,
    customer_id="cust_x",
)


def test_unverified_caller_gets_no_action_and_escalates():
    decision = evaluate(verified=False, risk_context=BASE_RISK, evidence=Evidence(), customer_id="cust_x")
    assert decision.authorized_actions == []
    assert decision.requires_human_escalation is True
    assert decision.action_token is None


def test_otp_disclosed_freezes_and_escalates():
    ev = Evidence(otp_disclosed=True)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    assert decision.authorized_actions == ["freeze_card"]
    assert decision.requires_human_escalation is True
    assert decision.action_token is not None


def test_active_impersonation_freezes_and_escalates():
    ev = Evidence(active_impersonation_claimed=True)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    assert decision.authorized_actions == ["freeze_card"]
    assert decision.requires_human_escalation is True


def test_card_not_in_possession_freezes_and_escalates():
    ev = Evidence(card_possession_confirmed=False)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    assert decision.authorized_actions == ["freeze_card"]
    assert decision.requires_human_escalation is True


def test_recognized_transaction_takes_no_action():
    ev = Evidence(transaction_recognized=True)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    assert decision.authorized_actions == []
    assert decision.requires_human_escalation is False


def test_unrecognized_transaction_alone_freezes_without_escalation():
    ev = Evidence(transaction_recognized=False)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    assert decision.authorized_actions == ["freeze_card"]
    assert decision.requires_human_escalation is False
    assert decision.action_token is not None


def test_incomplete_evidence_fails_closed():
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=Evidence(), customer_id="cust_x")
    assert decision.authorized_actions == []
    assert decision.requires_human_escalation is True


def test_otp_disclosure_takes_priority_over_recognized_transaction():
    # Even if the customer recognizes the transaction, a disclosed OTP
    # means broader compromise — freeze + escalate must still win.
    ev = Evidence(transaction_recognized=True, otp_disclosed=True)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    assert decision.authorized_actions == ["freeze_card"]
    assert decision.requires_human_escalation is True


def test_action_token_is_single_use():
    ev = Evidence(transaction_recognized=False)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    token = decision.action_token
    assert redeem_token("cust_x", token, "freeze_card") is True
    # second redemption of the same token must fail
    assert redeem_token("cust_x", token, "freeze_card") is False


def test_action_token_rejected_for_wrong_customer():
    ev = Evidence(transaction_recognized=False)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    token = decision.action_token
    assert redeem_token("someone_else", token, "freeze_card") is False


def test_action_token_rejected_for_wrong_action():
    ev = Evidence(transaction_recognized=False)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_x")
    token = decision.action_token
    assert redeem_token("cust_x", token, "revoke_sessions") is False


def test_action_token_rejected_after_expiry():
    import time
    import app.policy as policy_mod

    ev = Evidence(transaction_recognized=False)
    decision = evaluate(verified=True, risk_context=BASE_RISK, evidence=ev, customer_id="cust_y")
    token = decision.action_token
    # force-expire it rather than sleeping TOKEN_TTL_SECONDS in a test
    customer_id, action, _ = policy_mod._ISSUED_TOKENS[token]
    policy_mod._ISSUED_TOKENS[token] = (customer_id, action, time.time() - 1)
    assert redeem_token("cust_y", token, "freeze_card") is False
