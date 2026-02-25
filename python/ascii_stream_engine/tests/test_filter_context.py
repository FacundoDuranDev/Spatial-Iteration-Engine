"""Tests for FilterContext — dict-compatible wrapper with lazy temporal access."""

import unittest

import numpy as np

from ascii_stream_engine.application.pipeline.filter_context import FilterContext


class MockTemporalManager:
    """Mock TemporalManager for testing FilterContext temporal delegation."""

    def __init__(self):
        self._prev_input = None
        self._prev_output = None
        self._flow = None
        self._delta = None

    def get_previous_input(self, n=1):
        return self._prev_input

    def get_previous_output(self):
        return self._prev_output

    def get_optical_flow(self):
        return self._flow

    def get_delta(self):
        return self._delta


class TestFilterContextDictProtocol(unittest.TestCase):
    """Test dict-compatible interface for backwards compatibility."""

    def setUp(self):
        self.analysis = {
            "face": {"bbox": [0.1, 0.2, 0.3, 0.4]},
            "hands": [{"landmarks": []}],
            "pose": {"keypoints": []},
        }
        self.ctx = FilterContext(self.analysis)

    def test_contains(self):
        self.assertIn("face", self.ctx)
        self.assertNotIn("nonexistent", self.ctx)

    def test_getitem(self):
        self.assertEqual(self.ctx["face"], {"bbox": [0.1, 0.2, 0.3, 0.4]})

    def test_getitem_missing_raises_key_error(self):
        with self.assertRaises(KeyError):
            _ = self.ctx["nonexistent"]

    def test_get_existing_key(self):
        self.assertEqual(self.ctx.get("face"), {"bbox": [0.1, 0.2, 0.3, 0.4]})

    def test_get_missing_key_returns_default(self):
        self.assertIsNone(self.ctx.get("nonexistent"))
        self.assertEqual(self.ctx.get("nonexistent", 42), 42)

    def test_keys(self):
        self.assertEqual(set(self.ctx.keys()), {"face", "hands", "pose"})

    def test_values(self):
        values = list(self.ctx.values())
        self.assertEqual(len(values), 3)

    def test_items(self):
        items = dict(self.ctx.items())
        self.assertEqual(items, self.analysis)

    def test_iter(self):
        keys = [k for k in self.ctx]
        self.assertEqual(set(keys), {"face", "hands", "pose"})

    def test_len(self):
        self.assertEqual(len(self.ctx), 3)
        self.assertEqual(len(FilterContext()), 0)

    def test_bool_always_truthy(self):
        self.assertTrue(bool(FilterContext()))
        self.assertTrue(bool(FilterContext({})))
        self.assertTrue(bool(FilterContext({"a": 1})))

    def test_empty_analysis_default(self):
        ctx = FilterContext()
        self.assertEqual(len(ctx), 0)
        self.assertNotIn("face", ctx)
        self.assertIsNone(ctx.get("face"))


class TestFilterContextPerceptionShortcuts(unittest.TestCase):
    """Test perception property shortcuts."""

    def test_face_shortcut(self):
        ctx = FilterContext({"face": {"bbox": [1, 2, 3, 4]}})
        self.assertEqual(ctx.face, {"bbox": [1, 2, 3, 4]})

    def test_hands_shortcut(self):
        ctx = FilterContext({"hands": [{"landmarks": []}]})
        self.assertEqual(ctx.hands, [{"landmarks": []}])

    def test_pose_shortcut(self):
        ctx = FilterContext({"pose": {"keypoints": [1, 2]}})
        self.assertEqual(ctx.pose, {"keypoints": [1, 2]})

    def test_tracking_shortcut(self):
        ctx = FilterContext({"tracking": {"id": 1}})
        self.assertEqual(ctx.tracking, {"id": 1})

    def test_missing_shortcuts_return_none(self):
        ctx = FilterContext()
        self.assertIsNone(ctx.face)
        self.assertIsNone(ctx.hands)
        self.assertIsNone(ctx.pose)
        self.assertIsNone(ctx.tracking)


