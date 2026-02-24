"""Shared subprocess cleanup utility for ffmpeg-based output sinks."""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_subprocess(proc: Optional[subprocess.Popen], timeout: int = 1) -> None:
    """Clean up a subprocess following the safe shutdown pattern.

    Pattern: close stdin -> wait -> terminate -> kill.
    This prevents zombie processes and ensures proper resource cleanup.

    Args:
        proc: The subprocess to clean up. If None, this is a no-op.
        timeout: Timeout in seconds for each wait step.
    """
    if proc is None:
        return

    # Step 1: Close stdin to signal EOF to the process
    if proc.stdin:
        try:
            proc.stdin.close()
        except Exception as e:
            logger.debug(f"Error closing subprocess stdin: {e}")

    # Step 2: Wait for graceful exit
    try:
        proc.wait(timeout=timeout)
        return  # Process exited cleanly
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        logger.debug(f"Error waiting for subprocess: {e}")

    # Step 3: Try SIGTERM
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
        return  # Process responded to SIGTERM
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        logger.debug(f"Error terminating subprocess: {e}")

    # Step 4: Force kill with SIGKILL
    try:
        logger.warning("Force-killing unresponsive subprocess")
        proc.kill()
        proc.wait()
    except Exception as e:
        logger.debug(f"Error killing subprocess: {e}")
