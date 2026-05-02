"""Curvas puras para mapear señal normalizada [0,1] → respuesta [0,1].

Cinco funciones canónicas, todas puras (sin estado, sin side effects). El
ModulationEngine las usa entre el escalado in_range y el escalado out_range
para darle "feel" al mapping (lineal vs aceleración vs threshold).

Para personalizar threshold o exponente: ajustá in_min/in_max — el "punto
medio" se traslada con el rango, no con la curva.
"""
from __future__ import annotations

from typing import Callable, Dict


def linear(t: float) -> float:
    return t


def ease_in_out(t: float) -> float:
    """Smooth-step clásica: aceleración suave en bordes, plana en el medio."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def ease_in(t: float) -> float:
    """Empieza lento, termina rápido. Bueno para "build-up" de intensidad."""
    return t * t


def ease_out(t: float) -> float:
    """Empieza rápido, termina lento. Bueno para "ataque" agresivo."""
    return 1.0 - (1.0 - t) * (1.0 - t)


def invert(t: float) -> float:
    """Espejado: la señal alta → respuesta baja. Útil para mapear "alejarse" a
    "encender efecto" sin re-escribir el rango."""
    return 1.0 - t


CURVES: Dict[str, Callable[[float], float]] = {
    "linear": linear,
    "ease_in_out": ease_in_out,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "invert": invert,
}

CURVE_NAMES = list(CURVES.keys())


def apply(name: str, t: float) -> float:
    """Resuelve por nombre con fallback a `linear` si el nombre no existe.

    Defensivo: el name puede llegar de un mapping persistido en JSON con
    una versión vieja del catálogo. No tirar excepción → degradar limpio.
    """
    fn = CURVES.get(name, linear)
    return fn(t)
