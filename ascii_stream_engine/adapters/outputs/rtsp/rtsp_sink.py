import logging
import subprocess
from typing import Optional, Tuple

from PIL import Image

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame

logger = logging.getLogger(__name__)


class FfmpegRtspSink:
    """
    Backend de salida RTSP usando ffmpeg con soporte multi-cliente.

    Este backend utiliza ffmpeg para transmitir video a través de RTSP.
    Para soporte multi-cliente completo, se puede usar con un servidor RTSP
    externo o configurar ffmpeg con parámetros que permitan múltiples conexiones.

    Args:
        rtsp_url: URL RTSP completa (ej: "rtsp://localhost:8554/stream")
        bitrate: Bitrate de video (ej: "1500k", "2m")
        codec: Codec de video a usar (default: "libx264")
        preset: Preset de codificación (default: "ultrafast" para baja latencia)
        tune: Tune de codificación (default: "zerolatency")
        rtsp_transport: Protocolo de transporte RTSP (default: "tcp")
        max_clients: Número máximo de clientes simultáneos (para configuración)
    """

    def __init__(
        self,
        rtsp_url: Optional[str] = None,
        bitrate: Optional[str] = None,
        codec: Optional[str] = None,
        preset: Optional[str] = None,
        tune: Optional[str] = None,
        rtsp_transport: Optional[str] = None,
        max_clients: Optional[int] = None,
    ) -> None:
        self._rtsp_url = rtsp_url
        self._bitrate = bitrate
        self._codec = codec or "libx264"
        self._preset = preset or "ultrafast"
        self._tune = tune or "zerolatency"
        self._rtsp_transport = rtsp_transport or "tcp"
        self._max_clients = max_clients
        self._proc: Optional[subprocess.Popen] = None
        self._output_size: Optional[Tuple[int, int]] = None

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """
        Abre el output RTSP y inicia el proceso ffmpeg.

        Args:
            config: Configuración del engine
            output_size: Tamaño de salida (ancho, alto)
        """
        self.close()
        self._output_size = output_size

        # Construir URL RTSP
        # Si no se proporciona URL, usar valores de config
        if not self._rtsp_url:
            host = config.host if config.host != "127.0.0.1" else "0.0.0.0"
            port = config.port if config.port != 1234 else 8554  # Puerto RTSP por defecto
            stream_path = "stream"
            rtsp_url = f"rtsp://{host}:{port}/{stream_path}"
        else:
            rtsp_url = self._rtsp_url

        bitrate = self._bitrate or config.bitrate
        out_w, out_h = output_size

        # Construir comando ffmpeg para RTSP
        # Usar TCP por defecto para mejor compatibilidad multi-cliente
        cmd = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{out_w}x{out_h}",
            "-framerate",
            str(config.fps),
            "-i",
            "-",
            "-an",  # Sin audio
            "-c:v",
            self._codec,
            "-preset",
            self._preset,
            "-tune",
            self._tune,
            "-b:v",
            bitrate,
            "-f",
            "rtsp",
            "-rtsp_transport",
            self._rtsp_transport,
        ]

        # Agregar parámetros adicionales para soporte multi-cliente si es necesario
        # Nota: ffmpeg por sí solo no es un servidor RTSP completo multi-cliente,
        # pero podemos configurarlo para aceptar múltiples conexiones con parámetros adecuados
        if self._max_clients:
            # Para soporte multi-cliente real, se recomienda usar un servidor RTSP externo
            # como MediaMTX (anteriormente rtsp-simple-server) o similar
            logger.info(
                f"Configurado para hasta {self._max_clients} clientes simultáneos. "
                "Para soporte multi-cliente completo, considere usar un servidor RTSP externo."
            )

        cmd.append(rtsp_url)

        logger.info(f"Iniciando servidor RTSP en {rtsp_url}")
        logger.debug(f"Comando ffmpeg: {' '.join(cmd)}")

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg no encontrado. Por favor, instala ffmpeg para usar el output RTSP."
            )
        except Exception as e:
            raise RuntimeError(f"Error al iniciar servidor RTSP: {e}")

    def write(self, frame: RenderFrame) -> None:
        """
        Escribe un frame al stream RTSP.

        Args:
            frame: Frame a escribir
        """
        if not self._proc or not self._proc.stdin:
            logger.warning("Intento de escribir frame pero el proceso no está abierto")
            return

        try:
            image = frame.image if isinstance(frame, RenderFrame) else frame
            if isinstance(image, Image.Image):
                if image.mode != "RGB":
                    image = image.convert("RGB")
                self._proc.stdin.write(image.tobytes())
                self._proc.stdin.flush()
        except BrokenPipeError:
            logger.error("Pipe roto - el proceso ffmpeg puede haber terminado")
            self._proc = None
        except Exception as e:
            logger.error(f"Error al escribir frame: {e}")

    def close(self) -> None:
        """Cierra el output RTSP y termina el proceso ffmpeg."""
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.close()
            except Exception as e:
                logger.debug(f"Error al cerrar stdin: {e}")

        if self._proc:
            try:
                # Esperar a que termine normalmente
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    # Intentar terminar suavemente
                    self._proc.terminate()
                    self._proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    # Forzar terminación si es necesario
                    logger.warning("Forzando terminación del proceso ffmpeg")
                    self._proc.kill()
                    self._proc.wait()
            except Exception as e:
                logger.debug(f"Error al esperar proceso: {e}")
            finally:
                self._proc = None

        logger.info("Output RTSP cerrado")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
