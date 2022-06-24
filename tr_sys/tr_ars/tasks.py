# Create your celery tasks here
from __future__ import absolute_import, unicode_literals
import logging, requests, sys, json
from celery import shared_task
from tr_ars.models import Message, Actor
from celery.utils.log import get_task_logger
from django.conf import settings
from django.urls import reverse
import html
from celery.decorators import task
from tr_smartapi_client.smart_api_discover import SmartApiDiscover
import traceback

logger = get_task_logger(__name__)
#logger.propagate = True

@shared_task(name="send-message-to-actor")
def send_message(actor_dict, mesg_dict, timeout=300):
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
    mesg = Message.create(actor=Actor.objects.get(pk=actor_dict['pk']),
                          name=mesg_dict['fields']['name'], status='R',
                          ref=Message.objects.get(pk=mesg_dict['pk']))
    mesg.save()

    # TODO Add Translator API Version to Actor Model ... here one expects strict 0.92 format
    if 'url' in actor_dict['fields'] and actor_dict['fields']['url'].find('/ara-explanatory/api/runquery') == 0:
        pass
    else:
        callback = settings.DEFAULT_HOST + reverse('ars-messages') + '/' + str(mesg.pk)
        data['fields']['data']['callback'] = callback

    status = 'U'
    status_code = 0
    rdata = data['fields']['data']
    inforesid = actor_dict['fields']['inforesid']
    endpoint=SmartApiDiscover().endpoint(inforesid)
    params=SmartApiDiscover().params(inforesid)
    query_endpoint = (endpoint if endpoint is not None else "") + (("?"+params) if params is not None else "")

    try:
        r = requests.post(url, json=data, timeout=timeout)
        logger.debug('%d: receive message from actor %s...\n%s.\n'
                     % (r.status_code, url, str(r.text)[:500]))
        status_code = r.status_code
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
            if(endpoint)=="asyncquery":

                if(callback is not None):
                    ar = requests.get(callback, json=data, timeout=timeout)
                    arj=ar.json()
                    if(arj["fields"]["data"] is None):
                        logger.debug("data field empty")
                        status = 'R'
                        status_code=202
                    else:
                        if(arj["fields"]["data"]["message"] is None):
                            logger.debug("data field doesnt contains the message, still running... ")
                            status = 'R'
                            status_code=202
                        else:
                            logger.debug("data field contains "+ arj["fields"]["data"]["message"])
                            status = 'D'
                            status_code=200
            else:
                logger.debug("Not async? "+query_endpoint)
                status = 'D'
            if 'tr_ars.message.status' in r.headers:
                status = r.headers['tr_ars.message.status']
            rdata = dict()
            try:
                rdata = r.json()
            except json.decoder.JSONDecodeError:
                status = 'E'
        else:
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
    except Exception as e:
        logger.error("Unexpected error 2: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
        logger.exception("Can't send message to actor %s\n%s"
                         % (url,sys.exc_info()))
        status_code = 598
        status = 'E'

    mesg.code = status_code
    mesg.status = status
    mesg.data = rdata
    mesg.url = url
    mesg.save()
    logger.debug('+++ message saved: %s' % (mesg.pk))

