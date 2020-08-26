import json
import logging
import requests
import sys

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

QUERY_URL = 'https://translator.broadinstitute.org/genetics_data_provider/query'

def index(req):
    return HttpResponse('Example Data Provider wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
                            reverse('run-app-query')))

def query(url, data, timeout=600):
    r = requests.post(url, json=data, timeout=timeout)
    logger.debug('%d: %s\n%s' % (r.status_code, r.headers, r.text))
    return r

def callquery(url, req):
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
                r = query(url, data)
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
def runapp(req):
    return callquery(QUERY_URL, req)
