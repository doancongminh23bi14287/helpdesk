# Load-test 100 users

Result: PARTIAL / STOPPED

- Configuration: 100 users, spawn rate 5/s, target duration 10 minutes
- Completed before stop: 366 requests, 0 failures observed
- No 429, 500 or deadlock observed in the partial run
- GET /api/tickets/[id] reached 31,105 ms maximum latency
- Partial overall P95/P99: 610/1,000 ms; maximum: 31,000 ms
- The run was stopped because the ordinary endpoint latency showed a bottleneck and the 100-user result is not a complete capacity measurement.
