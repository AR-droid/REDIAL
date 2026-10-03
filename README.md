# Redial: voice agent for failed autopay recovery

Redial is a voice agent that calls a customer whose autopay charge failed, explains what happened, and follows a documented decision policy: retry, offer a payment link, inform only, or escalate to a person. It runs on a real phone call, using Twilio for the phone line and the OpenAI Realtime API for the conversation. Ten fictional customer records drive the scenarios.

**Status:** a demonstration, not production software. Retry and payment-link actions are mocked. See [LIMITATIONS.md](LIMITATIONS.md) before pointing this at anyone.

## Architecture

```
  approved phone  <--PSTN-->  Twilio (US number)
                                  |  1. POST /voice/twiml  -> <Connect><Stream>
                                  |  2. WebSocket /voice/media (8 kHz G.711 mu-law)
                                  v
                       backend (FastAPI, port 8000, exposed via ngrok)
                          |  audio <-> OpenAI Realtime (gpt-realtime-mini)
                          |  tool calls -> backend/tools.py -> data/customers.json
                          |  every tool call -> demo/audit.jsonl (mocked: true)
```

- `agent/system_prompt.md` is the decision policy. It is scenario-agnostic: the call's `customer_id` is injected, and the agent's first step is `check_payment_status`.
- `backend/voice.py` maps Twilio audio to the Realtime API and runs tool calls for the customer on that call only.
- The same prompt and tool definitions are used in the recorded calls and in the offline simulations.

## Setup

Requirements: Python 3.11+ (tested on 3.14), ngrok, a Twilio account, and an OpenAI API key.

```
make setup                 # creates .venv and installs requirements
cp .env.example .env       # then fill in the values; never commit .env
```

Fill in `.env` with:
- `OPENAI_API_KEY`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` (a Twilio number on your account)
- `APPROVED_CALL_NUMBER`: the one phone number the demo may call. Scripts refuse any other destination.

Twilio setup:
1. Enable the destination country under Voice > Geo permissions. Calls to India are blocked until this is on.
2. The approved number must be a verified caller ID on a trial account.

## Run

```
make test                  # offline test suite (32 tests, no network)
make mock-server           # backend on port 8000
ngrok http 8000            # in another terminal; copy the https URL into PUBLIC_BASE_URL in .env
make call SCENARIO=1       # dry run: prints the Twilio request, places nothing
make call SCENARIO=1 CONFIRM=1   # places one real call to the approved number
make simulate              # offline run of all three scripted scenarios (OpenAI API, no phone)
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
- [demo/baseline.md](demo/baseline.md): human-agent comparison (not measured)
- [demo/call_log.md](demo/call_log.md): real call results
- [PROJECT_BRIEF.md](PROJECT_BRIEF.md): the original build brief

## Layout

```
agent/        system prompt, assistant config (Vapi attempt, see LIMITATIONS)
backend/      FastAPI app, tools, audit log, voice bridge, customer store
data/         customers.json (10 fictional records)
demo/         scenarios, call log, baseline, audit log, simulation transcripts
scripts/      place_voice_call.py, simulate.py
tests/        offline tests
```
