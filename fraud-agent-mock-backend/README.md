# Fraud Agent Mock Backend

Mocked verification, policy-evaluation, and action-execution services for the ElevenLabs Real-Time Fraud Intervention voice agent (ThunderRunes, Ignyte x ElevenLabs Future of Voice AI Challenge, Banking & Insurance track).

**What this is:** the three webhooks the agent's ElevenLabs Tools call during a call, standing in for the bank's real systems until Build Sprint platform access. **What this proves:** the canvas's central guardrail claim — *"the model gathers evidence; only a separate policy layer authorises actions"* — is enforced in code, not just asserted in a document.

## The trust boundary, in one diagram

```
Agent (ElevenLabs)                    This backend
──────────────────                    ───────────────────────────
"Are you speaking with        --->    POST /verify
 anyone from the bank?"                 -> verification_id (or verified: false)

extracts evidence from        --->    POST /policy/evaluate
the conversation                        -> authorized_actions, action_token
(never decides the action itself)       (policy.py — plain rule table, no LLM call)

confirms verbally,            --->    POST /actions/freeze_card
passes the token along                  -> only executes if the token matches
                                            customer_id + action + hasn't expired/been used
```

The agent cannot skip a step or talk its way past one: `/actions/freeze_card` doesn't check anything the agent *said* — only whether it's holding a valid token that `/policy/evaluate` actually issued.

## Policy rules (`app/policy.py`)

Evaluated in this priority order — evidence in, decision out, no model involved:

| # | Condition | Result |
|---|---|---|
| 1 | Not verified | No action, escalate |
| 2 | OTP disclosed | `freeze_card` **and** escalate |
| 3 | Active impersonation claimed | `freeze_card` **and** escalate |
| 4 | Card not confirmed in possession | `freeze_card` **and** escalate |
| 5 | Transaction recognized | No action, no escalation |
| 6 | Transaction not recognized, nothing else | `freeze_card` only |
| 7 | Evidence incomplete | No action, escalate (fails closed) |

Rows 2–4 all still authorize the safe, reversible action immediately (freezing costs nothing and protects the customer right away) — they additionally force escalation because those evidence combinations imply compromise broader than one transaction, which needs a human. This is exactly the distinction the canvas's Box I argues for: reversible and irreversible decisions are handled differently, deterministically, not left to model judgement.

## Endpoints

- `GET /health`
- `POST /verify` — `{customer_id, challenge_response}` → `{verified, verification_id}`. Takes an opaque response, never a PIN/password/OTP. Send `challenge_response: "fail"` to simulate a failed challenge.
- `POST /policy/evaluate` — `{customer_id, verification_id, risk_context, evidence}` → `{authorized_actions, requires_human_escalation, escalation_reason, action_token}`
- `POST /actions/freeze_card` — `{customer_id, action_token}` → executes only with a valid, unexpired, single-use, customer-matched token
- `GET /mock/sample-risk-events` — example risk-context payloads

`fixtures/sample_scenarios.json` has four full worked examples — happy path, OTP-disclosure escalation, active-impersonation escalation, and a failed-verification adversarial case — matching the demo scenarios the canvas commits to for 14 October.

## Running it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -v
```

**Docker** (not build-verified in the environment this was authored in — verify locally):
```bash
docker build -t fraud-agent-mock-backend .
docker run -p 8000:8000 fraud-agent-mock-backend
```

## What's intentionally out of scope here

- **No real ElevenLabs wiring** — that happens on-platform during the Build Sprint, once access is granted. This repo is the backend those Tools will point at.
- **Token signing is a stand-in** — `secrets.token_urlsafe` + an in-memory dict, not a production-grade signed token. The *enforcement shape* (action requires a token this service minted) is the real point; production would use a proper signed/short-lived credential.
- **Four evidence dimensions only** (transaction recognized, OTP disclosed, active impersonation, card possession) — deliberately not a general fraud ontology, to stay buildable solo in two weeks (see canvas Box L).
