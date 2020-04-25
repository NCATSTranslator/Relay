from django.urls import path, include

from . import api

apipatterns = [
    path(r'', api.index, name='ars-api'),
#    path(r'registration', api.registration, name='ars-registration'),
    path(r'submit', api.submit, name='ars-submit'),
    path(r'messages', api.messages, name='ars-messages'),
    path(r'agents', api.agents, name='ars-agents'),
    path(r'actors', api.actors, name='ars-actors'),
    path(r'channels', api.channels, name='ars-channels'),
    path(r'agents/<name>', api.agent, name='ars-agent'),
    path(r'messages/<uuid:key>', api.message, name='ars-message'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
