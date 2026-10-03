# Scenarios

Ten fictional customers, defined in `data/customers.json`. Each scenario is one call to the approved phone, with the customer ID passed in. The expected outcome comes from the decision policy (brief section 6). The recorded result for each is in [call_log.md](call_log.md).

| # | Customer | Failure | Autopay | Disputing | Expected outcome | Recorded result |
|---|---|---|---|---|---|---|
| 1 | Asha Kulkarni (cust_001) | Insufficient funds (1st) | Active | No | Offer retry | Retry offered and run (mock) |
| 2 | Rahul Mehta (cust_002) | Insufficient funds (2nd, retry_count 1) | Active | No | Offer link, not retry | Link sent (mock) |
| 3 | Priya Nair (cust_003) | Card expired | Active | No | Link only, no retry | Link sent (mock) |
| 4 | Vikram Shah (cust_004) | Card expired | Paused by customer | No | Inform only, no pressure | Declined link; no action |
| 5 | Fatima Sheikh (cust_005) | Bank declined, no reason | Active | No | Offer retry, then link if declined | Retry and link both declined by user |
| 6 | Arjun Rao (cust_006) | Insufficient funds | Active | Yes | No collection; offer a person | No retry, no link |
| 7 | Divya Pillai (cust_007) | Insufficient funds | Active | No | Customer asks for time; reminder link | Reminder link sent; status check skipped |
| 8 | Karan Malhotra (cust_008) | Card expired | Active | No | No answer; log honestly | Unanswered, logged as no-answer |
| 9 | Sneha Reddy (cust_009) | Insufficient funds | Active | No | Customer disputes amount; stop, offer a person | Stopped; offered a person (spoken offer only) |
| 10 | Imran Qureshi (cust_010) | Bank declined, fraud flag | Active | No | Link only, no retry | Retry refused; link sent (mock) |

## Notes

- Scenario 8 was first placed and answered by the user, who hung up after 13 seconds. It was re-run and left unanswered. Only the re-run counts as a no-answer.
- Scenario 4's expected policy also covers an expired card. Because the policy puts the expired-card rule first, the agent should not offer a retry in either case.
- Scenario 7 was not checked by the agent before it sent the link, which the prompt requires. This is a known defect (see LIMITATIONS).
