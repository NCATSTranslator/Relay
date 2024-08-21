

from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware

class CustomOpenTelemetryMiddleware(OpenTelemetryMiddleware):
    def __init__(self, application):
        super().__init__(application)
        self.application = application

    def __call__(self, environ, start_response):
        # Skip tracing for GET requests
        if environ.get('REQUEST_METHOD') == 'GET':
            # Call the wrapped application directly without tracing
            return self.application(environ, start_response)

        # Continue with default tracing behavior
        return super().__call__(environ, start_response)

