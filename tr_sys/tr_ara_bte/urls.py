from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='ara-bte-api'),
    path(r'runbtequery', api.runbte, name='ara-bte-runquery')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
