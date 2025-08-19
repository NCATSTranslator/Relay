import os,sys
import logging
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME as telemetery_service_name_key, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from celery.signals import worker_process_init


def configure_opentelemetry():

    logging.info('About to instrument ARS app for OTEL')
    try:
        # Read OTLP endpoint config from env vars
        otlp_host = os.environ.get("JAEGER_HOST", "http://localhost").rstrip('/')
        #otlp_host = os.environ.get("JAEGER_HOST", "http://jaeger-otel-collector").rstrip('/')
        otlp_port = os.environ.get("JAEGER_PORT", "4317")
        otlp_endpoint = f'{otlp_host}:{otlp_port}'
        service_name= 'ARS'
        resource = Resource.create({telemetery_service_name_key: service_name})

        trace.set_tracer_provider(TracerProvider(resource=resource))

        tracer_provider = trace.get_tracer_provider()

        #configure OTLP Exporter (for Jaeger/Collector/etc.)
        OTLP_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True
        )

        span_processor = BatchSpanProcessor(OTLP_exporter)
        tracer_provider.add_span_processor(span_processor)

        #adding this if condition because with pytest the test proces shuts down then opentelemtry SDK or console exporter is trying to log for a closed operation
        # Console exporter for debugging
        if "pytest" not in sys.modules:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        if "pytest" not in sys.modules:
            DjangoInstrumentor().instrument()
            RequestsInstrumentor().instrument()

        @worker_process_init.connect(weak=False)
        def init_celery_tracing(*args, **kwargs):
            CeleryInstrumentor().instrument()


        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))