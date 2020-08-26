from django.apps import AppConfig as SuperAppConfig
from django.urls import path, include
from tr_ars.default_ars_app.api import *

class AppConfig(SuperAppConfig):
    name = 'tr_ara_unsecret.unsecret_app' #must be module dot path
    reasoner = 'https://unsecret.ncats.io/query'
    app_path = 'unsecret'
    regex_path = '^' + app_path + '/'
    query_path = 'run'+app_path+'query'
    query_name = 'ara-unsecret-runquery'

    def ready(self):
        logger.debug('### %s ready...' % self.name)

### code below this line is required, but doesn't require updating in most cases

@csrf_exempt
def runapp(req):
    return callreasoner(AppConfig.reasoner, req)

def index(req):
    return HttpResponse(AppConfig.app_path + ' agent wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
        reverse(AppConfig.query_name)))

apipatterns = [
    path(r'', index, name=AppConfig.app_path + '-api'),
    path(AppConfig.query_path, runapp, name=AppConfig.query_name)
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]


