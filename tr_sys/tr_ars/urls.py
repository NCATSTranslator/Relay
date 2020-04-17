from django.urls import path, include

from . import api

apipatterns = [
    path(r'', api.index, name='ars-api'),
    path(r'registration', api.registration, name='ars-registration'),
    path(r'states', api.states, name='ars-states'),
    path(r'agents', api.agents, name='ars-agents'),
    path(r'actors', api.actors, name='ars-actors'),
    path(r'channels', api.channels, name='ars-channels'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
