from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='ara-robokop-api'),
    path(r'runquick', api.runquick, name='ara-robokop-runquick'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]

