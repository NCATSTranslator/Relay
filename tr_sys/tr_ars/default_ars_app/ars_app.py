from django.apps import AppConfig as SuperAppConfig
from django.urls import path, include
from tr_ars.default_ars_app.api import *
import sys
import traceback

class AppConfig(SuperAppConfig):
    name = 'tr_ars.default_ars_app.ars_app' # must be dot path for module
    actors = [make_actorconf('infores:ars',  # !!! Fictitous infores
                            'http://localhost:8080/query', 'runquery', 'general')] # tuple of remote, name, channel; run default test server as `python simple-trapi-test-server.py`
    app_path = 'example'
    regex_path = '^' + app_path + '/'

### code below this line is required, but doesn't require updating in most cases

    def ready(self):
        # register agent and actors
        try: # TODO this fails if the database doesn't already exist ... sigh ...
            from tr_ars.api import get_or_create_agent, get_or_create_actor
            agent = dict()
            agent['name'] = self.app_path
            agent['uri'] = reverse(self.app_path + '-api')
            get_or_create_agent(agent)
            #logger.debug('### agent: {0} {1}'.format(agentObj, status));
            for actorconf in self.actors:
                actorObj = dict()
                actorObj['agent'] = agent
                actorObj['channel'] =  actorconf.path()
                actorObj['path'] = actorconf.name()
                actorObj['remote'] = actorconf.query()
                actorObj['inforesid'] = actorconf.inforesid()
                get_or_create_actor(actorObj)

        except:
            #traceback.print_exc()
            pass

        logger.debug('### %s ready...' % self.name)


apipatterns = [path(r'', init_api_index(AppConfig.actors, AppConfig.app_path), name=AppConfig.app_path + '-api')]
for actor in AppConfig.actors:
    query_path = actor.name()
    query_name = AppConfig.app_path + '-' + query_path
    apipatterns.append(path(query_path, init_api_fn(actor), name=query_name))

urlpatterns = [
    path(r'', init_redirect(AppConfig.app_path), name=AppConfig.app_path + '-base'),
    path(r'api/', include(apipatterns)),
]


