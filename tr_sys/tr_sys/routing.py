from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import tr_ars.routing as ars_router
from .middleware import CustomOpenTelemetryMiddleware

application = ProtocolTypeRouter({
    "http": CustomOpenTelemetryMiddleware(get_asgi_application()),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            ars_router.ws_urlpatterns  # Routes WebSocket requests
        )
    ),
})
