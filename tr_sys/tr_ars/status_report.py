from django.http import HttpResponse, Http404, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.core import serializers
from django.utils import timezone
from .models import Agent, Message, Channel, Actor
import json, sys, logging, traceback, html
from inspect import currentframe, getframeinfo
import requests

logger = logging.getLogger(__name__)

def status_ars(req, smartapi):
    response = dict()
    response['messages'] = dict()
    response['messages']['submitted'] = Message.objects.filter(ref=None).count()
    response['messages']['responses'] = Message.objects.count()-response['messages']['submitted']
    for mesg in Message.objects.filter(ref=None).order_by('-timestamp')[:1]:
        latest = Message.objects.get(pk=mesg.pk)
        response['messages']['latest_message'] = req.build_absolute_uri("/ars/api/messages/"+str(latest.pk)+"?trace=y")
        response['messages']['latest'] = latest.timestamp

    response['actors'] = dict()
    response['actors']['count'] = Actor.objects.count()-1
    for a in Actor.objects.exclude(path__exact=''):
        actor = json.loads(serializers.serialize('json', [a]))[0]
        del actor['fields']
        #actor['name'] = a.agent.name + '-' + a.path
        actor['channel'] = a.channel.name
        actor['agent'] = a.agent.name
        actor['remote'] = a.remote
        actor['path'] = req.build_absolute_uri(a.url())
        actor['messages'] = Message.objects.filter(actor=a.pk).count()
        for mesg in Message.objects.filter(actor=a.pk).order_by('-timestamp')[:1]:
            actor['latest'] = req.build_absolute_uri("/ars/api/messages/"+str(mesg.pk))
            message = Message.objects.get(pk=mesg.pk)
            if message.timestamp > response['messages']['latest']:
                actor['status'] = message.status
                for elem in Message.STATUS:
                    if elem[0] == actor['status']:
                        actor['status'] = elem[1]
        if 'status' not in actor:
            actor['status'] = Message.STATUS[-1][1]
        response['actors'][a.agent.name + '-' + a.path] = actor

    if 'latest' in response['messages']:
        response['messages']['latest'] = str(latest.timestamp)

    return response

def status_smartapi():
    response = dict()
    response['site'] = "https://smart-api.info/registry?tags=translator"
    smartapis = requests.get("https://smart-api.info/api/query/?q=translator&size=200").json()
    response['count'] = smartapis['total']
    response['apis'] = []
    for entry in smartapis["hits"]:
        api = dict()
        api['title'] = str(len(response['apis']))
        if 'title' in entry['info']:
            api['title'] = entry['info']['title']
        if 'version' in entry['info']:
            api['title'] = api['title'] + " (v" + entry['info']['version'] + ")"
        api['contact'] = ""
        if 'contact' in entry['info']:
            api['contact'] = entry['info']['contact']
        api['timestamp'] = entry['_meta']['timestamp']
        servers = []
        for item in entry['servers']:
            servers.append(item['url'])
        api['servers'] = servers
        api['entities'] = []
        response['apis'].append(api)
    return response

def status(req):
    response = dict()
    smartapi = status_smartapi() #TODO pull new info upon RSS feed notification
    response['ARS'] = status_ars(req, smartapi)
    response['SmartAPI'] = smartapi

    return response
