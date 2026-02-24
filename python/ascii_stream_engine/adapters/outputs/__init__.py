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

try:
    from .osc import OscOutputSink
except ImportError:
    OscOutputSink = None  # type: ignore

try:
    from .recorder import VideoRecorderSink
except ImportError:
    VideoRecorderSink = None  # type: ignore

try:
    from .ndi import NdiOutputSink
except ImportError:
    NdiOutputSink = None  # type: ignore

__all__ = [
    "AsciiFrameRecorder",
    "CompositeOutputSink",
    "FfmpegUdpOutput",
    "NotebookPreviewSink",
    "OutputSink",
    "PreviewSink",
]
for _cls_name, _cls in [
    ("FfmpegRtspSink", FfmpegRtspSink),
    ("WebRTCOutput", WebRTCOutput),
    ("OscOutputSink", OscOutputSink),
    ("VideoRecorderSink", VideoRecorderSink),
    ("NdiOutputSink", NdiOutputSink),
]:
    if _cls is not None:
        __all__.append(_cls_name)
