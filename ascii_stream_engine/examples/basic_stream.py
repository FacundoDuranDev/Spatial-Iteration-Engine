from ascii_stream_engine import (
    EngineConfig,
    StreamEngine,
    OpenCVCameraSource,
    AsciiRenderer,
    FfmpegUdpOutput,
    FilterPipeline,
)
from ascii_stream_engine.adapters.processors import BrightnessFilter, InvertFilter


def main() -> None:
    config = EngineConfig(host="127.0.0.1", port=1234)
    filters = FilterPipeline([BrightnessFilter(), InvertFilter()])
    engine = StreamEngine(
        source=OpenCVCameraSource(0),
        renderer=AsciiRenderer(),
        sink=FfmpegUdpOutput(),
        config=config,
        filters=filters,
    )
    engine.start(blocking=True)


if __name__ == "__main__":
    main()
