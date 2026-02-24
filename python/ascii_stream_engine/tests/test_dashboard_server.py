"""Tests for the DashboardServer HTTP endpoints."""

import json
import socket
import time
import urllib.request

import pytest

from ascii_stream_engine.infrastructure.dashboard.server import DashboardServer
from ascii_stream_engine.infrastructure.performance.budget_tracker import BudgetTracker
from ascii_stream_engine.infrastructure.performance.metrics_aggregator import MetricsAggregator
from ascii_stream_engine.infrastructure.performance.metrics_exporter import MetricsExporter


def _find_free_port():
    """Find a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_exporter():
    """Create a MetricsExporter with sample data."""
    agg = MetricsAggregator(sample_interval=0.0)
    tracker = BudgetTracker()
    agg.record_snapshot(
        {
            "fps": 30.0,
            "frames_processed": 100,
            "total_errors": 0,
            "errors_by_component": {},
            "latency_avg": 0.033,
            "latency_min": 0.020,
            "latency_max": 0.050,
            "uptime": 10.0,
        },
        {
            "capture": {
                "count": 100,
                "total_time": 0.1,
                "avg_time": 0.001,
                "min_time": 0.0005,
                "max_time": 0.003,
                "std_dev": 0.0003,
            },
        },
    )
    tracker.record_phase("capture", 0.001)
    tracker.record_frame(0.033)
    return MetricsExporter(agg, tracker)


@pytest.fixture
def server():
    """Create and start a dashboard server on a free port."""
    port = _find_free_port()
    exporter = _make_exporter()
    srv = DashboardServer(
        host="127.0.0.1",
        port=port,
        metrics_exporter=exporter,
    )
    srv.start()
    time.sleep(0.3)  # Allow server to start
    yield srv
    srv.stop()


@pytest.fixture
def base_url(server):
    """Get the base URL for the server."""
    return server.get_url()


def _get_json(url):
    """Make a GET request and parse JSON response."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


class TestDashboardServerLifecycle:
    """Tests for server start/stop."""

    def test_start_stop(self):
        """Server starts and stops cleanly."""
        port = _find_free_port()
        srv = DashboardServer(host="127.0.0.1", port=port)
        srv.start()
        assert srv.is_running()
        srv.stop()
        assert not srv.is_running()

    def test_get_url(self):
        """get_url returns correct URL."""
        port = _find_free_port()
        srv = DashboardServer(host="127.0.0.1", port=port)
        assert srv.get_url() == f"http://127.0.0.1:{port}"

    def test_double_start(self):
        """Double start is safe."""
        port = _find_free_port()
        srv = DashboardServer(host="127.0.0.1", port=port)
        srv.start()
        srv.start()  # Should not raise
        srv.stop()

    def test_double_stop(self):
        """Double stop is safe."""
        port = _find_free_port()
        srv = DashboardServer(host="127.0.0.1", port=port)
        srv.start()
        srv.stop()
        srv.stop()  # Should not raise


class TestHealthEndpoint:
    """Tests for /api/health."""

    def test_health_returns_200(self, base_url):
        """Health endpoint returns 200."""
        status, data = _get_json(f"{base_url}/api/health")
        assert status == 200

    def test_health_contains_status(self, base_url):
        """Health response contains status field."""
        _, data = _get_json(f"{base_url}/api/health")
        assert data["status"] == "ok"

    def test_health_contains_uptime(self, base_url):
        """Health response contains uptime field."""
        _, data = _get_json(f"{base_url}/api/health")
        assert "uptime" in data
        assert isinstance(data["uptime"], (int, float))


class TestMetricsEndpoint:
    """Tests for /api/metrics."""

    def test_metrics_returns_200(self, base_url):
        """Metrics endpoint returns 200."""
        status, data = _get_json(f"{base_url}/api/metrics")
        assert status == 200

    def test_metrics_contains_current(self, base_url):
        """Metrics response contains current metrics."""
        _, data = _get_json(f"{base_url}/api/metrics")
        assert "current" in data
        assert data["current"]["fps"] == 30.0

    def test_metrics_contains_budget(self, base_url):
        """Metrics response contains budget data."""
        _, data = _get_json(f"{base_url}/api/metrics")
        assert "budget" in data


class TestBudgetEndpoint:
    """Tests for /api/budget."""

    def test_budget_returns_200(self, base_url):
        """Budget endpoint returns 200."""
        status, data = _get_json(f"{base_url}/api/budget")
        assert status == 200

    def test_budget_contains_utilization(self, base_url):
        """Budget response contains utilization data."""
        _, data = _get_json(f"{base_url}/api/budget")
        assert "utilization" in data
        assert "violations" in data


class TestInstancesEndpoint:
    """Tests for /api/instances."""

    def test_instances_returns_200(self, base_url):
        """Instances endpoint returns 200 even without collector."""
        status, data = _get_json(f"{base_url}/api/instances")
        assert status == 200
        assert "instances" in data


class TestHistoryEndpoint:
    """Tests for /api/metrics/history."""

    def test_history_returns_200(self, base_url):
        """History endpoint returns 200."""
        status, data = _get_json(f"{base_url}/api/metrics/history?seconds=60")
        assert status == 200
        assert "history" in data


class TestNotFoundEndpoint:
    """Tests for unknown routes."""

    def test_unknown_route_returns_404(self, base_url):
        """Unknown route returns 404 JSON."""
        try:
            req = urllib.request.Request(f"{base_url}/api/nonexistent")
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except urllib.error.HTTPError as e:
            assert e.code == 404
            data = json.loads(e.read().decode("utf-8"))
            assert "error" in data


class TestCorsHeaders:
    """Tests for CORS headers."""

    def test_cors_header_present(self, base_url):
        """Responses include Access-Control-Allow-Origin header."""
        req = urllib.request.Request(f"{base_url}/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            cors = resp.headers.get("Access-Control-Allow-Origin")
            assert cors == "*"


class TestStreamEndpoint:
    """Tests for /stream MJPEG endpoint."""

    def test_stream_without_buffer_returns_503(self, base_url):
        """Stream endpoint returns 503 when no frame buffer configured."""
        try:
            req = urllib.request.Request(f"{base_url}/stream")
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except urllib.error.HTTPError as e:
            assert e.code == 503
            data = json.loads(e.read().decode("utf-8"))
            assert "error" in data
