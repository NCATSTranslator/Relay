from django.http import HttpResponse, Http404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.core import serializers
from django.utils import timezone
from .models import Agent, State, Channel, Actor
import json, sys, logging, traceback, inspect

logger = logging.getLogger(__name__)

def index(req):
    return HttpResponse("Translator ARS API.")

@csrf_exempt
def registration(req):
    """Agent registration"""
    if req.method != 'POST':
        return HttpResponse("Only POST is permitted!", status=405)
    #print ('Content-Type: %s' % req.content_type)
    code = 200
    try:
        data = json.loads(req.body)
        if 'agent' not in data:
            return HttpResponse('Not a valid ARS json', status=400)

        agent = Agent.objects.get(name=data['agent'])
        print ('agent.. %s' % agent)
    except Agent.DoesNotExist:
        agent = Agent(name=data['agent'], description=data['description'],
                      uri = data['uri'], contact=data['contact'])
        agent.save()
        code = 201
    except:
        print("Unexpected error:", sys.exc_info()[0])
        return HttpResponse('Content is not valid JSON', status=400)
    
    return HttpResponse(serializers.serialize('json', [agent]),
                        content_type='application/json', status=code)

def get_or_create_channel(name):
    logger.debug('*** %s: %s' % (inspect.stack()[0][3], name))
    try:
        channel = Channel.objects.get(name=name)
    except Channel.DoesNotExist:
        channel = Channel (name=name)
        channel.save()
        logger.debug('+++ new channel "%s" (%d) created' % (channel, channel.id))
    return channel

def get_state_actor(agent):
    try:
        channel = get_or_create_channel('state')
        actor = Actor.objects.get(channel=channel, agent=agent)
        return actor
    except Actor.DoesNotExist:
        logger.error('No actor found for agent=%s channel=%s' % (agent, channel))
    return None
    
@csrf_exempt
def states(req):
    if req.method == 'GET':
        states = State.objects.order_by('-timestamp')[:5]
        return HttpResponse(serializers.serialize('json', states), status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            if 'agent' not in data:
                return HttpResponse('Not a valid ARS json', status=400)

            agent = Agent.objects.get(name=data['agent'])
            logger.debug('+++ agent: %s' % agent)
            
            actor = get_state_actor(agent)
            if None == actor:
                return HttpResponse('Not a valid agent: %s' % agent)
            logger.debug('*** actor: %s' % actor)
            
            state = State(name=data['name'], status=data['status'],
                          actor=actor)
            if 'data' in data and data['data'] != None:
                state.data = bytearray(json.dumps(data['data']), 'utf8')
            if 'url' in data and data['url'] != None:
                state.url = data['url']
            if 'ref' in data and data['ref'] != None:
                rid = int(data['ref'])
                state.ref = State.objects.get(pk=rid)
            state.save()
            return HttpResponse('State %d created' % state.id, status=201)

        except State.DoesNotExist:
            logger.error('Unknown state %d' % pid)
            return HttpResponse('Unknown state reference %d' % pid, status=404)
        except Agent.DoesNotExist:
            return HttpResponse('Unknown agent "%s"' % data['agent'],
                                status=404)
        except:
            traceback.print_last()
        return HttpResponse('Internal server error', status=500)

def channels(req):
    if req.method == 'GET':
        channels = Channel.objects.order_by('name')
        return HttpResponse(serializers.serialize('json', channels), status=200)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

def agents(req):
    if req.method == 'GET':
        agents = Agent.objects.order_by('name')
        return HttpResponse(serializers.serialize('json', agents), status=200)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

def actors(req):
    if req.method == 'GET':
        return HttpResponse(serializers.serialize('json', Actor.objects.all()),
                            status=200)
    return HttpResponse('Unsupported method %s' % req.method, status=400)
