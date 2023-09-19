#!/usr/bin/env python
import os
import sys
import requests

if __name__ == "__main__":
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tr_sys.settings")
    try:
        from django.core.management import execute_from_command_line

    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    from opentelemetry import trace
    from opentelemetry.propagate import inject
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    execute_from_command_line(sys.argv)


    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer_provider().get_tracer(__name__)

    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter())
    )


    with tracer.start_as_current_span("client"):

        with tracer.start_as_current_span("client-server"):
            headers = {}
            inject(headers)
            requested = requests.get(
                "http://localhost:8000",
                headers=headers,
            )

            assert requested.status_code == 200

