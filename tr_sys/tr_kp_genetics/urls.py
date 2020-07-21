from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='kp-genetics-api'),
    path(r'rungeneticsquery', api.runkp, name='kp-genetics-runquery')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
