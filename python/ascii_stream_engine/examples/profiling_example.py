"""Ejemplo de uso del sistema de profiling del engine."""

import signal
import sys
import time

from ascii_stream_engine import (
    AsciiRenderer,
    EngineConfig,
    FfmpegUdpOutput,
    OpenCVCameraSource,
    StreamEngine,
)


def main() -> None:
    """Ejecuta el engine con profiling habilitado y muestra reportes periódicos."""
    config = EngineConfig(host="127.0.0.1", port=1234, fps=10)

    # Crear engine con profiling habilitado
    engine = StreamEngine(
        source=OpenCVCameraSource(0),
        renderer=AsciiRenderer(),
        sink=FfmpegUdpOutput(),
        config=config,
        enable_profiling=True,  # Habilitar profiling
    )

    # Variable para controlar la salida
    running = True

    def signal_handler(sig, frame):
        """Maneja la señal de interrupción."""
        nonlocal running
        print("\n\nDeteniendo engine...")
        running = False
        engine.stop()

    signal.signal(signal.SIGINT, signal_handler)

    print("Iniciando engine con profiling habilitado...")
    print("Presiona Ctrl+C para detener y ver el reporte final\n")

    # Iniciar engine en un hilo separado
    engine.start(blocking=False)

    # Mostrar reportes periódicos cada 5 segundos
    try:
        while running and engine.is_running:
            time.sleep(5)
            if engine.is_running:
                print("\n" + "=" * 70)
                print("REPORTE PERIÓDICO DE PROFILING")
                print("=" * 70)
                print(engine.get_profiling_report())
                print("\n")
    except KeyboardInterrupt:
        pass

    # Detener el engine
    engine.stop()

    # Mostrar reporte final
    print("\n" + "=" * 70)
    print("REPORTE FINAL DE PROFILING")
    print("=" * 70)
    print(engine.get_profiling_report())

    # También mostrar estadísticas como diccionario
    print("\n" + "=" * 70)
    print("ESTADÍSTICAS COMO DICCIONARIO")
    print("=" * 70)
    stats = engine.get_profiling_stats()
    for phase, phase_stats in stats.items():
        print(f"\n{phase}:")
        for key, value in phase_stats.items():
            if isinstance(value, float):
                if "time" in key:
                    print(f"  {key}: {value*1000:.3f} ms")
                else:
                    print(f"  {key}: {value:.6f}")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
