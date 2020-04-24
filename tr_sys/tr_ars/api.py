from django.http import HttpResponse, Http404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.core import serializers
from django.utils import timezone
from .models import Agent, Message, Channel, Actor
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
        logger.debug("Unexpected error: %s" % sys.exc_info()[0])
        return HttpResponse('Content is not valid JSON', status=400)
    
    return HttpResponse(serializers.serialize('json', [agent]),
                        content_type='application/json', status=code)

def get_default_actor():
    # default actor is the first actor initialized in the database per
    # apps.setup_schema()
    return Actor.objects.get(pk=1)

@csrf_exempt
def submit(req):
    """Query submission"""
    if req.method != 'POST':
        return HttpResponse('Only POST is permitted!', status=405)
    try:
        data = json.loads(req.body)
        if 'query' not in data:
            return HttpResponse('Not a valid query json', status=400)
        # create a head message
        query = data['query']
        message = Message (status='D', data=json.dumps(query),
                           actor=get_default_actor())
        if 'name' in data:
            message.name = data['name']
        # save and broadcast
        message.save()
        data = json.loads(serializers.serialize('json', [message]))[0]
        data['fields']['data'] = query
        return HttpResponse(json.dumps(data),
                            content_type='application/json', status=201)
    except:
        logger.debug("Unexpected error: %s" % sys.exc_info())
        return HttpResponse('Content is not JSON', status=400)
    
@csrf_exempt
def messages(req):
    if req.method == 'GET':
        messages = Message.objects.order_by('-timestamp')[:5]
        return HttpResponse(serializers.serialize('json', messages),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            if 'actor' not in data:
                return HttpResponse('Not a valid ARS json', status=400)

            actor = Agent.objects.get(pk=data['actor'])
            #logger.debug('*** actor: %s' % actor)
            
            mesg = Message(name=data['name'], status=data['status'],
                           actor=actor)
            if 'data' in data and data['data'] != None:
                mesg.data = data['data']
            if 'url' in data and data['url'] != None:
                mesg.url = data['url']
            if 'ref' in data and data['ref'] != None:
                rid = int(data['ref'])
                mesg.ref = Message.objects.get(pk=rid)
            mesg.save()
            return HttpResponse('Message %d created' % mesg.id, status=201)

        except Message.DoesNotExist:
            return HttpResponse('Unknown state reference %d' % rid, status=404)
        
        except Actor.DoesNotExist:
            return HttpResponse('Unknown actor: %s!' % data['actor'],
                                status=404)
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
            
        return HttpResponse('Internal server error', status=500)

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
            if 'name' in data and 'description' in data:
                channel = Channel.objects.get(name=data['name'])
        except Channel.DoesNotExit:
            channel = Channel(name=data['name'],
                              description=data['description'])
            channel.save()
            code = 201
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
            return HttpResponse('Internal server error', status=500)
        return HttpResponse(serializers.serialize('json', channel),
                            content_type='application/json', status=code)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

def agents(req):
    if req.method == 'GET':
        agents = Agent.objects.order_by('name')
        return HttpResponse(serializers.serialize('json', agents),
                            content_type='application/json', status=200)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

def agent(req, name):
    try:
        agent = Agent.objects.get(name=name)
        return HttpResponse(serializers.serialize('json', [agent]),
                            content_type='application/json', status=200)
    except Agent.DoesNotExist:
        return HttpResponse('Unknown agent: %s' % name, status=400)
    
def actors(req):
    if req.method == 'GET':
        return HttpResponse(serializers.serialize('json', Actor.objects.all()),
                            content_type='application/json', status=200)
    return HttpResponse('Unsupported method %s' % req.method, status=400)
