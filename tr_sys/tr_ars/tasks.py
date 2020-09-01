# Create your celery tasks here
from __future__ import absolute_import, unicode_literals
import logging, requests, sys, json
from celery import shared_task
from tr_ars.models import Message, Actor
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

host_name = 'http://localhost:8000' # TODO get url base at server startup; no request to use build_absolute_uri()

@shared_task
def send_message(actor_dict, mesg_dict, timeout=60):
    #logger.error(actor_dict)
    logger.info(mesg_dict)
    url = host_name + actor_dict['fields']['url']
    logger.debug('sending message %s to %s...' % (mesg_dict['pk'], url))
    data = mesg_dict
    data['fields']['actor'] = {
        'id': actor_dict['pk'],
        'channel': actor_dict['fields']['channel'], #['name'],
        'agent': actor_dict['fields']['agent'], #['name'],
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
                                  data=data, actor=Actor.objects.get(pk=actor_dict['pk']),
                                  name=mesg_dict['fields']['name'], ref=Message.objects.get(pk=mesg_dict['pk']))
            mesg.save()
    except:
        logger.exception("Can't send message to actor %s\n%s"
                         % (url,sys.exc_info()))

