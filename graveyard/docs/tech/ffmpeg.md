# FFmpeg

## Rol en el proyecto
Se usa para codificar frames RGB y enviarlos por UDP como MPEG-TS.

## Arquitectura basica
Pipeline tipico:
input -> decode -> filter -> encode -> mux -> output

En este caso:
stdin (rawvideo RGB) -> encoder mpeg1video -> mpegts -> udp://

## Parametros clave
- -f rawvideo: entrada sin container.
- -pix_fmt rgb24: formato de pixel.
- -s WxH: resolucion.
- -framerate: fps de entrada.
- -c:v mpeg1video: codec.
- -b:v: bitrate.
- -f mpegts: container.
- pkt_size: tamano de paquete UDP.

## Buenas practicas
- Ajustar bitrate segun red (LAN vs WiFi).
- Mantener fps estable en el engine.
- Usar broadcast solo cuando se necesita.
