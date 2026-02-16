"""
Diagnóstico de cámara: dispositivos /dev/video*, permisos y OpenCV.
Ejecutar: python python/ascii_stream_engine/examples/diagnose_camera.py
"""
import os
import sys
import subprocess

def main():
    print("=== 1. Dispositivos de video (Linux) ===")
    if sys.platform == "linux":
        if os.path.exists("/dev"):
            videos = [f for f in os.listdir("/dev") if f.startswith("video")]
            videos.sort(key=lambda x: (len(x), x))
            if videos:
                for v in videos:
                    path = f"/dev/{v}"
                    try:
                        st = os.stat(path)
                        mode = oct(st.st_mode)[-3:]
                        print(f"  {path}  modo={mode}")
                    except Exception as e:
                        print(f"  {path}  error: {e}")
            else:
                print("  No hay /dev/video*")
        print("\n  Comprobar grupo (deberías estar en 'video'):")
        try:
            out = subprocess.run(["groups"], capture_output=True, text=True, timeout=2)
            print("  groups:", out.stdout.strip() or out.stderr)
            if "video" not in (out.stdout or ""):
                print("  >>> Si no aparece 'video', ejecuta: sudo usermod -aG video $USER")
                print("     y cierra sesión/reinicia para que aplique.")
        except Exception as e:
            print("  ", e)
    else:
        print("  (Solo comprobación detallada en Linux)")

    print("\n=== 2. OpenCV: backends y cámaras ===")
    try:
        import cv2
        print("  cv2.__version__:", cv2.__version__)
        # Probar índices 0..5
        for i in range(6):
            cap = cv2.VideoCapture(i)
            ok = cap.isOpened()
            if ok:
                ret, frame = cap.read()
                cap.release()
                info = f"  índice {i}: ABRE" + (f", frame shape={frame.shape}" if ret and frame is not None else ", read() falló")
                print(info)
            else:
                print(f"  índice {i}: no abre")
        # Backend por defecto
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            backend = cap.getBackendName() if hasattr(cap, 'getBackendName') else "?"
            print("  Backend al abrir 0:", backend)
            cap.release()
    except Exception as e:
        print("  Error:", e)

    print("\n=== 3. Probar con backend V4L2 (Linux) ===")
    if sys.platform == "linux":
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            ok = cap.isOpened()
            print("  CAP_V4L2 índice 0:", "ABRE" if ok else "no abre")
            if ok:
                cap.release()
        except Exception as e:
            print("  ", e)

    print("\n=== Resumen ===")
    print("  - Si no hay /dev/video*: conecta la cámara o revisa el driver.")
    print("  - Si hay video* pero 'no abre': permisos (usermod -aG video $USER) o otro programa usando la cámara.")
    print("  - En WSL: la cámara suele requerir configuración extra (USB passthrough o usar Windows para probar).")

if __name__ == "__main__":
    main()
