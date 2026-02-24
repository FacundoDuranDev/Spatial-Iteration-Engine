#!/usr/bin/env python3
"""Script para probar detección con cámara real."""

import os
import sys
import time
import numpy as np
from pathlib import Path

# Configurar rutas
repo_root = Path.cwd()
sys.path.insert(0, str(repo_root / "python"))
sys.path.insert(0, str(repo_root / "cpp" / "build"))
os.environ["ONNX_MODELS_DIR"] = str(repo_root / "onnx_models" / "mediapipe")

print("=" * 70)
print("PRUEBA DE DETECCIÓN CON CÁMARA REAL")
print("=" * 70)
print()

# 1. Verificar cámara
print("1. VERIFICANDO CÁMARA")
print("-" * 70)

try:
    from ascii_stream_engine.adapters.sources import OpenCVCameraSource
    
    camera_index = 0
    print(f"Intentando abrir cámara índice {camera_index}...")
    
    source = OpenCVCameraSource(camera_index)
    source.open()
    
    print("✅ Cámara abierta correctamente")
    
    # Leer un frame
    print("Leyendo frame de la cámara...")
    frame = source.read()
    
    if frame is not None:
        print(f"✅ Frame capturado: shape={frame.shape}, dtype={frame.dtype}")
        print(f"   Valores: min={frame.min()}, max={frame.max()}, mean={frame.mean():.1f}")
    else:
        print("❌ Frame es None")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error con cámara: {e}")
    print("   Verifica que la cámara esté conectada y disponible")
    sys.exit(1)

# 2. Verificar perception_cpp
print("\n2. VERIFICANDO PERCEPTION_CPP")
print("-" * 70)

try:
    import perception_cpp
    print("✅ perception_cpp importado")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# 3. Probar detección con frame real de cámara
print("\n3. PROBANDO DETECCIÓN CON FRAME REAL DE CÁMARA")
print("-" * 70)

print("Probando detect_pose con frame de cámara...")
try:
    result = perception_cpp.detect_pose(frame)
    n_points = result.shape[0] if hasattr(result, 'shape') and len(result.shape) > 0 else 0
    print(f"  ✅ Pose: {n_points} puntos detectados")
    if n_points > 0 and n_points < 100:
        print(f"     ✅ CORRECTO: {n_points} keypoints (esperado ~17)")
        print(f"     Primeros valores: {result[:min(5, n_points)]}")
    elif n_points == 0:
        print(f"     ⚠️  Cero puntos (puede ser normal si no hay persona visible)")
    else:
        print(f"     ⚠️  Demasiados puntos ({n_points})")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nProbando detect_face con frame de cámara...")
try:
    result = perception_cpp.detect_face(frame)
    n_points = result.shape[0] if hasattr(result, 'shape') and len(result.shape) > 0 else 0
    print(f"  Face: {n_points} puntos detectados")
    if n_points > 0:
        print(f"     ✅ Detectado: {n_points} puntos")
    else:
        print(f"     ⚠️  Cero puntos (modelo puede no funcionar)")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\nProbando detect_hands con frame de cámara...")
try:
    result = perception_cpp.detect_hands(frame)
    n_points = result.shape[0] if hasattr(result, 'shape') and len(result.shape) > 0 else 0
    print(f"  Hands: {n_points} puntos detectados")
    if n_points > 0:
        print(f"     ✅ Detectado: {n_points} puntos")
    else:
        print(f"     ⚠️  Cero puntos (modelo es TFLite, no ONNX)")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 4. Probar con AnalyzerPipeline completo
print("\n4. PROBANDO CON ANALYZERPIPELINE COMPLETO")
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
    
    # Habilitar solo pose
    analyzers.set_enabled("face", False)
    analyzers.set_enabled("hands", False)
    analyzers.set_enabled("pose", True)
    
    print("Analyzers creados:")
    for analyzer in analyzers.analyzers:
        enabled = getattr(analyzer, 'enabled', True)
        print(f"  - {analyzer.name}: {'✅' if enabled else '❌'}")
    
    config = EngineConfig()
    result = analyzers.run(frame, config)
    
    print(f"\nResultados del análisis:")
    for name, data in result.items():
        if isinstance(data, dict):
            keys = list(data.keys())
            print(f"  {name}: {keys}")
            for key, value in data.items():
                if hasattr(value, 'shape'):
                    print(f"    {key}: shape={value.shape}")
                else:
                    print(f"    {key}: {type(value).__name__}")
        else:
            print(f"  {name}: {type(data).__name__}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Cerrar cámara
source.close()

print("\n" + "=" * 70)
print("RESUMEN")
print("=" * 70)
print("✅ Si pose detectó ~17 puntos, la detección funciona con cámara real")
print("⚠️  Si todos devuelven 0, verifica:")
print("   1. Que el motor esté corriendo (Start en el panel)")
print("   2. Que los analyzers estén habilitados (checkboxes en pestaña IA)")
print("   3. Que haya una persona visible en la cámara")
print("   4. Que los modelos estén en la ruta correcta")

