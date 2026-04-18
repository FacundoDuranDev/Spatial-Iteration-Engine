# Análisis del Sistema - Problemas Identificados

**Fecha**: 2025-02-20  
**Problemas reportados**: FPS no se actualiza, filtros no se aplican con IA, rendimiento degradado

---

## 🔍 Análisis del Flujo del Sistema

### Flujo Completo

```
1. Cámara (OpenCVCameraSource)
   ↓
2. StreamEngine._run() [Loop principal]
   ├─ Lee cfg = self.get_config() en cada iteración (línea 460)
   ├─ Control de FPS: target = 1.0 / max(1, int(cfg.fps)) (línea 496)
   └─ time.sleep(sleep) para mantener FPS
   ↓
3. GraphScheduler.process_frame()  (el DAG que arma GraphBuilder)
   ├─ SourceNode
   ├─ AnalyzerNode(s)  (IA - perception_cpp) ⚠️ COSTOSO
   ├─ TrackerNode(s)
   ├─ TransformNode(s)
   ├─ ProcessorNode(s) (filtros de imagen)
   ├─ RendererNode     (LandmarksOverlayRenderer)
   └─ OutputNode       (NotebookPreviewSink)
```

---

## 🐛 Problemas Identificados

### 1. FPS no se actualiza desde el panel

**Causa probable**:
- El loop principal (`_run()`) lee `cfg = self.get_config()` en cada iteración (línea 460)
- Esto DEBERÍA funcionar, pero puede haber un problema de sincronización
- El control de FPS está en la línea 496: `target = 1.0 / max(1, int(cfg.fps))`

**Verificación necesaria**:
- Confirmar que `engine.update_config(fps=X)` actualiza `self._config.fps`
- Verificar que `get_config()` devuelve la configuración actualizada
- Verificar que el loop lee `cfg.fps` correctamente

**Solución propuesta**:
- Asegurar que `update_config()` actualice `self._config` correctamente
- Verificar que no haya caché de configuración en el orquestador

---

### 2. Filtros no se aplican correctamente con IA

**Análisis del flujo**:
1. Los filtros se aplican en **Fase 4: Filtrado** (línea 208 de `pipeline_orchestrator.py`)
2. El renderizado (LandmarksOverlayRenderer) ocurre en **Fase 5: Renderizado** (línea 232)
3. El overlay dibuja sobre el frame **DESPUÉS** de aplicar filtros

**Esto es CORRECTO** - Los filtros deberían aplicarse antes del overlay.

**Posibles problemas**:
- Los filtros no están activos en `filter_pipeline`
- El `LandmarksOverlayRenderer` está reemplazando el frame filtrado
- Los filtros se están aplicando pero no se ven por el overlay

**Verificación necesaria**:
- Confirmar que los filtros están en `engine.filter_pipeline.filters`
- Verificar que `filter_pipeline.has_any()` devuelve `True`
- Verificar que el frame filtrado llega al renderer

---

### 3. Rendimiento degradado (menos FPS)

**Causas probables**:

1. **Inferencia de IA (ONNX) es costosa**:
   - YOLOv8 pose inference puede tomar 50-200ms por frame
   - Esto limita el FPS máximo a ~5-20 FPS

2. **Filtros complejos**:
   - Algunos filtros (edges, blur) son costosos
   - Múltiples filtros en secuencia multiplican el tiempo

3. **Renderizado del overlay**:
   - Dibujar landmarks con OpenCV añade overhead
   - Conversión de formatos (BGR ↔ RGB) añade latencia

4. **Control de FPS no funciona**:
   - Si el FPS no se actualiza, el sistema puede estar corriendo más rápido de lo necesario
   - O puede estar bloqueado esperando frames

**Soluciones propuestas**:

1. **Procesamiento asíncrono de IA**:
   - Ejecutar inferencia en un thread separado
   - Usar el último análisis disponible mientras se procesa el siguiente

2. **Reducir FPS cuando IA está activa**:
   - Automáticamente reducir FPS objetivo cuando analyzers están activos
   - Permitir al usuario ajustar manualmente

3. **Optimizar filtros**:
   - Desactivar filtros innecesarios cuando IA está activa
   - Usar filtros más eficientes

4. **Verificar control de FPS**:
   - Asegurar que el loop principal respete el FPS configurado

---

## 📋 Plan de Testing

