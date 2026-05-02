"""Protocol para renderers que exponen un overlay toggleable."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class OverlayCapable(Protocol):
    """Renderers que dibujan información on-top del frame y pueden apagarla.

    Lo cumplen `LandmarksOverlayRenderer` y cualquier futuro renderer con
    HUD / debug overlay. El web bridge lo usa con `isinstance` para hallar
    el renderer apropiado en el chain sin atarse a una clase concreta.
    """

    @property
    def overlay_enabled(self) -> bool: ...

    @overlay_enabled.setter
    def overlay_enabled(self, on: bool) -> None: ...
