# UDP

## Conceptos
- Unicast: host especifico (127.0.0.1 o IP de un equipo).
- Broadcast: enviar a toda la red (255.255.255.255).
- Multicast: grupo especial (239.0.0.0/8).

## Rol en el proyecto
FFmpeg envia MPEG-TS por UDP y VLC lo recibe.

## Buenas practicas
- Usar unicast para pruebas locales.
- Broadcast solo en LAN controlada.
- Multicast si hay varios receptores.
- Definir puertos claros y documentarlos.
