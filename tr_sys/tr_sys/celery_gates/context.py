# this code holds context manager, imprts try_acqurie/release from expensive_gate.py

# Relay/tr_sys/tr_sys/celery_gates/context.py
from contextlib import contextmanager
from celery.exceptions import Retry, MaxRetriesExceededError
from .expensive_gate import try_acquire, release, LeaseRenewer, exp_backoff_with_jitter, DEFAULT_LIMIT
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@contextmanager
def expensive_section(task_self, limit: int = DEFAULT_LIMIT):
    """
    Usage: inside a Celery task with `bind=True`:
        with expensive_section(self, limit=6):
            # do expensive work
    If acquire fails -> raises self.retry(...) to requeue quickly.
    """
    # require task_self (bind=True)
    task_id = str(task_self.request.id)
    delay = exp_backoff_with_jitter(getattr(task_self.request, "retries", 0))
    # Try to acquire; if fail -> retry right away with backoff
    try:
        if not try_acquire(task_id, limit=limit):
            # Use task_self.request.retries (celery increments retries on retry()).
            logger.debug("Task %s could not acquire token; retrying in %ss (retries=%s)", task_id, delay, getattr(task_self.request, "retries", 0))
            # We raise self.retry so Celery releases the worker and requeues.
            raise task_self.retry(countdown=delay)
    except MaxRetriesExceededError:
        # Out of retries — fail gracefully and log
        logger.warning("Task %s exceeded max retries while waiting for expensive token; failing.", task_id)
        # Optionally: raise or return. We raise to mark task as failed.
        raise


    # We have the token; start renewer to extend lease periodically
    renewer = LeaseRenewer(task_id)
    renewer.start()

    try:
        yield
    finally:
        # stop renewing and release token (always run)
        renewer.stop()
        release(task_id)