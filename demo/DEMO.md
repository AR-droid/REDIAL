# Demo: 60-second walkthrough

Everything here is from real phone calls to the approved number, unless labelled as offline. Full records are in [call_log.md](call_log.md).

## Architecture

```
  customer phone  <-- PSTN -->  Twilio (US number)
                                   |  TwiML (signed by Twilio) -> <Connect><Stream>
                                   |  Media Stream WebSocket (token-checked)
                                   v
                     FastAPI backend (backend/)
                        |  audio <-> OpenAI Realtime (gpt-realtime-mini)
                        |  policy: agent/system_prompt.md
                        |  tools:  check_payment_status, retry_autopay_charge,
                        |          send_payment_link, escalate_to_human
                        v
                     Mock payment backend (backend/tools.py, data/customers.json)
                        every call -> demo/audit.jsonl with mocked: true
```

## Scenario 1: insufficient funds, retry accepted (real call)

Customer says "Yes, please retry it."

| Time (UTC) | Tool | Result |
|---|---|---|
| 18:36:58 | check_payment_status(cust_001) | amount 1249.00 INR, insufficient_funds, autopay active, not disputing |
| 18:37:16 | retry_autopay_charge(cust_001) | status `succeeded` (mocked) |

Call: CAa8c2e8733b5a51b07301a7f6c22a46f8, 38 seconds. During this call the agent said the payment "went through," which was wrong for a mocked retry. The wording was changed afterward to say the payment was recorded on the account.

## Scenario 3: expired card, no retry (real call)

Customer asks for a payment link. The agent never offers a retry on an expired card.

Call: CA8c99cab7a9a9fe681126db2b13196c25, 35 seconds. Tools: check_payment_status, then send_payment_link (mocked).

## Scenario 9: amount disputed mid-call, escalation (offline run)

Customer says "That's not what I agreed to." The agent should stop pursuing payment and call `escalate_to_human` with reason `amount_dispute`.

This run is an offline simulation in `demo/simulations/cust_009.md`, using the same prompt and tool definitions. The live call for this scenario was run before escalation was added, so the phone result shows the agent offering a person without a recorded escalation.

## A failure found during testing (scenario 7)

On a real call, the agent sent a reminder link without first checking the account, which the prompt requires. The fix is a backend gate: retry and payment-link calls are refused until `check_payment_status` has run on that call. Covered by offline tests. Not re-run on a phone.

## What is mocked

- **Retry and payment link:** no charge is attempted and no link or message is sent. Every call is logged with `mocked: true`.
- **Human escalation:** `escalate_to_human` records a request in the audit log. **It is mocked because no human team exists to receive it.** Nothing is transferred.

## Run it

```
make test          # 36 offline tests
make simulate      # offline scenario runs (needs OPENAI_API_KEY)
make mock-server   # backend; expose port 8000 with ngrok
make call SCENARIO=1 CONFIRM=1   # real call to the approved number only
```
