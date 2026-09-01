import os,sys
import logging
import re

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.sdk.resources import SERVICE_NAME as telemetery_service_name_key, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, Decision, ParentBased, SamplingResult
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.semconv.attributes.http_attributes import HTTP_ROUTE
from celery.signals import worker_process_init

# Don't trace health checks and other noise endpoints.
# Deployment env can override with its own comma separated list with OTEL_PYTHON_DJANGO_EXCLUDED_URLS
DEFAULT_EXCLUDED_URLS = "ars/api/health,ars/api/retain"


class ARSSampler(ParentBased):
    """Drop traces for the catch_timeout beat task, which runs every 3 minutes,
    and for GET requests, which are mostly clients polling for results.

    The excluded-URL list above can't cover either one.
    """

    def should_sample(self, parent_context, trace_id, name, kind=None, attributes=None, *args, **kwargs):
        if name.endswith("/catch_timeout"):
            return SamplingResult(Decision.DROP)
        if kind == SpanKind.SERVER and attributes and attributes.get("http.method") == "GET":
            return SamplingResult(Decision.DROP)
        return super().should_sample(parent_context, trace_id, name, kind, attributes, *args, **kwargs)


def record_error(exc):
    """Attach an exception to the currently active span.

    A span records an exception automatically only when that exception escapes
    it. try/catch blocks that log errors and carry on never let that happen.
    Calling this in such places keeps the trace honest: the active span gets the
    stack trace and an ERROR status, and the caller still decides what to do about the failure.
    """
    try:
        span = trace.get_current_span()
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
    except Exception:
        logging.exception('Failed to record exception on the active OTEL span')


def count_error(exc, attribute):
    """Count an error on the active span, with a traceback only for the first one.

    This avoids significant performance issues from formatting a stack trace on every
    iteration of a hot loop - the repeated traces are identical, so just take the
    first instance and record the error with that. This is only applicable for errors
    that are likely to occur many times in one span. Just use record_error() instead
    for errors that would only fire once per message.
    """
    try:
        span = trace.get_current_span()
        if not span.is_recording():
            return
        count = (span.attributes or {}).get(attribute, 0) + 1
        span.set_attribute(attribute, count)
        if count == 1:
            record_error(exc)
    except Exception:
        logging.exception('Failed to count exception on the active OTEL span')


def _otel_disabled():
    #If we're running pytests, don't instrument OTEL.  We don't need to log the tests and OTEL breaks them anyway
    return "pytest" in sys.modules


def configure_opentelemetry():
    """Set up the tracer provider plus the non-Django instrumentation.

    Idempotent, and deliberately called from more than one place: the top of
    settings.py, ARSConfig.ready() and celery.py.  Deployments mount their own
    settings.py over ours, so a call from that file alone is not something we
    can rely on shipping, and without a provider every span goes to the no-op
    proxy and is silently dropped, middleware installed or not.  The Django
    instrumentation does not live here -- see instrument_django().
    """
    if _otel_disabled():
        return
    # A second call must not reach add_span_processor() below: set_tracer_provider()
    # only warns and no-ops the second time, so get_tracer_provider() would hand
    # back the provider already in place and we would attach a duplicate
    # BatchSpanProcessor to it and export every span twice.  get_tracer_provider()
    # returns a ProxyTracerProvider until a real one is set.
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return
    logging.info('About to instrument ARS app for OTEL')
    try:
        # Read OTLP endpoint config from env vars
        #otlp_host = os.environ.get("JAEGER_HOST", "http://localhost").rstrip('/')
        otlp_host = os.environ.get("JAEGER_HOST", "http://jaeger-otel-collector.sri").rstrip('/')
        otlp_port = os.environ.get("JAEGER_PORT", "4317")
        otlp_endpoint = f'{otlp_host}:{otlp_port}'
        service_name= 'ARS'
        resource = Resource.create({telemetery_service_name_key: service_name})

        trace.set_tracer_provider(
            TracerProvider(resource=resource, sampler=ARSSampler(ALWAYS_ON))
        )

        tracer_provider = trace.get_tracer_provider()

        #configure OTLP Exporter (for Jaeger/Collector/etc.)
        OTLP_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True
        )

        span_processor = BatchSpanProcessor(OTLP_exporter)
        tracer_provider.add_span_processor(span_processor)

        RequestsInstrumentor().instrument()
        # biothings_annotator calls out over httpx, not requests, so without this
        # its spans have no children and the time inside them is unattributable.
        # biothings_annotator does have its own OTEL implementation,
        # it only runs when used as a standalone application, not when imported
        # as a package like it is here.
        HTTPXClientInstrumentor().instrument()
        # Producer side (web/beat processes): hooks before_task_publish so
        # outgoing task messages carry the current trace context.  Celery
        # connects these handlers with weak=False, so prefork children inherit
        # them; the worker_process_init hook below is belt and braces for the
        # case where this never ran in the parent.
        CeleryInstrumentor().instrument()

        @worker_process_init.connect(weak=False)
        def init_celery_tracing(*args, **kwargs):
            # Children inherit the parent's "already instrumented" flag, so a
            # bare instrument() would warn and no-op -- clear it first.
            CeleryInstrumentor().uninstrument()
            CeleryInstrumentor().instrument()


        logging.info('Finished instrumenting ARS app for OTEL')
    except Exception as e:
        logging.error('OTEL instrumentation failed because: %s'%str(e))


