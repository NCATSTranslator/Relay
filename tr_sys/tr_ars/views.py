from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.urls import path, include

from . import api
from . import status_report
from .models import Message

import json, sys, logging, traceback, html

# Create your views here.
def app_home(req):
    about = '\n'.join(open('README.md').readlines())
    template = loader.get_template('ncatspage.html')
    context = {
        'Title': 'Translator ARS',
        'bodytext': about
    }
    return HttpResponse(template.render(context, req))

def status(req):
    status = status_report.status(req)
    template = loader.get_template('status.html')
    context = {
        'Title': 'Translator ARS Status',
        'Short_title': 'ARS Status',
        'actors': status['ARS']['actors'],
        'reasoners': status['SmartAPI']['Other-Reasoners'],
        'sources': status['SmartAPI']['Other-Translator-SmartAPIs'],
        'queue': status['ARS-Queue-Status']
    }
    return HttpResponse(template.render(context, req))

def answer(req,key):
    pass
    if req.method != 'GET':
        return HttpResponse('Method %s not supported!' % req.method, status=400)
    try:
        baseMessage = json.loads(api.message(req,key).content)
        queryGraph = baseMessage['fields']['data']
        response = api.trace_message(req,key)
        jsonRes = json.loads(response.content)
        answer_list=[]
        html = '<html><body>Answers for the query graph:<br>'
        html+="<pre>"+json.dumps(queryGraph,indent=2)+"</pre><br>"
        for child in jsonRes['children']:
            childId = str(child['message'])
            jsonChild = json.loads(api.message(req,childId).content)
            jsonChildData = jsonChild['fields']['data']
            if not (jsonChildData.get('knowledge_graph') is None):
                kg = json.dumps(jsonChildData['knowledge_graph'],indent=2)
            else:
                kg = "No knowledge_graph present in response"


            if not (jsonChildData.get('query_graph') is None):
                qg = json.dumps(jsonChildData['query_graph'],indent=2)
            else:
                qg = "No query_graph present in response"

            if not (jsonChildData.get('results') is None):
                results = json.dumps(jsonChildData['results'],indent=2)
            else:
                results = "No results present in response"

            answer_list.append({"child":child,
                                "qg":qg,
                                "kg":kg,
                                "results":results})

        #     html += "<a href="+str(req.META['HTTP_HOST'])+"/ars/api/messages/"+childId+" target=\"_blank\">"+str(child['actor']['agent'])+"</a>"
        #     try:
        #         jsonChild = json.loads(api.message(req,childId).content)
        #         jsonChildData = json.loads(jsonChild['fields']['data'])
        #         html+="<pre>"+json.dumps(jsonChildData,indent=2)+"</pre><br>"
        #     except json.decoder.JSONDecodeError:
        #         html+="Response was not present or not valid"
        #     html += "<br>"
        # html+="</body></html>"
        context = {
            "answer_list":answer_list
        }
        #return HttpResponse(html,status=200)
        return render(req, 'answers_template.html', context=context)
    except Message.DoesNotExist:
        return HttpResponse('Unknown message: %s' % key, status=404)

