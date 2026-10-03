# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This repository currently contains only `PROJECT_BRIEF.md` and an `archive/` folder — no code has been written yet. There is no `pyproject.toml`, `Makefile`, or `backend/`/`agent/`/`scripts/` tree on disk. Before running any build/lint/test command, check whether it actually exists; the commands below are what the brief specifies the project *will* use once scaffolded, not commands that work today.

`PROJECT_BRIEF.md` is the authoritative build spec (a Razorpay Forward-Deployed Engineer application assignment, Option 2: a voice agent that attempts to recover failed autopay payments). Read it in full before starting implementation.

**`archive/connector-option/`** holds a fully-researched prior plan for a different assignment option (Option 3, a Freshdesk MCP connector) that was abandoned mid-Phase-1 when the user pivoted to the voice-agent option. It's kept for reference only — don't build from it, and don't let its architecture (Provider protocol, MCP tools, allowlists) bleed into this project; the two options are unrelated.

## What is being built: Redial

A voice agent (**Vapi**, outbound calling via an imported **Twilio** number) that calls about a failed autopay charge, looks up the account via a mocked backend, and follows a documented decision policy (retry / payment link / extension / escalate-to-human) live on the call. 10 fictional customer scenarios drive the demo; every call target is the one phone number the user has explicitly approved — never any other number.

Planned layout (see brief section 4 for full detail):
```
redial/
├── data/customers.json       # 10 fictional customer records (brief section 5)
├── backend/                  # FastAPI: tool webhook endpoints (check_payment_status, retry_autopay_charge, send_payment_link), audit log
├── agent/                    # Vapi assistant config + the decision-policy system prompt
├── scripts/                  # place_call.py, call_all.py, fetch_transcript.py
├── tests/                    # backend logic tests, fully offline
└── demo/                     # scenarios.md, call_log.md (real outcomes), baseline.md
```

## Commands (once scaffolded, per the brief)

- Mock backend: `make mock-server` (FastAPI app exposing the 3 tools)
- Tunnel for Vapi's webhook during dev: `ngrok http <port>`
- Place one scenario's call: `make call SCENARIO=<n>`
- Tests (fully offline, no Vapi/Twilio credentials needed): `pytest`

Toolchain per the brief: Python 3.11+, FastAPI + `uvicorn`, `httpx`, `pytest`.

## Architecture rules that shape every change

- **Build the mock backend before touching Vapi.** It's the part that's fast and free to iterate on; Vapi dashboard testing comes next, real phone calls last (they cost real minutes against a $10 free-credit budget).
- **The decision policy (brief section 6) is the actual product being evaluated here** — the call is just the delivery mechanism. Any change to the system prompt must be checked against every row of that table (dispute → never collect, expired card → never retry, fraud-flagged decline → never retry, paused autopay → inform don't pressure, second failure → link not retry, customer requests time → acknowledge don't push, no answer → log honestly with no fabricated conversation).
- **Every tool call is mocked and must say so.** `retry_autopay_charge` and `send_payment_link` never touch a real payment rail; every invocation is logged with `mocked: true` in `backend/audit.py`. Never let a transcript, log line, or write-up imply a real charge or real link was sent.
- **Never dial a number other than the one the user explicitly approved.** This is a hardcoded guard in `scripts/place_call.py`, not a convention to remember — Twilio's trial-account verified-numbers restriction backs this up at the infrastructure level, but the app-level guard must exist independently of that.
- **The prompt is scenario-agnostic; the data isn't hardcoded into it.** Dynamic variables (`assistantOverrides.variableValues`, Vapi's confirmed mechanism) pass only a `customer_id` per call — the agent's first move is calling `check_payment_status` to pull real facts from the tool, so the same prompt drives all 10 scenarios.
- **Fictional data only** — no real names, numbers, amounts, or anything resembling a real person's situation. `data/customers.json` and any seeded transcripts must stay fictional.
- **Verification honesty**: `demo/call_log.md` must state plainly, per scenario, whether it was a real placed call or a dashboard-simulated run — never claim a live call happened if it didn't. This mirrors the same "don't claim what you didn't verify" discipline used throughout this project's planning.

## Verified platform facts (don't re-derive these — confirmed against current docs during Phase 1 research)

- Vapi's own free phone numbers **cannot** place outbound calls — a Twilio (or Vonage/Telnyx) number must be imported.
- Twilio trial accounts can only call **verified** numbers — add the user's own number as verified; this is relied on as part of the "only a number you control" safety story, not just documented as a constraint.
- Outbound call API: `POST /call` with `assistantId`, `phoneNumberId`, `customer.number`, and `assistantOverrides.variableValues` for per-call personalization.
- Tool webhooks: Vapi POSTs `{"message": {"type": "tool-calls", "toolCallList": [...]}}`; the server must always respond HTTP 200 with `{"results": [{"toolCallId": ..., "result": "<flat string>"}]}` (or `error` instead of `result` on failure) — never a non-200, even for a tool-level error.
- Vapi gives $10 free credit (~60+ min); budget test calls accordingly — ask the user before placing more than a couple of exploratory calls while iterating on the prompt.

## Scope guardrails

Per the brief (section 14): ask the user before spending beyond the free credits on Vapi/Twilio, before placing more than a couple of test calls while iterating, and before expanding beyond the 10-scenario single-number demo (e.g., inbound handling, multi-number support — both are explicitly out of scope, listed as future work in `LIMITATIONS.md`, not to be built now). If Vapi/Twilio's actual behavior differs from what the brief assumes, don't silently work around it — note it in `LIMITATIONS.md` and tell the user.
