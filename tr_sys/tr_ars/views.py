from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from . import status_report

# Create your views here.
def app_home(req):
    template = loader.get_template('ncatspage.html')
    context = { }
    return HttpResponse(template.render(context, req))

def status(req):
    status = status_report.status(req)
    template = loader.get_template('status.html')
    context = {
        'actors': status['ARS']['actors']
    }
    return HttpResponse(template.render(context, req))
