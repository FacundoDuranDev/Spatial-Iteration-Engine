"""Audio analyzer service — threaded mic capture + FFT / RMS / onset.

Runs in its own thread so the pipeline never waits for audio. Filters read
the latest analysis dict through ``FilterContext.audio`` with no lock
contention on the hot path. ``sounddevice`` is an optional dependency; if
it is missing the service reports ``available=False`` and filters see a
zeroed-out dict.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd

    _SD_AVAILABLE = True
except Exception:  # pragma: no cover — import guards, hardware-dependent
    sd = None  # type: ignore
    _SD_AVAILABLE = False


# Classic 3-band split (roughly vocals/kick vs melody vs hats/cymbals).
_BASS_HZ = (20.0, 250.0)
_MID_HZ = (250.0, 4000.0)
_HIGH_HZ = (4000.0, 18000.0)


class AudioAnalyzerService:
    """Background audio capture + feature extraction.

    Features published (dict keys, all floats normalized to ``[0.0, 1.0]``
    unless noted):

    - ``rms``          Root-mean-square amplitude this block.
    - ``level``        Smoothed version of ``rms``, rises fast, decays slow.
    - ``bass``         Energy in 20-250 Hz, smoothed.
    - ``mid``          Energy in 250-4000 Hz, smoothed.
    - ``high``         Energy in 4-18 kHz, smoothed.
    - ``onset``        1.0 on detected beats/transients, decays to 0 in ~200 ms.
    - ``bpm``          Rough BPM estimate from onset spacing (0 when unknown).
    - ``available``    True when sounddevice is usable and a stream opened.
    """

    name = "audio_analyzer"

    def __init__(
        self,
        sample_rate: int = 44100,
        block_size: int = 1024,
        channels: int = 1,
        device: Optional[int] = None,
        attack: float = 0.35,
        release: float = 0.08,
    ) -> None:
        self._sample_rate = int(sample_rate)
        self._block_size = int(block_size)
        self._channels = int(channels)
        self._device = device
        self._attack = float(attack)
        self._release = float(release)

        self._stream: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # Published state — a flat dict is cheap to read without a lock.
        # We copy-assign it atomically in the worker; readers always get a
        # coherent snapshot.
        self._snapshot: Dict[str, float] = {
            "rms": 0.0, "level": 0.0,
            "bass": 0.0, "mid": 0.0, "high": 0.0,
            "onset": 0.0, "bpm": 0.0,
            "available": 0.0,
        }
        # Smoothed peak tracking for normalization (auto-gain).
        self._peak = 1e-3
        # Onset detector state.
        self._prev_flux = 0.0
        self._last_onset_time: Optional[float] = None
        self._onset_intervals: "deque[float]" = deque(maxlen=12)
        self._onset_value = 0.0

        # Precomputed frequency bin masks, set on first block.
        self._bins_bass: Optional[np.ndarray] = None
        self._bins_mid: Optional[np.ndarray] = None
        self._bins_high: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Open the input stream and start the reader thread. Returns True
        on success, False when sounddevice / the device is unavailable."""
        if not _SD_AVAILABLE:
            logger.warning(
                "sounddevice is not installed; audio-reactive features are "
                "disabled. Install it with: pip install sounddevice"
            )
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                blocksize=self._block_size,
                dtype=np.float32,
                device=self._device,
            )
            self._stream.start()
        except Exception as e:
            logger.error(f"Could not open audio input: {e}")
            self._stream = None
            return False

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="audio-analyzer", daemon=True
        )
        self._thread.start()
        self._snapshot = {**self._snapshot, "available": 1.0}
        logger.info(
            "Audio analyzer started (sample_rate=%d, block=%d, device=%s)",
            self._sample_rate, self._block_size, self._device,
        )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._snapshot = {**self._snapshot, "available": 0.0, "onset": 0.0}

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def latest(self) -> Dict[str, float]:
        """Return the most recent analysis snapshot. Safe from any thread."""
        return self._snapshot

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    def _ensure_bin_masks(self, freqs: np.ndarray) -> None:
        if self._bins_bass is not None:
            return
        self._bins_bass = (freqs >= _BASS_HZ[0]) & (freqs < _BASS_HZ[1])
        self._bins_mid = (freqs >= _MID_HZ[0]) & (freqs < _MID_HZ[1])
        self._bins_high = (freqs >= _HIGH_HZ[0]) & (freqs < _HIGH_HZ[1])

    def _run(self) -> None:
        import time

        hop_time = self._block_size / max(1, self._sample_rate)
        freqs = np.fft.rfftfreq(self._block_size, 1.0 / self._sample_rate)
        self._ensure_bin_masks(freqs)
        prev_spectrum: Optional[np.ndarray] = None

        # Smoothers for the band levels.
        band_level = {"bass": 0.0, "mid": 0.0, "high": 0.0}
        level = 0.0

        while not self._stop.is_set():
            try:
                if self._stream is None:
                    break
                data, _ = self._stream.read(self._block_size)
            except Exception as e:
                logger.debug(f"audio read failed: {e}")
                time.sleep(hop_time)
                continue

            mono = data[:, 0] if data.ndim > 1 else data
            if mono.size == 0:
                continue

            # RMS and smoothed level.
            rms = float(np.sqrt(np.mean(mono * mono)))
            # Auto-gain: track peak with slow decay, normalize.
            self._peak = max(rms, self._peak * 0.999) + 1e-6
            norm_rms = min(1.0, rms / self._peak)
            level = self._smooth(level, norm_rms, self._attack, self._release)

            # FFT → per-band energy.
            spectrum = np.abs(np.fft.rfft(mono * _hann(self._block_size)))
            band_energy = {
                "bass": float(spectrum[self._bins_bass].mean()),
                "mid": float(spectrum[self._bins_mid].mean()),
                "high": float(spectrum[self._bins_high].mean()),
            }
            # Per-band auto-gain using the same peak estimate.
            denom = self._peak * self._block_size * 0.5 + 1e-6
            for k in band_energy:
                norm = min(1.0, band_energy[k] / denom)
                band_level[k] = self._smooth(
                    band_level[k], norm, self._attack, self._release
                )

            # Spectral flux for onset detection.
            if prev_spectrum is not None:
                flux = float(np.sum(np.maximum(0.0, spectrum - prev_spectrum)))
            else:
                flux = 0.0
            prev_spectrum = spectrum

            now = time.monotonic()
            is_onset = False
            # Simple adaptive threshold: flux must exceed 1.3× the running mean
            # AND be higher than the previous frame's flux.
            threshold = max(1e-3, self._prev_flux * 1.3)
            if flux > threshold and flux > self._prev_flux * 1.1:
                if (self._last_onset_time is None
                        or now - self._last_onset_time > 0.18):
                    is_onset = True
                    if self._last_onset_time is not None:
                        self._onset_intervals.append(
                            now - self._last_onset_time
                        )
                    self._last_onset_time = now
            self._prev_flux = 0.9 * self._prev_flux + 0.1 * flux

            if is_onset:
                self._onset_value = 1.0
            else:
                self._onset_value = max(0.0, self._onset_value - hop_time * 5.0)

            bpm = self._estimate_bpm()

            self._snapshot = {
                "rms": float(rms),
                "level": float(level),
                "bass": float(band_level["bass"]),
                "mid": float(band_level["mid"]),
                "high": float(band_level["high"]),
                "onset": float(self._onset_value),
                "bpm": float(bpm),
                "available": 1.0,
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _smooth(prev: float, new: float, attack: float, release: float) -> float:
        # Fast rise, slow fall — the usual "VU meter" behavior.
        coef = attack if new > prev else release
        return prev + coef * (new - prev)

    def _estimate_bpm(self) -> float:
        if len(self._onset_intervals) < 4:
            return 0.0
        median = float(np.median(self._onset_intervals))
        if median <= 0.0:
            return 0.0
        bpm = 60.0 / median
        # Clamp to a plausible range, musical context.
        if bpm < 50.0 or bpm > 220.0:
            return 0.0
        return bpm


def _hann(n: int) -> np.ndarray:
    # Standard Hann window, cached by size.
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / max(1, n - 1))
