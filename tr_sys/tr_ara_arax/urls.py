from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='ara-arax-api'),
    path(r'query', api.runquery, name='ara-arax-query'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