def _readable_route(route):
    """Turn a Django URL pattern into the path clients actually call.

    'ars/api/^submit/?$' becomes '/ars/api/submit'.  Routes registered with
    path() rather than re_path() only pick up the leading slash, so
    'ars/api/messages/<uuid:key>' becomes '/ars/api/messages/<uuid:key>'.
    """
    cleaned = route.replace('^', '').replace('$', '')
    cleaned = re.sub(r'/\?(?=/|$)', '', cleaned)  # the optional trailing slash
    cleaned = cleaned.replace('\\', '')  # escapes such as \.
    return '/' + cleaned.lstrip('/')


def _rename_span_for_route(span, request, response):
    """Report the readable path instead of the raw URL pattern.

    The Django instrumentation names each server span after the route template
    Django resolved the request to, so the re_path() endpoints in tr_ars/urls.py
    arrive in Jaeger as 'POST ars/api/^submit/?$'.  Naming spans after the route
    rather than the request path is what we want - otherwise every request for a
    single message would get its UUID baked into the span name - so clean up the
    template instead of going back to paths.
    """
    try:
        if not span.is_recording():
            return
        match = getattr(request, 'resolver_match', None)
        route = getattr(match, 'route', None) if match else None
        if not route:
            return
        readable = _readable_route(route)
        if readable == route:
            return
        # The instrumentation names the span '<METHOD> <route>'; keep whatever
        # prefix it decided on and swap out just the route.
        if span.name.endswith(route):
            span.update_name(span.name[:-len(route)] + readable)
        span.set_attribute(HTTP_ROUTE, readable)
    except Exception:
        logging.exception('Failed to clean up the OTEL span name for a request')


def instrument_django():
    """Install the OTEL Django middleware.

    This is called from ARSConfig.ready(), NOT from settings.py, and that
    matters.  DjangoInstrumentor works by mutating settings.MIDDLEWARE, but
    reading django.conf.settings while the settings module is still being
    imported makes Django build a throwaway Settings object from the
    half-initialised module.  The middleware is inserted into that throwaway
    object and then discarded when the real Settings replaces it, so no server
    spans are ever produced and no incoming traceparent is extracted.

    Deployments mount their own settings.py over ours (see
    deploy/templates/deployment.yaml), so we cannot rely on the call sitting in
    the right place in that file.  App registry ready() runs after settings are
    fully loaded but before the middleware chain is built, which is what we
    need and ships in the image.
    """
    if _otel_disabled():
        return
    try:
        DjangoInstrumentor().instrument(
            excluded_urls=os.environ.get("OTEL_PYTHON_DJANGO_EXCLUDED_URLS", DEFAULT_EXCLUDED_URLS),
            response_hook=_rename_span_for_route
        )
        logging.info('Instrumented Django for OTEL')
    except Exception as e:
        logging.error('OTEL Django instrumentation failed because: %s'%str(e))
