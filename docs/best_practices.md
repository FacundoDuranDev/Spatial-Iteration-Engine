# Buenas practicas

## Configuracion
- Centralizar valores en EngineConfig.
- Validar rangos (fps, grid_w, grid_h) antes de aplicar.
- Usar presets para perfiles de calidad.

## Rendimiento
- Evitar copiar frames innecesariamente.
- Preferir operaciones vectorizadas (numpy, cv2).
- Mantener frame_buffer_size bajo para baja latencia.

## Concurrencia
- Usar locks solo donde sea necesario.
- Evitar trabajo pesado dentro del lock.
- Cortar hilos de forma segura en stop().

## Error handling
- Fallar rapido si falta dependencia critica.
- Manejar excepciones en pipelines y outputs.
- Mantener logs simples para diagnostico.

## Diseno
- Respetar limites de capas (hexagonal).
- Colocar adapters nuevos sin tocar application.
- Mantener __all__ claro para API publica.

## Seguridad y red
- Limitar broadcast cuando no se necesita.
- Definir puertos y bitrate adecuados.
- Documentar requisitos de firewall.
