"""Ejemplo de uso del sistema de configuración con YAML/JSON y perfiles predefinidos."""

from ascii_stream_engine import (
    EngineConfig,
    load_config_from_file,
    load_config_from_profile,
    list_predefined_profiles,
    save_config_to_file,
    merge_configs,
)


def example_predefined_profiles():
    """Ejemplo de uso de perfiles predefinidos."""
    print("=== Ejemplo: Perfiles Predefinidos ===\n")

    # Listar perfiles disponibles
    print("Perfiles disponibles:", list_predefined_profiles())
    print()

    # Cargar configuración desde un perfil
    config = load_config_from_profile("low_latency")
    print(f"Configuración 'low_latency':")
    print(f"  FPS: {config.fps}, Grid: {config.grid_w}x{config.grid_h}")
    print(f"  Buffer: {config.frame_buffer_size}, Bitrate: {config.bitrate}")
    print()

    # Cargar perfil con sobrescrituras
    config = load_config_from_profile(
        "balanced", overrides={"host": "192.168.1.100", "port": 5000}
    )
    print(f"Configuración 'balanced' con sobrescrituras:")
    print(f"  Host: {config.host}, Port: {config.port}")
    print()


def example_yaml_json():
    """Ejemplo de carga desde archivos YAML/JSON."""
    print("=== Ejemplo: Carga desde Archivos ===\n")

    # Crear un archivo de ejemplo YAML
    yaml_content = """
fps: 30
grid_w: 150
grid_h: 75
host: "127.0.0.1"
port: 1234
bitrate: "2000k"
gpu_enabled: true
parallel_workers: 2
"""
    with open("example_config.yaml", "w") as f:
        f.write(yaml_content)

    # Cargar desde YAML
    try:
        config = load_config_from_file("example_config.yaml")
        print("Configuración cargada desde YAML:")
        print(f"  FPS: {config.fps}, Grid: {config.grid_w}x{config.grid_h}")
        print(f"  GPU: {config.gpu_enabled}, Workers: {config.parallel_workers}")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # Crear un archivo de ejemplo JSON
    import json

    json_config = {
        "fps": 25,
        "grid_w": 120,
        "grid_h": 60,
        "host": "127.0.0.1",
        "port": 5678,
        "bitrate": "1500k",
        "invert": True,
        "contrast": 1.3,
    }
    with open("example_config.json", "w") as f:
        json.dump(json_config, f, indent=2)

    # Cargar desde JSON
    try:
        config = load_config_from_file("example_config.json")
        print("Configuración cargada desde JSON:")
        print(f"  FPS: {config.fps}, Grid: {config.grid_w}x{config.grid_h}")
        print(f"  Invert: {config.invert}, Contrast: {config.contrast}")
    except Exception as e:
        print(f"Error: {e}")
    print()


def example_save_and_merge():
    """Ejemplo de guardado y combinación de configuraciones."""
    print("=== Ejemplo: Guardar y Combinar Configuraciones ===\n")

    # Crear una configuración base
    base_config = EngineConfig(host="127.0.0.1", port=1234, fps=20)

    # Guardar a archivo
    try:
        save_config_to_file(base_config, "saved_config.yaml", format="yaml")
        print("Configuración guardada en 'saved_config.yaml'")
    except Exception as e:
        print(f"Error al guardar: {e}")
    print()

    # Combinar configuraciones
    merged = merge_configs(base_config, {"fps": 30, "grid_w": 200})
    print("Configuración combinada:")
    print(f"  FPS: {merged.fps} (original: {base_config.fps})")
    print(f"  Grid W: {merged.grid_w} (original: {base_config.grid_w})")
    print(f"  Host: {merged.host} (sin cambios)")
    print()


def main():
    """Ejecuta todos los ejemplos."""
    print("Ejemplos del Sistema de Configuración\n")
    print("=" * 50)
    print()

    example_predefined_profiles()
    example_yaml_json()
    example_save_and_merge()

    print("=" * 50)
    print("\nEjemplos completados.")


if __name__ == "__main__":
    main()

