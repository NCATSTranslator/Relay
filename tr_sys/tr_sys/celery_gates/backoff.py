"""
Retry backoff helpers and the merge-lock retry budget.

These used to live next to the redis "expensive token" gate in expensive_gate.py.
The gate is gone: memory-heavy tasks are bounded by the `heavy` celery queue's
worker concurrency instead (see task_routes in tr_sys/celery.py). The helpers
stay because merge_and_post_process still retries on two things:
  - the per-parent merge db lock (constant backoff, MERGE_LOCK_MAX_RETRIES)
  - real errors (exponential backoff, MERGE_ERROR_MAX_RETRIES in tr_ars/utils.py)
"""
import os
import random

# Celery retry budget for waiting on the per-parent merge db lock. Each attempt
# waits 2-5s (constant_backoff_with_jitter), so the default is ~6 min worst case.
# Now a lock retry republishes only pks, so a generous budget is cheap.
MERGE_LOCK_MAX_RETRIES = int(os.getenv("ARS_MERGE_LOCK_MAX_RETRIES", "100"))


def exp_backoff_with_jitter(retries: int, base: int = 1, max_delay: int = 30) -> int:
    """
    Exponential backoff with jitter.
    `retries` is the current retry count (0..).

    Use this for retrying genuine failures (e.g. a downstream error), NOT for
    lock contention. Use constant_backoff_with_jitter for that.
    """
    rcount = max(0, int(retries or 0))
    delay = min(max_delay, base * (2 ** rcount))
    delay = int(delay * random.uniform(0.8, 1.2))  # first retry ~1s, next ~2s, ... capping at 30s
    return max(1, delay)


def constant_backoff_with_jitter(base: float = 2,
                                 spread: float = 3) -> float:
    """
    Short, roughly-constant backoff with jitter, for lock contention.
    Unlike exponential backoff this keeps the task re-checking on a short, steady
    cadence so a lock freed by a finishing merge is picked up within a few seconds
    instead of sitting idle for the longer delays used for failure retries. The
    delay is 2-5 seconds by default. Don't go much faster than that: each retry is a
    full round trip through the celery broker.
    """
    return base + random.random() * spread