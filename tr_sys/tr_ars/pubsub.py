from django.core import serializers
import sys, logging, json, threading, queue, requests
from .models import Message
from tr_ars.tasks import send_message as celery_send_message
from django.conf import settings

logger = logging.getLogger(__name__)

def send_message(actor, mesg, timeout=60):
    url = settings.DEFAULT_HOST + actor.url() # TODO get url base at server startup; no request to use build_absolute_uri()
    logger.debug('sending message %s to %s...' % (mesg.id, url))
    data = mesg.to_dict()
    data['fields']['actor'] = {
        'id': actor.id,
        'channel': actor.channel.name,
        'agent': actor.agent.name,
        'uri': url
    }
    try:
        r = requests.post(url, json=data, timeout=timeout)
        logger.debug('%d: receive message from actor %s...\n%s.\n'
                     % (r.status_code, url, str(r.text)[:500]))
        if r.status_code == 200:
            # now create a new message here
            status = 'U'
            if 'tr_ars.message.status' in r.headers:
                status = r.headers['tr_ars.message.status']
            data = dict()
            try:
                data = r.json()
            except json.decoder.JSONDecodeError:
                status = 'E'
            mesg = Message.create(code=r.status_code, status=status,
                           data=data, actor=actor,
                           name=mesg.name, ref=mesg)
            mesg.save()
    except:
        logger.exception("Can't send message to actor %s\n%s"
                     % (url,sys.exc_info()))

def send_messages(actors, messages):
    for mesg in messages:
        for actor in actors:
            if (actor == mesg.actor or len(actor.path) == 0
                or len(actor.agent.uri) == 0):
                pass
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
            if settings.USE_CELERY:
                celery_send_message.delay(actor.to_dict(), mesg.to_dict())
            else:
                send_message(actor, mesg)
            queue.task_done()
        logger.debug('%s: BackgroundWorker stopped!' % __name__)

queue = queue.Queue()
# FIXME: handle properly for deployment
if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
    BackgroundWorker().start()
