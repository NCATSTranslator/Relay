# Create your celery tasks here
from __future__ import absolute_import, unicode_literals
import logging, requests, sys, json
from celery import shared_task
from tr_ars.models import Message, Actor
from celery.utils.log import get_task_logger
from django.conf import settings
import html

logger = get_task_logger(__name__)

@shared_task
def send_message(actor_dict, mesg_dict, timeout=60):
    logger.info(mesg_dict)
    url = settings.DEFAULT_HOST + actor_dict['fields']['url']
    logger.debug('sending message %s to %s...' % (mesg_dict['pk'], url))
    data = mesg_dict
    data['fields']['actor'] = {
        'id': actor_dict['pk'],
        'channel': actor_dict['fields']['channel'],
        'agent': actor_dict['fields']['agent'],
        'uri': url
    }
    try:
        r = requests.post(url, json=data, timeout=timeout)
        logger.debug('%d: receive message from actor %s...\n%s.\n'
                     % (r.status_code, url, str(r.text)[:500]))
        url = r.url
        if 'tr_ars.url' in r.headers:
            url = r.headers['tr_ars.url']
        # status defined in https://github.com/NCATSTranslator/ReasonerAPI/blob/master/TranslatorReasonerAPI.yaml
        # paths: /query: post: responses:
        # 200 = OK. There may or may not be results. Note that some of the provided
        #             identifiers may not have been recognized.
        # 202 = Accepted. Poll /aresponse for results.
        # 400 = Bad request. The request is invalid according to this OpenAPI
        #             schema OR a specific identifier is believed to be invalid somehow
        #             (not just unrecognized).
        # 500 = Internal server error.
        # 501 = Not implemented.
        # Message.STATUS
        # ('D', 'Done'),
        # ('S', 'Stopped'),
        # ('R', 'Running'),
        # ('E', 'Error'),
        # ('W', 'Waiting'),
        # ('U', 'Unknown')
        if r.status_code == 200:
            # now create a new message here
            status = 'D'
            if 'tr_ars.message.status' in r.headers:
                status = r.headers['tr_ars.message.status']
            rdata = dict()
            try:
                rdata = r.json()
            except json.decoder.JSONDecodeError:
                status = 'E'
            mesg = Message.create(code=r.status_code, status=status,
                                  data=rdata, url=url,
                                  actor=Actor.objects.get(pk=actor_dict['pk']),
                                  name=mesg_dict['fields']['name'],
                                  ref=Message.objects.get(pk=mesg_dict['pk']))
            mesg.save()
        else:
            status = 'U'
            rdata = data['fields']['data']['message']
            if r.status_code == 202:
                status = 'W'
                url = url[:url.rfind('/')] + '/aresponse/' + r.text
            if r.status_code >= 400:
                if r.status_code != 503:
                    status = 'E'
                rdata['logs'] = []
                rdata['logs'].append(html.escape(r.text))
                for key in r.headers:
                    if key.lower().find('tr_ars') > -1:
                        rdata['logs'].append(key+": "+r.headers[key])
            mesg = Message.create(code=r.status_code, status=status,
                                  url = url,
                                  data = rdata,
                                  actor=Actor.objects.get(pk=actor_dict['pk']),
                                  name=mesg_dict['fields']['name'],
                                  ref=Message.objects.get(pk=mesg_dict['pk']))
            logger.debug('+++ message created: %s' % (mesg.pk))
            mesg.save()
            logger.debug('+++ message saved: %s' % (mesg.pk))
    except:
        logger.exception("Can't send message to actor %s\n%s"
                         % (url,sys.exc_info()))

