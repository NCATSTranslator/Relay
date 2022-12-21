from django.core import serializers
import sys, logging, json, threading, queue, requests
from .models import Message
from tr_ars.tasks import send_message
from django.utils import timezone
from django.conf import settings
from tr_smartapi_client.smart_api_discover import Singleton

logger = logging.getLogger(__name__)

def send_messages(actors, messages):
    logger.debug("++ sending messages ++")
    for mesg in messages:
        logger.debug("message being sent: \n"+str(mesg.to_dict))
        for actor in actors:
            logger.debug("Being sent to actor: "+str(actor))
            if (actor == mesg.actor or len(actor.path) == 0
                or len(actor.agent.uri) == 0):
                pass
            #mysql vs sqlite handle this field differently; checking for both ways
            elif not actor.active or actor.active=="0":
                logger.debug("Skipping actor %s/%s; it's inactive..." % (
                    actor.agent, actor.url()))
            elif settings.USE_CELERY:
                result = send_message.delay(actor.to_dict(), mesg.to_dict())
                #logger.debug('>>>> task future: %s' % result)
                result.forget()
            else:
                queue1.put((actor, mesg))

class BackgroundWorker(threading.Thread):
    def __init__(self, **kwargs):
        super(BackgroundWorker, self).__init__(**kwargs)

    def run(self):
        logger.debug('%s: BackgroundWorker started!' % __name__)
        while True:
            actor, mesg = queue1.get()
            if actor is None:
                break
            else:
                send_message(actor.to_dict(), mesg.to_dict())
            queue1.task_done()
        logger.debug('%s: BackgroundWorker stopped!' % __name__)

queue1 = queue.Queue()
# FIXME: handle properly for deployment

class TimeoutQueue(metaclass=Singleton):
    q = queue.Queue()

    def __init__(self):
        super()

    def Add(self, record):
        self.q.put(record)

    def getQ(self):
        return self.q

    def Check(self, time):
        timeq = self.q
        first = timeq.queue[0]
        now = timezone.now()
        time_diff = now - first["timestamp"]
        if time_diff.total_seconds() > time:
            mesg = Message.objects.get(pk=first["pk"])
            if mesg.status == 'R':
                logger.info('the ARA tool has not sent their resposne back after 15min, setting status to 598')
                mesg.code = 598
                mesg.status = 'E'
                mesg.save()
            timeq.queue.popleft()
            self.Check(time)

if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
    BackgroundWorker().start()
    theQueue = TimeoutQueue()
