from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
from django.shortcuts import redirect
from django.urls import path, re_path, include, reverse

from utils2 import urlRemoteFromInforesid
from .models import Agent, Message, Channel, Actor
import json, sys, logging
import traceback
from inspect import currentframe, getframeinfo
from tr_ars import status_report
from tr_ars.tasks import send_message

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

def get_default_actor():
    # default actor is the first actor initialized in the database per
    # apps.setup_schema()
    return get_or_create_actor(DEFAULT_ACTOR)[0]
def get_workflow_actor():
    # default actor is the first actor initialized in the database per
    # apps.setup_schema()
    print("boop")
    return get_or_create_actor(WORKFLOW_ACTOR)[0]

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
        return HttpResponse('Content is not JSON', status=400)

@csrf_exempt
def messages(req):
    logger.debug("entering messages endpoint")

    if req.method == 'GET':
        response = []
        for mesg in  Message.objects.order_by('-timestamp')[:10]:
            response.append(Message.objects.get(pk=mesg.pk).to_dict())
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
                mesg.data = data['data']
            if 'url' in data and data['url'] != None:
                mesg.url = data['url']
            if 'ref' in data and data['ref'] != None:
                rid = int(data['ref'])
                mesg.ref = Message.objects.get(pk=rid)
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
        channel_names=[]
        for ch in child.actor.channel:
            channel_names.append(ch['fields']['name'])
        n = {
            'message': str(child.id),
            'status': dict(Message.STATUS)[child.status],
            'code': child.code,
            'actor': {
                'pk': child.actor.pk,
                'inforesid': child.actor.inforesid,
                #'channel': child.actor.channel.name,
                'channel': channel_names,
                'agent': child.actor.agent.name,
                'path': child.actor.path
            },
            'children': []
        }
        trace_message_deepfirst(n)
        node['children'].append(n)


def trace_message(req, key):
    logger.debug("entering trace_message")
    try:
        mesg = Message.objects.get(pk=key)
        channel_names=[]
        for ch in mesg.actor.channel:
            channel_names.append(ch['fields']['name'])
        tree = {
            'message': str(mesg.id),
            'status': dict(Message.STATUS)[mesg.status],
            'actor': {
                'pk': mesg.actor.pk,
                'inforesid': mesg.actor.inforesid,
                #'channel': mesg.actor.channel.name,
                'channel':channel_names,
                'agent': mesg.actor.agent.name,
                'path': mesg.actor.path

            },
            'children': []
        }
        trace_message_deepfirst(tree)
        return HttpResponse(json.dumps(tree, indent=2),
                            content_type='application/json',
                            status=200)
    except Message.DoesNotExist:
        logger.debug('Unknown message: %s' % key)
        return HttpResponse('Unknown message: %s' % key, status=404)
    return HttpResponse('Internal server error', status=500)

@csrf_exempt
def message(req, key):
    logger.debug("entering message endpoint %s " % key)

    if req.method == 'GET':
        if req.GET.get('trace', False):
            return trace_message(req, key)
        try:
            mesg = Message.objects.get(pk=key)
            return HttpResponse(json.dumps(mesg.to_dict(), indent=2),
                                status=200)

        except Message.DoesNotExist:
            return HttpResponse('Unknown message: %s' % key, status=404)

    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            #if 'query_graph' not in data or 'knowledge_graph' not in data or 'results' not in data:
            #    return HttpResponse('Not a valid Translator API json', status=400)

            mesg = Message.objects.get(pk = key)
            status = 'D'
            if 'tr_ars.message.status' in req.headers:
                status = req.headers['tr_ars.message.status']

            # create child message if this one already has results
            if mesg.data and 'results' in mesg.data and mesg.data['results'] != None and len(mesg.data['results']) > 0:
                mesg = Message.create(name=mesg.name, status=status,
                                  actor=mesg.actor, ref=mesg)

            mesg.status = status
            mesg.data = data
            mesg.save()
            return HttpResponse(json.dumps(mesg.to_dict(), indent=2),
                                status=201)

        except Message.DoesNotExist:
            return HttpResponse('Unknown state reference %s' % key, status=404)

        except json.decoder.JSONDecodeError:
            return HttpResponse('Can not decode json:<br>\n%s' % req.body, status=500)

        except Exception as e:
            logger.error("Unexpected error 12: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))

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
           actor, created = Actor.objects.update_or_create(
               channel=json.loads(serializers.serialize('json',channel)), agent=agent, path=data['path'], inforesid=inforesid)
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
        pass
        print()
        return HttpResponse(json.loads(jsonRes),status=200)
    except Message.DoesNotExist:
        return HttpResponse('Unknown message: %s' % key, status=404)

@csrf_exempt
def status(req):
    if req.method == 'GET':
        return HttpResponse(json.dumps(status_report.status(req), indent=2),
                            content_type='application/json', status=200)

apipatterns = [
    path('', index, name='ars-api'),
    re_path(r'^submit/?$', submit, name='ars-submit'),
    re_path(r'^messages/?$', messages, name='ars-messages'),
    re_path(r'^agents/?$', agents, name='ars-agents'),
    re_path(r'^actors/?$', actors, name='ars-actors'),
    re_path(r'^channels/?$', channels, name='ars-channels'),
    path('agents/<name>', get_agent, name='ars-agent'),
    path('messages/<uuid:key>', message, name='ars-message'),
    re_path(r'^status/?$', status, name='ars-status'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
