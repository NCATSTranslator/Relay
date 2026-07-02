# this code holds context manager, imprts try_acqurie/release from expensive_gate.py

# Relay/tr_sys/tr_sys/celery_gates/context.py
from contextlib import contextmanager
from celery.exceptions import Retry, MaxRetriesExceededError
from .expensive_gate import (try_acquire, release, LeaseRenewer, constant_backoff_with_jitter,
                             ARS_EXPENSIVE_TOKEN_LIMIT)
from tr_ars.utils import TASK_MAX_RETRIES
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@contextmanager
def expensive_section(task_self, limit: int = ARS_EXPENSIVE_TOKEN_LIMIT, max_retries: int = TASK_MAX_RETRIES):
    """
    Usage: inside a Celery task with `bind=True`:
        with expensive_section(self, max_retries=TASK_MAX_RETRIES):
            # do expensive work
    If acquire fails -> raises self.retry(...) to requeue quickly.
    """
    # require task_self (bind=True)
    task_id = str(task_self.request.id)
    # Try to acquire; if fail -> retry after a quick delay
    try:
        if not try_acquire(task_id, limit=limit):
            delay = constant_backoff_with_jitter()
            logger.debug("Task %s could not acquire token; retrying in %.1fs (retries=%s)", task_id, delay, getattr(task_self.request, "retries", 0))
            # We raise self.retry so Celery releases the worker and requeues.
            raise task_self.retry(countdown=delay, max_retries=max_retries)
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