from django.urls import reverse
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
import json, sys, logging, requests

logger = logging.getLogger(__name__)

ROBOKOP_URL = 'https://robokop.renci.org/api/simple/quick/?rebuild=false&output_format=MESSAGE&max_connectivity=0&max_results=500'

def index(req):
    return HttpResponse('Robokop ARA wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
                            reverse('ara-robokop-runquick')))

def eval(data):
    r = requests.post(ROBOKOP_URL, verify=False, json=data, timeout=60)
    logger.debug('%d: %s\n%s' % (r.status_code, r.headers, r.text))
    return r

@csrf_exempt
def runquick(req):
    if req.method != 'POST':
        return HttpResponse('Method %s not supported!' % req.method, status=400)

    try:
        data = json.loads(req.body)
        logger.debug('%s: received payload...\n%s' % (__name__, data))
        if 'model' in data:
            logger.debug('%s: processing message %s\n%s'
                         % (__name__, data['pk'], data['fields']))
            data = data['fields']
            if 'data' in data and data['data'] != None:
                data = json.loads(data['data'])
            elif 'url' in data and data['url'] != None:
                data = requests.get(data['url'], timeout=60).json()
            else:
                data = None

            if data != None:
                r = eval (data)
                return HttpResponse(r.text,
                                    content_type='application/json',
                                    status=r.status_code)
        return HttpResponse('Not a valid ARS message!', status=400)
    except:
        logger.debug("Unexpected error: %s" % sys.exc_info())
        return HttpResponse('Content is not JSON', status=400)
