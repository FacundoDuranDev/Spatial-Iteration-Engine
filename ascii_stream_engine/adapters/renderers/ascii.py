import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ...domain.config import EngineConfig
from ...domain.types import RenderFrame


class AsciiRenderer:
    def __init__(
        self,
        font: Optional[ImageFont.ImageFont] = None,
        font_path: Optional[str] = None,
        font_size: int = 12,
    ) -> None:
        if font is not None and font_path is not None:
            raise ValueError("Usa font o font_path, no ambos.")
        if font is None:
            font = self._load_font(font_path, font_size)
        self._font = font
        bbox = self._font.getbbox("M")
        self._char_w = bbox[2] - bbox[0]
        self._char_h = bbox[3] - bbox[1]
        # Cache para reutilizar imágenes PIL cuando el tamaño no cambia (solo para modo ASCII)
        self._cached_ascii_image: Optional[Image.Image] = None
        self._cached_ascii_size: Optional[Tuple[int, int]] = None

    def _load_font(
        self, font_path: Optional[str], font_size: int
    ) -> ImageFont.ImageFont:
        if font_path:
            try:
                return ImageFont.truetype(font_path, font_size)
            except Exception:
                pass

        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, font_size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def output_size(self, config: EngineConfig) -> Tuple[int, int]:
        mode = getattr(config, "render_mode", "ascii")
        if mode == "raw":
            raw_w = getattr(config, "raw_width", None)
            raw_h = getattr(config, "raw_height", None)
            if raw_w and raw_h:
                return int(raw_w), int(raw_h)
        return config.grid_w * self._char_w, config.grid_h * self._char_h

    def _frame_to_image(
        self, frame: np.ndarray, output_size: Tuple[int, int]
    ) -> Image.Image:
        # Optimización: verificar si el frame ya está en RGB antes de convertir
        if frame.ndim == 2:
            # Frame es escala de grises, necesitamos convertir a RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        else:
            # Frame es color, verificar si ya está en RGB
            # OpenCV usa BGR por defecto, así que asumimos BGR y convertimos
            # Nota: Si el frame ya viene en RGB, esta conversión es innecesaria,
            # pero sin metadata no podemos saberlo. Asumimos BGR por compatibilidad.
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Optimización: solo redimensionar si el tamaño es diferente
        # Esto evita una copia innecesaria cuando el frame ya tiene el tamaño correcto
        # Verificar dimensiones antes de redimensionar para evitar operaciones costosas
        h, w = rgb.shape[:2]
        if (w, h) != output_size:
            rgb = cv2.resize(rgb, output_size, interpolation=cv2.INTER_AREA)
        
        # Optimización: usar copy=False cuando sea posible para evitar copias adicionales
        # Image.fromarray() crea una nueva imagen PIL, pero podemos optimizar el tipo
        # Asegurar que el array sea contiguo en memoria para mejor rendimiento
        if not rgb.flags['C_CONTIGUOUS']:
            rgb = np.ascontiguousarray(rgb)
        
        # Nota: Image.fromarray() crea una nueva imagen PIL, pero esto es necesario
        # porque PIL mantiene sus propios buffers internos. La optimización principal
        # está en evitar el resize innecesario y asegurar contigüidad de memoria.
        return Image.fromarray(rgb)

    def _frame_to_lines(self, frame: np.ndarray, config: EngineConfig) -> List[str]:
        # Optimización: evitar conversión de color si el frame ya es escala de grises
        # Usar view cuando sea posible para evitar copias innecesarias
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            # Frame ya es escala de grises, usar directamente (puede ser una vista)
            gray = frame
        
        # Optimización: solo redimensionar si el tamaño es diferente
        target_size = (config.grid_w, config.grid_h)
        current_size = gray.shape[:2][::-1]  # numpy usa (h, w), cv2.resize usa (w, h)
        if current_size != target_size:
            small = cv2.resize(gray, target_size, interpolation=cv2.INTER_AREA)
        else:
            # Ya tiene el tamaño correcto, usar directamente
            # Asegurar contiguidad para operaciones vectorizadas eficientes
            if not gray.flags['C_CONTIGUOUS']:
                small = np.ascontiguousarray(gray)
            else:
                small = gray
        
        chars = config.charset
        charset_array = np.array(list(chars), dtype='U1')  # Array de caracteres Unicode de 1 byte
        
        # Optimización: vectorización completa usando numpy
        # Calcular índices de manera vectorizada con clip para evitar índices fuera de rango
        idx = np.clip(
            (small.astype(np.float32) / 255.0 * (len(chars) - 1)).astype(np.int32),
            0, len(chars) - 1
        )
        
        # Optimización: usar indexación avanzada de numpy para obtener caracteres
        # Esto es mucho más rápido que comprensiones de listas anidadas
        char_matrix = charset_array[idx]
        
        # Optimización: convertir array 2D de caracteres a lista de strings de forma eficiente
        # Usar view para convertir cada fila a string directamente, evitando tolist() intermedio
        # cuando sea posible. Para arrays pequeños, tolist() + join es más eficiente.
        # Para arrays grandes, podríamos usar np.char.array, pero para el caso de uso típico
        # (grids pequeños), tolist() + join es óptimo.
        return [''.join(row) for row in char_matrix.tolist()]

    def render(
        self, frame: np.ndarray, config: EngineConfig, analysis: Optional[dict] = None
    ) -> RenderFrame:
        metadata = {"analysis": analysis or {}}
        mode = getattr(config, "render_mode", "ascii")
        out_w, out_h = self.output_size(config)

        if mode == "raw":
            img = self._frame_to_image(frame, (out_w, out_h))
            return RenderFrame(image=img, text=None, lines=None, metadata=metadata)

        lines = self._frame_to_lines(frame, config)
        text = "\n".join(lines)
        
        # Optimización: reutilizar imagen PIL si el tamaño no ha cambiado
        # Esto evita crear una nueva imagen en cada frame, reduciendo allocaciones
        if self._cached_ascii_image is not None and self._cached_ascii_size == (out_w, out_h):
            img = self._cached_ascii_image
            # Limpiar la imagen reutilizada dibujando un rectángulo negro
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0, 0), (out_w, out_h)], fill=(0, 0, 0))
        else:
            # Crear nueva imagen solo si el tamaño cambió
            img = Image.new("RGB", (out_w, out_h), color=(0, 0, 0))
            self._cached_ascii_image = img
            self._cached_ascii_size = (out_w, out_h)
            draw = ImageDraw.Draw(img)
        
        y = 0
        for line in lines:
            draw.text((0, y), line, fill=(255, 255, 255), font=self._font)
            y += self._char_h
        return RenderFrame(image=img, text=text, lines=lines, metadata=metadata)
