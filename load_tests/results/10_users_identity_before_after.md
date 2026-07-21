# Unique-identity 10-user load-test result

The corrected run used 10 unique prepared sessions in the isolated local runtime: 6 customers, 3 staff and 1 admin. Login was excluded from measured capacity traffic.

| Metric | Shared-token run | Unique-token run |
|---|---:|---:|
| Virtual users | 10 | 10 |
| Unique authenticated users | 3 | 10 |
| Unique tokens | 3 | 10 |
| Requests | 1,184 | 1,249 |
| Failures | 125 | 0 |
| Error rate | 10.56% | 0% |
| HTTP 429 | 125 | 0 |
| HTTP 500 | 0 | 0 |
| Deadlocks | 0 | 0 observed |
| Overall P95 | 100 ms | 130 ms |
| Overall P99 | 440 ms | 260 ms |
| Ticket-create failures | 0/46 | 0/58 |
| Ticket-create P95 | 740 ms | 320 ms |
| External calls | 0 | 0 observed |

Result: GREEN for the controlled 10-user safety and acceptance gate.
