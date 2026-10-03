# Limitations

## Mocked, not real

- **Payments:** `retry_autopay_charge` and `send_payment_link` return mock results. No charge is attempted, and no link or message is sent. Every call to them is logged with `mocked: true`.
- **Payment link domain:** `pay.example.com`, a placeholder.
- **Account data:** `data/customers.json` is ten fictional records. Nothing is read from a real customer database.
- **Account flags:** the policy's "flag for human review" step has no tool, so it cannot be recorded.
- **Human handoff:** the agent offers to connect the customer to a person, but no transfer exists.

## Platform and setup

- **Vapi attempt:** the first design used Vapi. The assistant was created and tested, but Vapi requires a completed payment before chat tests run, and no live calls were placed through it. Recorded calls use Twilio with the OpenAI Realtime API instead. `agent/assistant_config.json` is kept as the Vapi attempt, and its tool endpoints point at a tunnel URL that no longer applies.
- **Twilio trial account:** calls from a trial account play a short Twilio message first, and the callee must press a key before the call continues. Without a key press, the call ends after about 14 seconds with no agent speech. This happened on the first attempts.
- **Geo permissions:** Twilio blocks calls to India until the destination is enabled in Voice > Geo permissions.
- **Tunnel URL:** the ngrok address changes when the tunnel restarts. Update `PUBLIC_BASE_URL` in `.env` each time.
- **Cost:** OpenAI Realtime is billed per minute of audio, and Twilio bills per minute and for the trial number. Costs for the recorded calls were not measured precisely. Estimates are from pricing, not invoices.

## Known defects

- **Scenario 7 status check:** the agent sent a link without calling `check_payment_status` first, although the prompt requires it. Fixed in code after the call: the backend now refuses retry and payment-link calls until the account check has run on that call. This fix is covered by offline tests but has not been re-run on a live call.
- **Scenario 9 handoff:** the agent offered a transfer that doesn't exist (see above).
- **Scenario 1 wording:** the first recorded call told the user the payment "went through," which was wrong for a mock retry. The wording was changed afterward. No transcript was saved, so the wording is recorded from the user's report.
- **Early calls without audio:** the first attempts did not produce agent speech. One was a missing streamSid, which is fixed and covered by a test. The other attempts that ended after about 14 seconds likely had an unconfirmed trial key press. The call log records both.

## Not production-ready

These are needed before any real customer is contacted:

- **Webhook authentication:** `/voice/twiml` now verifies Twilio's request signature and returns 403 otherwise. The signature check has been tested offline, but not yet against a live Twilio request. `/voice/media` is a WebSocket that Twilio does not sign, so it is not authenticated; anyone who knows its URL and sends a valid start message can open a session. `/tools`, the older Vapi webhook, has no authentication.
- **Secrets:** API keys and tokens were pasted into the development chat during this project. They should be rotated before the repo is shared.
- **Audit storage:** the audit log is a local JSONL file. It isn't durable, isn't tamper-evident, and isn't shared across processes.
- **Persistence:** account state is in memory and resets when the backend restarts.
- **Scale and rate limits:** nothing limits call volume. The approved-number guard is the only safety control on outbound calls.
- **Recording and consent:** call recording and disclosure rules differ by jurisdiction. The repo does not handle them.
- **Model behaviour:** the policy is enforced by a prompt, not by code. The decision table was checked against recorded calls, not against every possible customer reply.

## Scope limits

- Ten scenarios, each run once, plus one re-run for no-answer. Not a statistical test.
- One phone number, one assistant, one language (English).
- No inbound calls, no multi-merchant support, no voicemail detection.

## Long-term fixes

- Replace `retry_autopay_charge` and `send_payment_link` with real payment-processor calls behind the same tool interface.
- Authenticate `/voice/media` and `/tools`, for example with a per-call token issued at TwiML time.
- Add a real warm transfer to a human agent, and a tool that flags accounts.
- Persist customer state and audit logs in a database.
