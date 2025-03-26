"""
Metrics collection for the Stock Scanner application.

This module provides a centralized way to collect and expose metrics for the
application. It uses the Prometheus client library to collect metrics and
expose them via HTTP endpoints.

Note: This module requires the prometheus_client library to be installed.
You can install it with pip:
    pip install prometheus-client

Usage:
    from backend.core.metrics import metrics

    # Increment a counter
    metrics.counter('api_requests_total').inc()

    # Observe a histogram
    metrics.histogram('request_duration_seconds').observe(duration)

    # Set a gauge
    metrics.gauge('connected_users').set(connected_users)
"""

import time
from typing import Dict, Optional, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, Gauge, Summary, REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware


class Metrics:
    """
    Metrics collection for the Stock Scanner application.

    This class provides methods for collecting and exposing metrics for the
    application. It uses the Prometheus client library to collect metrics and
    expose them via HTTP endpoints.

    Attributes:
        _counters (Dict[str, Counter]): Dictionary of Counter metrics.
        _histograms (Dict[str, Histogram]): Dictionary of Histogram metrics.
        _gauges (Dict[str, Gauge]): Dictionary of Gauge metrics.
        _summaries (Dict[str, Summary]): Dictionary of Summary metrics.
    """

    def __init__(self):
        """Initialize the metrics collection."""
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._summaries: Dict[str, Summary] = {}

        # Common metrics that are used across all services
        self.counter('http_requests_total', 'Total number of HTTP requests', ['method', 'endpoint', 'status'])
        self.histogram('http_request_duration_seconds', 'HTTP request duration in seconds', ['method', 'endpoint'])
        self.gauge('process_start_time_seconds', 'Start time of the process since unix epoch in seconds')
        self.gauge('process_start_time_seconds').set_to_current_time()

    def counter(self, name: str, description: str = '', labels: Optional[list] = None) -> Counter:
        """
        Get or create a Counter metric.

        Args:
            name (str): The name of the metric.
            description (str, optional): The description of the metric. Defaults to ''.
            labels (Optional[list], optional): The labels for the metric. Defaults to None.

        Returns:
            Counter: The Counter metric.
        """
        if name not in self._counters:
            self._counters[name] = Counter(name, description, labels or [])
        return self._counters[name]

    def histogram(self, name: str, description: str = '', labels: Optional[list] = None, 
                 buckets: Optional[list] = None) -> Histogram:
        """
        Get or create a Histogram metric.

        Args:
            name (str): The name of the metric.
            description (str, optional): The description of the metric. Defaults to ''.
            labels (Optional[list], optional): The labels for the metric. Defaults to None.
            buckets (Optional[list], optional): The buckets for the histogram. Defaults to None.

        Returns:
            Histogram: The Histogram metric.
        """
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, description, labels or [], buckets=buckets)
        return self._histograms[name]

    def gauge(self, name: str, description: str = '', labels: Optional[list] = None) -> Gauge:
        """
        Get or create a Gauge metric.

        Args:
            name (str): The name of the metric.
            description (str, optional): The description of the metric. Defaults to ''.
            labels (Optional[list], optional): The labels for the metric. Defaults to None.

        Returns:
            Gauge: The Gauge metric.
        """
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, description, labels or [])
        return self._gauges[name]

    def summary(self, name: str, description: str = '', labels: Optional[list] = None) -> Summary:
        """
        Get or create a Summary metric.

        Args:
            name (str): The name of the metric.
            description (str, optional): The description of the metric. Defaults to ''.
            labels (Optional[list], optional): The labels for the metric. Defaults to None.

        Returns:
            Summary: The Summary metric.
        """
        if name not in self._summaries:
            self._summaries[name] = Summary(name, description, labels or [])
        return self._summaries[name]

    def generate_latest(self) -> bytes:
        """
        Generate the latest metrics in Prometheus format.

        Returns:
            bytes: The latest metrics in Prometheus format.
        """
        return generate_latest(REGISTRY)

# Create a singleton instance of the Metrics class
metrics = Metrics()

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting HTTP request metrics.

    This middleware collects metrics for HTTP requests, including the number of
    requests, request duration, and request status.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process an incoming request and record metrics.

        Args:
            request (Request): The incoming request.
            call_next (Callable): The next middleware or route handler.

        Returns:
            Response: The response from the next middleware or route handler.
        """
        # Skip metrics collection for the metrics endpoint itself
        if request.url.path == '/metrics':
            return await call_next(request)

        # Record request start time
        start_time = time.time()

        # Process the request
        response = await call_next(request)

        # Record request duration
        duration = time.time() - start_time

        # Record metrics
        metrics.counter('http_requests_total').labels(
            request.method, request.url.path, response.status_code
        ).inc()

        metrics.histogram('http_request_duration_seconds').labels(
            request.method, request.url.path
        ).observe(duration)

        return response

def setup_metrics(app: FastAPI) -> None:
    """
    Set up metrics collection for a FastAPI application.

    This function adds the metrics middleware and endpoint to a FastAPI application.

    Args:
        app (FastAPI): The FastAPI application to set up metrics for.
    """
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)

    # Add metrics endpoint
    @app.get('/metrics')
    async def metrics_endpoint():
        """Endpoint for exposing Prometheus metrics."""
        return Response(
            content=metrics.generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
