from django.apps import AppConfig
from django.urls import path, include
from tr_ars.default_ars_app.api import *

REASONER_URL = 'https://unsecret.ncats.io/query'

class UnsecretConfig(AppConfig):
    name = 'tr_ara_unsecret.unsecret_app'

    def ready(self):
        logger.debug('### %s ready...' % self.name)

@csrf_exempt
def runapp(req):
    return callreasoner(REASONER_URL, req)

def index(req):
    return HttpResponse('Unsecret Agent wrapper API available via POST at %s\n'
                        % req.build_absolute_uri(
        reverse('ara-unsecret-runquery')))

apipatterns = [
    path(r'', index, name='ara-unsecret-api'),
    path(r'rununsecretquery', runapp, name='ara-unsecret-runquery')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]


