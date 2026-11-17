"""
WSGI config for tr_sys project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application
from tr_sys.gc_tuning import apply_gc_threshold

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tr_sys.settings")

application = get_wsgi_application()

apply_gc_threshold()
