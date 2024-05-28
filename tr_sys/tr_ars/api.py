from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
from django.shortcuts import redirect, get_object_or_404
from django.urls import path, re_path, include, reverse
from django.utils import timezone
from tr_ars import utils
from utils2 import urlRemoteFromInforesid
from .models import Agent, Message, Channel, Actor
import json, sys, logging
import traceback
from inspect import currentframe, getframeinfo
from tr_ars import status_report
from datetime import datetime, timedelta
#from tr_ars.tasks import send_message
import ast
from tr_smartapi_client.smart_api_discover import ConfigFile


#from reasoner_validator import validate_Message, ValidationError, validate_Query

logger = logging.getLogger(__name__)

def index(req):
    logger.debug("entering index")
    data = dict()
    data['name'] = "Translator Autonomous Relay System (ARS) API"
    data['entries'] = []
    for item in apipatterns:
        try:
            data['entries'].append(req.build_absolute_uri(reverse(item.name)))
        except Exception as e:
            logger.error("Unexpected error 17: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
            data['entries'].append(req.build_absolute_uri() + str(item.pattern))
    return HttpResponse(json.dumps(data, indent=2),
                        content_type='application/json', status=200)

def api_redirect(req):
    logger.debug("api redirecting")
    response = redirect(reverse('ars-api'))
    return response


DEFAULT_ACTOR = {
    'channel': ['general'],
    'agent': {
        'name': 'ars-default-agent',
        'uri': ''
    },
    'path': '',
    'inforesid': ''
}
WORKFLOW_ACTOR = {
    'channel': ['workflow'],
    'agent': {
        'name': 'ars-workflow-agent',
        'uri': ''
    },
    'path': '',
    'inforesid': ''
}
ARS_ACTOR = {
    'channel': [],
    'agent': {
        'name': 'ars-ars-agent',
        'uri': ''
    },
    'path': '',
    'inforesid': 'ARS'
}

def get_default_actor():
    # default actor is the first actor initialized in the database per
    # apps.setup_schema()
    return get_or_create_actor(DEFAULT_ACTOR)[0]
def get_workflow_actor():
    # default actor is the first actor initialized in the database per
    # apps.setup_schema()
    return get_or_create_actor(WORKFLOW_ACTOR)[0]
def get_ars_actor():
    return get_or_create_actor(ARS_ACTOR)[0]
@csrf_exempt
def submit(req):
    logger.debug("submit")
    """Query submission"""
    logger.debug("entering submit")
    if req.method != 'POST':
        return HttpResponse('Only POST is permitted!', status=405)

    try:
        logger.debug('++ submit: %s' % req.body)
        data = json.loads(req.body)
        # if 'message' not in data:
        #     return HttpResponse('Not a valid Translator query json', status=400)
        # create a head message
        # try:
        #     validate_Query(data)
        # except ValidationError as ve:
        #     logger.debug("Warning! Input query failed TRAPI validation "+str(data))
        #     logger.debug(ve)
        #     return HttpResponse('Input query failed TRAPI validation',status=400)
        if("workflow" in data):
            wf = data["workflow"]
            if(isinstance(wf,list)):
                if(len(wf)>0):
                    message = Message.create(code=202, status='Running', data=data,
                                             actor=get_workflow_actor())
                    logger.debug("Sending message to workflow runner")#TO-DO CHANGE
                    # message.save()
                    # send_message(get_workflow_actor().to_dict(),message.to_dict())
                    # return HttpResponse(json.dumps(data, indent=2),
                    #                     content_type='application/json', status=201)
        else:
            message = Message.create(code=202, status='Running', data=data,
                              actor=get_default_actor())

        if 'name' in data:
            message.name = data['name']
        # save and broadcast

        message.save()
        data = message.to_dict()
        return HttpResponse(json.dumps(data, indent=2),
                            content_type='application/json', status=201)
    except Exception as e:
        logger.error("Unexpected error 10: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
        logging.info(e, exc_info=True)
        logging.info('error message %s' % str(e))
        logging.info(e.__cause__)
        logging.error(type(e).__name__)
        logging.error(e.args)
        return HttpResponse('failing due to %s with the message %s' % (e.__cause__, str(e)), status=400)

@csrf_exempt
def messages(req):
    logger.debug("entering messages endpoint")

    if req.method == 'GET':
        response = []
        for mesg in Message.objects.order_by('-timestamp')[:10]:
            response.append(get_object_or_404(Message.objects.filter(pk=mesg.pk)).to_dict())
        return HttpResponse(json.dumps(response),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            #if 'actor' not in data:
            #    return HttpResponse('Not a valid ARS json', status=400)

            actor = Agent.objects.get(pk=data['actor'])
            # logger.debug('*** actor: %s' % actor)

            mesg = Message.create(name=data['name'], status=data['status'],
                           actor=actor)
            if 'data' in data and data['data'] != None:
                mesg.save_compressed_dict(data['data'])
            if 'url' in data and data['url'] != None:
                mesg.url = data['url']
            if 'ref' in data and data['ref'] != None:
                rid = int(data['ref'])
                mesg.ref = get_object_or_404(Message.objects.filter(pk=rid))
            mesg.save()
            return HttpResponse(json.dumps(mesg.to_dict(), indent=2),
                                status=201)

        except Message.DoesNotExist:
            return HttpResponse('Unknown state reference %s' % rid, status=404)

        except Actor.DoesNotExist:
            return HttpResponse('Unknown actor: %s!' % data['actor'],
                                status=404)
        except Exception as e:
            logger.error("Unexpected error 11: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))

        return HttpResponse('Internal server error', status=500)


def trace_message_deepfirst(node):
    logger.debug('entering trace_message_deepfirst')

    children = Message.objects.filter(ref__pk=node['message'])
    logger.debug('%s: %d children' % (node['message'], len(children)))
    for child in children:
        if child.actor.inforesid == 'ARS':
            pass
        else:
            channel_names=[]
            for ch in child.actor.channel:
                channel_names.append(ch['fields']['name'])
            n = {
                'message': str(child.id),
                'status': dict(Message.STATUS)[child.status],
                'parent' : str(node['message']),
                'result_count' : str(child.result_count),
                'result_stat' : child.result_stat,
                #This cast to Int shouldn't be necessary, but it is coming through as Str in the CI environment despite
                #having the same code base deployed there as in environments where it is working correctly
                'code': int(child.code),
                'actor': {
                    'pk': child.actor.pk,
                    'inforesid': child.actor.inforesid,
                    'channel': channel_names,
                    'agent': child.actor.agent.name,
                    'path': child.actor.path
                },
                'result_count': child.result_count,
                'children': []
            }
            trace_message_deepfirst(n)
            node['children'].append(n)


def trace_message(req, key):
    logger.debug("entering trace_message")
    try:
        mesg = get_object_or_404(Message.objects.filter(pk=key))
        channel_names=[]
        for ch in mesg.actor.channel:
            channel_names.append(ch['fields']['name'])
        n_merged={}
        if mesg.code == 200:
            merged_pk = mesg.merged_version_id
            logger.info('the last merged pk is %s'% str(merged_pk))
            if merged_pk is not None:
                merged_msg = get_object_or_404(Message.objects.filter(pk=merged_pk))
                n_merged = {
                    'message': str(merged_pk),
                    'status': dict(Message.STATUS)[merged_msg.status],
                    'parent': str(mesg.id),
                    'result_count': str(merged_msg.result_count),
                    'result_stat': merged_msg.result_stat,
                    'code': int(merged_msg.code),
                    'actor': {
                        'pk': merged_msg.actor_id,
                        'inforesid': merged_msg.actor.inforesid,
                        'agent': merged_msg.actor.agent.name
                    },
                    'children': []
                }
        tree = {
            'message': str(mesg.id),
            'status': dict(Message.STATUS)[mesg.status],
            'code':mesg.code,
            'retain': mesg.retain,
            'timestamp': str(mesg.timestamp),
            'updated_at': str(mesg.updated_at),
            'actor': {
                'pk': mesg.actor.pk,
                'inforesid': mesg.actor.inforesid,
                #'channel': mesg.actor.channel.name,
                'channel':channel_names,
                'agent': mesg.actor.agent.name,
                'path': mesg.actor.path
            },
            'result_count': mesg.result_count,
            'merged_version': str(mesg.merged_version_id),
            'merged_versions_list':str(mesg.merged_versions_list),
            'children': []
        }
        if n_merged:
            tree['children'].append(n_merged)
        trace_message_deepfirst(tree)
        return HttpResponse(json.dumps(tree, indent=2),
                            content_type='application/json',
                            status=200)
    except Message.DoesNotExist:
        logger.debug('Unknown message: %s' % key)
        return HttpResponse('Unknown message: %s' % key, status=404)
    return HttpResponse('Internal server error', status=500)

@csrf_exempt
def get_report(req,inforesid):
    try:
        report={}
        now =timezone.now()
        if req.method == 'GET':

            time_threshold = now - timezone.timedelta(hours=24)
            messages = Message.objects.filter(timestamp__gt=time_threshold,actor__inforesid__iendswith=inforesid).values_list('code','id','timestamp','updated_at','result_count')
            for msg in messages:
                code = msg[0]
                mid = msg[1]
                time_start = msg[2]
                time_end = msg[3]
                time_elapsed = time_end - time_start
                result_count = msg[4]
                report[str(mid)]= {"status_code":code, "time_elapsed":str(time_elapsed), "result_count":result_count, "created_at":str(time_start), "updated_at": str(time_end)}
            return HttpResponse(json.dumps(report, indent=2), content_type='text/plain',
                                status=200)
    except Exception as e:
        print(e.__traceback__)
        print(inforesid)

def filter_message_deepfirst(rdata, filter, arg):

    results = rdata['message']['results']
    kg_nodes = rdata['message']['knowledge_graph']['nodes']
    
    if filter == 'hop':
        filter_response = utils.hop_level_filter(results, arg)
    elif filter == 'score':
        filter_response = utils.score_filter(results, arg)
    elif filter == 'node_type':
        filter_response = utils.node_type_filter(kg_nodes, results, arg)
    elif filter == 'spec_node':
        filter_response = utils.specific_node_filter(results, arg)

    rdata['message']['results'] = filter_response
    final_result_count = len(filter_response)
    return rdata, final_result_count

def filter_message(key, filter_arg_list):
    mesg = get_object_or_404(Message.objects.filter(pk=key))
    if str(mesg.actor.agent.name) == 'ars-default-agent':
        new_mesg = Message.create(actor=get_default_actor(), code=200, status='Done')
        new_id=new_mesg.pk
        new_mesg.save_compressed_dict(mesg.data)
        new_mesg.save()
        children = Message.objects.filter(ref__pk=str(mesg.pk))
        for child in children:
            if child.status == "D" and child.result_count != 0 and child.result_count is not None:
                child_dict = child.to_dict()
                rdata = child_dict['fields']['data']
                for fil in filter_arg_list:
                    filter_type = fil[0]
                    filter_value = fil[1]
                    rdata, final_result_count = filter_message_deepfirst(rdata, filter_type, filter_value)
                child_mesg = Message.create(actor=Actor.objects.get(pk=int(child.actor_id)), ref=get_object_or_404(Message.objects.filter(pk=new_mesg.pk)), code=200, status='Done')
                child_mesg.result_count = final_result_count
                child_mesg.save_compressed_dict(rdata)
                child_mesg.save()
        return redirect('/ars/api/messages/'+str(new_id)+'?trace=y')
    else:
        if mesg.status == "D" and mesg.result_count != 0:
            mesg_dict = mesg.to_dict()
            rdata = mesg_dict['fields']['data']
            for fil in filter_arg_list:
                filter_type = fil[0]
                filter_value = fil[1]
                rdata, final_result_count = filter_message_deepfirst(rdata, filter_type, filter_value)
            child_mesg = Message.create(actor=Actor.objects.get(pk=int(mesg.actor_id)), code=200, status='Done')
            child_mesg.result_count = final_result_count
            child_mesg.save_compressed_dict(rdata)
            child_mesg.save()
            new_id=child_mesg.id
        else:
            return HttpResponse('message doesnt have results or marked as "Done"', status=400)

        return redirect('/ars/api/messages/'+str(new_id)+'?trace=y')

@csrf_exempt
def filter(req, key):
    logger.debug("entering filter endpoint %s " % key)
    if req.method == 'GET':
        filter_dict = dict(req.GET.lists())
        filter_arg_list=[]
        for filter_type, value in filter_dict.items():
            filter_value = ast.literal_eval(value[0])
            filter_arg_list.append([filter_type, filter_value])

        return filter_message(key, filter_arg_list)

    return HttpResponse('Only GET & POST are permitted!', status=405)

@csrf_exempt
def filters(req):
    if req.method == 'GET':
        filters={
            'hop_level': {'default': int(3), 'description': 'Returns a new message pk with results that contain N nodes or less. Takes one Int parameter, the number of nodes desired',
                            'example_url': 'https://ars-prod.transltr.io/ars/api/filter/{pk}?hop=3'},
            'score_level': {'default': [20, 80], 'description': 'Returns a new message pk with results that have normalized scores between a desired range. Takes a list of min and max values to filter on',
                            'example_url': 'https://ars-prod.transltr.io/ars/api/filter/{pk}?score=[20,80]'},
            'node_type': {'default': ['ChemicalEntity', 'BiologicalEntity'], 'description': 'Returns a new message pk with results that dont hold the given node category. Takes a list of node categories to be eliminated',
                          'example_url': 'https://ars-prod.transltr.io/ars/api/filter/{pk}?node_type=["ChemicalEntity","BiologicalEntity"]'},
            'spec_node': {'default': ['NCBIGene:2064', 'MONDO:0005147'], 'description': 'Returns a new message pk with results that dont hold the given node Curie. Takes a list of node Curies to be eliminated',
                          'example_url': 'https://ars-prod.transltr.io/ars/api/filter/{pk}?spec_node=["NCBIGene:2064","MONDO:0005147"]'},
            'multi-filtering': {
            'example_url':'https://ars-prod.transltr.io/ars/api/filter/{pk}?hop=3&score=[20,80]&node_type=["ChemicalEntity","BiologicalEntity"]&spec_node=["NCBIGene:2064","MONDO:0005147"]'
            }
        }
    return HttpResponse(json.dumps(filters, indent=2),
                            content_type='application/json', status=200)

@csrf_exempt
def latest_pk(req, n):
    logger.debug("entering latest_pk endpoint")
    response = {}
    response[f'pk_count_last_{n}_days']={}
    response[f'latest_{n}_pks']=[]
    if req.method == 'GET':
        for actor in Actor.objects.all():
            if actor.agent.name == 'ars-default-agent':
                actor_id = actor.id

        end_date = timezone.now()
        start_date = end_date - timedelta(days=n)

        while start_date <= end_date:
        
            mesg_list = Message.objects.values('id').filter(timestamp__date=start_date, actor=actor_id)
            response[f'pk_count_last_{n}_days'][f'{start_date.date()}'] = len(mesg_list)
            start_date += timedelta(days=1)

        mesg_list = Message.objects.values('actor','timestamp','id').filter(actor=actor_id).order_by('-timestamp')[:n]
        for mesg in mesg_list:
            response[f'latest_{n}_pks'].append(str(mesg['id']))

        return HttpResponse(json.dumps(response, indent=2),
                            status=200)

@csrf_exempt
def message(req, key):
    logger.debug("entering message endpoint %s " % key)

    if req.method == 'GET':
        if req.GET.get('trace', False):
            return trace_message(req, key)
        try:
            mesg = get_object_or_404(Message.objects.filter(pk=key))
            #UI has stated that just the data field is sufficient for the compressed version, but it should be noted
            #that this does not return any fields other than data.
            if req.GET.get('compress',False):

                data = mesg.data
                if data.startswith(b'\x1f\x8b'):
                    return HttpResponse(data, content_type='application/octet-stream')
                else:
                    stringv= data.decode('utf-8')
                    json_data= json.loads(stringv)
                    mesg.save_compressed_dict(json_data)
                    return HttpResponse(mesg.data, content_type='application/octet-stream')



            actor = Actor.objects.get(pk=mesg.actor_id)
            mesg.name = actor.agent.name
            mesg_dict = mesg.to_dict()
            code=utils.get_safe(mesg_dict,"fields","code")
            if code is not None:
                mesg_dict['fields']['code']=int(code)

            return HttpResponse(json.dumps(mesg_dict, indent=2),
                                status=200)

        except Message.DoesNotExist:
            return HttpResponse('Unknown message: %s' % key, status=404)

    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            #if 'query_graph' not in data or 'knowledge_graph' not in data or 'results' not in data:
            #    return HttpResponse('Not a valid Translator API json', status=400)
            mesg = get_object_or_404(Message.objects.filter(pk=key))
            status = 'D'
            code = 200
            if 'tr_ars.message.status' in req.headers:
                status = req.headers['tr_ars.message.status']
            res=utils.get_safe(data,"message","results")
            kg = utils.get_safe(data,"message", "knowledge_graph")
            actor = Actor.objects.get(pk=mesg.actor_id)
            inforesid =actor.inforesid
            logging.info('received msg from agent: %s with parent pk: %s' % (str(inforesid), str(mesg.ref_id)))
            if mesg.result_count is not None and mesg.result_count >0:
                return HttpResponse('ARS already has a response with: %s results for pk %s \nWe are temporarily '
                                   'disallowing subsequent updates to PKs which already have results\n'
                                   % (str(len(res)), str(key)),status=409)

            if mesg.status=='E':
                return HttpResponse("Response received but Message is already in state "+str(mesg.code)+". Response rejected\n",status=400)
            if res is not None and len(res)>0:
                mesg.result_count = len(res)
                scorestat = utils.ScoreStatCalc(res)
                mesg.result_stat = scorestat
                #before we do basically anything else, we normalize
                parent_pk = mesg.ref_id
                #message_to_merge =utils.get_safe(data,"message")
                message_to_merge = data
                agent_name = str(mesg.actor.agent.name)
                logger.info("Running pre_merge_process for agent %s with %s" % (agent_name, len(res)))
                utils.pre_merge_process(message_to_merge,key, agent_name, inforesid)
                if mesg.data and 'results' in mesg.data and mesg.data['results'] != None and len(mesg.data['results']) > 0:
                    mesg = Message.create(name=mesg.name, status=status, actor=mesg.actor, ref=mesg)
                valid = utils.validate(data)
                if valid:
                    if agent_name.startswith('ara-'):
                        logger.info("pre async call for agent %s" % agent_name)
                        #utils.merge_and_post_process(parent_pk,message_to_merge['message'],agent_name)
                        utils.merge_and_post_process.apply_async((parent_pk,message_to_merge['message'],agent_name))
                        logger.info("post async call for agent %s" % agent_name)
                else:
                    logger.debug("Validation problem found for agent %s with pk %s" % (agent_name, str(mesg.ref_id)))
                    code = 422
                    status = 'E'
                    mesg.status = status
                    mesg.code = code
                    mesg.save_compressed_dict(data)
                    mesg.save()
                    return HttpResponse("Problem with TRAPI Validation",
                                        status=422)

            mesg.status = status
            mesg.code = code
            mesg.save_compressed_dict(data)
            if len(res) == 0 and res is not None:
                mesg.result_count = 0
            mesg.save()

            return HttpResponse(json.dumps(mesg.to_dict(), indent=2),
                                status=201)

        except Message.DoesNotExist:
            return HttpResponse('Unknown state reference %s' % key, status=404)

        except json.decoder.JSONDecodeError:
            return HttpResponse('Can not decode json:<br>\n%s for the pk: %s' % (req.body, key), status=500)

        except Exception as e:
            mesg.status = 'E'
            mesg.code = 500
            log_entry = {
                "message":"Internal ARS Server Error",
                "timestamp":mesg.updated_at,
                "level":"ERROR"
            }
            if 'logs' in data.keys():
                data['logs'].append(log_entry)
            else:
                data['logs'] = [log_entry]
            mesg.save_compressed_dict(data)
            #mesg.data = data
            mesg.save()
            logger.error("Unexpected error 12: {} with the pk: %s".format(traceback.format_exception(type(e), e, e.__traceback__), key))

            return HttpResponse('Internal server error', status=500)

    else:
        return HttpResponse('Method %s not supported!' % req.method, status=400)


@csrf_exempt
def channels(req):
    if req.method == 'GET':
        channels = Channel.objects.order_by('name')
        return HttpResponse(serializers.serialize('json', channels),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        code = 200
        try:
            data = json.loads(req.body)
            if 'model' in data and 'tr_ars.channel' == data['model']:
                data = data['fields']

            if 'name' not in data:
                return HttpResponse('JSON does not contain "name" field',
                                    status=400)
            channel, created = Channel.objects.get_or_create(
                name=data['name'], defaults=data)
            status = 201
            if not created:
                if 'description' in data:
                    channel.description = data['description']
                    channel.save()
                status = 302
            data = channel.to_dict()
            return HttpResponse(json.dumps(data, indent=2),
                                content_type='application/json', status=status)
        except Exception as e:
            logger.error("Unexpected error 13: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
            return HttpResponse('Internal server error', status=500)
    return HttpResponse('Unsupported method %s' % req.method, status=400)


def get_or_create_agent(data):
    defs = {
        'uri': data['uri']
    }
    if 'description' in data:
        defs['description'] = data['description']
    if 'contact' in data:
        defs['contact'] = data['contact']
    agent, created = Agent.objects.get_or_create(
        name=data['name'], defaults=defs)

    status = 201
    if not created:
        if data['uri'] != agent.uri:
            # update uri
            agent.uri = data['uri']
            agent.save()
        status = 302
    data = agent.to_dict()
    return data, status

@csrf_exempt
def agents(req):
    if req.method == 'GET':
        agents = Agent.objects.order_by('name')
        return HttpResponse(serializers.serialize('json', agents),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            logger.debug('%s: payload...\n%s' % (req.path, str(req.body)[:500]))
            if 'model' in data and 'tr_ars.agent' == data['model']:
                # this in the serialized model of agent
                data = data['fields']

            if 'name' not in data or 'uri' not in data:
                return HttpResponse(
                    'JSON does not contain "name" and "uri" fields',
                    status=400)

            data, status = get_or_create_agent(data)
            return HttpResponse(json.dumps(data, indent=2),
                                content_type='application/json', status=status)
        except Exception as e:
            logger.error("Unexpected error 14: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
            return HttpResponse('Not a valid json format', status=400)
    return HttpResponse('Unsupported method %s' % req.method, status=400)


def get_agent(req, name):
    try:
        agent = Agent.objects.get(name=name)
        data = agent.to_dict()
        return HttpResponse(json.dumps(data, indent=2),
                            content_type='application/json', status=200)
    except Agent.DoesNotExist:
        return HttpResponse('Unknown agent: %s' % name, status=400)


def get_or_create_actor(data):
    config = ConfigFile('config.yaml')
    config_map = config.get_map()
    inactive_actors = config_map['inactive_clients']

    if ('channel' not in data or 'agent' not in data or 'path' not in data):
        return HttpResponse(
            'JSON does not contain "channel", "agent", and "path" fields',
            status=400)

    channel = data['channel']
    temp_channel=[]
    if isinstance(channel,list):
        for item in channel:
            if isinstance(item, int):
                temp_channel.append(Channel.objects.get(pk=item))
            elif item.isnumeric():
                # primary channel key
                temp_channel.append(Channel.objects.get(pk=int(item)))
            else:
                # name
                channel_by_name, created = Channel.objects.get_or_create(name=item)
                temp_channel.append(channel_by_name)
                if created:
                    logger.debug('%s:%d: new channel created "%s"'
                                 % (__name__, getframeinfo(currentframe()).lineno,
                                    data['channel']))

    channel = temp_channel
    agent = data['agent']

    if isinstance(agent, int):
        agent = Agent.objects.get(pk=agent)
    elif isinstance(agent, str):
        if agent.isnumeric():
            agent = Agent.objects.get(pk=int(agent))
        else:
            agent = Agent.objects.get(name=agent)
    else:
        if 'name' in agent and 'uri' in agent:
            agent, created = Agent.objects.get_or_create(
                name=agent['name'], uri=agent['uri'])
            if created:
                logger.debug('%s:%d: new agent created "%s"'
                             % (__name__, getframeinfo(currentframe()).lineno,
                                data['agent']))
        else:
            return HttpResponse('Invalid agent object: %s' % data['agent'])

    if 'remote' not in data:
        data['remote'] = None
    inforesid = data['inforesid']
    created = False
    inforesid_update=False
    try:
        actor = Actor.objects.get(
             agent=agent, path=data['path'])
        if inforesid in inactive_actors:
            actor.active=False
        if (actor.inforesid is not None):
            if not actor.inforesid == inforesid:
                inforesid_update=True
        else:
            inforesid_update=True
        if (inforesid_update):
            actor.inforesid=inforesid
            actor.save()
        #This catches initial cases where an Actor had been created in the older way with Channel being an Int not List
        if(actor.channel != channel):
            actor.channel = json.loads(serializers.serialize('json',channel))
            actor.save()
        status = 302
    #TODO Exceptions as part of flow control?  Is this Django or have I done a bad?
    except Actor.DoesNotExist:
           logger.debug("No such actor found for "+inforesid)
           #JSON serializer added for 'channel' as we are now using a list that we're approximating by using a JSON
           #because Django's db models do not support List fields in SQLite
           if inforesid in inactive_actors:
               active=False
           else:
               active=True
           actor, created = Actor.objects.update_or_create(
               channel=json.loads(serializers.serialize('json',channel)), agent=agent, path=data['path'], inforesid=inforesid, active=active)
           status = 201

    #Testing Code Above

    return (actor, status)


@csrf_exempt
def actors(req):
    if req.method == 'GET':
        actors = []
        for a in Actor.objects.exclude(path__exact=''):
            actor = json.loads(serializers.serialize('json', [a]))[0]
            actor['fields'] = dict()
            actor['fields']['name'] = a.agent.name + '-' + a.path
            #actor['fields']['channel'] = str(a.channel) #a.channel.pk
            #need to add these in a for each as we now support lists of channels
            actor['fields']['channel']=[]
            for channel in a.channel:
                actor['fields']['channel'].append(channel['fields']['name'])
            actor['fields']['agent'] = a.agent.name #a.agent.pk
            actor['fields']['urlRemote'] = urlRemoteFromInforesid(a.inforesid)
            actor['fields']['path'] = req.build_absolute_uri(a.url()) #a.path
            actor['fields']['active'] = a.active
            actor['fields']['inforesid'] = a.inforesid
            actors.append(actor)
        return HttpResponse(json.dumps(actors, indent=2),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            logger.debug('%s: payload...\n%s' % (req.path, str(req.body)[:500]))
            if 'model' in data and 'tr_ars.agent' == data['model']:
                # this in the serialized model of agent
                data = data['fields']
            actor, status = get_or_create_actor(data)
            data = actor.to_dict()
            data['fields']['channel'] = actor.channel.name
            data['fields']['agent'] = actor.agent.name
            return HttpResponse(json.dumps(data, indent=2),
                                content_type='application/json', status=status)
        except Channel.DoesNotExist:
            logger.debug('Unknown channel: %s' % channel)
            return HttpResponse('Unknown channel: %s' % channel, status=404)
        except Agent.DoesNotExist:
            logger.debug('Unknown agent: %s' % agent)
            return HttpResponse('Unknown agent: %s' % agent, status=404)
        except Exception as e:
            logger.error("Unexpected error 15: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
            return HttpResponse('Not a valid json format', status=400)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

@csrf_exempt
def answers(req, key):
    if req.method != 'GET':
        return HttpResponse('Method %s not supported!' % req.method, status=400)
    try:
        baseMessage = json.loads(message(req,key).content)
        queryGraph = baseMessage['fields']['data']
        response = trace_message(req,key)
        jsonRes = response.content
        jsonRes.update({"query_graph":queryGraph})
        # html = '<html><body>Answers for the query graph:<br>'
        # html+="<pre>"+json.dumps(queryGraph,indent=2)+"</pre><br>"
        # for child in jsonRes['children']:
        #     childId = str(child['message'])
        #     childStatus = str(child['status'])
        #     html += "<a href="+str(req.META['HTTP_HOST'])+"/ars/api/messages/"+childId+" target=\"_blank\">"+str(child['actor']['agent'])+"</a>"
        #     html += "<br>"
        # html+="</body></html>"mesg

        return HttpResponse(json.loads(jsonRes),status=200)
    except Message.DoesNotExist:
        return HttpResponse('Unknown message: %s' % key, status=404)

@csrf_exempt
def status(req):
    if req.method == 'GET':
        return HttpResponse(json.dumps(status_report.status(req), indent=2),
                            content_type='application/json', status=200)
@csrf_exempt
def timeoutTest(req,time=300):
    if req.method == 'POST':
        #message = json.loads(req.body)
        #utils.validate(message)
        pass
    else:
        pass
        #utils.remove_blocked()

def block(req,key):
    if req.method == 'GET':
        mesg = get_object_or_404(Message.objects.filter(pk=key))
        data = mesg.decompress_dict()
        report=utils.remove_blocked(mesg,data)
        httpjson = {
            "pk":report[0],
            "blocked_nodes":report[1],
            "removed_results":report[2]

        }
        #return redirect('/ars/api/messages/'+str(blocked_id))
        return HttpResponse(json.dumps(httpjson, indent=2),
                            content_type='application/json', status=200)

def retain_all(parent_mesg, json_response):

    if parent_mesg.status != 'R':
        parent_mesg.retain = True
        parent_mesg.save(update_fields=['retain'])
        children = Message.objects.filter(ref__pk=parent_mesg.pk)
        for child in children:
            child.retain = True
            child.save(update_fields=['retain'])
        json_response["success"]=True
        json_response["parent_pk"]= str(parent_mesg.id)
    else:
        json_response["parent_pk"]= str(parent_mesg.id)
        json_response["description"] = 'PK still running'

    return json_response
@csrf_exempt
def retain(req, key):
  
    mesg = get_object_or_404(Message.objects.filter(pk=key))
    json_response={
        "success":False
    }

    if str(mesg.actor.agent.name) == 'ars-default-agent':

        json_response = retain_all(mesg, json_response)

    elif mesg.ref_id is not None:
        parent_mesg = get_object_or_404(Message.objects.filter(pk=mesg.ref_id))
        json_response = retain_all(parent_mesg,json_response)

    else:
        json_response["description"] = 'Invalid PK'

    return HttpResponse(json.dumps(json_response, indent=2),
                            content_type='application/json', status=200)

def merge(req, key):
    logger.debug("Beginning merge for %s " % key)
    if req.method == 'GET':
        logger.debug("Beginning merge for %s " % key)
        parent = get_object_or_404(Message.objects.filter(pk=key))
        merged_message=utils.createMessage(get_ars_actor(),key)
        mid=merged_message.id
        merged_message.save_compressed_dict(parent.data)
        merged_message.save()
        utils.merge.apply_async((key,mid))
        print(str(mid))
        #return redirect('/ars/api/messages/'+str(mid))
def post_process(req, key):
    if req.method=='GET':
        logger.debug("Beginning debugging post_process for %s " % key)
        mesg = get_object_or_404(Message.objects.filter(pk=key))
        data = mesg.decompress_dict()
        actor_name = mesg.actor
        utils.post_process(data['message'],key,actor_name)



apipatterns = [
    path('', index, name='ars-api'),
    re_path(r'^submit/?$', submit, name='ars-submit'),
    re_path(r'^messages/?$', messages, name='ars-messages'),
    re_path(r'^agents/?$', agents, name='ars-agents'),
    re_path(r'^actors/?$', actors, name='ars-actors'),
    re_path(r'^channels/?$', channels, name='ars-channels'),
    path('agents/<name>', get_agent, name='ars-agent'),
    path('messages/<uuid:key>', message, name='ars-message'),
    re_path(r'^filters/?$', filters, name='ars-filters'),
    path('filter/<uuid:key>', filter, name='ars-filter'),
    re_path(r'^status/?$', status, name='ars-status'),
    path('reports/<inforesid>',get_report,name='ars-report'),
    re_path(r'^timeoutTest/?$', timeoutTest, name='ars-timeout'),
    path('merge/<uuid:key>', merge, name='ars-merge'),
    path('retain/<uuid:key>', retain, name='ars-retain'),
    path('block/<uuid:key>', block, name='ars-block'),
    path('latest_pk/<int:n>', latest_pk, name='ars-latestPK'),
    path('post_process/<uuid:key>', post_process, name='ars-post_process_debug')



]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
