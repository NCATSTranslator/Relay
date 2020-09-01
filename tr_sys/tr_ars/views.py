from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from . import status_report

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
        'sources': status['SmartAPI']['Other-Translator-SmartAPIs']
    }
    return HttpResponse(template.render(context, req))
