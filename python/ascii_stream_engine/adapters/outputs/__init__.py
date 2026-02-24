from ...ports.outputs import OutputSink
from .ascii_recorder import AsciiFrameRecorder
from .composite import CompositeOutputSink
from .notebook_preview_sink import NotebookPreviewSink
from .preview_sink import PreviewSink
from .udp import FfmpegUdpOutput

try:
    from .rtsp import FfmpegRtspSink
except ImportError:
    FfmpegRtspSink = None  # type: ignore

try:
    from .webrtc import WebRTCOutput
except ImportError:
    WebRTCOutput = None  # type: ignore

__all__ = [
    "AsciiFrameRecorder",
    "CompositeOutputSink",
    "FfmpegUdpOutput",
    "NotebookPreviewSink",
    "OutputSink",
    "PreviewSink",
]
if FfmpegRtspSink is not None:
    __all__.append("FfmpegRtspSink")
if WebRTCOutput is not None:
    __all__.append("WebRTCOutput")
