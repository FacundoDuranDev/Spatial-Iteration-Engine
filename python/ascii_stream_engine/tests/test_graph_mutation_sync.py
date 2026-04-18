"""Tests for graph auto-rebuild on pipeline mutation and version counters."""

import numpy as np
import pytest

from ascii_stream_engine.application.engine import StreamEngine
from ascii_stream_engine.application.pipeline import (
    AnalyzerPipeline,
    FilterPipeline,
    TrackingPipeline,
    TransformationPipeline,
)
from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame


# --- Dummy adapters ---


class DummySource:
    def open(self):
        pass

    def read(self):
        return np.zeros((10, 10, 3), dtype=np.uint8)

    def close(self):
        pass


class DummyRenderer:
    def output_size(self, config):
        return (10, 10)

    def render(self, frame, config, analysis=None):
        return RenderFrame(image=object(), text="x", lines=["x"])


class DummySink:
    def __init__(self):
        self.count = 0

    def open(self, config, output_size):
        pass

    def write(self, frame):
        self.count += 1

    def close(self):
        pass


class DummyFilter:
    name = "dummy_filter"
    enabled = True

    def __init__(self, tag="default"):
        self.tag = tag
        self.call_count = 0

    def apply(self, frame, config, analysis=None):
        self.call_count += 1
        return frame


class DummyAnalyzer:
    name = "dummy_analyzer"
    enabled = True

    def analyze(self, frame, config):
        return {"detected": True}


# --- Version counter tests ---


class TestFilterPipelineVersion:
    def test_initial_version_is_zero(self):
        fp = FilterPipeline()
        assert fp.version == 0

    def test_add_increments_version(self):
        fp = FilterPipeline()
        fp.add(DummyFilter())
        assert fp.version == 1

    def test_remove_increments_version(self):
        f = DummyFilter()
        fp = FilterPipeline([f])
        fp.remove(f)
        assert fp.version == 1

    def test_extend_increments_version(self):
        fp = FilterPipeline()
        fp.extend([DummyFilter(), DummyFilter()])
        assert fp.version == 1

    def test_insert_increments_version(self):
        fp = FilterPipeline()
        fp.insert(0, DummyFilter())
        assert fp.version == 1

    def test_pop_increments_version(self):
        fp = FilterPipeline([DummyFilter()])
        fp.pop()
        assert fp.version == 1

    def test_clear_increments_version(self):
        fp = FilterPipeline([DummyFilter()])
        fp.clear()
        assert fp.version == 1

    def test_replace_increments_version(self):
        fp = FilterPipeline([DummyFilter()])
        fp.replace([DummyFilter()])
        assert fp.version == 1

    def test_set_enabled_does_not_increment_version(self):
        f = DummyFilter()
        fp = FilterPipeline([f])
        fp.set_enabled("dummy_filter", False)
        assert fp.version == 0

    def test_multiple_mutations_accumulate(self):
        fp = FilterPipeline()
        fp.add(DummyFilter())
        fp.add(DummyFilter())
        fp.clear()
        assert fp.version == 3


class TestAnalyzerPipelineVersion:
    def test_initial_version_is_zero(self):
        ap = AnalyzerPipeline()
        assert ap.version == 0

    def test_add_increments_version(self):
        ap = AnalyzerPipeline()
        ap.add(DummyAnalyzer())
        assert ap.version == 1

    def test_remove_increments_version(self):
        a = DummyAnalyzer()
        ap = AnalyzerPipeline([a])
        ap.remove(a)
        assert ap.version == 1

    def test_replace_increments_version(self):
        ap = AnalyzerPipeline([DummyAnalyzer()])
        ap.replace([DummyAnalyzer()])
        assert ap.version == 1

    def test_set_enabled_does_not_increment_version(self):
        ap = AnalyzerPipeline([DummyAnalyzer()])
        ap.set_enabled("dummy_analyzer", False)
        assert ap.version == 0


class TestTrackingPipelineVersion:
    def test_initial_version_is_zero(self):
        tp = TrackingPipeline()
        assert tp.version == 0

    def test_append_increments_version(self):
        tp = TrackingPipeline()

        class T:
            name = "t"
            enabled = True

        tp.append(T())
        assert tp.version == 1

    def test_clear_increments_version(self):
        tp = TrackingPipeline()
        tp.clear()
        assert tp.version == 1


