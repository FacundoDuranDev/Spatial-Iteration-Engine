#!/usr/bin/env python3
"""Script de diagnóstico detallado para problemas de percepción."""

import os
import sys
import numpy as np
from pathlib import Path

# Configurar rutas
repo_root = Path.cwd()
sys.path.insert(0, str(repo_root / "python"))
sys.path.insert(0, str(repo_root / "cpp" / "build"))
os.environ["ONNX_MODELS_DIR"] = str(repo_root / "onnx_models" / "mediapipe")

print("=" * 70)
print("DIAGNÓSTICO DETALLADO - PERCEPCIÓN IA")
print("=" * 70)
print()

# 1. Verificar modelos
print("1. VERIFICANDO MODELOS ONNX")
print("-" * 70)
models_dir = os.environ.get("ONNX_MODELS_DIR")
models = {
    "face": "face_landmark.onnx",
    "hand": "hand_landmark.onnx",
    "pose": "pose_landmark.onnx",
}

for name, filename in models.items():
    model_path = Path(models_dir) / filename
    print(f"\n{name.upper()}: {filename}")
    print(f"  Ruta: {model_path}")
    
    if not model_path.exists():
        print(f"  ❌ NO EXISTE")
        continue
    
    size_mb = model_path.stat().st_size / (1024 * 1024)
    print(f"  ✅ Existe ({size_mb:.1f} MB)")
    
    # Verificar tipo de archivo
    import subprocess
    result = subprocess.run(
        ["file", str(model_path)],
        capture_output=True,
        text=True
    )
    file_type = result.stdout.strip().split(":")[-1].strip()
    print(f"  Tipo: {file_type}")
    
    # Verificar si es ONNX válido
    if "ONNX" in file_type.upper() or "data" in file_type.lower():
        # Intentar leer magic bytes
        with open(model_path, "rb") as f:
            magic = f.read(4)
            if magic == b"\x08\x00\x00\x00" or magic[:2] == b"PK":
                if magic[:2] == b"PK":
                    print(f"  ⚠️  Es un archivo ZIP (probablemente TFLite, no ONNX)")
                else:
                    print(f"  ✅ Parece ser ONNX válido")
            else:
                print(f"  ⚠️  Magic bytes: {magic.hex()} (verificar formato)")

# 2. Verificar perception_cpp
print("\n\n2. VERIFICANDO MÓDULO C++")
print("-" * 70)
try:
    import perception_cpp
    print("✅ perception_cpp importado correctamente")
    print(f"   Ubicación: {perception_cpp.__file__ if hasattr(perception_cpp, '__file__') else 'N/A'}")
except ImportError as e:
    print(f"❌ Error importando perception_cpp: {e}")
    print("   Solución: cd cpp/build && cmake .. && make")
    sys.exit(1)

# 3. Probar detección con frame realista
print("\n\n3. PROBANDO DETECCIÓN")
print("-" * 70)

# Crear frame más realista (simulando una persona)
test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
# Agregar un "cuerpo" simulado
test_frame[100:400, 200:400] = [200, 180, 160]  # Torso
test_frame[50:150, 250:350] = [220, 200, 180]   # Cabeza
test_frame[400:480, 220:240] = [180, 160, 140]  # Pierna izquierda
test_frame[400:480, 360:380] = [180, 160, 140]  # Pierna derecha

print("Frame de prueba: 480x640 con figura simulada")
print()

# Probar cada detector
detectors = [
    ("detect_pose", perception_cpp.detect_pose, "Pose (YOLOv8)"),
    ("detect_face", perception_cpp.detect_face, "Face (DETR)"),
    ("detect_hands", perception_cpp.detect_hands, "Hands (MediaPipe)"),
]

for func_name, func, description in detectors:
    print(f"{description}:")
    try:
        result = func(test_frame)
        
        if hasattr(result, "shape"):
            shape = result.shape
            n_points = shape[0] if len(shape) > 0 else 0
            print(f"  Shape: {shape}")
            print(f"  Puntos detectados: {n_points}")
            
            if n_points == 0:
                print(f"  ⚠️  PROBLEMA: Cero puntos detectados")
                print(f"     Posibles causas:")
                print(f"     - Modelo no se cargó (verificar ruta)")
                print(f"     - Modelo no es compatible (formato incorrecto)")
                print(f"     - Modelo requiere post-procesamiento")
            elif n_points > 1000:
                print(f"  ⚠️  PROBLEMA: Demasiados puntos ({n_points})")
                print(f"     El modelo está devolviendo toda la salida sin filtrar")
                print(f"     Necesita post-procesamiento para extraer detecciones válidas")
                if n_points > 0:
                    print(f"     Primeros valores: {result[:5]}")
            elif n_points > 0:
                print(f"  ✅ Detectado: {n_points} puntos")
                print(f"     Primeros valores: {result[:min(5, n_points)]}")
        else:
            print(f"  Resultado: {type(result)} (sin shape)")
            print(f"  Longitud: {len(result) if hasattr(result, '__len__') else 'N/A'}")
            
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()

# 4. Verificar carga de modelos (intentar cargar directamente)
print("\n4. VERIFICANDO CARGA DIRECTA DE MODELOS")
print("-" * 70)

try:
    import onnxruntime as ort
    print("✅ onnxruntime disponible")
    
    for name, filename in models.items():
        model_path = Path(models_dir) / filename
        if not model_path.exists():
            continue
        
        print(f"\n{name.upper()}: {filename}")
        try:
            session = ort.InferenceSession(str(model_path))
            print(f"  ✅ Modelo cargado correctamente")
            print(f"  Inputs: {len(session.get_inputs())}")
            for inp in session.get_inputs():
                print(f"    - {inp.name}: shape={inp.shape}, type={inp.type}")
            print(f"  Outputs: {len(session.get_outputs())}")
            for out in session.get_outputs():
                print(f"    - {out.name}: shape={out.shape}, type={out.type}")
        except Exception as e:
            print(f"  ❌ Error cargando modelo: {e}")
            print(f"     El archivo puede no ser un ONNX válido")
            
except ImportError:
    print("⚠️  onnxruntime no disponible (pip install onnxruntime)")
    print("   No se puede verificar la carga directa de modelos")

print("\n" + "=" * 70)
print("RESUMEN Y RECOMENDACIONES")
print("=" * 70)
print()
print("PROBLEMAS IDENTIFICADOS:")
print()
print("1. POSE: Devuelve demasiados puntos (necesita post-procesamiento)")
print("   - El modelo YOLOv8 funciona pero devuelve toda la salida")
print("   - Necesita filtrar detecciones válidas (confianza > umbral)")
print()
print("2. FACE: Cero puntos (modelo puede no cargarse o formato incompatible)")
print("   - Verificar que el modelo DETR sea compatible")
print("   - Puede requerir formato de entrada diferente")
print()
print("3. HANDS: Cero puntos (archivo es ZIP/TFLite, no ONNX)")
print("   - hand_landmark.onnx contiene TFLite, no ONNX")
print("   - Necesita convertir TFLite → ONNX o usar runtime TFLite")
print()
print("SOLUCIONES:")
print("   - Ver: onnx_models/mediapipe/VERIFIED_MODELS.md")
print("   - Ver: onnx_models/mediapipe/ALTERNATIVE_FORMATS.md")

