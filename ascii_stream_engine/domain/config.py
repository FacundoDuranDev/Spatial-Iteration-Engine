import re
import socket
from dataclasses import dataclass
from typing import Optional


class ConfigValidationError(ValueError):
    """Excepción lanzada cuando la validación de configuración falla."""

    pass


@dataclass
class EngineConfig:
    fps: int = 20
    grid_w: int = 120
    grid_h: int = 60
    charset: str = " .:-=+*#%@"
    render_mode: str = "ascii"  # "ascii" o "raw"
    raw_width: Optional[int] = None
    raw_height: Optional[int] = None
    invert: bool = False
    contrast: float = 1.2
    brightness: int = 0
    host: str = "127.0.0.1"
    port: int = 1234
    pkt_size: int = 1316
    bitrate: str = "1500k"
    udp_broadcast: bool = False
    frame_buffer_size: int = 2
    sleep_on_empty: float = 0.01

    def __post_init__(self) -> None:
        """Valida la configuración después de la inicialización."""
        errors = []

        # Validar fps: rango 1-120
        if not (1 <= self.fps <= 120):
            errors.append(
                f"fps debe estar entre 1 y 120, se recibió: {self.fps}"
            )

        # Validar grid_w: mínimo 10, máximo 1000
        if not (10 <= self.grid_w <= 1000):
            errors.append(
                f"grid_w debe estar entre 10 y 1000, se recibió: {self.grid_w}"
            )

        # Validar grid_h: mínimo 10, máximo 1000
        if not (10 <= self.grid_h <= 1000):
            errors.append(
                f"grid_h debe estar entre 10 y 1000, se recibió: {self.grid_h}"
            )

        # Validar charset: no debe estar vacío
        if not self.charset or len(self.charset) < 2:
            errors.append(
                f"charset debe tener al menos 2 caracteres, se recibió: '{self.charset}'"
            )

        # Validar render_mode: solo "ascii" o "raw"
        if self.render_mode not in ("ascii", "raw"):
            errors.append(
                f"render_mode debe ser 'ascii' o 'raw', se recibió: '{self.render_mode}'"
            )

        # Validar raw_width y raw_height si render_mode es "raw"
        if self.render_mode == "raw":
            if self.raw_width is not None and not (10 <= self.raw_width <= 10000):
                errors.append(
                    f"raw_width debe estar entre 10 y 10000, se recibió: {self.raw_width}"
                )
            if self.raw_height is not None and not (10 <= self.raw_height <= 10000):
                errors.append(
                    f"raw_height debe estar entre 10 y 10000, se recibió: {self.raw_height}"
                )

        # Validar contrast: rango razonable 0.1-5.0
        if not (0.1 <= self.contrast <= 5.0):
            errors.append(
                f"contrast debe estar entre 0.1 y 5.0, se recibió: {self.contrast}"
            )

        # Validar brightness: rango razonable -255 a 255
        if not (-255 <= self.brightness <= 255):
            errors.append(
                f"brightness debe estar entre -255 y 255, se recibió: {self.brightness}"
            )

        # Validar host: debe ser una dirección IP válida o hostname válido
        if not self._is_valid_host(self.host):
            errors.append(
                f"host debe ser una dirección IP válida o hostname válido, se recibió: '{self.host}'"
            )

        # Validar port: rango 1-65535
        if not (1 <= self.port <= 65535):
            errors.append(
                f"port debe estar entre 1 y 65535, se recibió: {self.port}"
            )

        # Validar pkt_size: rango razonable 512-65507 (máximo UDP)
        if not (512 <= self.pkt_size <= 65507):
            errors.append(
                f"pkt_size debe estar entre 512 y 65507, se recibió: {self.pkt_size}"
            )

        # Validar bitrate: formato "número[k|m|K|M]" o solo número
        if not self._is_valid_bitrate(self.bitrate):
            errors.append(
                f"bitrate debe tener formato válido (ej: '1500k', '2m', '1000'), se recibió: '{self.bitrate}'"
            )

        # Validar frame_buffer_size: mínimo 0 (deshabilitado) o positivo
        if self.frame_buffer_size < 0:
            errors.append(
                f"frame_buffer_size debe ser >= 0, se recibió: {self.frame_buffer_size}"
            )

        # Validar sleep_on_empty: debe ser positivo
        if self.sleep_on_empty <= 0:
            errors.append(
                f"sleep_on_empty debe ser > 0, se recibió: {self.sleep_on_empty}"
            )

        # Si hay errores, lanzar excepción
        if errors:
            error_msg = "Errores de validación en EngineConfig:\n  - " + "\n  - ".join(
                errors
            )
            raise ConfigValidationError(error_msg)

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        """Valida si un host es una dirección IP válida o hostname válido."""
        if not host or len(host) > 253:  # Longitud máxima de hostname
            return False

        # Intentar validar como dirección IP
        try:
            socket.inet_aton(host)
            return True
        except (socket.error, OSError):
            pass

        # Intentar validar como IPv6
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return True
        except (socket.error, OSError):
            pass

        # Validar como hostname: letras, números, guiones, puntos
        # No puede empezar ni terminar con guión o punto
        hostname_pattern = re.compile(
            r"^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
        )
        if hostname_pattern.match(host):
            return True

        # Permitir "localhost"
        if host.lower() == "localhost":
            return True

        return False

    @staticmethod
    def _is_valid_bitrate(bitrate: str) -> bool:
        """Valida el formato de bitrate."""
        if not bitrate:
            return False

        # Patrón: número opcionalmente seguido de k, K, m, M
        pattern = re.compile(r"^\d+[kKmM]?$")
        if not pattern.match(bitrate):
            return False

        # Extraer el número
        match = re.match(r"^(\d+)[kKmM]?$", bitrate)
        if match:
            number = int(match.group(1))
            # Validar que el número sea razonable (1-100000)
            return 1 <= number <= 100000

        return False
