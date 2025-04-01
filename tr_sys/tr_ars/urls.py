from django.urls import path, re_path, include

from . import views
from . import api
from . import views

apipatterns = [
    path('', api.index, name='ars-api'),
    re_path(r'^submit/?$', api.submit, name='ars-submit'),
    re_path(r'^messages/?$', api.messages, name='ars-messages'),
    re_path(r'^agents/?$', api.agents, name='ars-agents'),
    re_path(r'^actors/?$', api.actors, name='ars-actors'),
    re_path(r'^channels/?$', api.channels, name='ars-channels'),
    path('agents/<name>', api.get_agent, name='ars-agent'),
    path('messages/<uuid:key>', api.message, name='ars-message'),
    re_path(r'^filters/?$', api.filters, name='ars-filters'),
    path('filter/<uuid:key>', api.filter, name='ars-filter'),
    path('reports/<inforesid>',api.get_report,name='ars-report'),
    re_path(r'^timeoutTest/?$', api.timeoutTest, name='ars-timeout'),
    path('merge/<uuid:key>', api.merge, name='ars-merge'),
    path('retain/<uuid:key>', api.retain, name='ars-retain'),
    path('block/<uuid:key>', api.block, name='ars-block'),
    path('latest_pk/<int:n>', api.latest_pk, name='ars-latestPK'),
    re_path(r'^query_event_subscribe/?$', api.query_event_subscribe, name='ars-subscribe'),
    re_path(r'^query_event_unsubscribe/?$', api.query_event_unsubscribe, name='ars-unsubscribe'),
    path('post_process/<uuid:key>', api.post_process, name='ars-post_process_debug')
]



urlpatterns = [
    path(r'', api.api_redirect, name='ars-base'),
    path(r'app/', views.app_home, name='ars-app-home'),
    path(r'app/status', views.status, name='ars-app-status'),
    path(r'api/', include(apipatterns)),
    path(r'answer/<uuid:key>', views.answer, name='ars-answer'),
]
