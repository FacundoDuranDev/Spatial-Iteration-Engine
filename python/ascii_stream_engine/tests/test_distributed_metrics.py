"""Tests for distributed metrics: protocol, reporter, collector."""

import socket
import threading
import time

import pytest

from ascii_stream_engine.infrastructure.distributed.metrics_collector import MetricsCollector
from ascii_stream_engine.infrastructure.distributed.metrics_reporter import MetricsReporter
from ascii_stream_engine.infrastructure.distributed.protocol import MetricsMessage


class TestMetricsMessage:
    """Tests for MetricsMessage protocol."""

    def test_serialize_deserialize_roundtrip(self):
        """Message round-trips through serialize/deserialize."""
        msg = MetricsMessage(
            version=1,
            instance_id="test-1",
            timestamp=12345.6789,
            metrics={"fps": 30.0, "frames": 100},
        )
        data = msg.serialize()
        restored = MetricsMessage.deserialize(data)
        assert restored.version == 1
        assert restored.instance_id == "test-1"
        assert restored.timestamp == 12345.6789
        assert restored.metrics["fps"] == 30.0
        assert restored.metrics["frames"] == 100

    def test_serialize_compact_keys(self):
        """Serialized format uses compact keys."""
        msg = MetricsMessage(version=1, instance_id="x", timestamp=1.0, metrics={})
        data = msg.serialize()
        text = data.decode("utf-8")
        assert '"v":' in text
        assert '"id":' in text
        assert '"ts":' in text
        assert '"m":' in text

    def test_deserialize_invalid_json(self):
        """Deserialize raises on invalid JSON."""
        with pytest.raises(ValueError, match="Invalid"):
            MetricsMessage.deserialize(b"not json")

    def test_create_now(self):
        """create_now sets current timestamp."""
        msg = MetricsMessage.create_now("inst-1", {"fps": 25.0})
        assert msg.instance_id == "inst-1"
        assert msg.metrics["fps"] == 25.0
        assert msg.timestamp > 0

    def test_serialize_size_limit(self):
        """Serialize raises if message exceeds max size."""
        big_metrics = {"data": "x" * 70000}
        msg = MetricsMessage(version=1, instance_id="x", timestamp=1.0, metrics=big_metrics)
        with pytest.raises(ValueError, match="exceeds max size"):
            msg.serialize()

    def test_deserialize_missing_keys(self):
        """Deserialize handles missing keys with defaults."""
        import json

        data = json.dumps({}).encode("utf-8")
        msg = MetricsMessage.deserialize(data)
        assert msg.version == 1
        assert msg.instance_id == ""
        assert msg.metrics == {}


