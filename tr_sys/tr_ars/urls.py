from django.urls import path, re_path, include

from . import api

apipatterns = [
    path('', api.index, name='ars-api'),
    re_path(r'^submit/?$', api.submit, name='ars-submit'),
    re_path(r'^messages/?$', api.messages, name='ars-messages'),
    re_path(r'^agents/?$', api.agents, name='ars-agents'),
    re_path(r'^actors/?$', api.actors, name='ars-actors'),
    re_path(r'^channels/?$', api.channels, name='ars-channels'),
    path('agents/<name>', api.get_agent, name='ars-agent'),
    path('messages/<uuid:key>', api.message, name='ars-message'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
