"""
Prueba solo la cámara: abre el dispositivo y muestra el video en una ventana.
Sirve para verificar que el índice de cámara es correcto y que el LED se enciende.

Uso: python python/ascii_stream_engine/examples/test_camera_only.py [índice]
  índice: 0 por defecto. En Linux a veces la cámara real es 2 (prueba 0, 2, 4).
Salir: pulsar 'q' en la ventana o Ctrl+C.
"""
import sys
import cv2

def main():
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"No se pudo abrir la cámara con índice {index}.")
        print("Prueba: python .../test_camera_only.py 2   (o 4 en algunos sistemas)")
        sys.exit(1)
    print(f"Cámara {index} abierta. Debería encenderse el LED. Pulsa 'q' en la ventana para salir.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error leyendo frame")
            break
        cv2.imshow("Camara (q=salir)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
    print("Listo.")

if __name__ == "__main__":
    main()
