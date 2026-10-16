from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab

from .otel_config import configure_opentelemetry

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tr_sys.settings')

configure_opentelemetry()

app = Celery('tr_sys')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure broker retry on startup
app.conf.broker_connection_retry_on_startup = True

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

app.conf.beat_schedule = {
 #Excute the timeout fucntion every 3 min
    'checking_timeout_3min':{
        'task': 'catch_timeout',
        'schedule': crontab(minute='*/3'),
    },
}
# Memory-heavy tasks ie a merge, or ingesting an ARA callback; both expand a
# multi-MB TRAPI message ~10x in memory. They go to their own queue, consumed only
# by the `heavy` worker pool. That pool's replicas x concurrency IS the
# cluster-wide cap on concurrent heavy work (it replaced the redis token gate).
# Everything else stays on the default queue so cheap tasks never wait on heavy tasks.
app.conf.task_routes = {
    "merge-and-post-process": {"queue": "heavy"},
    "ingest-ara-response": {"queue": "heavy"},
}

# this make sure that celery and rabbitMQ can reprocess the unacknowledged messages
app.conf.update(
    task_acks_late=True, #task messages will be acknowledged after the task has been executed
    task_reject_on_worker_lost=True, # allows the message to be re-queued instead if worker is killed/exited, so that the task will execute again by the same worker, or another worker.
    task_publish_retry=True, #publishing task messages will be retried in the case of connection loss
    task_default_delivery_mode='persistent',
    task_create_missing_queues=True,  # ← This one ensures auto-creation with durability
    worker_prefetch_multiplier=1,#Rabbit doesn’t dump a huge pile of messages onto workers
    worker_disable_prefetch=True,#reduce “workers reserving work they can’t start yet” which directly reduces “unacknowledged sitting around
    # useful for crash resilience,when you have task with long duration->
    # reserve one task per worker process at a time (https://docs.celeryq.dev/en/stable/userguide/optimizing.html#prefetch-limits)
)