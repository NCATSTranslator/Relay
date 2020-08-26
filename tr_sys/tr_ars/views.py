from django.shortcuts import render
from django.urls import path, include

from django.http import HttpResponse
from . import api
from .models import Message
from django.core.exceptions import ObjectDoesNotExist


import json, sys, logging, traceback, html

# Create your views here.
def answer(req,key):
    pass
    if req.method != 'GET':
        return HttpResponse('Method %s not supported!' % req.method, status=400)
    try:
        baseMessage = json.loads(api.message(req,key).content)
        queryGraph = json.loads(baseMessage['fields']['data'])
        response = api.trace_message(req,key)
        jsonRes = json.loads(response.content)
        html = '<html><body>Answers for the query graph:<br>'
        html+="<pre>"+json.dumps(queryGraph,indent=2)+"</pre><br>"
        for child in jsonRes['children']:
            childId = str(child['message'])
            html += "<a href="+str(req.META['HTTP_HOST'])+"/ars/api/messages/"+childId+" target=\"_blank\">"+str(child['actor']['agent'])+"</a>"
            try:
                jsonChild = json.loads(api.message(req,childId).content)
                jsonChildData = json.loads(jsonChild['fields']['data'])
                html+="<pre>"+json.dumps(jsonChildData,indent=2)+"</pre><br>"
            except json.decoder.JSONDecodeError:
                html+="Response was not present or not valid"
            html += "<br>"
        html+="</body></html>"
        return HttpResponse(html,status=200)
    except Message.DoesNotExist:
        return HttpResponse('Unknown message: %s' % key, status=404)
