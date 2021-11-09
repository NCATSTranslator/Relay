import json
import logging
import requests
import sys
import traceback

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from tr_smartapi_client.smart_api_discover import SmartApiDiscover

logger = logging.getLogger(__name__)

QUERY_URL = 'https://translator.broadinstitute.org/genetics_data_provider/query'

def index(req):
    return HttpResponse('Example Data Provider wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
                            reverse('run-app-query')))

def query(url, data, timeout=600):
    headers = {'Content-Type': 'application/json'}
    logging.info("about to POST 3 url={}".format(url))
    r = requests.post(url, json=data, headers=headers, timeout=timeout)
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
                try:
                    r = query(url, data)
                    resp = HttpResponse(r.text,
                                         content_type='application/json',
                                         status=r.status_code)
                    for key in r.headers:
                        resp['tr_ars.'+key] = r.headers[key]
                    resp['tr_ars.reason'] = r.reason
                    resp['tr_ars.url'] = r.url
                    return resp
                except Exception as e:
                    logger.error("Unexpected error 6: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    resp = HttpResponse(exc_value,
                                     status = 503)
                    resp['tr_ars.url'] = url
                    return resp

    except Exception as e:
        logger.error("Unexpected error 7: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
        logger.debug(mesg)

    # notify the ARS that we have nothing to contribute
    resp = HttpResponse(mesg, status=400)
    return resp

@csrf_exempt
def runapp(req):
    return callquery(QUERY_URL, req)

def init_api_fn(actorconf):
    inforesid = actorconf.inforesid()
    if SmartApiDiscover().urlServer(inforesid) is None:
        logging.warn("could not configure inforesid={}".format(inforesid))
    @csrf_exempt
    def fn(req):
        urlServer=SmartApiDiscover().urlServer(inforesid)
        if urlServer is not None:
            endpoint=SmartApiDiscover().endpoint(inforesid)
            params=SmartApiDiscover().params(inforesid)
            remote = (urlServer +
                    (("/"+endpoint) if endpoint is not None else "") +
                    (("?"+params) if params is not None else "")) if urlServer is not None else None
            return callquery(remote, req)
    fn.__name__ = actorconf.name()
    fn.__doc__ = "Forward api request at %s to %s" % (fn.__name__, actorconf.inforesid())
    return fn

class Actorconf:
    def __init__(self, inforesid,  name, path, method, params) -> None:
        self._inforesid = inforesid
        self._name = name
        self._path = path
        self._method = method
        self._params = params

    def inforesid(self):
        return self._inforesid

    def name(self):
        return self._name
    
    def path(self):
        return self._path
    
    def method(self):
        return self._method
    
    def params(self):
        return self._params


def make_actorconf(inforesid, name, path, method=None, params=None):
    return Actorconf(inforesid, name, path, method, params)

def init_api_index(actors, app_path):
    def fn(req):
        data = dict()
        data['agent'] = app_path
        data['actors'] = []

        from tr_ars.models import Actor
        actobjs = Actor.objects.filter(agent__name=app_path)
        for actor in actobjs:
            query_name = app_path + '-' + actor.path #actor[1]
            actorObj = dict()
            actorObj['name'] = query_name
            actorObj['channel'] = actor.channel.name #actor[2]
            actorObj['remote'] = actor.remote #actor[0]
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
