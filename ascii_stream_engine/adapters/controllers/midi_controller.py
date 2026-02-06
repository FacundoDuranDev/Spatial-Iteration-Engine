"""Controlador MIDI usando python-rtmidi o mido."""

import logging
from typing import Any, Dict, Optional

from .base import BaseController

logger = logging.getLogger(__name__)

# Intentar importar librerías MIDI
try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False
    rtmidi = None

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False
    mido = None


class MidiController(BaseController):
    """Controlador MIDI usando python-rtmidi o mido."""

    name = "midi_controller"

    def __init__(
        self,
        port: Optional[int] = None,
        port_name: Optional[str] = None,
        enabled: bool = True,
        use_rtmidi: bool = True,
    ) -> None:
        """
        Inicializa el controlador MIDI.

        Args:
            port: Número de puerto MIDI (None para auto-detectar)
            port_name: Nombre del puerto MIDI (None para auto-detectar)
            enabled: Si el controlador está habilitado
            use_rtmidi: Si usar rtmidi en lugar de mido (si ambos están disponibles)
        """
        super().__init__(enabled)

        if not RTMIDI_AVAILABLE and not MIDO_AVAILABLE:
            raise ImportError(
                "Se requiere 'python-rtmidi' o 'mido' para usar MidiController. "
                "Instala con: pip install python-rtmidi o pip install mido"
            )

        self.port = port
        self.port_name = port_name
        self.use_rtmidi = use_rtmidi and RTMIDI_AVAILABLE
        self._midi_in = None
        self._midi_port = None

    def _do_connect(self) -> None:
        """Conecta al puerto MIDI."""
        if self.use_rtmidi and RTMIDI_AVAILABLE:
            self._connect_rtmidi()
        elif MIDO_AVAILABLE:
            self._connect_mido()
        else:
            raise RuntimeError("No hay librerías MIDI disponibles")

    def _connect_rtmidi(self) -> None:
        """Conecta usando python-rtmidi."""
        self._midi_in = rtmidi.MidiIn()
        ports = self._midi_in.get_ports()

        if not ports:
            raise RuntimeError("No se encontraron puertos MIDI disponibles")

        if self.port_name:
            if self.port_name not in ports:
                raise RuntimeError(f"Puerto MIDI '{self.port_name}' no encontrado")
            port_index = ports.index(self.port_name)
        elif self.port is not None:
            if self.port >= len(ports):
                raise RuntimeError(f"Puerto MIDI {self.port} no existe")
            port_index = self.port
        else:
            port_index = 0

        self._midi_in.open_port(port_index)
        self._midi_in.set_callback(self._rtmidi_callback)
        self._midi_port = ports[port_index]
        logger.info(f"Conectado a puerto MIDI: {self._midi_port}")

    def _connect_mido(self) -> None:
        """Conecta usando mido."""
        ports = mido.get_input_names()

        if not ports:
            raise RuntimeError("No se encontraron puertos MIDI disponibles")

        if self.port_name:
            if self.port_name not in ports:
                raise RuntimeError(f"Puerto MIDI '{self.port_name}' no encontrado")
            port_name = self.port_name
        elif self.port is not None:
            if self.port >= len(ports):
                raise RuntimeError(f"Puerto MIDI {self.port} no existe")
            port_name = ports[self.port]
        else:
            port_name = ports[0]

        self._midi_port = mido.open_input(port_name, callback=self._mido_callback)
        logger.info(f"Conectado a puerto MIDI: {port_name}")

    def _rtmidi_callback(self, message_data, _) -> None:
        """Callback para mensajes MIDI usando rtmidi."""
        message, _ = message_data
        self._process_midi_message(message)

    def _mido_callback(self, message) -> None:
        """Callback para mensajes MIDI usando mido."""
        self._process_midi_message(message.bytes())

    def _process_midi_message(self, message: bytes) -> None:
        """
        Procesa un mensaje MIDI.

        Args:
            message: Bytes del mensaje MIDI
        """
        if len(message) < 1:
            return

        status = message[0] & 0xF0
        channel = message[0] & 0x0F

        params: Dict[str, Any] = {
            "status": status,
            "channel": channel,
            "raw": message,
        }

        if status == 0x90:  # Note On
            if len(message) >= 3:
                note = message[1]
                velocity = message[2]
                params.update({"note": note, "velocity": velocity, "type": "note_on"})
                self._notify_callbacks(params)
                self._publish_event("note_on", params, note)

        elif status == 0x80:  # Note Off
            if len(message) >= 3:
                note = message[1]
                velocity = message[2] if len(message) > 2 else 0
                params.update({"note": note, "velocity": velocity, "type": "note_off"})
                self._notify_callbacks(params)
                self._publish_event("note_off", params, note)

        elif status == 0xB0:  # Control Change
            if len(message) >= 3:
                controller = message[1]
                value = message[2]
                params.update({"controller": controller, "value": value, "type": "cc"})
                self._notify_callbacks(params)
                self._publish_event("control_change", params, value)

    def _do_disconnect(self) -> None:
        """Desconecta del puerto MIDI."""
        if self._midi_in:
            self._midi_in.close_port()
            self._midi_in = None
        elif self._midi_port and hasattr(self._midi_port, "close"):
            self._midi_port.close()
            self._midi_port = None

