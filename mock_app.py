import logging
import random
import time
import requests
from logging_loki import LokiHandler

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter # Added for HTTP exporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# --- OpenTelemetry (Traces) Setup ---
# This sends traces to Tempo

# Define a resource to set the service.name attribute. This is CRITICAL for Tempo.
resource = Resource(attributes={
    "service.name": "my-app"
})

trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)
# otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
otlp_exporter = OTLPSpanExporter(endpoint="http://127.0.0.1:4318/v1/traces") # Changed to HTTP exporter with correct endpoint
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# --- Logging (Loki) Setup ---
def create_loki_logger(service_name):
    handler = LokiHandler(
        url="http://127.0.0.1:3100/loki/api/v1/push",
        tags={"application": "my-app", "service": service_name},
        version="1",
    )
    # Create a custom formatter to add the service name to the message
    formatter = logging.Formatter(f'[{service_name}] - %(message)s')
    handler.setFormatter(formatter)

    logger = logging.getLogger(service_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

loggers = {
    "frontend": create_loki_logger("frontend"),
    "backend": create_loki_logger("backend"),
    "database": create_loki_logger("database"),
}

# --- Simulation Logic ---
def get_trace_id():
    """Injects traceID into logs for correlation."""
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        return format(ctx.trace_id, 'x')
    return None

def database_operation():
    """This function now returns True for success and False for failure."""
    with tracer.start_as_current_span("db_query") as db_span:
        loggers["database"].info("Executing database query", extra={"tags": {"trace_id": get_trace_id()}})
        time.sleep(random.uniform(0.05, 0.1))
        # Simulate occasional DB errors (e.g., 8% chance)
        if random.random() < 0.08:
            db_span.set_status(trace.Status(trace.StatusCode.ERROR, "DB connection failed"))
            loggers["database"].error("DB connection failed", extra={"tags": {"trace_id": get_trace_id()}})
            return False # Indicate failure
        loggers["database"].info("Query successful", extra={"tags": {"trace_id": get_trace_id()}})
        return True # Indicate success

def backend_process():
    """This function also returns True/False and has its own failure chance."""
    with tracer.start_as_current_span("backend_processing") as backend_span:
        loggers["backend"].info("Processing request in backend", extra={"tags": {"trace_id": get_trace_id()}})
        
        # Independent backend error (e.g., 5% chance of a cache failure)
        if random.random() < 0.05:
            backend_span.set_status(trace.Status(trace.StatusCode.ERROR, "Cache service unavailable"))
            loggers["backend"].error("Cache service unavailable", extra={"tags": {"trace_id": get_trace_id()}})
            return False

        time.sleep(random.uniform(0.1, 0.3))
        
        # Call the next service
        if not database_operation():
            # The error came from the database, but the backend is also failing because of it.
            backend_span.set_status(trace.Status(trace.StatusCode.ERROR, "Downstream DB error"))
            loggers["backend"].error("Backend failed due to downstream DB error", extra={"tags": {"trace_id": get_trace_id()}})
            return False

        loggers["backend"].info("Backend processing successful", extra={"tags": {"trace_id": get_trace_id()}})
        return True

def frontend_request():
    # This is the parent span for the entire request
    with tracer.start_as_current_span("/api/users", kind=trace.SpanKind.SERVER) as parent_span:
        loggers["frontend"].info("Received request for /api/users", extra={"tags": {"trace_id": get_trace_id()}})

        # Independent frontend error (e.g., 3% chance of a bad request/auth issue)
        if random.random() < 0.03:
            parent_span.set_status(trace.Status(trace.StatusCode.ERROR, "Invalid user session"))
            loggers["frontend"].error("Invalid user session token", extra={"tags": {"trace_id": get_trace_id()}})
            return # End the request here

        # Call the backend service and handle its success/failure response
        if backend_process():
            parent_span.set_status(trace.Status(trace.StatusCode.OK))
            loggers["frontend"].info("Request to /api/users successful", extra={"tags": {"trace_id": get_trace_id()}})
        else:
            parent_span.set_status(trace.Status(trace.StatusCode.ERROR, "Request failed in backend"))
            loggers["frontend"].error("Request to /api/users failed due to backend error", extra={"tags": {"trace_id": get_trace_id()}})

if __name__ == "__main__":
    print("Starting mock application... Press Ctrl+C to stop.")
    while True:
        try:
            frontend_request()
            time.sleep(random.uniform(1, 5))
        except KeyboardInterrupt:
            print("Stopping application.")
            break

