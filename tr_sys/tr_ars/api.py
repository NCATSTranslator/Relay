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
        if 'machine_question' not in data:
            return HttpResponse('Not a valid Translator query json', status=400)
        # create a head message
        message = Message (code=200, status='D', data=json.dumps(data),
                           actor=get_default_actor())
        if 'name' in data:
            message.name = data['name']
        # save and broadcast
        message.save()
        payload = data
        data = json.loads(serializers.serialize('json', [message]))[0]
        data['fields']['data'] = payload
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

def message(req, key):
    if req.method != 'GET':
        return HttpResponse('Method %s not supported!' % req.method, status=400)
    try:
        mesg = Message.objects.get(pk=key)
        data = json.loads(serializers.serialize('json', [mesg]))[0]
        # now get children if any
        children = Message.objects.filter(ref=mesg)
        if children.count() > 0:
            data['children'] = json.loads(serializers.serialize('json',
                                                                children))
        return HttpResponse(json.dumps(data), content_type='application/json',
                            status=200)
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
            data = json.loads(serializers.serialize('json', [channel]))[0]
            return HttpResponse(json.dumps(data),
                                content_type='application/json', status=status)
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
            return HttpResponse('Internal server error', status=500)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

@csrf_exempt
def agents(req):
    if req.method == 'GET':
        agents = Agent.objects.order_by('name')
        return HttpResponse(serializers.serialize('json', agents),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            logger.debug('%s: payload...\n%s' % (req.path, req.body))
            if 'model' in data and 'tr_ars.agent' == data['model']:
                # this in the serialized model of agent
                data = data['fields']
                
            if 'name' not in data or 'uri' not in data:
                return HttpResponse(
                    'JSON does not contain "name" and "uri" fields',
                    status=400)
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
            data = json.loads(serializers.serialize('json', [agent]))[0]
            return HttpResponse(json.dumps(data),
                                content_type='application/json', status=status)
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
            return HttpResponse('Not a valid json format', status=400)
    return HttpResponse('Unsupported method %s' % req.method, status=400)

def get_agent(req, name):
    try:
        agent = Agent.objects.get(name=name)
        data = json.loads(serializers.serialize('json', [agent]))[0]
        return HttpResponse(json.dumps(data),
                            content_type='application/json', status=200)
    except Agent.DoesNotExist:
        return HttpResponse('Unknown agent: %s' % name, status=400)

@csrf_exempt
def actors(req):
    if req.method == 'GET':
        actors = []
        for a in Actor.objects.exclude(path__exact=''):
            actor = json.loads(serializers.serialize('json', [a]))[0]
            actor['fields']['channel'] = a.channel.name
            actor['fields']['agent'] = a.agent.name
            actors.append(actor)
        return HttpResponse(json.dumps(actors),
                            content_type='application/json', status=200)
    elif req.method == 'POST':
        try:
            data = json.loads(req.body)
            logger.debug('%s: payload...\n%s' % (req.path, req.body))
            if 'model' in data and 'tr_ars.agent' == data['model']:
                # this in the serialized model of agent
                data = data['fields']
            if ('channel' not in data or
                'agent' not in data or 'path' not in data):
                return HttpResponse(
                    'JSON does not contain "channel", "agent", and "path" fields', status=400)
            
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
                    logger.debug('%s: new channel created "%s"'
                                 % (req.path, data['channel']))

            agent = data['agent']
            if isinstance(agent, int):
                agent = Agent.objects.get(pk=agent)
            elif agent.isnumeric():
                agent = Agent.objects.get(pk=int(agent))
            else:
                agent, created = Agent.objects.get_or_create(name=agent)
                if created:
                    logger.debug('%s: new agent created "%s"'
                                 % (req.path, data['agent']))
                    
            actor, created = Actor.objects.get_or_create(
                channel=channel, agent=agent, path=data['path'])
            
            status = 201
            if not created:
                if actor.path != data['path']:
                    actor.path = data['path']
                    actor.save() # update
                status = 302
            data = json.loads(serializers.serialize('json', [actor]))[0]
            return HttpResponse(json.dumps(data),
                                content_type='application/json',
                                status=status)
        except Channel.DoesNotExist:
            logger.debug('Unknown channel: %s' % channel)
            return HttpResponse('Unknown channel: %s' % channel, status=404)
        except Agent.DoesNotExit:
            logger.debug('Unknown agent: %s' % agent)
            return HttpResponse('Unknown agent: %s' % agent, status=404)
        except:
            logger.debug("Unexpected error: %s" % sys.exc_info())
            return HttpResponse('Not a valid json format', status=400)
    return HttpResponse('Unsupported method %s' % req.method, status=400)
