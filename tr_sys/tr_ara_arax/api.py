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
            # all we're doing here is to only contribute if the parent
            # message is coming from the ara-arax-agent
            if (data['actor']['agent'] == 'ara-arax-agent'
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
        
