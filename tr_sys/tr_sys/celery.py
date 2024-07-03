from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab
from opentelemetry.instrumentation.celery import CeleryInstrumentor
# from celery.signals import worker_process_init
#
# @worker_process_init.connect(weak=False)
# def init_celery_tracing(*args, **kwargs):
#     CeleryInstrumentor().instrument()

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tr_sys.settings')

app = Celery('tr_sys')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

CeleryInstrumentor().instrument()

app.conf.beat_schedule = {
 #Excute the timeout fucntion every 3 min
    'checking_timeout_3min':{
        'task': 'catch_timeout',
        'schedule': crontab(minute='*/3'),
    },
}
