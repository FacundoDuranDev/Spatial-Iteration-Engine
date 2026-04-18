# ASCII Stream Viewer — UI Kit

Recreation of the product's OUTPUT surface: the VLC window receiving an ASCII render over UDP. This is what users actually see after running `stream_with_preview.py` or opening `udp://@127.0.0.1:1234` in VLC.

Open `index.html` for the interactive viewer with play/stop, charset picker, filter toggles, and the phosphor glow.

## Components
- `Viewer.jsx` — the VLC-like window chrome + stream area
- `AsciiCanvas.jsx` — procedural ASCII frame generator
- `OverlayHUD.jsx` — FPS / grid / host overlay (mimics the LandmarksOverlayRenderer HUD)
