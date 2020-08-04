from django.urls import reverse
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
import json, sys, logging, requests

logger = logging.getLogger(__name__)

URL = 'https://arax.rtx.ai/api/rtx/v1/query'


def index(req):
    return HttpResponse('ARAX ARA wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
                            reverse('ara-arax-query')))


def arax(data, timeout=600):
    r = requests.post(URL, verify=False, json=data, timeout=timeout)
    logger.debug('%d: %s\n%s' % (r.status_code, r.headers, r.text))
    return r


@csrf_exempt
def query(req):
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
                data = json.loads(data['data'])
            elif 'url' in data and data['url'] != None:
                data = requests.get(data['url'], timeout=60).json()
            else:
                data = None
                mesg = 'Not a valid tr_ars.message'

            if data != None:
                r = arax(data)
                resp =  HttpResponse(r.text,
                                     content_type='application/json',
                                     status=r.status_code)
                resp['tr_ars.message.status'] = 'R'
                return resp
        else:
            mesg = 'Not a valid Translator message'
    except:
        mesg = "Unexpected error: %s" % sys.exc_info()
        logger.debug(mesg)

    # nothing to contribute
    resp = HttpResponse(mesg, status=400)
    logger.debug("nothing to contribute")
    return resp
        
