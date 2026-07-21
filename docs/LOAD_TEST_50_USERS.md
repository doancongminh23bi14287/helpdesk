# Load-test 50 users

Result: GREEN with two connection-level failures

- Users: 50 (30 customer, 15 staff, 5 admin), duration 10 minutes
- Requests: 10,785; failures: 2; error rate: 0.0185%
- Failure: 2 RemoteDisconnected responses on GET /api/tickets
- Overall P95/P99: 270/520 ms
- Ticket-create P95/P99: 790/1,400 ms
- HTTP 429/500: 0/0; deadlocks: 0; external calls: 0
- Backend restart count: 0
