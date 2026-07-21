# Load-test capacity summary

| Users | Duration | Requests | Error rate | P95 | P99 | Ticket P95 | 429 | 500 | Deadlocks | Result |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 5 min | 1,249 | 0% | 130 ms | 260 ms | 320 ms | 0 | 0 | 0 | GREEN |
| 25 | 5 min | 2,903 | 0% | 130 ms | 310 ms | 450 ms | 0 | 0 | 0 | GREEN |
| 50 | 10 min | 10,785 | 0.0185% | 270 ms | 520 ms | 790 ms | 0 | 0 | 0 | GREEN* |
| 100 | stopped early | 366 partial | 0% observed | 610 ms partial | 1,000 ms partial | not stable | 0 | 0 | 0 | PARTIAL/YELLOW |

*The 50-user stage had two RemoteDisconnected failures; no HTTP 500, deadlock or external side effect occurred.

Environment: isolated Docker MariaDB/Redis, one backend process, one Celery worker, no Beat, SQLAlchemy default pool size 5/max overflow 10, synthetic organisation only.

The highest complete GREEN stage is 50 users. The 100-user run is not a capacity claim.
