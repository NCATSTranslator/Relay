import os
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME as telemetery_service_name_key, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

def configure_opentelemetry():

    #jaeger_host = os.environ.get('JAEGER_HOST', 'jaeger-otel-agent')
    #jaeger_port = int(os.environ.get('JAEGER_PORT', '6831'))
    jaeger_host= 'jaeger-otel-agent.sri'
    jaeger_port= 6831
    resource = Resource.create({telemetery_service_name_key: 'ARS'})

    trace.set_tracer_provider(TracerProvider(resource=resource))

    tracer_provider = trace.get_tracer_provider()

    # Configure Jaeger Exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )

    span_processor = BatchSpanProcessor(jaeger_exporter)
    tracer_provider.add_span_processor(span_processor)

    #if we want the default POST changes to sth customize, we can add hooks to the Request Instrumentation
    # def request_hook(span, request, result):
    #     if span and request.method == "POST":
    #         span.update_name(f"Custom POST to {request.url}")
    # # Instrument requests with the custom hook
    # RequestsInstrumentor().instrument(request_hook=request_hook)

    # Optional: Console exporter for debugging
    console_exporter = ConsoleSpanExporter()
    tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

    DjangoInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    RequestsInstrumentor().instrument()