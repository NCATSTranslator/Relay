from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='ara-unsecret-api'),
    path(r'rununsecretquery', api.runara, name='ara-unsecret-runquery')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
