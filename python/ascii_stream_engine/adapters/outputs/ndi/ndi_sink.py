import logging
import threading
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from ascii_stream_engine.domain.config import EngineConfig
from ascii_stream_engine.domain.types import RenderFrame

logger = logging.getLogger(__name__)

# Intentar importar NDI, manejar graciosamente si no está disponible
try:
    import NDIlib as ndi

    NDI_AVAILABLE = True
except ImportError:
    NDI_AVAILABLE = False
    logger.warning(
        "NDI SDK no está disponible. Instala 'ndi-python' y el NDI SDK nativo "
        "para usar el output NDI."
    )


class NdiOutputSink:
    """
    Output sink que envía frames a través de NDI (Network Device Interface).

    Requiere:
    - ndi-python: pip install ndi-python
    - NDI SDK nativo instalado en el sistema

    El NDI SDK debe descargarse desde: https://www.ndi.tv/sdk/
    """

    def __init__(
        self,
        source_name: Optional[str] = None,
        groups: Optional[str] = None,
        clock_video: bool = True,
        clock_audio: bool = False,
    ) -> None:
        """
        Inicializa el output NDI.

        Args:
            source_name: Nombre de la fuente NDI (por defecto "Spatial Iteration Engine")
            groups: Grupos NDI (separados por comas)
            clock_video: Si True, sincroniza el video con el reloj del sistema
            clock_audio: Si True, sincroniza el audio con el reloj del sistema
        """
        if not NDI_AVAILABLE:
            raise ImportError(
                "NDI SDK no está disponible. Instala 'ndi-python' y el NDI SDK nativo."
            )

        self._source_name = source_name or "Spatial Iteration Engine"
        self._groups = groups
        self._clock_video = clock_video
        self._clock_audio = clock_audio

        self._ndi_send: Optional[object] = None
        self._video_frame: Optional[object] = None
        self._output_size: Optional[Tuple[int, int]] = None
        self._fps: Optional[float] = None
        self._lock = threading.Lock()
        self._is_open = False

    def open(self, config: EngineConfig, output_size: Tuple[int, int]) -> None:
        """
        Abre la conexión NDI y prepara el envío de frames.

        Args:
            config: Configuración del engine
            output_size: Tamaño de salida (ancho, alto)
        """
        if not NDI_AVAILABLE:
            raise RuntimeError("NDI SDK no está disponible")

        with self._lock:
            self.close()

            # Inicializar NDI si no está inicializado
            if not ndi.initialize():
                raise RuntimeError("No se pudo inicializar NDI")

            # Crear configuración de envío NDI
            send_settings = ndi.LibNDISendCreate()
            send_settings.ndi_name = self._source_name
            if self._groups:
                send_settings.ndi_groups = self._groups
            send_settings.clock_video = self._clock_video
            send_settings.clock_audio = self._clock_audio

            # Crear el sender NDI
            self._ndi_send = ndi.send_create(send_settings)
            if not self._ndi_send:
                raise RuntimeError("No se pudo crear el sender NDI")

            # Preparar frame de video NDI
            self._output_size = output_size
            self._fps = config.fps
            out_w, out_h = output_size

            self._video_frame = ndi.VideoFrameV2()
            self._video_frame.xres = out_w
            self._video_frame.yres = out_h
            self._video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRA
            self._video_frame.frame_rate_N = config.fps
            self._video_frame.frame_rate_D = 1
            self._video_frame.picture_aspect_ratio = out_w / out_h

            # Pre-asignar buffer para el frame (BGRA = 4 bytes por pixel)
            frame_size = out_w * out_h * 4
            self._video_frame.p_data = np.zeros(frame_size, dtype=np.uint8)

            self._is_open = True
            logger.info(
                f"NDI output abierto: {self._source_name} " f"({out_w}x{out_h} @ {config.fps} fps)"
            )

    def write(self, frame: RenderFrame) -> None:
        """
        Escribe un frame al stream NDI.

        Args:
            frame: Frame renderizado a enviar
        """
        if not NDI_AVAILABLE or not self._is_open:
            return

        with self._lock:
            if not self._ndi_send or not self._video_frame:
                return

            try:
                # Convertir imagen PIL a numpy array
                image = frame.image if isinstance(frame, RenderFrame) else frame
                if not isinstance(image, Image.Image):
                    logger.warning("Frame no contiene una imagen PIL válida")
                    return

                # Convertir a RGB si es necesario
                if image.mode != "RGB":
                    image = image.convert("RGB")

                # Redimensionar si es necesario
                if self._output_size:
                    out_w, out_h = self._output_size
                    if image.size != (out_w, out_h):
                        image = image.resize((out_w, out_h), Image.Resampling.LANCZOS)

                # Convertir RGB a BGRA (formato requerido por NDI)
                rgb_array = np.array(image, dtype=np.uint8)

                # Crear array BGRA (añadir canal alpha con valor 255)
                bgra_array = np.zeros((out_h, out_w, 4), dtype=np.uint8)
                bgra_array[:, :, 0] = rgb_array[:, :, 2]  # B
                bgra_array[:, :, 1] = rgb_array[:, :, 1]  # G
                bgra_array[:, :, 2] = rgb_array[:, :, 0]  # R
                bgra_array[:, :, 3] = 255  # A (opaco)

                # Copiar datos al buffer del frame NDI
                frame_data = bgra_array.flatten()
                if len(frame_data) == len(self._video_frame.p_data):
                    self._video_frame.p_data[:] = frame_data
                else:
                    # Reasignar buffer si el tamaño cambió
                    self._video_frame.p_data = frame_data

                # Enviar frame
                ndi.send_send_video_v2(self._ndi_send, self._video_frame)

            except Exception as e:
                logger.error(f"Error enviando frame NDI: {e}", exc_info=True)

    def close(self) -> None:
        """Cierra la conexión NDI y libera recursos."""
        with self._lock:
            if self._ndi_send:
                try:
                    ndi.send_destroy(self._ndi_send)
                except Exception as e:
                    logger.warning(f"Error cerrando sender NDI: {e}")
                self._ndi_send = None

            self._video_frame = None
            self._output_size = None
            self._fps = None
            self._is_open = False

            if NDI_AVAILABLE:
                try:
                    ndi.destroy()
                except Exception:
                    pass

            logger.info("NDI output cerrado")

    def __del__(self) -> None:
        """Asegura que los recursos se liberen al destruir el objeto."""
        if hasattr(self, "_lock"):
            self.close()
