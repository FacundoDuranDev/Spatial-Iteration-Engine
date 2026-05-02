# Sony FX3 como fuente de vídeo en Linux (vía PTP + v4l2loopback)

Setup que **sí funciona** después de descartar HDMI/capturadora, y bitácora del proceso de diagnóstico.

## TL;DR — para volver a usarlo

```bash
# (Una vez) Instalar dependencias
sudo apt install -y gphoto2 libgphoto2-dev v4l2loopback-dkms v4l2loopback-utils

# (Cada arranque del PC) Crear /dev/video10 virtual
sudo modprobe v4l2loopback video_nr=10 card_label="Sony FX3" exclusive_caps=1

# (Cada sesión) Cámara en modo PC Remote
# Sony FX3:  MENU → Red → Modo conexión USB → "Toma Remota"
# IMPORTANTE: tener la cámara conectada al cargador para evitar standby USB

# (Cada sesión) Pipeline cámara → /dev/video10
gphoto2 --stdout --capture-movie | \
  ffmpeg -loglevel warning -i - -vcodec rawvideo -pix_fmt yuv420p -f v4l2 /dev/video10

# (Cada sesión) Dashboard del motor
SIE_CAMERA_INDEX=10 SIE_TOKEN=fx3 \
  /home/fissure/miniconda3/envs/spatial-iteration-engine/bin/python \
  run_dashboard_mobile_v3.py

# Acceso desde móvil
http://<IP-LAN>:7861/?t=fx3
```

Calidad esperada: **1024×576 @ ~22 FPS, formato BGR**, vía OpenCV `cv2.VideoCapture(10, cv2.CAP_V4L2)` o `'/dev/video10'`.

---

## Arquitectura del setup

```
┌──────────┐  USB-C  ┌────────────┐  stdout  ┌────────┐  v4l2  ┌──────────────┐
│ Sony FX3 │────────▶│  gphoto2   │─MJPEG───▶│ ffmpeg │───────▶│ /dev/video10 │
│ (PC Rem) │ (PTP)   │ capture-   │          │ raw    │        │ (v4l2loop)   │
│  480Mbps │         │   movie    │          │ YUV420 │        │ "Sony FX3"   │
└──────────┘         └────────────┘          └────────┘        └──────┬───────┘
                                                                     │
                                                              cv2.VideoCapture
                                                                     │
                                                                     ▼
                                                        OpenCVCameraSource
                                                              │
                                                              ▼
                                                    StreamEngine (motor SIE)
```

- **PTP** (Picture Transfer Protocol) reemplaza al HDMI completamente.
- **`gphoto2 --capture-movie`** consume el "live view" de la cámara como stream de JPEGs (lo mismo que se ve en la pantalla de la FX3).
- **`ffmpeg`** decodifica el MJPEG y escribe frames YUV420p crudos en el dispositivo virtual.
- **`v4l2loopback`** crea un `/dev/video10` que se comporta como webcam UVC normal — cualquier programa (OpenCV, OBS, ffmpeg) puede leer de ahí sin saber que la fuente real es PTP.

## Limitaciones conocidas

| Limitación | Causa | Workaround |
|------------|-------|------------|
| Resolución fija 1024×576 | Sony hardcodea preview en firmware PTP | Upscale en post si necesitas 1080p |
| ~22 FPS máx | Limitación del live view PTP | Suficiente para 30 FPS target del motor |
| Sin control de foco en tiempo real | PTP solo permite UNA conexión simultánea | Foco automático (lente en AF) o manual con anillo |
| FX3 entra en standby | Modo bajo consumo automático | **Conectar al cargador** durante uso prolongado |
| Sin USB Streaming nativo | Firmware FX3 < 2.00 | Actualizar firmware (requiere Win/Mac) |

## Comandos útiles

### Verificar estado de la FX3
```bash
# USB ID esperado: 054c:0da3 (PC Control), 480 Mbps
for d in /sys/bus/usb/devices/*/; do
  if [ -f "$d/idVendor" ] && [ "$(cat $d/idVendor)" = "054c" ]; then
    echo "$(cat $d/product) ($(cat $d/idVendor):$(cat $d/idProduct)) @ $(cat $d/speed) Mbps"
  fi
done
```

USB IDs según el modo:
- `054c:0da3` — PC Control / Toma Remota (necesario)
- `054c:0da1` — Mass Storage (cambiar en menú Red)
- `054c:0d68` — Standby (despertar la cámara)

### Capturar un solo frame de prueba
```bash
gphoto2 --capture-preview --filename=/tmp/test.jpg --force-overwrite
```

### Verificar /dev/video10 con OpenCV
```python
import cv2
cap = cv2.VideoCapture(10, cv2.CAP_V4L2)
ok, frame = cap.read()
print(f"OK={ok}, frame.shape={frame.shape if ok else None}")
cap.release()
```

### Parar todo limpiamente
```bash
pkill -f "run_dashboard_mobile_v3"
pkill -f "ffmpeg.*video10"
pkill -f "gphoto2.*capture-movie"
```

---

## Bitácora del diagnóstico (cómo llegamos aquí)

### El plan original que NO funcionó

```
Sony FX3 ─HDMI─→ Elgato Game Capture Neo ─USB─→ PC ─→ /dev/video2
```

### Cosas probadas y descartadas

