from django.urls import path, include

from . import views
from . import api

apipatterns = [
    path(r'', api.index, name='ars-api'),
    path(r'submit', api.submit, name='ars-submit'),
    path(r'messages', api.messages, name='ars-messages'),
    path(r'agents', api.agents, name='ars-agents'),
    path(r'actors', api.actors, name='ars-actors'),
    path(r'channels', api.channels, name='ars-channels'),
    path(r'agents/<name>', api.get_agent, name='ars-agent'),
    path(r'messages/<uuid:key>', api.message, name='ars-message'),
]



urlpatterns = [
    path(r'api/', include(apipatterns)),
    path(r'answer/<uuid:key>', views.answer, name='ars-answer'),
]
