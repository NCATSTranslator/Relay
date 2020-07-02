from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='ara-ncats-api'),
    path(r'runquery', api.runquery, name='ara-ncats-runquery')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
