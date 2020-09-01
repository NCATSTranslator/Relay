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
    logger.debug('%d: %s\n%s' % (r.status_code, r.headers, r.text[:500]))
    return r

def callquery(url, req):
    if req.method != 'POST':
        return HttpResponse('Method %s not supported!' % req.method, status=400)

    mesg = ''
    try:
        data = json.loads(req.body)
        logger.debug('%s: received payload...\n%s' % (req.path, str(req.body)[:500]))
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
                resp = HttpResponse(r.text,
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

def init_api_fn(actor):
    @csrf_exempt
    def fn(req):
        return callquery(actor[0], req)
    fn.__name__ = actor[1]
    fn.__doc__ = "Forward api request at %s to %s" % (actor[1], actor[0])
    return fn

def init_api_index(actors, app_path):
    def fn(req):
        data = dict()
        data['agent'] = app_path
        data['actors'] = []
        for actor in actors:
            query_name = app_path + '-' + actor[1]
            actorObj = dict()
            actorObj['name'] = query_name
            actorObj['channel'] = actor[2]
            actorObj['remote'] = actor[0]
            actorObj['path'] = req.build_absolute_uri(reverse(query_name))
            data['actors'].append(actorObj)
        return HttpResponse(json.dumps(data, indent=2),
                            content_type='application/json', status=200)
    fn.__name__ = "index"
    fn.__doc__ = "index api response describing agent"
    return fn

from django.shortcuts import redirect

def init_redirect(app_path):
    def fn(req):
        response = redirect(reverse(app_path + '-api'))
        return response

    fn.__name__ = "redirect_index"
    fn.__doc__ = "redirect to index api response describing agent"
    return fn
