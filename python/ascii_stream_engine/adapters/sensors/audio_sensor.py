"""Sensor de audio para análisis de frecuencias y amplitud."""

import logging
from typing import Any, Dict, Optional

import numpy as np

from .base import BaseSensor

logger = logging.getLogger(__name__)

# Intentar importar librerías de audio
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    sd = None

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    pyaudio = None


class AudioSensor(BaseSensor):
    """Sensor de audio para análisis en tiempo real."""

    name = "audio_sensor"
    sensor_type = "audio"

    def __init__(
        self,
        sample_rate: int = 44100,
        chunk_size: int = 1024,
        channels: int = 1,
        enabled: bool = True,
        use_sounddevice: bool = True,
    ) -> None:
        """
        Inicializa el sensor de audio.

        Args:
            sample_rate: Tasa de muestreo en Hz
            chunk_size: Tamaño del chunk de audio
            channels: Número de canales
            enabled: Si el sensor está habilitado
            use_sounddevice: Si usar sounddevice en lugar de pyaudio
        """
        super().__init__(enabled)

        if not SOUNDDEVICE_AVAILABLE and not PYAUDIO_AVAILABLE:
            logger.warning(
                "Se requiere 'sounddevice' o 'pyaudio' para usar AudioSensor. "
                "Instala con: pip install sounddevice o pip install pyaudio"
            )

        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.use_sounddevice = use_sounddevice and SOUNDDEVICE_AVAILABLE
        self._audio_stream = None
        self._last_data: Optional[np.ndarray] = None

    def _do_is_available(self) -> bool:
        """Verifica si el audio está disponible."""
        return SOUNDDEVICE_AVAILABLE or PYAUDIO_AVAILABLE

    def _do_read(self) -> Dict[str, Any]:
        """Lee datos de audio."""
        if self.use_sounddevice and SOUNDDEVICE_AVAILABLE:
            return self._read_sounddevice()
        elif PYAUDIO_AVAILABLE:
            return self._read_pyaudio()
        else:
            return {"error": "No hay librerías de audio disponibles"}

    def _read_sounddevice(self) -> Dict[str, Any]:
        """Lee usando sounddevice."""
        try:
            if self._audio_stream is None:
                self._audio_stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    blocksize=self.chunk_size,
                    dtype=np.float32,
                )
                self._audio_stream.start()

            if self._audio_stream.read_available > 0:
                data, _ = self._audio_stream.read(self.chunk_size)
                self._last_data = data.flatten()
            else:
                # Retornar datos anteriores si no hay nuevos
                if self._last_data is None:
                    self._last_data = np.zeros(self.chunk_size, dtype=np.float32)
        except Exception as e:
            logger.error(f"Error leyendo audio con sounddevice: {e}", exc_info=True)
            if self._last_data is None:
                self._last_data = np.zeros(self.chunk_size, dtype=np.float32)

        return self._analyze_audio(self._last_data)

    def _read_pyaudio(self) -> Dict[str, Any]:
        """Lee usando pyaudio."""
        try:
            if self._audio_stream is None:
                p = pyaudio.PyAudio()
                self._audio_stream = p.open(
                    format=pyaudio.paFloat32,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size,
                )
                self._audio_stream.start_stream()

            if self._audio_stream.get_read_available() > 0:
                data = self._audio_stream.read(self.chunk_size, exception_on_overflow=False)
                self._last_data = np.frombuffer(data, dtype=np.float32)
            else:
                if self._last_data is None:
                    self._last_data = np.zeros(self.chunk_size, dtype=np.float32)
        except Exception as e:
            logger.error(f"Error leyendo audio con pyaudio: {e}", exc_info=True)
            if self._last_data is None:
                self._last_data = np.zeros(self.chunk_size, dtype=np.float32)

        return self._analyze_audio(self._last_data)

    def _analyze_audio(self, data: np.ndarray) -> Dict[str, Any]:
        """
        Analiza los datos de audio.

        Args:
            data: Datos de audio

        Returns:
            Diccionario con análisis
        """
        if data is None or len(data) == 0:
            return {"amplitude": 0.0, "rms": 0.0, "max_frequency": 0.0}

        # Amplitud RMS
        rms = np.sqrt(np.mean(data**2))

        # Amplitud máxima
        amplitude = np.max(np.abs(data))

        # FFT para frecuencias (simplificado)
        try:
            fft = np.fft.rfft(data)
            freqs = np.fft.rfftfreq(len(data), 1.0 / self.sample_rate)
            magnitude = np.abs(fft)
            max_freq_idx = np.argmax(magnitude)
            max_frequency = freqs[max_freq_idx]
        except Exception:
            max_frequency = 0.0

        return {
            "amplitude": float(amplitude),
            "rms": float(rms),
            "max_frequency": float(max_frequency),
            "sample_rate": self.sample_rate,
            "chunk_size": self.chunk_size,
        }

    def _do_calibrate(self) -> bool:
        """Calibra el sensor de audio."""
        # Calibración básica: leer algunos chunks para estabilizar
        try:
            for _ in range(5):
                self.read()
            return True
        except Exception as e:
            logger.error(f"Error en calibración de audio: {e}", exc_info=True)
            return False

    def close(self) -> None:
        """Cierra el stream de audio."""
        if self._audio_stream:
            if self.use_sounddevice and SOUNDDEVICE_AVAILABLE:
                self._audio_stream.stop()
                self._audio_stream.close()
            elif PYAUDIO_AVAILABLE:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            self._audio_stream = None

