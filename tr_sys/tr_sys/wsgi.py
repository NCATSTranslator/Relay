"""
WSGI config for tr_sys project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import os
from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware
from django.core.wsgi import get_wsgi_application
from .middleware import CustomOpenTelemetryMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tr_sys.settings")

application = get_wsgi_application()
# Wrap the Django application with your custom middleware
application = CustomOpenTelemetryMiddleware(application)
#application = OpenTelemetryMiddleware(application)