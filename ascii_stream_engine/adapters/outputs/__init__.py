from .ascii_recorder import AsciiFrameRecorder
from .composite import CompositeOutputSink
from .udp import FfmpegUdpOutput
from ...ports.outputs import OutputSink

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
    "OutputSink",
]
if FfmpegRtspSink is not None:
    __all__.append("FfmpegRtspSink")
if WebRTCOutput is not None:
    __all__.append("WebRTCOutput")
