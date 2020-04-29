from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='ara-robokop-api'),
    path(r'runquick', api.runquick, name='ara-robokop-runquick'),
    path(r'runpost', api.runpost, name='ara-robokop-runpost'),
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
