from django.core import serializers
import sys, logging, json, threading, queue, requests
from .models import Message
from tr_ars.tasks import send_message
from django.conf import settings

logger = logging.getLogger(__name__)

def send_messages(actors, messages):
    for mesg in messages:
        for actor in actors:
            if (actor == mesg.actor or len(actor.path) == 0
                or len(actor.agent.uri) == 0):
                pass
            elif settings.USE_CELERY:
                result = send_message.delay(actor.to_dict(), mesg.to_dict())
                result.forget()
            else:
                queue.put((actor, mesg))

class BackgroundWorker(threading.Thread):
    def __init__(self, **kwargs):
        super(BackgroundWorker, self).__init__(**kwargs)

    def run(self):
        logger.debug('%s: BackgroundWorker started!' % __name__)
        while True:
            actor, mesg = queue.get()
            if actor is None:
                break
            else:
                send_message(actor.to_dict(), mesg.to_dict())
            queue.task_done()
        logger.debug('%s: BackgroundWorker stopped!' % __name__)

queue = queue.Queue()
# FIXME: handle properly for deployment
if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
    BackgroundWorker().start()
