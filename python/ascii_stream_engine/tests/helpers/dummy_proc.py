"""Shared DummyProc test helper for ffmpeg-subprocess-based sink tests.

This mock replaces subprocess.Popen in tests to avoid spawning real ffmpeg
processes. It records written data and provides controllable behavior.
"""


class DummyProc:
    """Mock subprocess that mimics ffmpeg stdin pipe behavior.

    Usage in tests::

        from ascii_stream_engine.tests.helpers import DummyProc

        with patch("...subprocess.Popen", return_value=DummyProc()) as popen:
            sink.open(config, (640, 480))
            sink.write(frame)
            sink.close()
    """

    def __init__(self, fail_on_write: bool = False):
        """Initialize the dummy process.

        Args:
            fail_on_write: If True, write() raises BrokenPipeError.
        """
        self.stdin = self
        self.stdout = None
        self.stderr = None
        self.data = b""
        self.returncode = None
        self._closed = False
        self._fail_on_write = fail_on_write

    def write(self, data: bytes) -> int:
        """Write data to the mock stdin."""
        if self._fail_on_write:
            raise BrokenPipeError("Mock broken pipe")
        self.data += data
        return len(data)

    def flush(self) -> None:
        """Flush mock stdin (no-op)."""
        pass

    def close(self) -> None:
        """Close mock stdin."""
        self._closed = True

    def poll(self):
        """Poll process status."""
        return self.returncode

    def wait(self, timeout=None):
        """Wait for process to finish."""
        pass

    def terminate(self):
        """Terminate the process."""
        self.returncode = -15

    def kill(self):
        """Kill the process."""
        self.returncode = -9