| # | Probado | Resultado |
|---|---------|-----------|
| 1 | Conexión Elgato + cable USB original | USB negocia 480 Mbps (USB 2.0), no 5 Gbps esperado |
| 2 | 4 cables USB-A y USB-C distintos | Todos clavan a 480 Mbps |
| 3 | 2 puertos USB-C del T490 (Cannon Point + Thunderbolt) | Mismo resultado |
| 4 | Test con Xiaomi 12 conectado | También 480 Mbps (cable charge-only) |
| 5 | 2 unidades distintas de Elgato Game Capture Neo | Ambas reportan 720×576 negro absoluto |
| 6 | 3+ cables HDMI | Todos sin señal |
| 7 | FX3 conectada a proyector vía HDMI | ✅ Proyector ve la imagen — FX3 OK |
| 8 | FX3 con `Toma Log: Off`, `Salida RAW: Off`, `1080p`, `TC: Off`, `Picture Profile: Off` | Sigue sin señal en la Elgato |
| 9 | HD CAP USB U800 (capturadora china Ambarella) | Sin driver Linux (`Class=Vendor Specific, Driver=[none]`) |
| 10 | Solución: PTP via gphoto2 + v4l2loopback | ✅ **Funciona** |

### Hallazgos clave

1. **El micro-HDMI de la FX3 funciona** (verificado con proyector), pero la **Elgato Game Capture Neo no engancha la señal de la FX3** ni siquiera con todos los ajustes "amigables" (1080p 60p 8-bit BT.709). Sospechas no confirmadas: handshake HDMI específico, posible HDCP, o limitación del modelo Neo.

2. **Los 4 cables USB-C/USB-A probados son charge-only o solo USB 2.0** — esto se descubrió al probar el Xiaomi 12 (que sí soporta USB 3.x). Más del 90% de los cables USB-C del mercado son 2.0 internamente.

3. **El "HD CAP USB U800" no tiene driver Linux**. Se identifica como `4255:8801 GoPro Ambarella Data Streaming Gadget` — protocolo propietario. Solo funciona en Windows con software OEM. La versión "U800II" sí es UVC plug-and-play.

4. **La FX3 con firmware antiguo (<2.00) no tiene "Streaming USB"** en el menú. Solo expone Mass Storage / MTP / Toma Remota. El último (PC Remote) es el que abre la puerta a PTP.

5. **`gphoto2 --capture-movie` funciona perfectamente con la FX3** — entrega ~22 FPS de live view 1024×576 vía PTP, suficiente para el pipeline del motor.

6. **`v4l2loopback` con `exclusive_caps=1`** convierte el stream gphoto2/ffmpeg en una webcam virtual transparente al resto del sistema — **el motor SIE no necesita cambios**, abre `/dev/video10` como cualquier webcam.

### El problema del standby USB

Durante uso prolongado, la FX3 (sin cargador) entra en modo bajo consumo y cambia el USB ID a `054c:0d68 @ 12 Mbps`. gphoto2 muere con:

```
ERROR: Movie capture error... Exiting.
Movie capture finished (5489 frames)
```

**Solución**: tener la cámara conectada a su cargador durante toda la sesión. La alimentación externa evita el standby.

---

## Troubleshooting rápido

| Síntoma | Diagnóstico | Fix |
|---------|-------------|-----|
| `gphoto2 --auto-detect` no detecta la cámara | FX3 en modo wrong | MENU → Red → Modo USB → "Toma Remota" |
| USB ID = `054c:0d68` @ 12 Mbps | Cámara dormida | Pulsar botón / desconectar y reconectar USB |
| `Could not claim the USB device (busy)` | Otro proceso tiene la cámara | `pkill -f gphoto2` y reintentar |
| `/dev/video10` no existe | v4l2loopback no cargado | `sudo modprobe v4l2loopback video_nr=10 ...` |
| OpenCV `Device or resource busy` en /dev/video10 | Otro proceso ya lee el loopback | Solo UN reader simultáneo (exclusive_caps=1) |
| Pipeline gphoto2 muere tras N minutos | Cámara entró en standby | Conectar al cargador |

## Alternativas evaluadas

- **USB Streaming nativo FX3**: requiere firmware ≥2.00 (no disponible en esta cámara)
- **Sony Imaging Edge Webcam**: solo Windows/Mac
- **HDMI + Elgato**: descartado tras horas de pruebas
- **HDMI + capturadora UVC genérica MS2109** (~10€): viable si se compra; plug-and-play UVC
- **Móvil Xiaomi 12 vía DroidCam/IP Webcam**: viable como fallback rápido sin coste

## Implementación en el motor SIE

El stream de la FX3 entra al motor `ascii_stream_engine` **sin código nuevo**, vía el `OpenCVCameraSource` existente:

```python
from ascii_stream_engine.adapters.sources.camera import OpenCVCameraSource

src = OpenCVCameraSource(camera_index=10)  # /dev/video10 = FX3
src.open()
frame = src.read()  # numpy BGR (576, 1024, 3)
```

El dashboard `run_dashboard_mobile_v3.py` se controla con:

```bash
SIE_CAMERA_INDEX=10  # qué /dev/video* usar
SIE_TOKEN=fx3        # token fijo (modificación añadida)
SIE_V3_PORT=7861     # puerto HTTP
```

El token fijo se añadió en `run_dashboard_mobile_v3.py:161`:

```python
app, token, _bridge = create_app(engine, auth_token=os.environ.get("SIE_TOKEN") or None)
```

Si `SIE_TOKEN` no se pasa, se sigue generando un token aleatorio cada arranque (comportamiento por defecto previo).
