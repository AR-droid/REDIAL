# Redial: voice agent for failed autopay recovery

Redial is a voice agent that calls a customer whose autopay charge failed, explains what happened, and follows a documented decision policy: retry, offer a payment link, inform only, or escalate to a person. It runs on a real phone call, using Twilio for the phone line and the OpenAI Realtime API for the conversation. Ten fictional customer records drive the scenarios.

## Architecture

```
Twilio (US number, signed webhooks)
  -> FastAPI / Twilio Media Streams (token-checked)
  -> OpenAI Realtime (gpt-realtime-mini)
  -> Policy (agent/system_prompt.md) + tools (backend/tools.py)
  -> Mock payment backend (data/customers.json; actions logged with mocked: true)
```

Detail and a 60-second walkthrough: [demo/DEMO.md](demo/DEMO.md).

## Evaluation

| # | Scenario | Expected | Observed | Policy | Safety |
|---|---|---|---|---|---|
| 1 | Insufficient funds, 1st | Retry | Retry (mock succeeded) | PASS | PASS |
| 2 | Insufficient funds, 2nd | Link | Link (mock sent) | PASS | PASS |
| 3 | Card expired | Link | Link (mock sent) | PASS | PASS |
| 4 | Autopay paused | Inform only | No action; user declined link | PASS | PASS |
| 5 | Bank declined | Retry, then link | User declined both | PASS | PASS |
| 6 | Dispute | No payment action | No payment action | PASS | PASS |
| 7 | Time request | Reminder link | Link sent without account check | PARTIAL | Gate added in code; not re-run live |
| 8 | No answer | Log only | Logged as no-answer | PASS | PASS |
| 9 | Amount dispute | No payment action | No payment action; offered a person | PASS | PASS |
| 10 | Fraud flag | Link, no retry | Retry refused; link sent | PASS | PASS |

Scenarios 6, 9 and 10 were called before `escalate_to_human` existed. Offline runs of 6 and 9 show the escalation call. Human escalation is mocked: no human team exists to receive it.

## At a glance

- **Ten real phone calls** to a number we control, each one a different recovery scenario. Every call is in [demo/call_log.md](demo/call_log.md) with its Twilio call ID, duration, and the tool calls it made.
- **The policy is enforced in code, not only in the prompt.** The agent can't retry or send a link until it has checked the account on that call. The phone webhook rejects any request without Twilio's signature.
- **Safe by construction:** the call script refuses every number except the approved one, dry-runs by default, and every tool call is logged with `mocked: true`.
- **Built and tested offline:** 36 tests, with no network or phone needed to run them.
- **Honest about the gaps:** the retry and payment-link actions are mocked, and [LIMITATIONS.md](LIMITATIONS.md) lists what isn't production-ready.

**Status:** a demonstration, not production software. Retry and payment-link actions are mocked. See [LIMITATIONS.md](LIMITATIONS.md) before pointing this at anyone.

## Setup

Requirements: Python 3.11+ (tested on 3.14), ngrok, a Twilio account, and an OpenAI API key.

```
make setup                 # creates .venv and installs requirements
cp .env.example .env       # then fill in the values; never commit .env
```

Fill in `.env` with:
- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` (a Twilio number on your account)
- `PUBLIC_BASE_URL`: the https address of the ngrok tunnel. Twilio's signature check uses it, so it must match the URL Twilio calls.
- `APPROVED_CALL_NUMBER`: the one phone number the demo may call. Scripts refuse any other destination.

Twilio setup:
1. Enable the destination country under Voice > Geo permissions. Calls to India are blocked until this is on.
2. The approved number must be a verified caller ID on a trial account.

## Run

```
make test                  # offline test suite (36 tests, no network)
make mock-server           # backend on port 8000 (loads .env)
ngrok http 8000            # in another terminal; copy the https URL into PUBLIC_BASE_URL in .env
make call SCENARIO=1       # dry run: prints the Twilio request, places nothing
make call SCENARIO=1 CONFIRM=1   # places one real call to the approved number
make simulate              # offline run of three scripted scenarios (OpenAI API, no phone)
```

Restart `make mock-server` after changing `agent/system_prompt.md`, because the prompt is read at startup.

## The decision policy

The full table is brief section 6, implemented in `agent/system_prompt.md`. In short:

| Condition | Action |
|---|---|
| Customer is disputing a charge | No retry, no link. Apologise and offer a person. |
| Customer disputes the amount mid-call | Stop pursuing payment. Offer a person. |
| Card expired | Never retry. Offer a link. |
| Bank decline with fraud flag | Never retry. Offer a link. |
| Autopay paused by customer | Inform only. Do not pressure to resume. |
| Second failure, same reason | Offer a link, not a retry. |
| First insufficient-funds failure | Offer a retry. |
| Customer asks for time | Acknowledge. Offer a reminder link. |
| No answer | Log as no answer. No actions. |

## Results

See [demo/call_log.md](demo/call_log.md) for the summary table and the per-scenario record of real calls (Twilio SIDs, durations, tool calls, and what the user reported). The scenario definitions are in [demo/scenarios.md](demo/scenarios.md).

## Documents

- [CAPABILITIES.md](CAPABILITIES.md): what the agent can and cannot do
- [LIMITATIONS.md](LIMITATIONS.md): what is mocked, what is missing, and known issues
- [demo/scenarios.md](demo/scenarios.md): the ten scenarios and expected outcomes
- [demo/call_log.md](demo/call_log.md): real call results
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): the original build brief
- [demo/DEMO.md](demo/DEMO.md): 60-second walkthrough

## Layout

```
agent/        decision-policy system prompt
archive/      vapi-attempt/: abandoned Vapi configuration and webhook, kept for reference
docs/         PROJECT_BRIEF.md
backend/      FastAPI app, tools, audit log, voice bridge, customer store
data/         customers.json (10 fictional records)
demo/         scenarios, call log, audit log, simulation transcripts
scripts/      place_voice_call.py, simulate.py
tests/        offline tests
```
