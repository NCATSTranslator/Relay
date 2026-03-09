import os,sys
import logging
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME , Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from celery.signals import worker_process_init

def running_under_pytest() -> bool:
    return "pytest" in sys.modules

def configure_opentelemetry():

    logging.info('About to instrument ARS app for OTEL')
    try:
        
        service_name= os.environ.get("OTEL_SERVICE_NAME","ARS")

        #create provider and set it immediately
        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        if running_under_pytest():
        # Optional: enable console debug in local tests if desired
            if os.environ.get("OTEL_CONSOLE_DEBUG", "").lower() in ("1", "true", "yes"):
                provider.add_span_processor(
                    SimpleSpanProcessor(ConsoleSpanExporter())
                )
            logging.info("Running under pytest — skipped network exporters/instrumentation")
            return
        
        # === non-test runtime: add network exporter (OTLP example) ===
        jaeger_host= os.environ.get("JAEGER_HOST", "jaeger")
        jaeger_port= os.environ.get("JAEGER_PORT", "6381") # common default thrift port
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=int(jaeger_port)
        )
        
        processor = BatchSpanProcessor(jaeger_exporter)
        provider.add_span_processor(processor)
        


        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()

        @worker_process_init.connect(weak=False)
        def init_celery_tracing(*args, **kwargs):
            CeleryInstrumentor().instrument()


        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))