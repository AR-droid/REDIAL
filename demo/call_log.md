# Call log

## Summary (all ten scenarios)

All calls below are real outbound Twilio calls to the approved phone, answered or left unanswered by the user. The agent is OpenAI Realtime (gpt-realtime-mini). Retry and payment-link actions are mocked: no real charge or link was created.

| # | Customer | Expected branch | Tools called | Result |
|---|---|---|---|---|
| 1 | Asha Kulkarni | Offer retry | check, retry (succeeded) | Pass (wording fixed after call) |
| 2 | Rahul Mehta | Link, not retry (2nd failure) | check, send link | Pass |
| 3 | Priya Nair | Link only (expired card) | check, send link | Pass |
| 4 | Vikram Shah | Inform only (paused autopay) | check | Pass |
| 5 | Fatima Sheikh | Offer retry, then link | check | Pass (user declined both) |
| 6 | Arjun Rao | No collection (dispute) | check | Pass |
| 7 | Divya Pillai | Time request: reminder link | send link only | Partial: check not called first. Gate added in code after the call; not re-tested on a phone. |
| 8 | Karan Malhotra | No answer | none | Pass (re-run, unanswered) |
| 9 | Sneha Reddy | Stop on amount dispute, escalate | check | Pass |
| 10 | Imran Qureshi | Link only (fraud flag) | check, send link | Pass (flag for review not possible) |

## Scenario 1: Asha Kulkarni (cust_001)

- **Call type:** real outbound call placed through Twilio, from a Twilio US number to the approved number, answered on the approved phone.
- **Twilio call SID:** CAa8c2e8733b5a51b07301a7f6c22a46f8 (completed, 38 seconds)
- **Agent:** OpenAI Realtime (`gpt-realtime-mini`) using the project's decision-policy prompt and the three tools.
- **Tools called:** `check_payment_status`, then `retry_autopay_charge` (returned `succeeded`).
- **Retry was mocked:** no real charge was attempted. The audit log (`demo/audit.jsonl`) records each tool call with `mocked: true`.
- **What the agent said:** that the payment went through. That wording was wrong for a mocked retry. 
## Scenario 2: Rahul Mehta (cust_002)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CAa9f21f240f2a99c39b63852ec99c72bf (completed, 54 seconds)
- **Tools called:** `check_payment_status`, then `send_payment_link` (returned `sent`). No retry, as the policy requires for a second failure.
- **Link is mocked:** the link returned is `https://pay.example.com/link/cust_002`, a placeholder. No real link or message was sent.
- **User confirmed:** the agent spoke on the call.

## Scenario 3: Priya Nair (cust_003)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CA8c99cab7a9a9fe681126db2b13196c25 (completed, 35 seconds)
- **Tools called:** `check_payment_status`, then `send_payment_link` (returned `sent`). No retry, as the policy requires for an expired card.
- **Link is mocked:** `https://pay.example.com/link/cust_003`, a placeholder. No real link or message was sent.
- **User report:** the call finished. The user has not yet confirmed the spoken wording for this call.

## Scenario 4: Vikram Shah (cust_004)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CA7ca4aabc24a356c3c745bc3db5458edd (completed, 37 seconds)
- **Tools called:** `check_payment_status` only. The user declined a payment link, so none was sent.
- **User report:** the user said no to the offer, and the agent replied that it understood.
- **Policy check:** the autopay was paused by the customer, so the agent informed without pressing to resume. No retry was attempted.

## Scenario 5: Fatima Sheikh (cust_005)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CAa43699f380466d29fcc8f4a9390f8df9 (completed, 62 seconds)
- **Tools called:** `check_payment_status` only.
- **User report:** the agent offered a retry, and the user declined it. The agent then offered a payment link, which the user also declined. The agent acknowledged both and offered to redirect the user.
- **Policy check:** no retry or link was sent. Declining both matches the customer's choice.
- **Note:** the agent's "redirect" offer is not a defined tool or policy row. It's a human handoff in wording only. Record this for review.

## Scenario 6: Arjun Rao (cust_006)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CAfacb1cf921e27dfc6ebb1567879c0b03 (completed, 35 seconds)
- **Tools called:** `check_payment_status` only. No retry and no payment link, as the dispute rule requires.
- **User report:** the call finished. The spoken wording has not been confirmed yet.

## Scenario 7: Divya Pillai (cust_007)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CA8d4524653d389e8b006ec04e2e42a17f (completed, 43 seconds)
- **Tools called:** `send_payment_link` only (returned `sent`). **`check_payment_status` was not called**, although the prompt requires it first on every call. This is a deviation to investigate.
- **Link is mocked:** `https://pay.example.com/link/cust_007`, a placeholder. No real link or message was sent.
- **User report:** the user asked for more time. The agent said it would send a reminder. The reminder was sent as a payment link, which matches the policy for a time request, though the link was not timed to the date the user named.

## Scenario 8: Karan Malhotra (cust_008)

- **Call type:** real outbound call placed through Twilio to the approved phone.
- **Twilio call SID:** CA58e4fdd3ca793d2ba06fc012c8390a79 (completed, 13 seconds)
- **Outcome:** the call was answered by the user, who hung up after about 13 seconds. This is **not** a no-answer result. The no-answer case was not tested.
- **Tools called:** none. No check, retry, or link.
- **Note:** a true no-answer test requires the phone to go unanswered for the whole call.

## Scenario 8 (re-run): Karan Malhotra (cust_008), no answer

- **Call type:** real outbound call placed through Twilio to the approved phone, left unanswered.
- **Twilio call SID:** CA72d4be2561eb867afdaf2767db436300
- **Twilio status:** `no-answer`, duration 0.
- **Outcome:** logged as no answer. No conversation took place, and no tools were called, so there is no audit entry. Matches the policy row for no answer.

## Scenario 9: Sneha Reddy (cust_009)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CA58bdc52c3d07593388eba95daac392e1 (completed, 47 seconds)
- **Tools called:** `check_payment_status` only. No retry and no payment link.
- **User report:** the user said the amount was wrong. The agent apologised and said it would connect them to another person.
- **Policy check:** the agent stopped pursuing payment and offered human escalation, as the policy requires. Note: the agent said it would connect the user, but no transfer tool exists. This is a spoken offer only.

## Scenario 10: Imran Qureshi (cust_010)

- **Call type:** real outbound call placed through Twilio to the approved phone, answered by the user.
- **Twilio call SID:** CAdd3ebb63dd3575e7c09500a2b6f55b82 (completed, 43 seconds)
- **Tools called:** `check_payment_status`, then `send_payment_link` (returned `sent`). **No retry**, as the fraud-flag rule requires.
- **Link is mocked:** `https://pay.example.com/link/cust_010`, a placeholder. No real link or message was sent.
- **User report:** the user asked for a retry, which the agent refused, and then accepted the link.
- **Gap:** the policy says to flag the account for human review. No tool exists for that, so the agent could not record it. Noted in LIMITATIONS when written.
- **Earlier attempt:** the first call (CAf6716aec4e4293cb2cbd51bc07b58cbc) lasted 14 seconds and the agent never spoke. No request reached the backend, so the call never reached the stream. The likely cause is that the Twilio trial key press was not completed. This is not confirmed.