def _find_free_port():
    """Find a free UDP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestMetricsReporter:
    """Tests for MetricsReporter."""

    def test_start_stop(self):
        """Reporter starts and stops cleanly."""
        reporter = MetricsReporter(
            instance_id="test-1",
            collector_host="127.0.0.1",
            collector_port=_find_free_port(),
            report_interval=0.1,
        )
        reporter.start()
        assert reporter.is_running()
        reporter.stop()
        assert not reporter.is_running()

    def test_report_now_sends_udp(self):
        """report_now sends a UDP datagram."""
        port = _find_free_port()
        # Set up a receiver
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.bind(("127.0.0.1", port))
        recv_sock.settimeout(2.0)

        reporter = MetricsReporter(
            instance_id="test-2",
            collector_host="127.0.0.1",
            collector_port=port,
            report_interval=10.0,
        )
        reporter.start()
        try:
            reporter.report_now()
            data, addr = recv_sock.recvfrom(65535)
            msg = MetricsMessage.deserialize(data)
            assert msg.instance_id == "test-2"
        finally:
            reporter.stop()
            recv_sock.close()

    def test_double_start_is_safe(self):
        """Calling start twice is safe."""
        reporter = MetricsReporter(
            instance_id="test-3",
            collector_host="127.0.0.1",
            collector_port=_find_free_port(),
        )
        reporter.start()
        reporter.start()  # Should not raise
        reporter.stop()

    def test_double_stop_is_safe(self):
        """Calling stop twice is safe."""
        reporter = MetricsReporter(
            instance_id="test-4",
            collector_host="127.0.0.1",
            collector_port=_find_free_port(),
        )
        reporter.start()
        reporter.stop()
        reporter.stop()  # Should not raise


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_start_stop(self):
        """Collector starts and stops cleanly."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port)
        collector.start()
        time.sleep(0.1)
        collector.stop()

    def test_receive_from_reporter(self):
        """Collector receives metrics from a reporter."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port)
        collector.start()

        reporter = MetricsReporter(
            instance_id="inst-1",
            collector_host="127.0.0.1",
            collector_port=port,
            report_interval=10.0,
        )
        reporter.start()

        try:
            reporter.report_now()
            time.sleep(0.5)  # Allow time for UDP delivery

            instance_ids = collector.get_instance_ids()
            assert "inst-1" in instance_ids

            metrics = collector.get_instance_metrics("inst-1")
            assert metrics is not None
            assert metrics["instance_id"] == "inst-1"
        finally:
            reporter.stop()
            collector.stop()

    def test_multiple_instances(self):
        """Collector tracks multiple reporter instances."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port)
        collector.start()

        reporters = []
        try:
            for i in range(3):
                r = MetricsReporter(
                    instance_id=f"inst-{i}",
                    collector_host="127.0.0.1",
                    collector_port=port,
                    report_interval=10.0,
                )
                r.start()
                reporters.append(r)

            for r in reporters:
                r.report_now()
            time.sleep(0.5)

            ids = collector.get_instance_ids()
            assert len(ids) == 3
        finally:
            for r in reporters:
                r.stop()
            collector.stop()

    def test_aggregate(self):
        """Collector computes aggregate metrics."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port)
        collector.start()

        # Simulate sending metrics directly via UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for i in range(3):
                msg = MetricsMessage.create_now(
                    f"sim-{i}",
                    {"fps": 30.0, "frames_processed": 100, "total_errors": i},
                )
                sock.sendto(msg.serialize(), ("127.0.0.1", port))
            time.sleep(0.5)

            agg = collector.get_aggregate()
            assert agg["instance_count"] == 3
            assert agg["mean_fps"] == 30.0
            assert agg["total_frames"] == 300
            assert agg["total_errors"] == 3  # 0 + 1 + 2
        finally:
            sock.close()
            collector.stop()

    def test_max_instances_enforced(self):
        """Collector rejects instances beyond max_instances."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port, max_instances=2)
        collector.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for i in range(5):
                msg = MetricsMessage.create_now(f"inst-{i}", {"fps": 30.0})
                sock.sendto(msg.serialize(), ("127.0.0.1", port))
            time.sleep(0.5)

            ids = collector.get_instance_ids()
            assert len(ids) <= 2
        finally:
            sock.close()
            collector.stop()

    def test_prune_stale(self):
        """prune_stale removes old instances."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port, stale_timeout=0.1)
        collector.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            msg = MetricsMessage.create_now("old-inst", {"fps": 30.0})
            sock.sendto(msg.serialize(), ("127.0.0.1", port))
            time.sleep(0.3)  # Wait for stale timeout

            pruned = collector.prune_stale()
            assert pruned == 1
            assert collector.get_instance_ids() == []
        finally:
            sock.close()
            collector.stop()

    def test_get_all_instances(self):
        """get_all_instances returns data for all instances."""
        port = _find_free_port()
        collector = MetricsCollector(listen_host="127.0.0.1", listen_port=port)
        collector.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for i in range(2):
                msg = MetricsMessage.create_now(f"inst-{i}", {"fps": 25.0 + i})
                sock.sendto(msg.serialize(), ("127.0.0.1", port))
            time.sleep(0.5)

            all_inst = collector.get_all_instances()
            assert len(all_inst) == 2
            assert "inst-0" in all_inst
            assert "inst-1" in all_inst
        finally:
            sock.close()
            collector.stop()

    def test_empty_aggregate(self):
        """Aggregate with no instances returns zeros."""
        collector = MetricsCollector()
        agg = collector.get_aggregate()
        assert agg["instance_count"] == 0
        assert agg["mean_fps"] == 0.0
