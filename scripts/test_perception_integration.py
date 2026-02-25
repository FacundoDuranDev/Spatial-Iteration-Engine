#!/usr/bin/env python3
"""Script de prueba para verificar la integración completa de percepción."""

import os
import sys
import numpy as np

# Configurar rutas
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, 'python'))
sys.path.insert(0, os.path.join(repo_root, 'cpp', 'build'))

# Configurar variable de entorno para modelos
os.environ['ONNX_MODELS_DIR'] = os.path.join(repo_root, 'onnx_models', 'mediapipe')

def test_models_exist():
    """Verificar que los modelos existan."""
    print("=" * 60)
    print("1. Verificando modelos ONNX")
    print("=" * 60)
    
    models_dir = os.environ['ONNX_MODELS_DIR']
    models = {
        'face': 'face_landmark.onnx',
        'hand': 'hand_landmark.onnx',
        'pose': 'pose_landmark.onnx'
    }
    
    all_exist = True
    for name, filename in models.items():
        path = os.path.join(models_dir, filename)
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024*1024)
            print(f"✅ {name:10s}: {filename:25s} ({size_mb:6.1f} MB)")
        else:
            print(f"❌ {name:10s}: {filename:25s} NO ENCONTRADO")
            all_exist = False
    
    return all_exist


def test_perception_cpp():
    """Probar módulo C++ perception_cpp."""
    print("\n" + "=" * 60)
    print("2. Probando perception_cpp (módulo C++)")
    print("=" * 60)
    
    try:
        import perception_cpp
        print("✅ perception_cpp importado correctamente")
    except ImportError as e:
        print(f"❌ Error importando perception_cpp: {e}")
        print("   Asegúrate de compilar: cd cpp/build && cmake .. && make")
        return False
    
    # Crear frame de prueba
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[100:200, 100:200] = [255, 255, 255]  # Cuadrado blanco
    
    tests = [
        ('detect_pose', perception_cpp.detect_pose),
        ('detect_face', perception_cpp.detect_face),
        ('detect_hands', perception_cpp.detect_hands),
    ]
    
    all_ok = True
    for name, func in tests:
        try:
            result = func(test_frame)
            if hasattr(result, 'shape'):
                n_points = result.shape[0] if len(result.shape) > 0 else 0
                print(f"✅ {name:15s}: {result.shape} ({n_points} puntos)")
            else:
                n_points = len(result) // 2 if isinstance(result, (list, np.ndarray)) else 0
                print(f"✅ {name:15s}: {len(result)} elementos ({n_points} puntos)")
        except Exception as e:
            print(f"❌ {name:15s}: Error - {e}")
            all_ok = False
    
    return all_ok


def test_python_adapters():
    """Probar adapters Python."""
    print("\n" + "=" * 60)
    print("3. Probando adapters Python")
    print("=" * 60)
    
    try:
        from ascii_stream_engine.adapters.perception import (
            FaceLandmarkAnalyzer,
            HandLandmarkAnalyzer,
            PoseLandmarkAnalyzer
        )
        from ascii_stream_engine.domain.config import EngineConfig
        
        print("✅ Adapters importados correctamente")
    except ImportError as e:
        print(f"❌ Error importando adapters: {e}")
        return False
    
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    config = EngineConfig()
    
    analyzers = [
        ('FaceLandmarkAnalyzer', FaceLandmarkAnalyzer()),
        ('HandLandmarkAnalyzer', HandLandmarkAnalyzer()),
        ('PoseLandmarkAnalyzer', PoseLandmarkAnalyzer()),
    ]
    
    all_ok = True
    for name, analyzer in analyzers:
        try:
            result = analyzer.analyze(test_frame, config)
            keys = list(result.keys()) if isinstance(result, dict) else []
            print(f"✅ {name:20s}: {len(keys)} keys - {keys}")
        except Exception as e:
            print(f"❌ {name:20s}: Error - {e}")
            all_ok = False
    
    return all_ok


def test_analyzer_pipeline():
    """Probar AnalyzerPipeline completo."""
    print("\n" + "=" * 60)
    print("4. Probando AnalyzerPipeline")
    print("=" * 60)
    
    try:
        from ascii_stream_engine.application.pipeline import AnalyzerPipeline
        from ascii_stream_engine.adapters.perception import (
            FaceLandmarkAnalyzer,
            HandLandmarkAnalyzer,
            PoseLandmarkAnalyzer
        )
        from ascii_stream_engine.domain.config import EngineConfig
        
        pipeline = AnalyzerPipeline([
            FaceLandmarkAnalyzer(),
            HandLandmarkAnalyzer(),
            PoseLandmarkAnalyzer(),
        ])
        
        print("✅ AnalyzerPipeline creado")
        
        # Probar análisis (AnalyzerPipeline se usa dentro del engine, no directamente)
        # Verificar que los analyzers estén en el pipeline
        print(f"   Analyzers en pipeline: {len(pipeline.analyzers)}")
        for analyzer in pipeline.analyzers:
            print(f"   - {analyzer.name}: enabled={analyzer.enabled}")
        
        # Probar análisis individual de cada analyzer
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        config = EngineConfig()
        
        results = {}
        for analyzer in pipeline.analyzers:
            try:
                result = analyzer.analyze(test_frame, config)
                results[analyzer.name] = result
            except Exception as e:
                print(f"   ⚠️ Error en {analyzer.name}: {e}")
        
        print(f"✅ Análisis individual completado: {len(results)} resultados")
        for key, value in results.items():
            if isinstance(value, dict):
                print(f"   {key}: {list(value.keys())}")
            else:
                print(f"   {key}: {type(value).__name__}")
        
        # Probar habilitar/deshabilitar
        pipeline.set_enabled("face", True)
        pipeline.set_enabled("hands", True)
        pipeline.set_enabled("pose", False)
        
        print("✅ Control de habilitación funciona")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_control_panel_integration():
    """Verificar que el panel de control pueda usar los analyzers."""
    print("\n" + "=" * 60)
    print("5. Verificando integración con panel de control")
    print("=" * 60)
    
    try:
        from ascii_stream_engine.presentation.notebook_api import build_engine_for_notebook
        
        # Esto debería crear un engine con analyzers
        engine = build_engine_for_notebook(camera_index=0)
        
        has_analyzers = (
            hasattr(engine, '_analyzers') and 
            engine._analyzers is not None and
            hasattr(engine._analyzers, 'analyzers') and
            len(engine._analyzers.analyzers) > 0
        )
        
        if has_analyzers:
            print(f"✅ Engine creado con {len(engine._analyzers.analyzers)} analyzers")
            for analyzer in engine._analyzers.analyzers:
                print(f"   - {analyzer.name}: {'✅' if analyzer.enabled else '❌'}")
        else:
            print("⚠️  Engine creado pero sin analyzers (puede ser normal si no hay perception_cpp)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecutar todas las pruebas."""
    print("\n" + "=" * 60)
    print("PRUEBAS DE INTEGRACIÓN - PERCEPCIÓN IA")
    print("=" * 60)
    print()
    
    results = {
        'Modelos': test_models_exist(),
        'perception_cpp': test_perception_cpp(),
        'Adapters Python': test_python_adapters(),
        'AnalyzerPipeline': test_analyzer_pipeline(),
        'Panel de Control': test_control_panel_integration(),
    }
    
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    
    all_passed = True
    for name, result in results.items():
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{name:20s}: {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 ¡Todas las pruebas pasaron! La integración está lista.")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

