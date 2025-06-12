
import re
from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware

class CustomOpenTelemetryMiddleware(OpenTelemetryMiddleware):
    def __init__(self, application):
        super().__init__(application)
        self.application = application

    EXCLUDE_PATTERNS = [
            r'^/ars/api/messages/.*$',  # Example pattern to exclude
            r'^/ars/api/retain/.*$',
            r'^/ars/api/health/.*$'
        ]
    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD')
        path = environ.get('PATH_INFO', '')

        # Skip tracing for GET requests
        if method == 'GET':
            # Call the wrapped application directly without tracing
            return self.application(environ, start_response)
        elif method == 'POST':
            for pattern in self.EXCLUDE_PATTERNS:
                if re.match(pattern, path):
                    return self.application(environ, start_response)

        # Continue with default tracing behavior
        return super().__call__(environ, start_response)

