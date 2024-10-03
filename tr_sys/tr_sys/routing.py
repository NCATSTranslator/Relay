import os
import logging
import django
django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import tr_ars.routing as ars_router
from .middleware import CustomOpenTelemetryMiddleware


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tr_sys.settings")
logger = logging.getLogger(__name__)
logger.debug("Starting ASGI application")

application = ProtocolTypeRouter({
    "http": CustomOpenTelemetryMiddleware(get_asgi_application()),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            ars_router.ws_urlpatterns  # Routes WebSocket requests
        )
    ),
})
logger.debug("ASGI application loaded")