class TestFilterContextNoTemporal(unittest.TestCase):
    """Test that temporal properties return None when no TemporalManager is provided."""

    def setUp(self):
        self.ctx = FilterContext({"face": {}}, temporal=None)

    def test_previous_input_none(self):
        self.assertIsNone(self.ctx.previous_input)

    def test_get_previous_input_none(self):
        self.assertIsNone(self.ctx.get_previous_input(1))
        self.assertIsNone(self.ctx.get_previous_input(3))

    def test_previous_output_none(self):
        self.assertIsNone(self.ctx.previous_output)

    def test_optical_flow_none(self):
        self.assertIsNone(self.ctx.optical_flow)

    def test_delta_frame_none(self):
        self.assertIsNone(self.ctx.delta_frame)


class TestFilterContextWithTemporal(unittest.TestCase):
    """Test that temporal properties delegate to TemporalManager."""

    def setUp(self):
        self.temporal = MockTemporalManager()
        self.ctx = FilterContext({"face": {}}, temporal=self.temporal)

    def test_previous_input_delegates(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        self.temporal._prev_input = frame
        result = self.ctx.previous_input
        self.assertIs(result, frame)

    def test_get_previous_input_delegates(self):
        frame = np.ones((10, 10, 3), dtype=np.uint8)
        self.temporal._prev_input = frame
        result = self.ctx.get_previous_input(2)
        self.assertIs(result, frame)

    def test_previous_output_delegates(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        self.temporal._prev_output = frame
        result = self.ctx.previous_output
        self.assertIs(result, frame)

    def test_optical_flow_delegates(self):
        flow = np.zeros((10, 10, 2), dtype=np.float32)
        self.temporal._flow = flow
        result = self.ctx.optical_flow
        self.assertIs(result, flow)

    def test_delta_frame_delegates(self):
        delta = np.ones((10, 10, 3), dtype=np.uint8)
        self.temporal._delta = delta
        result = self.ctx.delta_frame
        self.assertIs(result, delta)

    def test_temporal_returns_none_when_no_data(self):
        self.assertIsNone(self.ctx.previous_input)
        self.assertIsNone(self.ctx.previous_output)
        self.assertIsNone(self.ctx.optical_flow)
        self.assertIsNone(self.ctx.delta_frame)


class TestFilterContextBackwardsCompatibility(unittest.TestCase):
    """Test that existing filter code patterns work unchanged with FilterContext."""

    def test_analysis_get_pattern(self):
        """Existing pattern: analysis.get('face') works on FilterContext."""
        analysis = {"face": {"bbox": [0, 0, 1, 1]}, "hands": None}
        ctx = FilterContext(analysis)

        # This is the exact pattern used in existing filters
        face = ctx.get("face")
        self.assertEqual(face, {"bbox": [0, 0, 1, 1]})

    def test_analysis_none_check_pattern(self):
        """Existing pattern: if analysis and 'face' in analysis."""
        ctx = FilterContext({"face": {"bbox": []}})

        # FilterContext is always truthy so `if analysis:` works
        if ctx and "face" in ctx:
            face = ctx["face"]
            self.assertEqual(face, {"bbox": []})
        else:
            self.fail("FilterContext should be truthy and contain 'face'")

    def test_empty_context_truthy_but_no_keys(self):
        """Empty FilterContext is truthy but contains no keys."""
        ctx = FilterContext()
        self.assertTrue(ctx)
        self.assertEqual(list(ctx.keys()), [])

    def test_filter_apply_receives_context_as_analysis(self):
        """Simulate a filter receiving FilterContext as the analysis parameter."""

        class SimpleFilter:
            def apply(self, frame, config, analysis=None):
                if analysis and "face" in analysis:
                    return analysis.get("face")
                return None

        f = SimpleFilter()
        ctx = FilterContext({"face": {"detected": True}})
        result = f.apply(None, None, ctx)
        self.assertEqual(result, {"detected": True})


if __name__ == "__main__":
    unittest.main()
