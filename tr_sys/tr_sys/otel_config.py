import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME as telemetery_service_name_key, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from celery.signals import worker_process_init


def configure_opentelemetry():

    #jaeger_host = os.environ.get('JAEGER_HOST', 'jaeger-otel-agent')
    #jaeger_port = int(os.environ.get('JAEGER_PORT', '6831'))
    logging.info('About to instrument ARS app for OTEL')
    try:
        jaeger_host= 'jaeger-otel-agent.sri'
        jaeger_port= 6831
        service_name= 'ARS'
        @worker_process_init.connect(weak=False)
        def init_celery_tracing(**kwargs):
            resource = Resource.create({telemetery_service_name_key: service_name})

            trace.set_tracer_provider(TracerProvider(resource=resource))

            tracer_provider = trace.get_tracer_provider()

            # Configure Jaeger Exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
            )

            span_processor = BatchSpanProcessor(jaeger_exporter)
            tracer_provider.add_span_processor(span_processor)

            # Optional: Console exporter for debugging
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

            DjangoInstrumentor().instrument()
            RequestsInstrumentor().instrument()
            CeleryInstrumentor().instrument()


            logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))