from django.urls import path, include
from . import api

apipatterns = [
    path(r'', api.index, name='kp-molecular-api'),
    path(r'runmolecularquery', api.runkp, name='kp-molecular-runquery')
]

urlpatterns = [
    path(r'api/', include(apipatterns)),
]
