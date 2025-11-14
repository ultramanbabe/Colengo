import logging
import random
import time
from logging_loki import LokiHandler

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

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
    "my-app": create_loki_logger("my-app"),
}

# --- OpenTelemetry (Tempo) Setup - Three Separate Tracer Providers ---
def create_tracer_provider(service_name):
    """Create a separate tracer provider for each service"""
    resource = Resource(attributes={
        "service.name": service_name
    })
    
    provider = TracerProvider(resource=resource)
    
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://127.0.0.1:4318/v1/traces"
    )
    
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    return provider

# Create separate tracer providers for each service
frontend_provider = create_tracer_provider("frontend")
backend_provider = create_tracer_provider("backend")
database_provider = create_tracer_provider("database")

# Create separate tracers from each provider
frontend_tracer = frontend_provider.get_tracer("frontend")
backend_tracer = backend_provider.get_tracer("backend")
database_tracer = database_provider.get_tracer("database")

def get_trace_id():
    """Helper to get the current trace ID for logging correlation"""
    span = trace.get_current_span()
    if span:
        trace_id = span.get_span_context().trace_id
        return format(trace_id, '032x')
    return "unknown"

# --- Service Functions ---
def database_operation():
    """This function now returns True for success and False for failure."""
    with database_tracer.start_as_current_span("db_query") as db_span:
        time.sleep(random.uniform(0.05, 0.15))
        
        # Simulate occasional DB errors (e.g., 8% chance)
        if random.random() < 0.08:
            db_span.set_status(trace.Status(trace.StatusCode.ERROR, "DB connection failed"))
            loggers["database"].error("DB connection failed", extra={"tags": {"trace_id": get_trace_id()}})
            return False # Indicate failure
        loggers["database"].info("Query successful", extra={"tags": {"trace_id": get_trace_id()}})
        return True # Indicate success

def backend_process():
    with backend_tracer.start_as_current_span("backend_processing", kind=trace.SpanKind.INTERNAL) as backend_span:
        
        # Independent backend error (e.g., 5% chance of a cache failure)
        if random.random() < 0.05:
            backend_span.set_status(trace.Status(trace.StatusCode.ERROR, "Cache service unavailable"))
            loggers["backend"].error("Cache service unavailable", extra={"tags": {"trace_id": get_trace_id()}})
            return False

        time.sleep(random.uniform(0.1, 0.3))
        
        # Call the database
        db_success = database_operation()
        if not db_success:
            backend_span.set_status(trace.Status(trace.StatusCode.ERROR, "Downstream DB error"))
            loggers["backend"].error("Backend failed due to downstream DB error", extra={"tags": {"trace_id": get_trace_id()}})
            return False
        
        loggers["backend"].info("Backend processing complete", extra={"tags": {"trace_id": get_trace_id()}})
        return True

def frontend_request():
    # This is the parent span for the entire request
    with frontend_tracer.start_as_current_span("/api/users", kind=trace.SpanKind.SERVER) as parent_span:
        trace_id = get_trace_id()
        loggers["frontend"].info(f"Received request for /api/users", extra={"tags": {"trace_id": trace_id}})
        
        # Independent frontend error (e.g., 3% chance of a bad request/auth issue)
        if random.random() < 0.03:
            parent_span.set_status(trace.Status(trace.StatusCode.ERROR, "Invalid user session"))
            loggers["frontend"].error("Invalid user session token", extra={"tags": {"trace_id": trace_id}})
            return # End the request here

        # Call the backend service and handle its success/failure response
        backend_success = backend_process()
        if not backend_success:
            parent_span.set_status(trace.Status(trace.StatusCode.ERROR, "Backend error"))
            loggers["frontend"].error("Request to /api/users failed due to backend error", extra={"tags": {"trace_id": trace_id}})
            return
        
        # If we get here, everything succeeded
        parent_span.set_status(trace.Status(trace.StatusCode.OK))
        loggers["frontend"].info("Transaction successful", extra={"tags": {"trace_id": trace_id}})

def main_loop():
    while True:
        try:
            frontend_request()
        except Exception as e:
            # This is a generic, unexpected error
            loggers["my-app"].error(f"An unexpected error occurred: {e}", extra={"tags": {"trace_id": "unknown"}})
        
        time.sleep(random.uniform(0.5, 1.5))

if __name__ == "__main__":
    print("Starting mock application with distributed tracing...")
    print("Sending logs to Loki at http://127.0.0.1:3100")
    print("Sending traces to Tempo at http://127.0.0.1:4318")
    main_loop()

