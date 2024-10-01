
import re
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

class CustomOpenTelemetryMiddleware(OpenTelemetryMiddleware):
    def __init__(self, application):
        super().__init__(application)
        self.application = application

    EXCLUDE_PATTERNS = [
            r'^/ars/api/messages/.*$',  # Example pattern to exclude
            r'^/ars/api/retain/.*$'
        ]
    async def __call__(self,  scope, receive, send):
        # Extract the HTTP method and path from the ASGI scope
        if scope['type'] == 'http':
            method = scope.get('method')
            path = scope.get('path', '')

        # Skip tracing for GET requests
        if method == 'GET':
            # Call the wrapped application directly without tracing
            return await self.application(scope, receive, send)
        elif method == 'POST':
            for pattern in self.EXCLUDE_PATTERNS:
                if re.match(pattern, path):
                    return await self.application(scope, receive, send)

        # Continue with the default OpenTelemetry behavior
        await super().__call__(scope, receive, send)

