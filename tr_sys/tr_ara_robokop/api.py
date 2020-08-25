from django.urls import reverse
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
import json, sys, logging, requests

logger = logging.getLogger(__name__)

#ROBOKOP_URL = 'https://robokop.renci.org/api/simple/quick/?rebuild=false&output_format=MESSAGE&max_connectivity=0&max_results=10'

ROBOKOP_URL = 'https://robokop.renci.org/ranker/api/query/?max_results=-1&output_format=STD&max_connectivity=-1&use_novelty=false'

def index(req):
    return HttpResponse('Robokop ARA wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
                            reverse('ara-robokop-runquery')))

def robokop(data, timeout=60):
    r = requests.post(ROBOKOP_URL, verify=False, json=data, timeout=timeout)
    logger.debug('%d: %s\n%s' % (r.status_code, r.headers, r.text))
    return r

@csrf_exempt
def runquick(req):
    if req.method != 'POST':
        return HttpResponse('Method %s not supported!' % req.method, status=400)

    mesg = ''
    try:
        data = json.loads(req.body)
        logger.debug('%s: received payload...\n%s' % (req.path, req.body))
        if 'model' in data and data['model'] == 'tr_ars.message':
            data = data['fields']
            if 'ref' in data and data['ref'] != None:
                data = None # only work on query message
                mesg = 'Not head message'
            elif 'data' in data and data['data'] != None:
                data = data['data']
            elif 'url' in data and data['url'] != None:
                data = requests.get(data['url'], timeout=60).json()
            else:
                data = None
                mesg = 'Not a valid tr_ars.message'

            if data != None:
                r = robokop(data)
                resp =  HttpResponse(r.text,
                                     content_type='application/json',
                                     status=r.status_code)
                resp['tr_ars.message.status'] = 'R'
                return resp
    except:
        mesg = 'Unexpected error: %s' % sys.exc_info()
        logger.debug(mesg)
        
    # notify the ARS that we have nothing to contribute
    resp = HttpResponse(mesg, status=400)
    return resp

@csrf_exempt
def runpost(req):
    if req.method != 'POST':
        return HttpResponse('Method %s not supported!' % req.method, status=400)

    # this endpoint serves to illustrate another actor that can be used
    # to interact with the messaging queue based on some condition
    mesg = ''
    try:
        data = json.loads(req.body)
        logger.debug('%s: received payload...\n%s' % (req.path, req.body))
        if 'model' in data and data['model'] == 'tr_ars.message':
            data = data['fields']
            # all we're doing here is to only contribute if the parent
            # message is coming from the ara-robokop-agent
            if (data['actor']['agent'] == 'ara-robokop-agent'
                and data['status'] == 'R'):
                resp = HttpResponse(data['data'],
                                    content_type='application/json',
                                    status=200)
                resp['tr_ars.message.status'] = 'D'
                return resp
        else:
            mesg = 'Not a valid Translator message'
    except:
        mesg = "Unexpected error: %s" % sys.exc_info()
        logger.debug(mesg)

    # nothing to contribute
    resp = HttpResponse(mesg, status=400)
    return resp
        
