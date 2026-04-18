"""Output adapter nodes — wrap OutputSink implementations as OutputNode."""

from typing import Any, Dict, Type

from ..nodes.output_node import OutputNode


def _make_output_node(output_class: type) -> Type[OutputNode]:
    """Generate an OutputNode subclass that delegates to a sink adapter."""

    class AdapterOutputNode(OutputNode):
        name = getattr(output_class, "name", output_class.__name__)

        def __init__(self, **kwargs):
            super().__init__()
            self._impl = output_class(**kwargs)

        def write(self, rendered: Any) -> None:
            self._impl.write(rendered)

        def setup(self) -> None:
            if hasattr(self._impl, "open"):
                self._impl.open(self.config, None)

        def teardown(self) -> None:
            if hasattr(self._impl, "close"):
                self._impl.close()

        @property
        def adapter(self):
            return self._impl

    AdapterOutputNode.__name__ = f"{output_class.__name__}Node"
    AdapterOutputNode.__qualname__ = f"{output_class.__name__}Node"
    return AdapterOutputNode


def _build_output_nodes() -> Dict[str, Type[OutputNode]]:
    nodes: Dict[str, Type[OutputNode]] = {}
    try:
        from ....adapters.outputs import (
            AsciiFrameRecorder,
            CompositeOutputSink,
            FfmpegUdpOutput,
            NotebookPreviewSink,
            PreviewSink,
        )

        for cls in [
            AsciiFrameRecorder,
            CompositeOutputSink,
            FfmpegUdpOutput,
            NotebookPreviewSink,
            PreviewSink,
        ]:
            nodes[cls.__name__] = _make_output_node(cls)
    except ImportError:
        pass

    # Optional outputs
    for cls_name in [
        "FfmpegRtspSink",
        "WebRTCOutput",
        "OscOutputSink",
        "VideoRecorderSink",
        "NdiOutputSink",
    ]:
        try:
            import importlib

            mod = importlib.import_module("ascii_stream_engine.adapters.outputs")
            cls = getattr(mod, cls_name, None)
            if cls is not None:
                nodes[cls_name] = _make_output_node(cls)
        except ImportError:
            pass

    return nodes


OUTPUT_NODE_CLASSES = _build_output_nodes()