### Test 1: Verificar Control de FPS

```python
# 1. Obtener FPS inicial
config = engine.get_config()
initial_fps = config.fps

# 2. Cambiar FPS
engine.update_config(fps=15)

# 3. Verificar que se actualizó
config_after = engine.get_config()
assert config_after.fps == 15, "FPS no se actualizó"

# 4. Iniciar motor y medir FPS real
engine.start()
time.sleep(5)
metrics = engine.metrics.get_summary()
actual_fps = metrics.get('fps', 0)

# 5. Verificar que FPS real se acerca al objetivo
assert abs(actual_fps - 15) < 2, f"FPS real ({actual_fps}) no coincide con objetivo (15)"
```

### Test 2: Verificar Filtros con IA

```python
# 1. Activar filtro (ej: edges)
from ascii_stream_engine.adapters.processors.filters import EdgeFilter
edge_filter = EdgeFilter()
engine.filter_pipeline.replace([edge_filter])

# 2. Activar overlay de IA
from ascii_stream_engine.adapters.renderers import LandmarksOverlayRenderer
engine.set_renderer(LandmarksOverlayRenderer())

# 3. Iniciar motor
engine.start()

# 4. Verificar que:
#    - Los filtros se aplican (frame tiene edges)
#    - Los landmarks se dibujan sobre el frame filtrado
#    - Ambos son visibles en la salida
```

### Test 3: Medir Rendimiento

```python
# 1. Medir FPS sin IA
engine.update_config(fps=30)
# Desactivar analyzers
engine.analyzer_pipeline.set_enabled("pose", False)
engine.start()
time.sleep(5)
metrics_no_ia = engine.metrics.get_summary()
fps_no_ia = metrics_no_ia.get('fps', 0)

# 2. Medir FPS con IA
engine.analyzer_pipeline.set_enabled("pose", True)
time.sleep(5)
metrics_with_ia = engine.metrics.get_summary()
fps_with_ia = metrics_with_ia.get('fps', 0)

# 3. Comparar
print(f"FPS sin IA: {fps_no_ia:.2f}")
print(f"FPS con IA: {fps_with_ia:.2f}")
print(f"Diferencia: {fps_no_ia - fps_with_ia:.2f} FPS")
```

---

## 🔧 Soluciones Propuestas

### 1. Fix para Control de FPS

**Problema**: El FPS puede no actualizarse si el orquestador tiene una copia de la configuración.

**Solución**: Asegurar que `update_config()` actualice el orquestador:

```python
def update_config(self, **kwargs) -> None:
    with self._config_lock:
        # Actualizar self._config
        ...
        # Actualizar orquestador si existe
        if self._orchestrator:
            self._orchestrator.update_config(self._config)
```

### 2. Fix para Filtros con IA

**Problema**: Los filtros pueden no estar activos o no verse con el overlay.

**Solución**: Verificar que los filtros se apliquen correctamente:

```python
# En el panel de control, al aplicar filtros:
def _apply_filters():
    selected = [filters[name] for name, cb in filter_checkboxes.items() if cb.value]
    engine.filter_pipeline.replace(selected)
    # Verificar que se aplicaron
    assert engine.filter_pipeline.has_any() == (len(selected) > 0)
```

### 3. Optimización de Rendimiento

**Solución**: Procesamiento asíncrono de IA:

```python
# Ejecutar inferencia en thread separado
# Usar último análisis disponible mientras se procesa el siguiente
# Esto permite mantener FPS alto incluso con IA activa
```

---

## 📊 Métricas a Monitorear

1. **FPS real vs objetivo**: Debe estar dentro de ±2 FPS
2. **Latencia promedio**: Debe ser < 100ms para 30 FPS
3. **Tiempo de inferencia IA**: Debe ser < 50ms para mantener 20+ FPS
4. **Uso de CPU**: Monitorear si hay cuellos de botella

---

## ✅ Checklist de Verificación

- [ ] FPS se actualiza correctamente desde el panel
- [ ] Filtros se aplican antes del overlay de IA
- [ ] Overlay dibuja correctamente sobre el frame filtrado
- [ ] Rendimiento es aceptable (< 50ms latencia por frame)
- [ ] FPS real se acerca al objetivo (±2 FPS)
- [ ] No hay bloqueos o deadlocks
- [ ] El sistema se recupera de errores correctamente

