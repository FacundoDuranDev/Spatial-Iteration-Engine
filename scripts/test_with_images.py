#!/usr/bin/env python3
"""Script INTERNO para probar detección con imágenes de prueba.
Este script es solo para testing interno, no se usa en el notebook."""

import os
import sys
import numpy as np
from pathlib import Path
import cv2

# Configurar rutas
repo_root = Path(__file__).parent.parent if '__file__' in globals() else Path.cwd()
sys.path.insert(0, str(repo_root / "python"))
sys.path.insert(0, str(repo_root / "cpp" / "build"))
os.environ["ONNX_MODELS_DIR"] = str(repo_root / "onnx_models" / "mediapipe")

print("=" * 70)
print("TEST INTERNO: DETECCIÓN CON IMÁGENES DE PRUEBA")
print("=" * 70)
print("Este script valida que los detectores funcionan correctamente")
print("usando imágenes sintéticas generadas localmente.")
print()

# Verificar que las imágenes existan
test_images_dir = repo_root / "test_images"
images = {
    "face": "test_face.jpg",
    "hands": "test_hands.jpg",
    "pose": "test_pose.jpg",
}

print("1. VERIFICANDO IMÁGENES DE PRUEBA")
print("-" * 70)

for name, filename in images.items():
    img_path = test_images_dir / filename
    if img_path.exists():
        size_kb = img_path.stat().st_size / 1024
        print(f"✅ {name}: {filename} ({size_kb:.1f} KB)")
    else:
        print(f"❌ {name}: {filename} NO ENCONTRADO")
        print(f"   Ejecuta: bash scripts/download_test_images.sh")

if not all((test_images_dir / f).exists() for f in images.values()):
    print("\n⚠️  Algunas imágenes faltan. Generando...")
    import subprocess
    result = subprocess.run(
        ["bash", str(repo_root / "scripts" / "download_test_images.sh")],
        cwd=repo_root,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"❌ Error generando imágenes: {result.stderr}")
        sys.exit(1)
    print("✅ Imágenes generadas")

print("\n2. CARGANDO Y PROBANDO IMÁGENES")
print("-" * 70)

try:
    import perception_cpp
    print("✅ perception_cpp importado")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Probar cada imagen
for name, filename in images.items():
    img_path = test_images_dir / filename
    if not img_path.exists():
        continue
    
    print(f"\n{name.upper()}: {filename}")
    print("-" * 50)
    
    # Cargar imagen
    try:
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  ❌ No se pudo cargar la imagen")
            continue
        
        # Convertir BGR a RGB (OpenCV usa BGR por defecto)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        print(f"  ✅ Imagen cargada: shape={img_rgb.shape}")
        
        # Probar detección según el tipo
        if name == "pose":
            print("  Probando detect_pose...")
            result = perception_cpp.detect_pose(img_rgb)
            n_points = result.shape[0] if hasattr(result, 'shape') and len(result.shape) > 0 else 0
            print(f"    Puntos detectados: {n_points}")
            if n_points > 0 and n_points < 100:
                print(f"    ✅ CORRECTO: {n_points} keypoints detectados")
                print(f"    Primeros valores: {result[:min(5, n_points)]}")
            elif n_points == 0:
                print(f"    ⚠️  Cero puntos (puede ser normal si no hay persona)")
            else:
                print(f"    ⚠️  Demasiados puntos ({n_points})")
        
        elif name == "face":
            print("  Probando detect_face...")
            result = perception_cpp.detect_face(img_rgb)
            n_points = result.shape[0] if hasattr(result, 'shape') and len(result.shape) > 0 else 0
            print(f"    Puntos detectados: {n_points}")
            if n_points > 0:
                print(f"    ✅ Detectado: {n_points} puntos")
            else:
                print(f"    ⚠️  Cero puntos (modelo puede no funcionar)")
        
        elif name == "hands":
            print("  Probando detect_hands...")
            result = perception_cpp.detect_hands(img_rgb)
            n_points = result.shape[0] if hasattr(result, 'shape') and len(result.shape) > 0 else 0
            print(f"    Puntos detectados: {n_points}")
            if n_points > 0:
                print(f"    ✅ Detectado: {n_points} puntos")
            else:
                print(f"    ⚠️  Cero puntos (modelo es TFLite, no ONNX)")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

# Probar con AnalyzerPipeline
print("\n3. PROBANDO CON ANALYZERPIPELINE")
print("-" * 70)

try:
    from ascii_stream_engine.adapters.perception import (
        FaceLandmarkAnalyzer,
        HandLandmarkAnalyzer,
        PoseLandmarkAnalyzer,
    )
    from ascii_stream_engine.application.pipeline import AnalyzerPipeline
    from ascii_stream_engine.domain.config import EngineConfig
    
    analyzers = AnalyzerPipeline([
        FaceLandmarkAnalyzer(),
        HandLandmarkAnalyzer(),
        PoseLandmarkAnalyzer(),
    ])
    
    config = EngineConfig()
    
    # Probar con imagen de pose
    pose_img_path = test_images_dir / "test_pose.jpg"
    if pose_img_path.exists():
        img = cv2.imread(str(pose_img_path))
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        print("Probando AnalyzerPipeline con imagen de pose...")
        
        # Habilitar solo pose
        analyzers.set_enabled("face", False)
        analyzers.set_enabled("hands", False)
        analyzers.set_enabled("pose", True)
        
        result = analyzers.run(img_rgb, config)
        
        print("Resultados:")
        for name, data in result.items():
            if isinstance(data, dict):
                print(f"  {name}:")
                for key, value in data.items():
                    if hasattr(value, 'shape'):
                        n = value.shape[0] if len(value.shape) > 0 else 0
                        print(f"    {key}: {n} puntos (shape={value.shape})")
                    else:
                        print(f"    {key}: {type(value).__name__}")
            else:
                print(f"  {name}: {type(data).__name__}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("RESUMEN")
print("=" * 70)
print("✅ Si pose detectó ~17 puntos, la detección funciona correctamente")
print("⚠️  Face y Hands pueden devolver 0 (problemas conocidos de modelos)")
print("")
print("💡 Estas imágenes se pueden usar para:")
print("   - Testing sin necesidad de cámara")
print("   - Verificar que los detectores funcionan")
print("   - Debugging de problemas de detección")

