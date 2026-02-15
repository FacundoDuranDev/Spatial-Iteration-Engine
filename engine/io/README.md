# engine/io

Capa de ingest/egress audiovisual basada en FFmpeg.

Objetivos:

- entrada live (cámara/video) hacia recursos accesibles por GPU,
- salida live con encode sin pasar píxeles por Python,
- timestamps y sincronización con el frame clock del runtime.

Requisito de diseño:

- el flujo de datos debe minimizar copias CPU<->GPU y evitar bloqueos.
