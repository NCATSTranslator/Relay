from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
from django.shortcuts import redirect
from django.urls import path, re_path, include, reverse
from .models import Agent, Message, Channel, Actor
import json, sys, logging
from inspect import currentframe, getframeinfo
from tr_ars import status_report

logger = logging.getLogger(__name__)


def index(req):
    data = dict()
    data['name'] = "Translator Autonomous Relay System (ARS) API"
    data['entries'] = []
    for item in apipatterns:
        try:
            data['entries'].append(req.build_absolute_uri(reverse(item.name)))
        except:
            data['entries'].append(req.build_absolute_uri() + str(item.pattern))
    return HttpResponse(json.dumps(data, indent=2),
                        content_type='application/json', status=200)

def api_redirect(req):
    response = redirect(reverse('ars-api'))
    return response


DEFAULT_ACTOR = {
    'channel': 'general',
    'agent': {
        'name': 'ars-default-agent',
        'uri': ''
    },
    'path': '',
    'remote': ''
}


def get_default_actor():
    # default actor is the first actor initialized in the database per
    # apps.setup_schema()
    return get_or_create_actor(DEFAULT_ACTOR)[0]


@csrf_exempt
def submit(req):
    """Query submission"""
    if req.method != 'POST':
        return HttpResponse('Only POST is permitted!', status=405)
    try:
        data = json.loads(req.body)
        if 'message' not in data:
            return HttpResponse('Not a valid Translator query json', status=400)
        # create a head message
        message = Message.create(code=200, status='Running', data=data,
                          actor=get_default_actor())
        if 'name' in data:
            message.name = data['name']
        # save and broadcast
        message.save()
        data = message.to_dict()
        return HttpResponse(json.dumps(data, indent=2),
                            content_type='application/json', status=201)
    except:
        logger.debug("Unexpected error: %s" % sys.exc_info())
        return HttpResponse('Content is not JSON', status=400)

@csrf_exempt
def messages(req):
    if req.method == 'GET':
        response = []
        for mesg in  Message.objects.order_by('-timestamp')[:10]:
            response.append(Message.objects.get(pk=mesg.pk).to_dict())
        return HttpResponse(json.dumps(response),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            if 'actor' not in data:
                return HttpResponse('Not a valid ARS json', status=400)

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
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())

        return HttpResponse('Internal server error', status=500)


def trace_message_deepfirst(node):
    children = Message.objects.filter(ref__pk=node['message'])
    logger.debug('%s: %d children' % (node['message'], len(children)))
    for child in children:
        n = {
            'message': str(child.id),
            'status': dict(Message.STATUS)[child.status],
            'actor': {
                'pk': child.actor.pk,
                'channel': child.actor.channel.name,
                'agent': child.actor.agent.name,
                'path': child.actor.path
            },
            'children': []
        }
        trace_message_deepfirst(n)
        node['children'].append(n)


def trace_message(req, key):
    try:
        mesg = Message.objects.get(pk=key)
        tree = {
            'message': str(mesg.id),
            'status': dict(Message.STATUS)[mesg.status],
            'actor': {
                'pk': mesg.actor.pk,
                'channel': mesg.actor.channel.name,
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
    if req.method == 'GET':
        if req.GET.get('trace', False):
            return trace_message(req, key)
        try:
            mesg = Message.objects.get(pk=key)
            return HttpResponse(json.dumps(mesg.to_dict(), indent=2),
                                status=200)

        except Message.DoesNotExit:
            return HttpResponse('Unknown message: %s' % key, status=404)

    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            if 'query_graph' not in data or 'knowledge_graph' not in data or 'results' not in data:
                return HttpResponse('Not a valid Translator API json', status=400)

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

        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())

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
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
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
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
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
    if isinstance(channel, int):
        channel = Channel.objects.get(pk=channel)
    elif channel.isnumeric():
        # primary channel key
        channel = Channel.objects.get(pk=int(channel))
    else:
        # name
        channel, created = Channel.objects.get_or_create(name=channel)
        if created:
            logger.debug('%s:%d: new channel created "%s"'
                         % (__name__, getframeinfo(currentframe()).lineno,
                            data['channel']))

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

    actor, created = Actor.objects.get_or_create(
        channel=channel, agent=agent, path=data['path'], remote=data['remote'])

    status = 201
    if not created:
        if actor.path != data['path']:
            actor.path = data['path']
            actor.save()  # update
        status = 302
    return (actor, status)


@csrf_exempt
def actors(req):
    if req.method == 'GET':
        actors = []
        for a in Actor.objects.exclude(path__exact=''):
            actor = json.loads(serializers.serialize('json', [a]))[0]
            actor['fields'] = dict()
            actor['fields']['name'] = a.agent.name + '-' + a.path
            actor['fields']['channel'] = a.channel.name #a.channel.pk
            actor['fields']['agent'] = a.agent.name #a.agent.pk
            actor['fields']['remote'] = a.remote
            actor['fields']['path'] = req.build_absolute_uri(a.url()) #a.path
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
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
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
    except Message.DoesNotExit:
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
