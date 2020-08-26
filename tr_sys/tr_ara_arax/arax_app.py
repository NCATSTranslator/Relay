from django.apps import AppConfig as SuperAppConfig
from django.urls import path, include
from tr_ars.default_ars_app.api import *

class AppConfig(SuperAppConfig):
    name = 'tr_ara_arax.arax_app' # must be dot path for module
    actors = [('https://arax.rtx.ai/api/rtx/v1/query', 'runquery', 'general')] # tuple of remote, name, channel
    app_path = 'ara-arax'

### code below this line is required, but doesn't require updating in most cases

    regex_path = '^' + app_path + '/'

    def ready(self):
        # register agent and actors
        try: # TODO this fails if the database doesn't already exist ... sigh ...
            from tr_ars.api import get_or_create_agent, get_or_create_actor
            agent = dict()
            agent['name'] = AppConfig.app_path
            agent['uri'] = SERVER + reverse(AppConfig.app_path + '-api')
            get_or_create_agent(agent)
            for actor in AppConfig.actors:
                actorObj = dict()
                actorObj['agent'] = agent
                actorObj['channel'] = actor[2]
                actorObj['path'] = actor[1]
                actorObj['remote'] = actor[0]
                get_or_create_actor(actorObj)
        except:
            pass

        logger.debug('### %s ready...' % self.name)

def init_api_fn(actor):
    @csrf_exempt
    def fn(req):
        return callquery(actor[0], req)
    fn.__name__ = actor[1]
    fn.__doc__ = "Forward api request at %s to %s" % (actor[1], actor[0])
    return fn

def index(req):
    data = dict()
    data['agent'] = AppConfig.app_path
    data['actors'] = []
    for actor in AppConfig.actors:
        query_name = AppConfig.app_path + '-' + actor[1]
        actorObj = dict()
        actorObj['name'] = query_name
        actorObj['channel'] = actor[2]
        actorObj['remote'] = actor[0]
        actorObj['path'] = req.build_absolute_uri(reverse(query_name))
        data['actors'].append(actorObj)
    return HttpResponse(json.dumps(data, indent=2),
                        content_type='application/json', status=200)

apipatterns = [path(r'', index, name=AppConfig.app_path + '-api')]
for actor in AppConfig.actors:
    query_path = actor[1]
    query_name = AppConfig.app_path + '-' + query_path
    apipatterns.append(path(query_path, init_api_fn(actor), name=query_name))

urlpatterns = [
    path(r'api/', include(apipatterns)),
]


