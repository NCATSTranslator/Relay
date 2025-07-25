# Create your celery tasks here
from __future__ import absolute_import, unicode_literals
import logging, requests, sys, json
from celery import shared_task
from tr_ars.models import Message, Actor, Agent
from tr_ars import utils
from celery.utils.log import get_task_logger
from django.conf import settings
from django.urls import reverse
import html
from tr_smartapi_client.smart_api_discover import SmartApiDiscover
import traceback
from django.utils import timezone
from django.shortcuts import get_object_or_404
from opentelemetry import trace
from opentelemetry.propagate import inject
# Ensure that the tracing context is properly propagated within tasks
from opentelemetry.context import attach, detach, set_value, get_current
import time as sleeptime
from .api import decrypt_secret
import hmac
import base64
import os
import hashlib
logger = get_task_logger(__name__)

def propagate_context(func):
    def wrapper(*args, **kwargs):
        token = attach(get_current())
        try:
            return func(*args, **kwargs)
        finally:
            detach(token)
    return wrapper


@shared_task(name="send-message-to-actor")
def send_message(actor_dict, mesg_dict, timeout=300):
    tracer = trace.get_tracer(__name__)
    infores=actor_dict['fields']['inforesid']
    agent= infores.split(':')[1]
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
                          ref=get_object_or_404(Message.objects.filter(pk=mesg_dict['pk'])),
                          params=mesg_dict['fields']['params'])

    if mesg.status == 'R':
        mesg.code = 202
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
    task_id=str(mesg.pk)
    with tracer.start_as_current_span(f"{agent}") as span:
        logger.debug(f"CURRENT span during task execution: {span}")
        span.set_attribute("pk", str(mesg.pk))
        span.set_attribute("ref_pk", str(mesg.ref_id))
        span.set_attribute("agent", agent)
        # Make HTTP request and trace it
        try:
            logger.debug(f"CURRENT span before request post call: {span}")
            #having to manually generate the traceparent_id since the automatic generation is disabled
            span_context = span.get_span_context()
            trace_id = span_context.trace_id
            span_id = span_context.span_id
            trace_flags = span_context.trace_flags
            # Format the traceparent header
            traceparent_header = (f"00-{trace_id:032x}-{span_id:016x}-{trace_flags:02x}")
            logging.info('POSTing to agent %s pk:%s with traceparent: %s '% (agent,task_id, traceparent_header))
            r = requests.post(url, json=data, timeout=timeout)
            span.set_attribute("http.url", url)
            span.set_attribute("http.status_code", r.status_code)
            span.set_attribute("http.method", "POST")
            span.set_attribute("task.id", task_id)
            #span.set_attribute("celery.task_id", send_message.request.id)
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
                rdata = dict()
                try:
                    rdata = r.json()
                except json.decoder.JSONDecodeError:
                    status = 'E'
                # now create a new message here
                if(endpoint)=="asyncquery":
                    if(callback is not None):
                        try:
                            ar = requests.get(callback, json=data, timeout=timeout)
                            arj=ar.json()
                            if utils.get_safe(rdata,"fields","data", "message") is None:
                                logger.debug("data field empty")
                                status = 'R'
                                status_code = 202
                            else:
                                logger.debug("data field contains "+ arj["fields"]["data"]["message"])
                                status = 'D'
                                status_code = 200
                        except json.decoder.JSONDecodeError:
                            status = 'E'
                            status_code = 422

                else:
                    logger.debug("Not async for agent: %s and endpoint: %s? " % (inforesid,query_endpoint))
                    status = 'D'
                    status_code = 200
                    results = utils.get_safe(rdata,"message","results")
                    kg = utils.get_safe(rdata,"message", "knowledge_graph")
                    #before we do basically anything else, we normalize
                    #no sense in processing something without results
                    if results is not None and len(results)>0:
                        mesg.result_count = len(rdata["message"]["results"])
                        scorestat = utils.ScoreStatCalc(results)
                        mesg.result_stat = scorestat
                        parent_pk = mesg.ref.id
                        parent = Message.objects.filter(pk=parent_pk)
                        message_to_merge=rdata
                        agent_name = str(mesg.actor.agent.name)
                        child_pk=str(mesg.pk)
                        logger.info("Running pre_merge_process for agent %s with %s" % (agent_name, len(results)))
                        utils.pre_merge_process(message_to_merge,child_pk, agent_name, inforesid)
                    #Whether we did any additional processing or not, we need to save what we have
                    mesg.code = status_code
                    mesg.status = status
                    mesg.save_compressed_dict(rdata)
                    #mesg.data = rdata
                    mesg.url = url
                    mesg.save()
                    logger.debug('+++ message saved: %s' % (mesg.pk))
            else:
                #if the tool returned something other than 200, we log as appropriate and then save
                if 'tr_ars.message.status' in r.headers:
                    status = r.headers['tr_ars.message.status']
                if r.status_code == 202:
                    status = 'R'
                    url = url[:url.rfind('/')] + '/aresponse/' + r.text
                if r.status_code >= 400:
                    if r.status_code != 503:
                        status = 'E'
                    rdata['logs'] = []
                    rdata['logs'].append(html.escape(r.text))
                    for key in r.headers:
                        if key.lower().find('tr_ars') > -1:
                            rdata['logs'].append(key+": "+r.headers[key])
                mesg.code = status_code
                mesg.status = status
                mesg.save_compressed_dict(rdata)
                #mesg.data = rdata
                mesg.url = url
                mesg.save()
                logger.debug('+++ message saved: %s' % (mesg.pk))
        #This exception is meant to handle unexpected errors in the ORIGINAL return from the ARA
        except Exception as e:
            logger.error("Unexpected error 2: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
            logger.exception("Can't send message to actor %s\n%s for pk: %s"
                             % (url,sys.exc_info(),mesg.pk))
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            status_code = 500
            status = 'E'
            mesg.code = status_code
            mesg.status = status
            mesg.save_compressed_dict(rdata)
            mesg.url = url
            mesg.save()
            logger.debug('+++ message saved: %s' % (mesg.pk))

        agent_name = str(mesg.actor.agent.name)
        if mesg.code == 200 and results is not None and len(results)>0:
            if "validate" in mesg.params.keys() and not mesg.params["validate"]:
                valid = True
            else:
                utils.remove_phantom_support_graphs(message_to_merge)
                valid = utils.validate(message_to_merge)
            if valid:
                if agent_name.startswith('ara-'):
                    logger.info("pre async call for agent %s" % agent_name)
                    # logging.debug("Merge starting for "+str(mesg.pk))
                    # new_merged = utils.merge_received(parent_pk,message_to_merge['message'], agent_name)
                    # logging.debug("Merge complete for "+str(new_merged.pk))
                    # utils.post_process(new_merged.data,new_merged.pk, agent_name)
                    # logging.debug("Post processing done for "+str(new_merged.pk))
                    #parent = get_object_or_404(Message.objects.filter(pk=parent_pk))
                    #logging.info(f'parent merged_versions_list before going into merge&post-process for pk: %s are %s' % (parent_pk,parent.merged_versions_list))
                    #utils.merge_and_post_process(parent_pk,message_to_merge['message'],agent_name)
                    #utils.merge_and_post_process(parent_pk,message_to_merge['message'],agent_name)
                    utils.merge_and_post_process.apply_async((parent_pk,message_to_merge['message'],agent_name))
                    logger.info("post async call for agent %s" % agent_name)
            else:
                logger.debug("Validation problem found for agent %s with pk %s" % (agent_name, str(mesg.ref_id)))
                code = 422
                status = 'E'
                mesg.code = code
                mesg.status = status
                mesg.save()
        else:
            logging.debug("Skipping merge and post for "+str(mesg.pk)+
                          " because the contributing message is in state: "+str(mesg.code))

@shared_task(name="catch_timeout")
def catch_timeout_async():
    now =timezone.now()
    logging.info(f'Checking timeout at {now}')
    time_threshold = now - timezone.timedelta(minutes=15)
    max_time = now-timezone.timedelta(minutes=5)
    max_time_merged=now-timezone.timedelta(minutes=8)
    max_time_pathfinder = now-timezone.timedelta(minutes=10)

    #retrieving last 15 min running records might become overwhelming, so we might need to refine this filter to grab records between 4 min< x < 15 min or have 2 sets (for standard/pathfinder) queires
    messages = Message.objects.filter(timestamp__gt=time_threshold, status__in='R').values_list('actor','id','timestamp','updated_at','params')
    for mesg in messages:
        mpk=mesg[0]
        id = mesg[1]
        actor = Agent.objects.get(pk=mpk)
        timestamp=mesg[2]
        query_type=mesg[4]['query_type'] if actor.name != 'ars-ars-agent' else None

        logging.info(f'actor: {actor} id: {mesg[1]} timestamp: {mesg[2]} updated_at {mesg[3]} query_type {query_type}')
        logging.info(f'max_time_pathfinder: {max_time_pathfinder} -- timestamp: {timestamp} -- max_time_merged: {max_time_merged} -- max_time: {max_time}')

        #exempting parents from timing out
        if actor.name == 'ars-default-agent':
            continue

        elif actor.name == 'ars-ars-agent':
            if timestamp < max_time_merged:
                logging.info('merge_agent pk: %s has been running more than 8 min, setting its code to 598')
                message = get_object_or_404(Message.objects.filter(pk=id))
                message.code = 598
                message.status = 'E'
                message.updated_at = timezone.now()
                message.save(update_fields=['status','code','updated_at'])
            else:
                continue
        else:
            if query_type == 'standard' and timestamp < max_time:
                logging.info(f'for actor: {actor.name}, and pk {str(id)} of query type: {query_type}, the status is still "Running" after 5 min, setting code to 598')
                message = get_object_or_404(Message.objects.filter(pk=id))
                message.code = 598
                message.status = 'E'
                message.updated_at = timezone.now()
                message.save(update_fields=['status','code','updated_at'])

            elif query_type == 'pathfinder' and timestamp < max_time_pathfinder:
                logging.info(f'for actor: {actor.name}, and pk {str(id)} of query type: {query_type},the status is still "Running" after 10 min, setting code to 598')
                message = get_object_or_404(Message.objects.filter(pk=id))
                message.code = 598
                message.status = 'E'
                message.updated_at = timezone.now()
                message.save(update_fields=['status','code','updated_at'])
            else:
                logging.info(f'NOT TIMING OUT for pk: {str(id)}')
                logging.info(f'{query_type} : max_time_pathfinder: {max_time_pathfinder} -- timestamp: {timestamp}')

@shared_task(name="notify_subscribers")
def notify_subscribers_task(pk, status_code, additional_notification_fields=None, count=0):
    from .models import Message
    try:
        message = get_object_or_404(Message.objects.filter(pk=pk))
        notification = {
            "pk": str(message.pk),
            "timestamp": timezone.now().isoformat(),
            "code": status_code
        }
        if additional_notification_fields:
            for k, v in additional_notification_fields.items():
                notification[k] = v

        all_subscribed_clients = message.clients.all()
        for client in all_subscribed_clients:
            callback = client.callback_url
            encrpyted_secret = client.client_secret
            encoded_master_key = os.getenv("AES_MASTER_KEY")
            master_key= base64.b64decode(encoded_master_key)
            client_secret = decrypt_secret(encrpyted_secret, master_key)
            data_json = json.dumps(notification, separators=(',', ':'), sort_keys=True).encode('utf-8') #convert notification to a consistent byte representation
            digest = hmac.new(client_secret.encode('utf-8'), data_json, hashlib.sha256).hexdigest()
            headers={
                "Content-Type": "application/json",
                "x-event-signature": digest
            }
            try:
                r = requests.post(url=callback, data=data_json, headers=headers)
                if r.status_code != 200:
                    if count <= 10:
                        count = count + 1
                        delay = 5 * pow(2, count)
                        sleeptime.sleep(delay)
                        notify_subscribers_task.apply_async((message.pk, status_code,additional_notification_fields, count))
            except Exception as e:
                logger.info("Unexpected error notifying %s about %s: %s" % (callback, str(message.pk), str(e)))

    except Message.DoesNotExist:
        logger.error(f"Message with ID {pk} does not exist")

