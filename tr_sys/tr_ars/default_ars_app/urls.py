from django.urls import path, include

from . import api

apipatterns = [
    path(r'', api.index, name='app-name-api'),
    path(r'runappquery', api.runapp, name='run-app-query')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
