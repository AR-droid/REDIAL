# Capabilities

## The agent can

- Place and receive a phone conversation through Twilio, with speech in both directions, using the OpenAI Realtime API.
- Look up a customer's failed payment (amount, currency, due date, failure reason, autopay status, dispute flag, retry count) before saying anything about the account.
- Apply the decision policy for the ten recorded scenarios:
  - retry (mocked) on a first insufficient-funds failure
  - payment link (mocked) instead of retry for expired cards, fraud-flagged declines, and second failures
  - inform only, without pressure, when autopay is paused
  - stop pursuing payment on a dispute or an amount dispute, and offer a person
  - acknowledge a request for time and offer a reminder link
- Handle a customer who declines an offer, and acknowledge it.
- Log every tool call to `demo/audit.jsonl` with `mocked: true`.

## The agent cannot

- Move money, charge a card, or send a real payment link or message. Those tools are mocked.
- Transfer a call to a person. Escalation is mocked: `escalate_to_human` records a request in the audit log, because no human team exists to receive one.
- Flag an account for human review. The policy asks for this in one scenario, but no tool records it.
- Call any number other than the approved one. The script refuses other destinations, and Twilio trial rules also apply.
- Take inbound calls.
- Detect voicemail or answering machines beyond what Twilio does by default.

## Good fits and designed-for escalations

Handled well by the policy: a customer who has a card problem, has the wrong amount, is disputing, has a paused autopay, or asks for time.

Designed to escalate rather than handle: a customer who disputes the amount or the charge, or whose charge was flagged for fraud. The agent stops pursuing payment in both cases.

Not tested: abusive or threatening callers, callers who speak other languages, and callers who ask detailed questions about the account beyond the stored fields.

## Honesty about what happened

- The recorded calls were real phone calls. Their results, durations, and tool calls are in `demo/call_log.md`.
- The retry and link results are mock outputs. The agent's spoken wording for a successful retry was changed after the first call so it no longer says money moved.
