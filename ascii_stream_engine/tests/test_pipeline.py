import unittest

from ascii_stream_engine.core.config import EngineConfig
from ascii_stream_engine.core.pipeline import AnalyzerPipeline, FilterPipeline


class DummyAnalyzer:
    name = "dummy"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def analyze(self, frame, config):
        return {"value": frame}


class DummyFilter:
    name = "dummy_filter"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def apply(self, frame, config, analysis=None):
        return frame + 1


class TestPipelines(unittest.TestCase):
    def test_analyzer_pipeline_run_and_enable(self) -> None:
        pipeline = AnalyzerPipeline([DummyAnalyzer()])
        config = EngineConfig()
        result = pipeline.run(123, config)
        self.assertIn("dummy", result)
        self.assertEqual(result["dummy"]["value"], 123)

        changed = pipeline.set_enabled("dummy", False)
        self.assertTrue(changed)
        result = pipeline.run(123, config)
        self.assertEqual(result, {})

    def test_filter_pipeline_apply_and_enable(self) -> None:
        pipeline = FilterPipeline([DummyFilter()])
        config = EngineConfig()
        output = pipeline.apply(1, config, {})
        self.assertEqual(output, 2)

        changed = pipeline.set_enabled("dummy_filter", False)
        self.assertTrue(changed)
        output = pipeline.apply(1, config, {})
        self.assertEqual(output, 1)

    def test_pipeline_locked_mutation(self) -> None:
        pipeline = FilterPipeline()
        with pipeline.locked() as filters:
            filters.append(DummyFilter())
        self.assertEqual(len(pipeline.filters), 1)


if __name__ == "__main__":
    unittest.main()
