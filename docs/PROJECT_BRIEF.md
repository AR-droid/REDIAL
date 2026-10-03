# Redial — Voice Agent for Autopay Recovery: Build Brief (v1)

---

## 0. One-paragraph description

Build **Redial**, a voice agent that calls a customer whose autopay charge just failed, explains what happened in plain language, and tries to resolve it on the call — retry the card, send a payment link, offer a short extension, or escalate to a human — using the same decision logic a Razorpay Agent Studio recovery agent would use. The voice layer is **Vapi**, backed by a **Twilio** phone number imported for outbound calling. A small local backend holds **10 fictional customer records** (name, amount due, due date, card last-4, autopay status) and exposes mock "check payment status" / "retry charge" / "send payment link" tools that the voice agent calls mid-conversation via webhook. All test calls go to **one number the user controls** (per the assignment's explicit constraint) — the 10 records are 10 distinct *scenarios*, each placed as a separate call to that same number, not 10 different real phone numbers.

**Why it matters (FDE framing):** this is the same recovery decision a Razorpay Agent Studio agent makes over chat or an API call, moved onto a channel merchants' customers still actually answer — a phone call. A merchant doesn't need an AI that sounds impressive; it needs one that says the right thing to the right customer and knows exactly when to stop and hand off to a human. The honest demo here is proving *that judgment*, end to end, on a real phone call — not proving voice synthesis quality, which is a solved problem the platform (Vapi) already handles.

---

## 1. Scope strategy (read this first)

This assignment option is inherently smaller than a full connector build — one voice agent, one phone number, ten scripted scenarios. The risk here isn't scope creep into "four providers," it's scope creep into *conversation design perfectionism* (endlessly tuning prompts) at the expense of the actual deliverables: a working end-to-end call, a clear decision policy, and an honest write-up.

**Build in this order:**
1. Mock backend first (customer records + tools), fully testable without touching Vapi.
2. One Vapi assistant with one solid system prompt and three tools, tested manually via the Vapi dashboard against the mock backend.
3. Outbound calling wired up via the API with per-call dynamic variables, tested against your own number for a couple of the 10 scenarios.
4. Run all 10 scenarios, capture transcripts/recordings, write the scenario-to-outcome table.
5. Docs last: `CAPABILITIES.md`, `LIMITATIONS.md`, a one-page README.

If time runs out, cut polish on the prompt and the number of scenarios actually *called* live (e.g., call 4–5 live and present the rest as scripted/mock-verified transcripts, clearly labeled) before cutting the backend's correctness or the honesty of the write-up.

---

## 2. Goals and non-goals

### Goals
1. One Vapi assistant, backed by a local mock backend, making real outbound phone calls to a number the user controls.
2. 10 fictional customer records covering a spread of recovery scenarios (see section 5).
3. Three tools the agent can call mid-call: `check_payment_status`, `retry_autopay_charge`, `send_payment_link` (all mocked — no real payment rails touched).
4. A clear, documented decision policy: when to retry, when to offer a link, when to escalate, when to just inform and hang up.
5. An honest demonstration: at minimum one real live call recorded/transcribed; the remaining scenarios run and documented, labeled by whether they were called live or walked through in testing.
6. `CAPABILITIES.md`-equivalent: what this agent can and cannot do, who it's safe to point at a real customer, and what's missing for production.

### Non-goals (state in docs)
- No real payment processing of any kind — `retry_autopay_charge` and `send_payment_link` are mocked and clearly logged as such.
- No real customer phone numbers — every call target is a number the user owns or has explicit permission to call.
- No outbound dialing at scale / no campaign management — this is a single-assistant, single-number demo, not a dialer product.
- No inbound call handling (the customer calling back) — out of scope for this cycle, noted as a natural next step.
- No voicemail-drop or answering-machine detection logic — if the call isn't picked up, that's logged as an outcome, not engineered around.

### Stretch (only after the 10 scenarios are solid)
- A short inbound flow: if the customer calls back, the same agent picks up with context from the original call.
- A simple outcome dashboard (just a markdown table generated from the audit log is enough — no actual dashboard needed).

---

## 3. PRD

### 3.1 Problem
When autopay fails, most merchants either do nothing (silent revenue loss) or send an email/SMS that goes unread. A short, well-timed phone call recovers payments that other channels miss — but it needs to sound human, know the account's actual status, and know when *not* to push (e.g., a customer already disputing the charge should be escalated, not re-charged).

### 3.2 Users
| User | Need |
|---|---|
| Customer (fictional, played by the user's own phone) | A clear, non-pushy explanation of what happened and an easy way to fix it |
| Merchant ops/finance person | Confidence the agent won't re-charge someone who shouldn't be charged, and a clear log of every call's outcome |
| Razorpay FDE / reviewer | A working live call, a sound decision policy, and an honest account of what's real vs. mocked |

### 3.3 User stories
1. As a customer whose card simply had insufficient funds, I get a courteous call offering to retry or send a payment link, and I can say "retry now" and have it happen (mocked).
2. As a customer whose card expired, I get told specifically that it's expired (not a generic "payment failed") and offered a payment link instead of a pointless retry.
3. As a customer who's already disputing this charge, the agent recognizes that from the account record and does *not* try to collect — it apologizes and offers to connect me to a human.
4. As a customer who doesn't answer, the call outcome is logged honestly as "no answer," not fabricated as a conversation.
5. As a reviewer, I can read a transcript or listen to a recording of at least one real call and see the decision policy actually executed.

### 3.4 Functional requirements
| ID | Requirement |
|---|---|
| FR-1 | 10 fictional customer records, each with: name, amount due, currency, due date, failure reason, card last-4, autopay status, "already disputing" flag |
| FR-2 | Mock backend (small local HTTP server) exposing `check_payment_status`, `retry_autopay_charge`, `send_payment_link` — no real payment integration |
| FR-3 | Vapi assistant with one system prompt encoding the decision policy (section 6), using dynamic variables to inject the current customer's record per call |
| FR-4 | Vapi tool definitions wired to the mock backend via a public webhook (ngrok for dev) |
| FR-5 | Outbound call script (`place_call.py` or similar) that, given a customer record, calls the one approved number with that record's variables injected |
| FR-6 | Audit log: every call's outcome (answered/no-answer), every tool call made during it, and the final decision taken |
| FR-7 | Fictional data only — no real names, numbers, or amounts resembling a real person |

### 3.5 Non-functional requirements
- **Honesty:** never claim a scenario was "called live" if it wasn't; never let the agent claim a payment was actually retried when the tool is mocked.
- **Safety:** the call script refuses to dial any number other than the one explicitly configured as approved — a hardcoded guard, not a convention.
- **Reproducibility:** `make setup` installs deps, `make mock-server` runs the backend, `make call SCENARIO=3` places one call, `make call-all` or a documented manual loop runs all 10.
- **Secrets:** Vapi and Twilio API keys via `.env`, never committed.

### 3.6 Success metrics
- At least one real outbound call placed and completed (answered or not) with a recording/transcript to show for it.
- All 10 scenarios produce a documented, policy-consistent outcome (live call or, if time-limited, a clear mock/simulated run through the same backend and prompt).
- The decision policy table (section 6) is followed correctly in every scenario reviewed.
- `CAPABILITIES.md` honestly states what's mocked vs. real.

---

## 4. Tech stack and repo layout

**Stack:** Vapi (voice agent platform, outbound calling + tool calling), Twilio (imported phone number for outbound — trial account, which conveniently restricts calls to verified numbers, reinforcing the "only a number you control" rule), Python 3.11+ for the mock backend (FastAPI, `uvicorn`), `ngrok` for local webhook tunneling during development, `httpx` for the call-placement script, `pytest` for backend tests.

```
redial/
├── PROJECT_BRIEF.md
├── README.md
├── CAPABILITIES.md
├── LIMITATIONS.md
├── .env.example  Makefile  .gitignore
├── data/
│   └── customers.json          # 10 fictional customer records (FR-1)
├── backend/
│   ├── app.py                  # FastAPI app: tool webhook endpoints
│   ├── store.py                # loads/queries customers.json, in-memory "account state"
│   ├── tools.py                # check_payment_status, retry_autopay_charge, send_payment_link logic
│   └── audit.py                # logs every tool call + outcome
├── agent/
│   ├── assistant_config.json   # Vapi assistant definition: prompt, tools, voice, model
│   └── system_prompt.md        # the decision-policy prompt, versioned separately for readability
├── scripts/
│   ├── place_call.py           # places one outbound call for a given scenario id, via Vapi API
│   ├── call_all.py             # loops through all 10 scenarios with a pause between calls
│   └── fetch_transcript.py     # pulls a completed call's transcript/recording from Vapi
├── tests/
│   ├── test_tools.py           # mock backend logic: correct status per scenario, mocked retry/link behavior
│   └── test_store.py
└── demo/
    ├── scenarios.md            # the 10 fictional records + expected policy outcome per one
    ├── call_log.md             # actual results: which were called live, transcript/recording links, outcome
    └── baseline.md             # how long a human agent would take to make these 10 calls, for comparison
```

---

## 5. The 10 fictional customer scenarios

Each record lives in `data/customers.json`. Spread chosen to exercise every branch of the decision policy (section 6), not just the happy path.

| # | Name (fictional) | Failure reason | Autopay status | Disputing? | Expected policy outcome |
|---|---|---|---|---|---|
| 1 | Asha Kulkarni | Insufficient funds | Active | No | Offer retry now |
| 2 | Rahul Mehta | Insufficient funds, 2nd failure | Active | No | Offer payment link instead of retry (retry already failed once) |
| 3 | Priya Nair | Card expired | Active | No | Payment link only, no retry (retry is pointless on an expired card) |
| 4 | Vikram Shah | Card expired | Paused by customer | No | Inform only, no push to re-enable — respect the pause |
| 5 | Fatima Sheikh | Bank declined, no reason given | Active | No | Offer retry, fallback to payment link if declined |
| 6 | Arjun Rao | Insufficient funds | Active | **Yes (disputing an earlier charge)** | Do not collect — apologize, offer human escalation |
| 7 | Divya Pillai | Insufficient funds | Active | No | Customer asks for a 3-day extension mid-call → agent offers to note it and send a reminder link for then |
| 8 | Karan Malhotra | Card expired | Active | No | No answer (simulate voicemail/no pickup) → logged honestly, no fabricated conversation |
| 9 | Sneha Reddy | Insufficient funds | Active | No | Customer disputes the amount itself mid-call ("that's not what I agreed to") → escalate, don't argue or retry |
| 10 | Imran Qureshi | Bank declined — suspected fraud flag from issuer | Active | No | Agent does not attempt retry on a fraud-flagged decline — payment link only, note for human review |

All names, amounts, and card details are fictional (`example.com`-style placeholders where an email is needed, fake last-4 digits, no real financial data).

---

## 6. Decision policy (the core of what this demo is actually testing)

The system prompt (`agent/system_prompt.md`) encodes these rules. This table **is** the product — the call itself is just the delivery mechanism.

| Condition | Action |
|---|---|
| Already disputing a charge (any charge, not just this one) | Never attempt retry or pitch a payment link. Apologize for the trouble, offer to connect to a human, end the call. |
| Customer disputes the amount or the charge itself, mid-call | Stop pursuing payment immediately. Don't argue the amount. Offer human escalation. |
| First failure, reason = insufficient funds, autopay active | Offer an immediate retry. If customer agrees, call `retry_autopay_charge`. |
| Second+ failure, same reason | Don't retry again blindly — offer a payment link instead (`send_payment_link`), explain a card issue may need the customer's attention. |
| Reason = card expired | Never offer a retry (an expired card will fail again) — always offer a payment link so they can update payment details. |
| Reason = bank decline with a fraud flag | Never retry (retrying a fraud-flagged decline can trigger issuer-side account action) — payment link only, flag the account for human review. |
| Autopay status = paused by customer | Inform about the failed charge but do not pressure to resume autopay — respect that the customer turned it off. |
| Customer requests more time | Acknowledge, don't push back, offer to send a reminder link timed to the requested date. |
| No answer / call not picked up | Log as `no_answer`. No retry/link/escalation actions are taken — there was no conversation. |

Every tool call and every policy branch taken is written to the audit log (`backend/audit.py`) so `demo/call_log.md` can be built directly from real call data, not from memory of what the call "was supposed to do."

---

## 7. Mock backend and tool specification

### 7.1 `check_payment_status`
- **Input:** `customer_id`
- **Output:** `{ amount_due, currency, due_date, failure_reason, autopay_status, is_disputing, retry_count }`
- Looks up `data/customers.json` — this is the single source of truth the agent queries at the start of the call via `{{customer_id}}` dynamic variable, so the prompt never hardcodes customer facts, it asks the tool.

### 7.2 `retry_autopay_charge`
- **Input:** `customer_id`
- **Output:** `{ status: "succeeded" | "declined", message }`
- **Always mocked.** Deterministic per scenario (e.g., scenario 5's "fallback to payment link if declined" needs this to return `declined` on the first call for that scenario) so test runs are reproducible. Every invocation is written to the audit log with a clear `mocked: true` field — never represented as a real charge attempt anywhere in code, logs, or the write-up.

### 7.3 `send_payment_link`
- **Input:** `customer_id`
- **Output:** `{ status: "sent", link: "https://pay.example.com/mock/{customer_id}" }`
- Mocked, same honesty requirement as above. The link domain is deliberately `example.com` so nothing could be mistaken for a real payment URL.

### 7.4 Read-only safety
The mock backend never touches a real payment processor, real SMS/email provider, or real customer database — it's a single JSON file and an in-memory dict. There's no real-world side effect to guard against here the way there was with the connector option's allowlist, but the same principle holds: everything the agent can *do* is enumerated and mocked, nothing is implicit.

---

## 8. Outbound calling mechanics (Vapi + Twilio)

1. **Twilio:** create a trial account, get a trial phone number. Twilio trial accounts can only call **verified** numbers by default — add the user's own number as verified. This is a feature here, not a limitation: it enforces the assignment's "only a number you control or have explicit permission to call" rule at the infrastructure level, not just by developer discipline.
2. **Vapi:** import the Twilio number (Vapi's own free numbers cannot make outbound calls — confirmed from Vapi docs). Create one assistant with the system prompt, voice, and the three tools pointing at the mock backend's webhook (via `ngrok` during development).
3. **Per-call personalization:** `scripts/place_call.py` calls Vapi's outbound call endpoint with `assistantOverrides.variableValues` set from the chosen customer record (confirmed mechanism — Vapi templates `{{variableName}}` into the system prompt and injects `variableValues` per call). The prompt references `{{customer_id}}` so the agent's first action is calling `check_payment_status` to pull the rest of the facts from the tool, keeping the prompt itself scenario-agnostic.
4. **Budget:** Vapi gives $10 free credit (~60+ minutes); Twilio trial accounts include their own small credit. Ten short calls (a few minutes each) comfortably fit inside this without spending anything, provided calls are kept focused.

---

## 9. Security and privacy checklist
- [ ] `.env` (Vapi API key, Twilio credentials) gitignored
- [ ] No real customer data anywhere — `data/customers.json` is 100% fictional
- [ ] No real phone numbers other than the user's own verified number
- [ ] Every mocked tool call clearly logged as mocked, never conflated with a real payment action
- [ ] Call recordings/transcripts (if kept) contain only fictional scenario data, nothing personally sensitive about a real third party
- [ ] The mock payment-link domain is `example.com`-style, not a real or real-looking URL

---

## 10. Testing plan

| Test group | Proves |
|---|---|
| `test_store` | Customer records load correctly, lookups by `customer_id` work, missing id handled |
| `test_tools` | Each tool returns the right shape; `retry_autopay_charge` returns the scenario-appropriate mocked result (success/decline) deterministically; every call is audit-logged with `mocked: true` |
| Manual Vapi dashboard test | Assistant follows the decision policy correctly against at least 3 scenarios before any real phone call is placed — cheaper and faster to iterate on than live calls |
| Live call (at least 1, ideally more) | The full path works end to end: outbound call → agent pulls customer data via tool → follows policy → mock action taken or correctly withheld → audit log entry written |

---

## 11. Build plan (phases with acceptance criteria)

| Phase | Work | Done when |
|---|---|---|
| 1. Setup (1–1.5 h) | Vapi account + $10 credit, Twilio trial account + verified number, `data/customers.json` with all 10 records | Both accounts active, records written and reviewed against section 5 |
| 2. Mock backend (2–3 h) | FastAPI app, 3 tools, audit log, tests | `pytest` green, backend runs locally, all 3 tools return correct mocked shapes |
| 3. Assistant + prompt (2–3 h) | System prompt encoding section 6's policy, tool definitions pointed at the (ngrok-tunneled) backend, manual dashboard testing against 3+ scenarios | Assistant correctly branches on dispute/expired/fraud-flag/paused cases in dashboard testing |
| 4. Outbound calling (1.5–2 h) | `place_call.py` with per-scenario variable injection, Twilio number imported into Vapi, at least one real call placed to the user's own number | A real call connects, the agent pulls the right customer record, and follows policy correctly on tape |
| 5. Run all 10 + capture (1.5–2 h) | Call (or dashboard-simulate, clearly labeled) all 10 scenarios, fill `demo/call_log.md` with real outcomes | Every scenario has a documented, policy-correct outcome |
| 6. Docs (2 h) | README, CAPABILITIES, LIMITATIONS, `demo/scenarios.md`, `demo/baseline.md` | Reviewed against section 12 |

Total: roughly 10–14 hours of focused work — comfortably inside the 48-hour window, leaving slack for Vapi/Twilio account setup friction and prompt iteration.

---

## 12. Documentation to produce

### README.md outline
1. What Redial is, in 3 sentences
2. Architecture: Vapi assistant ↔ mock backend (tools) ↔ `data/customers.json`, and how a real call flows through it
3. Setup: Vapi account, Twilio trial + number import + number verification, `.env`
4. Run: `make mock-server`, `ngrok`, `make call SCENARIO=<n>`, `pytest`
5. The decision policy (link to section 6)
6. Assumptions and what's mocked vs. real
7. Security/safety notes (the "only your own number" guard)
8. Link to `LIMITATIONS.md`

### CAPABILITIES.md
- **The agent can:** look up a customer's failed-payment status, hold a natural conversation about it, retry (mocked) or send a payment link (mocked) when appropriate, recognize disputes/expired cards/fraud flags/paused autopay and change its approach accordingly, and log every decision.
- **The agent cannot:** actually move money or send a real payment link (fully mocked in this build), call a real customer, call any number other than the one pre-approved, handle a call-back (inbound), or detect voicemail vs. a human beyond what Vapi's platform provides out of the box.
- Example questions/scenarios it handles well vs. scenarios (like a genuinely abusive or threatening caller) it's explicitly designed to escalate rather than handle.

### LIMITATIONS.md
- All payment actions are mocked — no real payment rails integrated
- Single phone number, single assistant — no multi-tenant or multi-merchant support
- No inbound handling
- Scenario coverage is 10 hand-picked cases, not exhaustive of every real-world failure mode
- Honest statement of which of the 10 scenarios were actually placed as live calls vs. verified via dashboard testing, and why
- **Long-term fix:** real payment-processor integration behind the same tool interface (so the agent code doesn't change, only what's behind `retry_autopay_charge`/`send_payment_link`), inbound call handling with call-context continuity, multi-number/multi-merchant support, and human-handoff via a real warm transfer rather than "offer to connect you"

---

## 13. Definition of done
- [ ] Mock backend implemented and tested (3 tools, audit log)
- [ ] 10 fictional customer records written, covering every branch in section 6
- [ ] Vapi assistant built with the decision-policy prompt and tools wired to the backend
- [ ] Twilio number imported, verified-number restriction confirmed as the live safety guard
- [ ] At least one real outbound call placed, recorded/transcribed, and reviewed against the policy
- [ ] All 10 scenarios have a documented outcome, honestly labeled live vs. dashboard-simulated
- [ ] README, CAPABILITIES, LIMITATIONS, `demo/scenarios.md`, `demo/call_log.md`, `demo/baseline.md` complete
- [ ] No real credentials, real phone numbers (other than the approved one), or real customer data anywhere in the repo
- [ ] Assumptions and any Vapi/Twilio behavior that differed from docs recorded

---

## 14. Instructions for the coding agent
1. Read this whole file first. Build the mock backend before touching Vapi — it's the part you can test fast and offline.
2. Never let a mocked tool call be represented as a real payment action anywhere — code, logs, transcripts, or the write-up.
3. Never dial a number other than the one the user explicitly approved. Hardcode this as a guard in `place_call.py`, don't rely on remembering not to.
4. Use only fictional data — no real names, numbers, or amounts resembling a real person's situation.
5. If Vapi or Twilio's actual behavior differs from what this brief assumes (phone number import flow, dynamic-variable mechanics, tool webhook format), don't silently work around it — note it in `LIMITATIONS.md` and tell the user.
6. Ask the user before: spending beyond the free credits on either platform, placing more than a couple of test calls while iterating (each one costs real minutes), or expanding scope beyond the 10-scenario, single-number demo.
7. When finished, produce a final checklist against section 13, stating what passed and what did not.
