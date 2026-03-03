#this code holds Redis connection, Lua script registration, try_acquire(), renew(), and release(), backoff helper and lease renew thread

# Relay/tr_sys/tr_sys/celery_gates/expensive_gate.py
import os
import time
import random
import threading
from typing import Optional
import redis
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

# Config via env (set these in your Helm values / CI)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
ZKEY = os.getenv("ARS_EXPENSIVE_ZKEY", "ars:expensive_tokens")
DEFAULT_LIMIT = int(os.getenv("ARS_EXPENSIVE_LIMIT", "6"))       # default token limit
LEASE_MS = int(os.getenv("ARS_EXPENSIVE_LEASE_MS", "180000"))   # default lease 3 minutes (ms)
RENEW_EVERY_SEC = int(os.getenv("ARS_EXPENSIVE_RENEW_SEC", "60"))  # renew interval

# Redis client
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Inline Lua script: cleanup expired, check limit, add member
_ACQUIRE_LUA = """
local zkey = KEYS[1]
local now = tonumber(ARGV[1])
local lease_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

-- remove expired tokens
redis.call("ZREMRANGEBYSCORE", zkey, "-inf", now)

-- check capacity
local current = redis.call("ZCARD", zkey)
if tonumber(current) >= limit then
  return 0
end

-- add member with expiry score
redis.call("ZADD", zkey, now + lease_ms, member)
return 1
"""

_ACQUIRE_SCRIPT = None


def _load_acquire_script():
    global _ACQUIRE_SCRIPT
    if _ACQUIRE_SCRIPT is None:
        _ACQUIRE_SCRIPT = r.register_script(_ACQUIRE_LUA)
    return _ACQUIRE_SCRIPT


def now_ms() -> int:
    return int(time.time() * 1000)


def try_acquire(task_id: str, limit: Optional[int] = None) -> bool:
    """
    Atomically attempt to acquire a lease token for task_id.
    Returns True when token claimed, False otherwise.
    """
    if limit is None:
        limit = DEFAULT_LIMIT
    script = _load_acquire_script()
    try:
        res = script(keys=[ZKEY], args=[now_ms(), LEASE_MS, limit, task_id])
        logger.warning("try_acquire task=%s limit=%s res=%s redis=%s zkey=%s",
                    task_id, limit, res, REDIS_URL, ZKEY)
        return bool(res)
    except redis.RedisError:
        # On Redis failure, be conservative and deny (or you can choose to allow)
        return False


def renew(task_id: str) -> None:
    """Extend the lease for this task if it still exists."""
    score = r.zscore(ZKEY, task_id)
    if score is not None:
        # set new score = now + lease_ms
        r.zadd(ZKEY, {task_id: now_ms() + LEASE_MS})


def release(task_id: str) -> None:
    """Release the token (remove the member)."""
    try:
        r.zrem(ZKEY, task_id)
    except redis.RedisError:
        # best-effort
        pass


def exp_backoff_with_jitter(retries: int, base: int = 1, max_delay: int = 60) -> int:
    """
    Exponential backoff with jitter.
    `retries` is the current retry count (0..).
    """
    rcount = max(0, int(retries or 0))
    delay = min(max_delay, base * (2 ** rcount))
    delay = int(delay * random.uniform(0.8, 1.2)) #makes first retry ~2sec, next ~4sec, etc. capping at 30 sec
    return max(1, delay)


class LeaseRenewer:
    """
    Background renewer thread to keep a token alive while the task runs.
    Call start() right after acquiring, and stop() in finally.
    """
    def __init__(self, task_id: str, interval: Optional[int] = None):
        self.task_id = task_id
        self.interval = interval or RENEW_EVERY_SEC
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        # thread will exit soon

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                renew(self.task_id)
            except Exception:
                # best-effort: ignore and continue
                pass