class TestTransformationPipelineVersion:
    def test_initial_version_is_zero(self):
        tp = TransformationPipeline()
        assert tp.version == 0

    def test_add_increments_version(self):
        tp = TransformationPipeline()

        class T:
            def transform(self, frame):
                return frame

            def inverse(self, frame):
                return frame

        tp.add(T())
        assert tp.version == 1

    def test_clear_increments_version(self):
        tp = TransformationPipeline()
        tp.clear()
        assert tp.version == 1


# --- Graph auto-rebuild tests ---


class TestGraphAutoRebuild:
    def _make_engine(self, filters=None, analyzers=None):
        """Create a StreamEngine with graph mode (now default)."""
        fp = FilterPipeline(filters or [])
        ap = AnalyzerPipeline(analyzers or [])
        return StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
            config=EngineConfig(),
            filters=fp,
            analyzers=ap,
            use_graph=True,
        )

    def test_combined_pipeline_version(self):
        f = DummyFilter()
        engine = self._make_engine(filters=[f])
        v0 = engine._combined_pipeline_version()
        engine.filter_pipeline.add(DummyFilter())
        v1 = engine._combined_pipeline_version()
        assert v1 > v0

    def test_graph_rebuilds_on_filter_add(self):
        """Adding a filter at runtime triggers graph rebuild on next frame."""
        engine = self._make_engine()
        engine._create_orchestrator()
        old_orchestrator = engine._orchestrator

        # Mutate pipeline
        engine.filter_pipeline.add(DummyFilter("new"))
        # Simulate rebuild check
        current_v = engine._combined_pipeline_version()
        assert current_v != engine._pipeline_version_snapshot

        engine._create_orchestrator()
        engine._pipeline_version_snapshot = current_v
        assert engine._orchestrator is not old_orchestrator

    def test_graph_rebuilds_on_filter_remove(self):
        f = DummyFilter()
        engine = self._make_engine(filters=[f])
        engine._create_orchestrator()
        old_orchestrator = engine._orchestrator

        engine.filter_pipeline.remove(f)
        current_v = engine._combined_pipeline_version()
        assert current_v != engine._pipeline_version_snapshot

        engine._create_orchestrator()
        assert engine._orchestrator is not old_orchestrator

    def test_graph_rebuilds_on_replace(self):
        engine = self._make_engine(filters=[DummyFilter()])
        engine._create_orchestrator()
        old = engine._orchestrator

        engine.filter_pipeline.replace([DummyFilter("a"), DummyFilter("b")])
        current_v = engine._combined_pipeline_version()
        assert current_v != engine._pipeline_version_snapshot

        engine._create_orchestrator()
        assert engine._orchestrator is not old

    def test_graph_rebuilds_on_analyzer_change(self):
        engine = self._make_engine()
        engine._create_orchestrator()
        old = engine._orchestrator

        engine.analyzer_pipeline.add(DummyAnalyzer())
        current_v = engine._combined_pipeline_version()
        assert current_v != engine._pipeline_version_snapshot

        engine._create_orchestrator()
        assert engine._orchestrator is not old

    def test_no_rebuild_on_enabled_toggle(self):
        f = DummyFilter()
        engine = self._make_engine(filters=[f])
        engine._create_orchestrator()
        engine._pipeline_version_snapshot = engine._combined_pipeline_version()

        # Toggle enabled — should NOT change version
        f.enabled = False
        current_v = engine._combined_pipeline_version()
        assert current_v == engine._pipeline_version_snapshot

    def test_use_graph_is_default(self):
        """Verify use_graph defaults to True."""
        import inspect

        sig = inspect.signature(StreamEngine.__init__)
        assert sig.parameters["use_graph"].default is True

    def test_get_node_timings_returns_dict(self):
        engine = self._make_engine(filters=[DummyFilter()])
        engine._create_orchestrator()
        timings = engine.get_node_timings()
        assert isinstance(timings, dict)

    def test_get_node_timings_empty_without_graph(self):
        engine = StreamEngine(
            source=DummySource(),
            renderer=DummyRenderer(),
            sink=DummySink(),
            config=EngineConfig(),
            use_graph=False,
        )
        engine._create_orchestrator()
        timings = engine.get_node_timings()
        assert timings == {}
