# Ticket-detail tail latency analysis

Branch: perf/ticket-detail-tail-latency
Base: f5dadfb

## Evidence

- The completed 50-user stage remains GREEN: 10,785 requests, P95 270 ms, P99 520 ms, two RemoteDisconnected failures, no HTTP 500/deadlock/external call.
- The 100-user stage was stopped after 366 requests. GET /api/tickets/{id} reached approximately 31 seconds maximum latency; no errors or deadlocks were observed before stop.
- The isolated runtime had one backend process, one Celery worker, SQLAlchemy default pool size 5/max overflow 10, MariaDB 10.11 and Redis 7.

## Focused reproduction

At low concurrency, representative LOADTEST tickets (IDs 325, 415, 3 and 63) completed in approximately 15–160 ms across repeated requests. The largest observed sample had only 5 replies and 7 activities. This does not support an individual oversized ticket or obvious unbounded child-record payload as the demonstrated root cause.

## Current conclusion

The extreme tail appears only under the 100-user concurrency profile and is consistent with saturation/queueing around the single backend process and database connection pool, but the available evidence does not isolate whether the dominant wait is application scheduling, pool acquisition or a specific query. No production code or pool setting was changed.

Status: YELLOW. The highest complete GREEN stage is 50 users. The 100-user run remains incomplete and no 100-user capacity claim is made.

## Next safe action

If further work is required, instrument SQLAlchemy pool checkout/wait time and per-request phase timing, then rerun the same 50-user regression before attempting 100 users. Do not add indexes, change public API, or increase pool size without measured evidence.
