# this code holds context manager, imprts try_acqurie/release from expensive_gate.py

# Relay/tr_sys/tr_sys/celery_gates/context.py
from contextlib import contextmanager
from celery.exceptions import Retry, MaxRetriesExceededError
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from .expensive_gate import try_acquire, release, LeaseRenewer, exp_backoff_with_jitter, ARS_EXPENSIVE_TOKEN_LIMIT
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)
tracer = trace.get_tracer(__name__)

@contextmanager
def expensive_section(task_self, limit: int = ARS_EXPENSIVE_TOKEN_LIMIT):
    """
    Usage: inside a Celery task with `bind=True`:
        with expensive_section(self):
            # do expensive work
    If acquire fails -> raises self.retry(...) to requeue quickly.
    """
    # require task_self (bind=True)
    task_id = str(task_self.request.id)
    retries = getattr(task_self.request, "retries", 0) or 0
    delay = exp_backoff_with_jitter(getattr(task_self.request, "retries", 0))
    # We're intentionally creating two different spans here:
    # `expensive_gate.acquire` says whether this attempt got a token and how many attempts it took
    with tracer.start_as_current_span(
        "expensive_gate.acquire", record_exception=False, set_status_on_exception=False
    ) as span:
        span.set_attribute("gate.task_id", task_id)
        span.set_attribute("gate.limit", limit)
        span.set_attribute("gate.attempt", retries + 1)
        try:
            # Try to acquire; if fail -> retry right away with backoff
            acquired = try_acquire(task_id, limit=limit)
            span.set_attribute("gate.acquired", bool(acquired))
            span.set_attribute("gate.result", "acquired" if acquired else "unavailable")
            if not acquired:
                span.set_attribute("gate.retry_delay_seconds", delay)
                # Use task_self.request.retries (celery increments retries on retry()).
                logger.debug("Task %s could not acquire token; retrying in %ss (retries=%s)", task_id, delay, getattr(task_self.request, "retries", 0))
                # We raise self.retry so Celery releases the worker and requeues.
                raise task_self.retry(countdown=delay)
        except MaxRetriesExceededError:
            # Out of retries — fail gracefully and log
            span.set_attribute("gate.result", "budget_exhausted")
            span.set_status(Status(StatusCode.ERROR, "exceeded max retries waiting for an expensive token"))
            logger.warning("Task %s exceeded max retries while waiting for expensive token; failing.", task_id)
            # Optionally: raise or return. We raise to mark task as failed.
            raise


    # We have the token; start renewer to extend lease periodically
    renewer = LeaseRenewer(task_id)
    renewer.start()

    # The other span `expensive_gate.hold` shows how long this task held a token once acquired
    with tracer.start_as_current_span(
        "expensive_gate.hold", record_exception=False, set_status_on_exception=False
    ) as span:
        span.set_attribute("gate.task_id", task_id)
        span.set_attribute("gate.limit", limit)
        span.set_attribute("gate.attempt", retries + 1)
        try:
            yield
            span.set_attribute("gate.result", "completed")
        except Retry:
            span.set_attribute("gate.result", "retry")
            raise
        except Exception as e:
            span.set_attribute("gate.result", "error")
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            # stop renewing and release token (always run)
            renewer.stop()
            release(task_id)