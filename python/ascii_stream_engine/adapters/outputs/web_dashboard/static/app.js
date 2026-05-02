/* ════════════════════════════════════════════════════════════════
   SIE · Web dashboard v3 — vanilla JS app
   ────────────────────────────────────────────────────────────────
   Phase B: drill-in nav (hub → cat list → detail) + widget atoms
   wired to the WS protocol (toggle_filter / set_param). Nav stack
   is non-destructive: views toggle .hidden + a 180ms enter anim.

   The REGISTRY const below is hard-embedded (mirror of
   adapters/outputs/web_dashboard/registry.py). It drives RENDERING
   only — the server snapshot remains the source of truth for
   VALUES. Keep both in sync when filters change.
   ════════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  // ────────────────────────────────────────────────────────────────
  // 1 · Registry (mirror of registry.py — labels, kinds, ranges)
  // ────────────────────────────────────────────────────────────────

  const CATEGORIES = [
    { id: "DISTORT",  name: "Distorsi\u00f3n" },
    { id: "COLOR",    name: "Color" },
    { id: "GLITCH",   name: "Glitch" },
    { id: "STYLIZE",  name: "Estilo" },
    { id: "TRACKING", name: "Tracking" },
    { id: "MOD",      name: "Mapeos" },
    { id: "PROJ",     name: "Proyecci\u00f3n" },
  ];

  // TRACKING no es una categor\u00eda real de filtros \u2014 es un panel de control
  // de los analyzers (face/hands) y del overlay de landmarks. Se renderiza
  // con un branch dedicado en renderCat.
  const TRACKING_TOGGLES = [
    { id: "face",    label: "Cara",       op: "toggle_analyzer", arg: "name" },
    { id: "hands",   label: "Manos",      op: "toggle_analyzer", arg: "name" },
    { id: "overlay", label: "Mostrar landmarks (overlay)", op: "toggle_overlay" },
  ];

  const FILTERS = [
    {
      id: "temporal_scan",
      name: "TemporalScan",
      cat: "GLITCH",
      wip: false,
      params: [
        { id: "angle",  kind: "angle",   min: 0,   max: 360, step: 1,   default: 0,        label: "\u00c1ngulo de scan" },
        { id: "buffer", kind: "stepper", min: 2,   max: 60,  step: 2,   default: 30,       label: "Buffer (frames)" },
        { id: "bands",  kind: "stepper", min: 0,   max: 60,  step: 1,   default: 0,        label: "Bandas (0=auto)" },
        { id: "curve",  kind: "select",  options: ["linear", "ease"],   default: "linear", label: "Curva" },
      ],
    },
    {
      id: "bc_cpp",
      name: "Brillo / Contraste",
      cat: "COLOR",
      wip: false,
      params: [
        { id: "brightness", kind: "slider", min: -100, max: 100, step: 5,   default: 0,   label: "Brillo" },
        { id: "contrast",   kind: "slider", min: 0.5,  max: 3.0, step: 0.1, default: 1.0, label: "Contraste" },
      ],
    },
    {
      id: "bloom",
      name: "Bloom \u00b7 audio-reactivo",
      cat: "COLOR",
      wip: false,
      params: [
        { id: "intensity",   kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.6, label: "Intensidad" },
        { id: "threshold",   kind: "slider", min: 100, max: 255, step: 5,    default: 200, label: "Umbral" },
        { id: "audio_react", kind: "slider", min: 0.0, max: 3.0, step: 0.1,  default: 1.0, label: "Reactividad audio (Bass)" },
      ],
    },
    {
      id: "chroma",
      name: "Aberraci\u00f3n crom\u00e1tica",
      cat: "GLITCH",
      wip: false,
      params: [
        { id: "strength", kind: "slider", min: 0.0, max: 15.0, step: 0.5, default: 3.0, label: "Fuerza" },
        { id: "center_x", kind: "slider", min: 0.0, max: 1.0,  step: 0.05, default: 0.5, label: "Centro X" },
        { id: "center_y", kind: "slider", min: 0.0, max: 1.0,  step: 0.05, default: 0.5, label: "Centro Y" },
        { id: "radial",   kind: "switch", default: true, label: "Radial" },
      ],
    },
    {
      id: "invert",
      name: "Invertir",
      cat: "STYLIZE",
      wip: false,
      params: [],
    },
    // ─── DISTORT extras ───────────────────────────────────────────────
    { id: "channel_swap_cpp", name: "Swap canales", cat: "DISTORT", wip: false, params: [] },
    { id: "hand_frame", name: "Marco entre manos", cat: "DISTORT", wip: false, params: [
      { id: "effect",   kind: "select", options: ["invert","blur","pixelate","edge","tint","ascii"], default: "invert", label: "Efecto" },
      { id: "strength", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 1.0, label: "Intensidad" },
      { id: "border",   kind: "stepper", min: 0, max: 10, step: 1, default: 2, label: "Borde" },
      { id: "hold",     kind: "stepper", min: 0, max: 60, step: 1, default: 15, label: "Hold (frames)" },
    ]},
    { id: "hand_warp", name: "Warp entre manos", cat: "DISTORT", wip: false, params: [
      { id: "strength",  kind: "slider", min: 0.0, max: 1000.0, step: 10.0, default: 300.0, label: "Fuerza" },
      { id: "falloff",   kind: "slider", min: 0.05, max: 1.0, step: 0.05, default: 0.35, label: "Ancho banda" },
      { id: "mode",      kind: "select", options: ["stretch","compress","twist"], default: "stretch", label: "Modo" },
      { id: "smoothing", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.3, label: "Suavizado" },
    ]},
    { id: "face_swap", name: "Intercambio de caras", cat: "DISTORT", wip: false, params: [
      { id: "feather",   kind: "slider", min: 0.0, max: 0.9, step: 0.05, default: 0.25, label: "Difuminado" },
      { id: "scale",     kind: "slider", min: 0.8, max: 1.5, step: 0.05, default: 1.05, label: "Escala" },
      { id: "smoothing", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.5,  label: "Suavizado" },
      { id: "hold",      kind: "stepper", min: 0, max: 60, step: 1, default: 8, label: "Hold (frames)" },
    ]},
    { id: "vans_face_tiles", name: "Vans (caras en damero)", cat: "DISTORT", wip: false, params: [
      { id: "cols",      kind: "stepper", min: 2, max: 24, step: 1, default: 8, label: "Columnas" },
      { id: "rows",      kind: "stepper", min: 2, max: 18, step: 1, default: 6, label: "Filas" },
      { id: "checker",   kind: "switch", default: true, label: "Damero" },
      { id: "face_pad",  kind: "slider", min: 0.0, max: 0.6, step: 0.05, default: 0.15, label: "Margen cara" },
      { id: "smoothing", kind: "slider", min: 0.0, max: 0.95, step: 0.05, default: 0.4, label: "Suavizado" },
    ]},
    { id: "face_hand_react", name: "Reactivo cara+manos", cat: "DISTORT", wip: false, params: [
      { id: "strength",    kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.6, label: "Deformación" },
      { id: "react",       kind: "slider", min: 0.0, max: 2.0, step: 0.05, default: 1.0, label: "Reactividad" },
      { id: "face_invert", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 1.0, label: "Invertir rostro" },
      { id: "smoothing",   kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.4, label: "Suavizado" },
      { id: "hold",        kind: "stepper", min: 0, max: 60, step: 1, default: 12, label: "Hold (frames)" },
    ]},
    { id: "kaleidoscope", name: "Caleidoscopio", cat: "DISTORT", wip: false, params: [
      { id: "segments", kind: "stepper", min: 2, max: 24, step: 1, default: 6, label: "Segmentos" },
      { id: "rotation", kind: "angle",   min: 0.0, max: 360.0, step: 1.0, default: 0.0, label: "Rotaci\u00f3n" },
      { id: "center_x", kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Centro X" },
      { id: "center_y", kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Centro Y" },
    ]},
    { id: "mosaic", name: "Mosaico", cat: "DISTORT", wip: false, params: [] },
    { id: "radial_collapse", name: "Colapso radial", cat: "DISTORT", wip: false, params: [
      { id: "strength", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Fuerza" },
      { id: "falloff",  kind: "slider", min: 0.05, max: 1.0, step: 0.05, default: 0.3, label: "Ca\u00edda" },
      { id: "mode",     kind: "select", options: ["collapse","expand"], default: "collapse", label: "Modo" },
      { id: "center_x", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Centro X" },
    ]},
    { id: "uv_displacement", name: "Despl. UV param.", cat: "DISTORT", wip: false, params: [
      { id: "function",    kind: "select", options: ["sin","cos","spiral","noise"], default: "sin", label: "Funci\u00f3n" },
      { id: "amplitude",   kind: "slider", min: 0.0, max: 60.0, step: 1.0, default: 10.0, label: "Amplitud" },
      { id: "frequency",   kind: "slider", min: 0.1, max: 10.0, step: 0.1, default: 2.0, label: "Frecuencia" },
      { id: "phase_speed", kind: "slider", min: 0.0, max: 0.5, step: 0.01, default: 0.05, label: "Velocidad fase" },
    ]},
    // ─── COLOR extras ─────────────────────────────────────────────────
    { id: "bloom_cinematic", name: "Bloom cinem\u00e1tico", cat: "COLOR", wip: false, params: [
      { id: "intensity",  kind: "slider", min: 0.0, max: 2.0, step: 0.05, default: 0.5, label: "Intensidad" },
      { id: "threshold",  kind: "slider", min: 100, max: 255, step: 5, default: 200, label: "Umbral" },
      { id: "anamorphic", kind: "slider", min: 1.0, max: 8.0, step: 0.5, default: 1.0, label: "Anam\u00f3rfico" },
      { id: "light_leak", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.0, label: "Light leak" },
    ]},
    { id: "brightness_cfg", name: "Brillo (config)", cat: "COLOR", wip: false, params: [] },
    { id: "color_grading", name: "Color grading", cat: "COLOR", wip: false, params: [
      { id: "saturation",         kind: "slider", min: 0.0, max: 2.0, step: 0.05, default: 1.0, label: "Saturaci\u00f3n" },
      { id: "shadow_strength",    kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.3, label: "Sombras" },
      { id: "highlight_strength", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.3, label: "Luces" },
      { id: "gain_r",             kind: "slider", min: 0.0, max: 2.0, step: 0.05, default: 1.0, label: "Gain R" },
    ]},
    { id: "grayscale_cpp", name: "Escala de grises", cat: "COLOR", wip: false, params: [] },
    { id: "infrared", name: "Infrarrojo", cat: "COLOR", wip: false, params: [
      { id: "colormap",  kind: "select", options: ["inferno","magma","plasma","viridis","jet","turbo","hot","cool","bone"], default: "inferno", label: "Paleta" },
      { id: "intensity", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 1.0, label: "Intensidad" },
      { id: "contrast",  kind: "slider", min: 0.5, max: 3.0, step: 0.1, default: 1.2, label: "Contraste" },
    ]},
    { id: "invert_py", name: "Invertir (config)", cat: "COLOR", wip: false, params: [] },
    { id: "lens_flare", name: "Lens flare", cat: "COLOR", wip: false, params: [
      { id: "intensity",     kind: "slider",  min: 0.0, max: 2.0, step: 0.05, default: 0.5, label: "Intensidad" },
      { id: "threshold",     kind: "slider",  min: 150, max: 255, step: 5, default: 240, label: "Umbral" },
      { id: "streak_length", kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.3, label: "Longitud streak" },
      { id: "ghost_count",   kind: "stepper", min: 0, max: 7, step: 1, default: 3, label: "Ghosts" },
    ]},
    { id: "vignette", name: "Vi\u00f1eta", cat: "COLOR", wip: false, params: [
      { id: "intensity",    kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.6, label: "Intensidad" },
      { id: "inner_radius", kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.4, label: "Radio interno" },
      { id: "outer_radius", kind: "slider", min: 0.1, max: 1.5, step: 0.05, default: 1.0, label: "Radio externo" },
    ]},
    // ─── GLITCH extras ────────────────────────────────────────────────
    { id: "chromatic_trails", name: "Estelas crom\u00e1ticas", cat: "GLITCH", wip: false, params: [
      { id: "r_delay", kind: "stepper", min: 0, max: 30, step: 1, default: 0, label: "Delay R" },
      { id: "g_delay", kind: "stepper", min: 0, max: 30, step: 1, default: 3, label: "Delay G" },
      { id: "b_delay", kind: "stepper", min: 0, max: 30, step: 1, default: 8, label: "Delay B" },
    ]},
    // chrono_scan + slit_scan removed — TemporalScan unifies them.
    { id: "crt_glitch", name: "CRT glitch", cat: "GLITCH", wip: false, params: [
      { id: "scanlines",  kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.3, label: "Scanlines" },
      { id: "aberration", kind: "slider", min: 0.0, max: 15.0, step: 0.5, default: 3.0, label: "Aberraci\u00f3n" },
      { id: "noise",      kind: "slider", min: 0.0, max: 0.5, step: 0.01, default: 0.05, label: "Ruido" },
      { id: "tear",       kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.1, label: "Tear prob." },
    ]},
    { id: "double_vision", name: "Doble visi\u00f3n", cat: "GLITCH", wip: false, params: [
      { id: "offset_x",    kind: "slider",  min: 0.0, max: 60.0, step: 1.0, default: 10.0, label: "Offset X" },
      { id: "offset_y",    kind: "slider",  min: 0.0, max: 60.0, step: 1.0, default: 5.0, label: "Offset Y" },
      { id: "ghost_alpha", kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.3, label: "Alpha fantasma" },
      { id: "copies",      kind: "stepper", min: 2, max: 4, step: 1, default: 2, label: "Copias" },
    ]},
    { id: "glitch_block", name: "Bloques glitch", cat: "GLITCH", wip: false, params: [
      { id: "block_size",   kind: "stepper", min: 4, max: 64, step: 2, default: 16, label: "Tama\u00f1o bloque" },
      { id: "corruption",   kind: "slider",  min: 0.0, max: 0.5, step: 0.01, default: 0.05, label: "Corrupci\u00f3n" },
      { id: "rgb_split",    kind: "stepper", min: 0, max: 30, step: 1, default: 3, label: "RGB split" },
      { id: "static_bands", kind: "stepper", min: 0, max: 10, step: 1, default: 2, label: "Bandas est\u00e1ticas" },
    ]},
    { id: "motion_blur", name: "Motion blur", cat: "GLITCH", wip: false, params: [
      { id: "strength", kind: "slider",  min: 0.0, max: 5.0, step: 0.1, default: 1.0, label: "Fuerza" },
      { id: "samples",  kind: "stepper", min: 2, max: 16, step: 1, default: 5, label: "Muestras" },
      { id: "scale",    kind: "slider",  min: 0.1, max: 5.0, step: 0.1, default: 1.0, label: "Escala flujo" },
      { id: "quality",  kind: "slider",  min: 0.25, max: 1.0, step: 0.05, default: 1.0, label: "Calidad" },
    ]},
    { id: "radial_blur", name: "Radial blur", cat: "GLITCH", wip: false, params: [
      { id: "strength", kind: "slider",  min: 0.0, max: 2.0, step: 0.05, default: 0.3, label: "Fuerza" },
      { id: "samples",  kind: "stepper", min: 2, max: 32, step: 1, default: 8, label: "Muestras" },
      { id: "falloff",  kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Ca\u00edda" },
      { id: "center_x", kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Centro X" },
    ]},
    // ─── STYLIZE extras ───────────────────────────────────────────────
    { id: "ascii", name: "ASCII", cat: "STYLIZE", wip: false, params: [
      { id: "font_size", kind: "stepper", min: 6, max: 24, step: 1, default: 10, label: "Tama\u00f1o de fuente" },
    ]},
    { id: "boids", name: "Boids", cat: "STYLIZE", wip: false, params: [
      { id: "num_boids",         kind: "stepper", min: 50, max: 600, step: 50, default: 200, label: "Agentes" },
      { id: "max_speed",         kind: "slider",  min: 1.0, max: 10.0, step: 0.5, default: 4.0, label: "Velocidad" },
      { id: "separation_radius", kind: "slider",  min: 5.0, max: 60.0, step: 1.0, default: 15.0, label: "Separaci\u00f3n" },
    ]},
    { id: "cpp_physarum", name: "Physarum (C++)", cat: "STYLIZE", wip: false, params: [
      { id: "num_agents",     kind: "stepper", min: 1000, max: 30000, step: 1000, default: 10000, label: "Agentes" },
      { id: "sensor_angle",   kind: "slider",  min: 0.05, max: 1.5, step: 0.05, default: 0.4, label: "\u00c1ngulo sensor" },
      { id: "deposit_amount", kind: "slider",  min: 0.5, max: 20.0, step: 0.5, default: 5.0, label: "Dep\u00f3sito" },
      { id: "opacity",        kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Opacidad" },
    ]},
    { id: "depth_of_field", name: "Profundidad de campo", cat: "STYLIZE", wip: false, params: [
      { id: "focal_y",          kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.5, label: "Foco vertical" },
      { id: "focal_range",      kind: "slider",  min: 0.02, max: 0.5, step: 0.02, default: 0.15, label: "Rango focal" },
      { id: "blur_radius",      kind: "stepper", min: 3, max: 51, step: 2, default: 15, label: "Radio desenfoque" },
      { id: "use_segmentation", kind: "switch",  default: false, label: "Usar segmentaci\u00f3n" },
    ]},
    { id: "detail_boost", name: "Realce de detalle", cat: "STYLIZE", wip: false, params: [
      { id: "clip_limit", kind: "slider", min: 0.5, max: 8.0, step: 0.5, default: 2.0, label: "CLAHE clip" },
      { id: "sharpness",  kind: "slider", min: 0.0, max: 2.0, step: 0.1, default: 0.6, label: "Nitidez" },
    ]},
    { id: "edges", name: "Bordes (Canny)", cat: "STYLIZE", wip: false, params: [
      { id: "low",  kind: "stepper", min: 0, max: 255, step: 5, default: 80, label: "Umbral bajo" },
      { id: "high", kind: "stepper", min: 0, max: 255, step: 5, default: 160, label: "Umbral alto" },
    ]},
    { id: "edge_smooth", name: "Suavizado de bordes", cat: "STYLIZE", wip: false, params: [
      { id: "diameter",    kind: "stepper", min: 3, max: 21, step: 2, default: 9, label: "Di\u00e1metro" },
      { id: "sigma_color", kind: "slider",  min: 10.0, max: 200.0, step: 5.0, default: 75.0, label: "Sigma color" },
      { id: "sigma_space", kind: "slider",  min: 10.0, max: 200.0, step: 5.0, default: 75.0, label: "Sigma espacio" },
      { id: "strength",    kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 1.0, label: "Mezcla" },
    ]},
    { id: "film_grain", name: "Grano de pel\u00edcula", cat: "STYLIZE", wip: false, params: [
      { id: "intensity",       kind: "slider",  min: 0.0, max: 1.0, step: 0.02, default: 0.15, label: "Intensidad" },
      { id: "grain_size",      kind: "stepper", min: 1, max: 8, step: 1, default: 1, label: "Tama\u00f1o grano" },
      { id: "color_variation", kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.1, label: "Variaci\u00f3n color" },
    ]},
    { id: "geometric_patterns", name: "Patrones geom\u00e9tricos", cat: "STYLIZE", wip: false, params: [
      { id: "pattern_mode", kind: "select", options: ["sacred_geometry","voronoi","delaunay","lissajous","strange_attractor"], default: "sacred_geometry", label: "Patr\u00f3n" },
      { id: "opacity",      kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.4, label: "Opacidad" },
      { id: "scale",        kind: "slider", min: 0.2, max: 3.0, step: 0.1, default: 1.0, label: "Escala" },
      { id: "animate",      kind: "switch", default: true, label: "Animar" },
    ]},
    { id: "kinetic_typography", name: "Tipograf\u00eda cin\u00e9tica", cat: "STYLIZE", wip: false, params: [
      { id: "font_size",       kind: "stepper", min: 12, max: 200, step: 4, default: 48, label: "Tama\u00f1o de fuente" },
      { id: "animation",       kind: "select",  options: ["scale_in","fade_in","hard_cut"], default: "scale_in", label: "Animaci\u00f3n" },
      { id: "duration_frames", kind: "stepper", min: 5, max: 240, step: 5, default: 30, label: "Duraci\u00f3n (frames)" },
      { id: "opacity",         kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.85, label: "Opacidad" },
    ]},
    { id: "kuwahara", name: "Kuwahara \u00b7 \u00f3leo", cat: "STYLIZE", wip: false, params: [
      { id: "radius", kind: "stepper", min: 2, max: 8, step: 1, default: 4, label: "Radio" },
    ]},
    { id: "optical_flow_particles", name: "Part\u00edculas (flujo)", cat: "STYLIZE", wip: false, params: [
      { id: "max_particles",     kind: "stepper", min: 200, max: 8000, step: 200, default: 2000, label: "M\u00e1x. part\u00edculas" },
      { id: "particle_lifetime", kind: "stepper", min: 5, max: 120, step: 5, default: 30, label: "Vida (frames)" },
      { id: "spawn_threshold",   kind: "slider",  min: 0.5, max: 10.0, step: 0.5, default: 2.0, label: "Umbral movimiento" },
      { id: "color_mode",        kind: "select",  options: ["flow","frame"], default: "flow", label: "Color" },
    ]},
    { id: "panel_compositor", name: "Compositor de paneles", cat: "STYLIZE", wip: false, params: [
      { id: "layout", kind: "select", options: ["1x1","2x1","1x2","2x2","3x1","1x3","3x2"], default: "2x1", label: "Disposici\u00f3n" },
    ]},
    { id: "physarum", name: "Physarum (Python)", cat: "STYLIZE", wip: false, params: [
      { id: "num_agents",     kind: "stepper", min: 500, max: 8000, step: 500, default: 4000, label: "Agentes" },
      { id: "sensor_angle",   kind: "slider",  min: 0.05, max: 1.5, step: 0.05, default: 0.4, label: "\u00c1ngulo sensor" },
      { id: "deposit_amount", kind: "slider",  min: 0.5, max: 30.0, step: 0.5, default: 10.0, label: "Dep\u00f3sito" },
      { id: "opacity",        kind: "slider",  min: 0.0, max: 1.0, step: 0.05, default: 0.7, label: "Opacidad" },
    ]},
    { id: "stippling", name: "Puntillismo", cat: "STYLIZE", wip: false, params: [
      { id: "density",      kind: "slider",  min: 0.05, max: 1.0, step: 0.05, default: 0.5, label: "Densidad" },
      { id: "min_dot_size", kind: "stepper", min: 1, max: 10, step: 1, default: 1, label: "Punto m\u00ednimo" },
      { id: "max_dot_size", kind: "stepper", min: 1, max: 12, step: 1, default: 4, label: "Punto m\u00e1ximo" },
      { id: "invert_size",  kind: "switch",  default: false, label: "Invertir tama\u00f1o" },
    ]},
    { id: "toon_shading", name: "Toon shading", cat: "STYLIZE", wip: false, params: [] },
  ];

  const FILTERS_BY_ID = {};
  FILTERS.forEach((f) => { FILTERS_BY_ID[f.id] = f; });

  const REGISTRY = { categories: CATEGORIES, filters: FILTERS, byId: FILTERS_BY_ID };

  // ────────────────────────────────────────────────────────────────
  // 2 · App state + WS client
  // ────────────────────────────────────────────────────────────────

  const PROTOCOL_VERSION = "1";
  const RECONNECT_INITIAL_MS = 250;
  const RECONNECT_MAX_MS = 4000;
  const PARAM_DEBOUNCE_MS = 50;

  const QS = new URLSearchParams(location.search);
  // Prefer the server-injected token (always present, survives reloads
  // and lost query strings). Fall back to ?t=… if a tester opens the
  // page directly.
  const TOKEN = window.SIE_TOKEN || QS.get("t") || "";

  // If we have no token at all, the served HTML must be a stale cache
  // from a build before the token-injection fix. Force a one-shot
  // cache-bust reload so the phone re-fetches `/` and gets the script
  // tag with the current token.
  if (!TOKEN && !QS.get("_cb")) {
    location.replace(location.pathname + "?_cb=" + Date.now());
    return;
  }

  const els = {
    hd:           document.getElementById("hd"),
    hdTitle:      document.getElementById("hd-title"),
    backBtn:      document.getElementById("back-btn"),
    pill:         document.getElementById("pill"),
    pillLabel:    document.getElementById("pill-label"),
    kpis:         document.getElementById("kpis"),
    fps:          document.getElementById("fps"),
    lat:          document.getElementById("lat"),
    primaryBtn:   document.getElementById("primary-btn"),
    primaryLabel: document.getElementById("primary-label"),
    clearBtn:     document.getElementById("clear-btn"),
    trackInd:     document.getElementById("track-indicator"),
    tiFace:       null,
    tiFaceN:      document.getElementById("ti-face-n"),
    tiHands:      null,
    tiHandsN:     document.getElementById("ti-hands-n"),
    body:         document.getElementById("body"),
    viewHub:      document.getElementById("view-hub"),
    viewCat:      document.getElementById("view-cat"),
    viewDetail:   document.getElementById("view-detail"),
    catList:      document.getElementById("cat-list"),
    detailBody:   document.getElementById("detail-body"),
    hubGrid:      document.getElementById("hub-grid"),
    viewModList:  document.getElementById("view-mod-list"),
    modListBody:  document.getElementById("mod-list-body"),
    viewModCreate:document.getElementById("view-mod-create"),
    modCreateBody:document.getElementById("mod-create-body"),
    viewProj:     document.getElementById("view-projection"),
    projBody:     document.getElementById("proj-body"),
  };

  const state = {
    ws: null,
    backoff: RECONNECT_INITIAL_MS,
    reconnectTimer: null,
    snapshot: { running: false, fps: 0, lat_ms: 0, filters: {}, modulations: [], signals: [] },
    navStack: [{ view: "hub" }],
    // Per-control "user is dragging right now" flag — keyed
    // "filter.param" — so server pushes don't yank the UI.
    dragging: {},
    // Per-(filter, param) debounce timers for set_param.
    paramTimers: {},
    // Wizard state — el draft que se va completando entre los 3 steps.
    // Vive aparte del navStack para que serializar el stack no cargue
    // un objeto pesado por step.
    modDraft: null,
  };

  function send(obj) {
    if (state.ws && state.ws.readyState === 1) {
      state.ws.send(JSON.stringify(obj));
    }
  }

  function debouncedSetParam(fid, pid, value) {
    const key = fid + "." + pid;
    if (state.paramTimers[key]) clearTimeout(state.paramTimers[key]);
    state.paramTimers[key] = setTimeout(() => {
      send({ op: "set_param", filter: fid, param: pid, value: value });
      state.paramTimers[key] = null;
    }, PARAM_DEBOUNCE_MS);
  }

  // ────────────────────────────────────────────────────────────────
  // 3 · Top-level chrome (header, KPIs, pill, primary btn)
  // ────────────────────────────────────────────────────────────────

  function setPill(label, mode) {
    els.pillLabel.textContent = label;
    els.pill.classList.remove("on", "warn");
    if (mode === "on") els.pill.classList.add("on");
    if (mode === "warn") els.pill.classList.add("warn");
  }

  function updateTrackIndicator(tracking) {
    if (!els.trackInd) return;
    const fEnabled = !!tracking.face_enabled;
    const hEnabled = !!tracking.hands_enabled;
    const fN = tracking.face_count || 0;
    const hN = tracking.hands_count || 0;
    const showFace  = fEnabled && fN > 0;
    const showHands = hEnabled && hN > 0;
    const anyVisible = showFace || showHands;
    els.trackInd.classList.toggle("hidden", !anyVisible);
    const faceWrap  = els.trackInd.querySelector(".ti-face");
    const handsWrap = els.trackInd.querySelector(".ti-hands");
    if (faceWrap)  faceWrap.classList.toggle("hidden", !showFace);
    if (handsWrap) handsWrap.classList.toggle("hidden", !showHands);
    if (els.tiFaceN)  els.tiFaceN.textContent  = fN;
    if (els.tiHandsN) els.tiHandsN.textContent = hN;
  }

  function activeFilterIds(snap) {
    const out = [];
    const fs = snap && snap.filters;
    if (!fs) return out;
    FILTERS.forEach((f) => {
      const s = fs[f.id];
      if (s && s.enabled) out.push(f.id);
    });
    return out;
  }

  function updateChrome(snap) {
    els.fps.textContent = (snap.fps || 0).toFixed(1);
    els.lat.textContent = (snap.lat_ms || 0).toFixed(1);
    // Mostrar "Limpiar" sólo cuando hay >=1 filtro activo — así no roba
    // espacio al primary en el caso común de "todo apagado".
    if (els.clearBtn) {
      els.clearBtn.classList.toggle("hidden", activeFilterIds(snap).length === 0);
    }
    // Indicador "lo estoy viendo" — face/hands counts en vivo. Solo visible
    // si el analyzer está encendido Y MediaPipe detecta algo. Sirve para
    // saber al toque por qué un mapping/filtro trackeado no responde.
    updateTrackIndicator(snap.tracking || {});
    if (snap.running) {
      setPill("LIVE", "on");
      els.primaryBtn.classList.remove("primary");
      els.primaryBtn.classList.add("danger");
      els.primaryLabel.textContent = "Detener";
      els.primaryBtn.querySelector(".gly").textContent = "\u25A0";
    } else {
      setPill("OFFLINE", null);
      els.primaryBtn.classList.add("primary");
      els.primaryBtn.classList.remove("danger");
      els.primaryLabel.textContent = "Iniciar";
      els.primaryBtn.querySelector(".gly").textContent = "\u25B6";
    }
    // The pill is hidden in cat / detail views (per brief).
    const cur = currentView();
    els.hd.dataset.view = cur.view;
    if (cur.view === "hub") {
      els.pill.classList.remove("hidden");
      els.kpis.classList.remove("hidden");
      els.backBtn.classList.add("hidden");
      els.hdTitle.textContent = "SIE \u00b7 Control";
    } else {
      // Hide pill + KPIs + track indicator in drill-down views —
      // back+title need the room.
      els.pill.classList.add("hidden");
      els.kpis.classList.add("hidden");
      if (els.trackInd) els.trackInd.classList.add("hidden");
      els.backBtn.classList.remove("hidden");
      if (cur.view === "cat") {
        const c = CATEGORIES.find((x) => x.id === cur.cat);
        els.hdTitle.textContent = c ? c.name : cur.cat;
      } else if (cur.view === "detail") {
        const f = FILTERS_BY_ID[cur.filter];
        els.hdTitle.textContent = f ? f.name : cur.filter;
      } else if (cur.view === "mod-list") {
        els.hdTitle.textContent = "Mapeos";
      } else if (cur.view === "mod-create") {
        els.hdTitle.textContent = "Nuevo mapeo · " + (cur.step || 1) + "/3";
      } else if (cur.view === "projection") {
        els.hdTitle.textContent = "Proyección · mapping";
      }
    }
  }

  // ────────────────────────────────────────────────────────────────
  // 4 · Nav stack (push / pop / current)
  // ────────────────────────────────────────────────────────────────

  function currentView() { return state.navStack[state.navStack.length - 1]; }

  function showView(view, animate) {
    let target = els.viewHub;
    if (view.view === "cat")        target = els.viewCat;
    if (view.view === "detail")     target = els.viewDetail;
    if (view.view === "mod-list")   target = els.viewModList;
    if (view.view === "mod-create") target = els.viewModCreate;
    if (view.view === "projection") target = els.viewProj;
    if (state.shownTarget === target && !animate) {
      // Same view as last call (e.g. server tick re-render) — don't
      // re-trigger animations or scroll-to-top, just let the per-view
      // renderer update content in place.
      return;
    }
    [
      els.viewHub, els.viewCat, els.viewDetail,
      els.viewModList, els.viewModCreate, els.viewProj,
    ].forEach((v) => v.classList.add("hidden"));
    target.classList.remove("hidden");
    target.classList.remove("enter");
    if (animate) {
      // Force reflow then add .enter for animation.
      void target.offsetWidth;
      target.classList.add("enter");
    }
    els.body.scrollTop = 0;
    state.shownTarget = target;
  }

  function pushView(view) {
    state.navStack.push(view);
    renderView(true);
  }

  function popView() {
    if (state.navStack.length <= 1) return;
    state.navStack.pop();
    renderView(true);
  }

  // ────────────────────────────────────────────────────────────────
  // 5 · Render (top-level dispatcher + per-view renderers)
  // ────────────────────────────────────────────────────────────────

  function render(snap) {
    state.snapshot = snap;
    updateChrome(snap);
    // Cheap diff so we don't rebuild the active view on every 1 Hz tick.
    const fJson = JSON.stringify(snap.filters || {});
    const cur = currentView();
    if (cur.view === "hub") {
      // Hub counts are cheap and reflect any filter change → always refresh.
      renderHub();
    } else if (fJson !== state.lastFiltersJson) {
      // Cat/detail views rebuild only when filters actually changed AND the
      // user is not mid-drag (debounce echo would otherwise yank a slider).
      const interacting = Object.keys(state.dragging).length > 0;
      if (!interacting) {
        if (cur.view === "cat")    renderCat(cur.cat);
        if (cur.view === "detail") renderDetail(cur.filter);
      }
    }
    // mod-list refresca con cualquier tick (hay un mapping nuevo, o se borró,
    // o cambió la lista). El re-render es barato con N pequeño (~10 mappings).
    if (cur.view === "mod-list") renderModList();
    // projection: solo refrescamos toggle/availability con server pushes;
    // los corners NO se reescriben mid-drag para no pelearle al usuario.
    if (cur.view === "projection") refreshProjectionState();
    state.lastFiltersJson = fJson;
  }

  function renderView(animate) {
    const cur = currentView();
    showView(cur, !!animate);
    updateChrome(state.snapshot);
    if (cur.view === "hub")        renderHub();
    if (cur.view === "cat")        renderCat(cur.cat);
    if (cur.view === "detail")     renderDetail(cur.filter);
    if (cur.view === "mod-list")   renderModList();
    if (cur.view === "mod-create") renderModCreate(cur.step || 1);
    if (cur.view === "projection") renderProjection();
  }

  // ── Hub ─────────────────────────────────────────────────────────
  // Cuántos chips de filtros activos cabemos en una tarjeta del hub
  // antes de cortar con "+N". 4 entra prolijo en una iPhone 14 a 390px.
  const HUB_CHIPS_MAX = 4;

  function renderHub() {
    const counts = {};
    const active = {};
    CATEGORIES.forEach((c) => { counts[c.id] = { active: 0, total: 0 }; active[c.id] = []; });
    FILTERS.forEach((f) => {
      if (!counts[f.cat]) return;
      counts[f.cat].total += 1;
      const snap = state.snapshot.filters && state.snapshot.filters[f.id];
      if (snap && snap.enabled) {
        counts[f.cat].active += 1;
        active[f.cat].push(f);
      }
    });
    // Tracking ocupa la 5ta tarjeta del hub: contador y chips son lo que
    // está ENCENDIDO de los analyzers + overlay, no filtros tradicionales.
    const tracking = state.snapshot.tracking || {};
    const trChips = [];
    if (tracking.face_enabled)    trChips.push({ id: "face",    label: "Cara" });
    if (tracking.hands_enabled)   trChips.push({ id: "hands",   label: "Manos" });
    if (tracking.overlay_enabled) trChips.push({ id: "overlay", label: "Overlay" });
    const trActive = trChips.length;
    // Mapeos: contador del N de modulations activas en el snapshot.
    const mods = state.snapshot.modulations || [];
    const modActive = mods.filter((m) => m.enabled !== false).length;
    // Proyección: el meta-count es ON/OFF + si el mesh está desplazado.
    const proj = state.snapshot.projection || {};
    const projOn = !!proj.enabled;
    const projWarped = projOn && !_isIdentityMesh(_projMeshFromSnap());
    document.querySelectorAll(".meta-count").forEach((el) => {
      const cat = el.dataset.cat;
      if (cat === "PROJ") {
        if (proj.available === false) {
          el.textContent = "no disponible";
          el.classList.remove("live");
        } else if (projWarped) {
          el.textContent = "encendido · calibrado";
          el.classList.add("live");
        } else if (projOn) {
          el.textContent = "encendido · sin calibrar";
          el.classList.add("live");
        } else {
          el.textContent = "apagado";
          el.classList.remove("live");
        }
        const card = el.closest(".cat");
        if (card) card.classList.toggle("has-active", projOn);
        return;
      }
      if (cat === "MOD") {
        const total = mods.length;
        el.textContent = modActive + " activo" + (modActive === 1 ? "" : "s") +
                         (total > modActive ? " / " + total + " total" : "");
        el.classList.toggle("live", modActive > 0);
        const card = el.closest(".cat");
        if (card) card.classList.toggle("has-active", modActive > 0);
        return;
      }
      if (cat === "TRACKING") {
        el.textContent = trActive + " fuente" + (trActive === 1 ? "" : "s") + " activa" + (trActive === 1 ? "" : "s");
        el.classList.toggle("live", trActive > 0);
        const card = el.closest(".cat");
        if (card) card.classList.toggle("has-active", trActive > 0);
        return;
      }
      const c = counts[cat] || { active: 0, total: 0 };
      el.textContent = c.active + " activos / " + c.total + " total";
      el.classList.toggle("live", c.active > 0);
      const card = el.closest(".cat");
      if (card) card.classList.toggle("has-active", c.active > 0);
    });
    document.querySelectorAll(".chips[data-chips]").forEach((slot) => {
      const cat = slot.dataset.chips;
      slot.innerHTML = "";
      if (cat === "TRACKING") {
        // Chips no clickables — para editar entrar a la cat por tap normal.
        trChips.forEach((t) => {
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent = t.label;
          slot.appendChild(chip);
        });
        return;
      }
      if (cat === "PROJ") {
        // Chip único describiendo el estado del warp — lo mostramos solo
        // cuando hay algo distinto a "apagado + identidad" para no ensuciar
        // el hub en el caso default.
        if (projWarped) {
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent = "warp activo";
          slot.appendChild(chip);
        } else if (projOn) {
          const chip = document.createElement("span");
          chip.className = "chip more";
          chip.textContent = "ON · identidad";
          slot.appendChild(chip);
        }
        return;
      }
      if (cat === "MOD") {
        // Mostrar las primeras 3 modulaciones activas como chips legibles
        // tipo "bloom←hands.right.y" — texto comprimido para entrar.
        const visible = mods.slice(0, 3);
        visible.forEach((m) => {
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent = _modShortLabel(m);
          if (m.enabled === false) chip.style.opacity = "0.5";
          slot.appendChild(chip);
        });
        if (mods.length > visible.length) {
          const more = document.createElement("span");
          more.className = "chip more";
          more.textContent = "+" + (mods.length - visible.length);
          slot.appendChild(more);
        }
        return;
      }
      const list = active[cat] || [];
      const visible = list.slice(0, HUB_CHIPS_MAX);
      const overflow = list.length - visible.length;
      visible.forEach((f) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.textContent = f.name;
        chip.setAttribute("aria-label", "Editar " + f.name);
        chip.addEventListener("click", (e) => {
          // El click en el chip NO debe propagar al .cat (que abriría el cat list).
          e.stopPropagation();
          pushView({ view: "detail", filter: f.id });
        });
        slot.appendChild(chip);
      });
      if (overflow > 0) {
        const more = document.createElement("button");
        more.type = "button";
        more.className = "chip more";
        more.textContent = "+" + overflow;
        more.setAttribute("aria-label", overflow + " filtros activos más");
        more.addEventListener("click", (e) => {
          e.stopPropagation();
          // Caer en el cat list normal — ahí los activos van arriba.
          pushView({ view: "cat", cat: cat });
        });
        slot.appendChild(more);
      }
    });
  }

  // ── Tracking control panel (TRACKING category) ──────────────────
  function renderTrackingCat() {
    const list = els.catList;
    list.innerHTML = "";
    const tracking = state.snapshot.tracking || {};
    TRACKING_TOGGLES.forEach((t) => {
      const row = document.createElement("div");
      row.className = "row";
      let on = false;
      if (t.id === "face")    on = !!tracking.face_enabled;
      if (t.id === "hands")   on = !!tracking.hands_enabled;
      if (t.id === "overlay") on = !!tracking.overlay_enabled;
      if (t.id === "overlay" && tracking.overlay_available === false) {
        row.classList.add("wip");
      }
      const toggle = document.createElement("button");
      toggle.className = "toggle" + (on ? " on" : "");
      toggle.type = "button";
      toggle.setAttribute("aria-label", t.label);
      bindToggle(toggle, on, (next) => {
        if (t.op === "toggle_overlay") {
          send({ op: "toggle_overlay", on: next });
        } else if (t.op === "toggle_analyzer") {
          send({ op: "toggle_analyzer", name: t.id, on: next });
        }
      });
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = t.label;
      // Sub-info: cuántas detecciones vivas hay ahora mismo.
      if (t.id === "face" && tracking.face_count > 0) {
        const sub = document.createElement("span");
        sub.className = "row-sub";
        sub.textContent = "· " + tracking.face_count + " detectada" + (tracking.face_count === 1 ? "" : "s");
        name.appendChild(sub);
      }
      if (t.id === "hands" && tracking.hands_count > 0) {
        const sub = document.createElement("span");
        sub.className = "row-sub";
        sub.textContent = "· " + tracking.hands_count;
        name.appendChild(sub);
      }
      row.appendChild(toggle);
      row.appendChild(name);
      list.appendChild(row);
    });
    // Pista de uso al pie — recordá que apagar el analyzer libera CPU,
    // mientras que apagar el overlay solo oculta los puntos.
    const hint = document.createElement("div");
    hint.className = "empty";
    hint.textContent = "Apagar un analyzer libera CPU. El overlay solo oculta los puntos sin apagar el tracking.";
    list.appendChild(hint);
  }

  // ── Modulation: list view ──────────────────────────────────────
  function renderModList() {
    const body = els.modListBody;
    body.innerHTML = "";
    const mods = state.snapshot.modulations || [];
    if (mods.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Sin mapeos. Usá + para crear el primero.";
      body.appendChild(empty);
    } else {
      mods.forEach((m, idx) => {
        const row = document.createElement("div");
        row.className = "mod-row";
        if (m.enabled === false) row.classList.add("disabled");

        const main = document.createElement("div");
        main.className = "mod-main";
        const sigEl = document.createElement("span");
        sigEl.className = "mod-sig";
        sigEl.textContent = _shortSignal(m.signal);
        const arrow = document.createElement("span");
        arrow.className = "mod-arrow";
        arrow.textContent = "→";
        const tgtEl = document.createElement("span");
        tgtEl.className = "mod-tgt";
        tgtEl.textContent = _shortFilter(m.filter_id) + " · " + m.param_id;
        main.appendChild(sigEl);
        main.appendChild(arrow);
        main.appendChild(tgtEl);

        const meta = document.createElement("div");
        meta.className = "mod-meta";
        meta.textContent = m.curve +
          " · suav " + (m.smoothing != null ? m.smoothing.toFixed(2) : "0.30") +
          " · out [" + (m.out_min != null ? m.out_min : 0) + ", " +
          (m.out_max != null ? m.out_max : 1) + "]";

        const del = document.createElement("button");
        del.type = "button";
        del.className = "mod-del";
        del.setAttribute("aria-label", "Borrar mapeo");
        del.textContent = "✕";
        del.addEventListener("click", () => {
          send({ op: "remove_modulation", idx: idx });
        });

        const left = document.createElement("div");
        left.className = "mod-row-left";
        left.appendChild(main);
        left.appendChild(meta);
        row.appendChild(left);
        row.appendChild(del);
        body.appendChild(row);
      });
    }

    // Footer del view: + nuevo / clear all
    const actions = document.createElement("div");
    actions.className = "mod-actions";
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn primary";
    addBtn.textContent = "+ Nuevo mapeo";
    addBtn.addEventListener("click", () => {
      state.modDraft = _newModDraft();
      pushView({ view: "mod-create", step: 1 });
    });
    actions.appendChild(addBtn);
    if (mods.length > 0) {
      const clearBtn = document.createElement("button");
      clearBtn.type = "button";
      clearBtn.className = "btn ghost";
      clearBtn.textContent = "Limpiar todos";
      clearBtn.addEventListener("click", () => {
        send({ op: "clear_modulations" });
      });
      actions.appendChild(clearBtn);
    }
    body.appendChild(actions);
  }

  function _newModDraft() {
    return {
      signal: null,
      filter_id: null,
      param_id: null,
      in_min: 0.0, in_max: 1.0,
      out_min: 0.0, out_max: 1.0,
      curve: "linear",
      smoothing: 0.3,
      enabled: true,
    };
  }

  // ── Modulation: create wizard (3 steps) ────────────────────────
  function renderModCreate(step) {
    const body = els.modCreateBody;
    body.innerHTML = "";
    if (state.modDraft == null) state.modDraft = _newModDraft();
    if (step === 1) renderModStep1(body);
    else if (step === 2) renderModStep2(body);
    else renderModStep3(body);
  }

  // Step 1: pick signal — chips agrupados por namespace (face / hands)
  function renderModStep1(body) {
    const intro = document.createElement("div");
    intro.className = "mod-step-intro";
    intro.textContent = "Elegí qué señal del cuerpo va a controlar el filtro.";
    body.appendChild(intro);

    const signals = state.snapshot.signals || [];
    if (signals.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No hay señales declaradas — el dashboard arrancó sin tracking?";
      body.appendChild(empty);
      return;
    }

    // Agrupar por namespace (primer segmento del dotted name).
    const groups = {};
    signals.forEach((s) => {
      const head = s.split(".")[0];
      (groups[head] = groups[head] || []).push(s);
    });
    Object.keys(groups).sort().forEach((g) => {
      const grp = document.createElement("div");
      grp.className = "sig-group";
      const cap = document.createElement("div");
      cap.className = "sig-cap";
      cap.textContent = g;
      grp.appendChild(cap);
      const wrap = document.createElement("div");
      wrap.className = "sig-chips";
      groups[g].forEach((s) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "sig-chip";
        if (state.modDraft.signal === s) chip.classList.add("on");
        chip.textContent = _shortSignal(s);
        chip.addEventListener("click", () => {
          state.modDraft.signal = s;
          renderModCreate(1);  // re-render para mostrar selección
        });
        wrap.appendChild(chip);
      });
      grp.appendChild(wrap);
      body.appendChild(grp);
    });

    const next = document.createElement("button");
    next.type = "button";
    next.className = "btn primary mod-next";
    next.textContent = "Siguiente →";
    next.disabled = !state.modDraft.signal;
    if (next.disabled) next.classList.add("disabled");
    next.addEventListener("click", () => {
      if (state.modDraft.signal) {
        state.navStack[state.navStack.length - 1].step = 2;
        renderView(false);
      }
    });
    body.appendChild(next);
  }

  // Step 2: pick filter + param — drill por categoría
  function renderModStep2(body) {
    const intro = document.createElement("div");
    intro.className = "mod-step-intro";
    intro.textContent = "Sobre " + _shortSignal(state.modDraft.signal) +
                        ": elegí qué parámetro de qué filtro va a controlar.";
    body.appendChild(intro);

    // Solo params modulables: slider, stepper, angle.
    const MODULABLE = new Set(["slider", "stepper", "angle"]);

    // Por categoría → filtros con al menos 1 param modulable.
    CATEGORIES.filter((c) => !["TRACKING", "MOD"].includes(c.id)).forEach((c) => {
      const filtersInCat = FILTERS.filter((f) =>
        f.cat === c.id && !f.wip &&
        f.params.some((p) => MODULABLE.has(p.kind))
      );
      if (filtersInCat.length === 0) return;
      const grp = document.createElement("div");
      grp.className = "sig-group";
      const cap = document.createElement("div");
      cap.className = "sig-cap";
      cap.textContent = c.name;
      grp.appendChild(cap);
      const wrap = document.createElement("div");
      wrap.className = "param-list";
      filtersInCat.forEach((f) => {
        f.params.forEach((p) => {
          if (!MODULABLE.has(p.kind)) return;
          const row = document.createElement("button");
          row.type = "button";
          row.className = "param-pick";
          if (state.modDraft.filter_id === f.id && state.modDraft.param_id === p.id) {
            row.classList.add("on");
          }
          const top = document.createElement("span");
          top.className = "param-pick-top";
          top.textContent = f.name + " · " + p.label;
          const sub = document.createElement("span");
          sub.className = "param-pick-sub";
          sub.textContent = p.kind + " [" + p.min + ", " + p.max + "]";
          row.appendChild(top);
          row.appendChild(sub);
          row.addEventListener("click", () => {
            state.modDraft.filter_id = f.id;
            state.modDraft.param_id = p.id;
            // Pre-llenar out_range con el rango natural del param.
            state.modDraft.out_min = p.min;
            state.modDraft.out_max = p.max;
            renderModCreate(2);
          });
          wrap.appendChild(row);
        });
      });
      grp.appendChild(wrap);
      body.appendChild(grp);
    });

    const next = document.createElement("button");
    next.type = "button";
    next.className = "btn primary mod-next";
    next.textContent = "Siguiente →";
    next.disabled = !(state.modDraft.filter_id && state.modDraft.param_id);
    if (next.disabled) next.classList.add("disabled");
    next.addEventListener("click", () => {
      if (state.modDraft.filter_id && state.modDraft.param_id) {
        state.navStack[state.navStack.length - 1].step = 3;
        renderView(false);
      }
    });
    body.appendChild(next);
  }

  // Step 3: ajustar rangos + curva + smoothing + crear
  function renderModStep3(body) {
    const intro = document.createElement("div");
    intro.className = "mod-step-intro";
    intro.textContent = _modLongLabel({
      signal: state.modDraft.signal,
      filter_id: state.modDraft.filter_id,
      param_id: state.modDraft.param_id,
    });
    body.appendChild(intro);

    // Curve selector
    const curveBlock = document.createElement("div");
    curveBlock.className = "param-block";
    const curveLbl = document.createElement("div");
    curveLbl.className = "lbl";
    curveLbl.textContent = "Curva";
    curveBlock.appendChild(curveLbl);
    const curveSel = document.createElement("div");
    curveSel.className = "select";
    ["linear", "ease_in_out", "ease_in", "ease_out", "invert"].forEach((c) => {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.value = c;
      b.textContent = c.replace("_", " ");
      if (state.modDraft.curve === c) b.classList.add("on");
      b.addEventListener("click", () => {
        state.modDraft.curve = c;
        renderModCreate(3);
      });
      curveSel.appendChild(b);
    });
    curveBlock.appendChild(curveSel);
    body.appendChild(curveBlock);

    // Smoothing slider [0..1]
    const smBlock = document.createElement("div");
    smBlock.className = "param-block";
    const smSlider = buildSlider({
      min: 0.0, max: 1.0, step: 0.05,
      label: "Suavizado (lag)",
    }, state.modDraft.smoothing);
    bindSlider(smSlider, state.modDraft.smoothing, 0.0, 1.0, 0.05, (v) => {
      state.modDraft.smoothing = v;
    });
    smBlock.appendChild(smSlider);
    body.appendChild(smBlock);

    // Out range — dos sliders min/max
    const outBlock = document.createElement("div");
    outBlock.className = "param-block";
    const outLbl = document.createElement("div");
    outLbl.className = "lbl";
    outLbl.textContent = "Rango de salida (sobre el parámetro)";
    outBlock.appendChild(outLbl);
    // Encontramos el rango natural del param para no dejar al usuario
    // escribir cualquier número.
    const fSpec = FILTERS_BY_ID[state.modDraft.filter_id];
    const pSpec = (fSpec && fSpec.params || []).find((p) => p.id === state.modDraft.param_id);
    const pMin = pSpec ? pSpec.min : 0.0;
    const pMax = pSpec ? pSpec.max : 1.0;
    const pStep = pSpec ? pSpec.step : 0.01;
    const outMinSlider = buildSlider({
      min: pMin, max: pMax, step: pStep, label: "Out min",
    }, state.modDraft.out_min);
    bindSlider(outMinSlider, state.modDraft.out_min, pMin, pMax, pStep, (v) => {
      state.modDraft.out_min = v;
    });
    outBlock.appendChild(outMinSlider);
    const outMaxSlider = buildSlider({
      min: pMin, max: pMax, step: pStep, label: "Out max",
    }, state.modDraft.out_max);
    bindSlider(outMaxSlider, state.modDraft.out_max, pMin, pMax, pStep, (v) => {
      state.modDraft.out_max = v;
    });
    outBlock.appendChild(outMaxSlider);
    body.appendChild(outBlock);

    // Confirm
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "btn primary mod-next";
    confirm.textContent = "Crear mapeo";
    confirm.addEventListener("click", () => {
      send({
        op: "add_modulation",
        signal: state.modDraft.signal,
        filter: state.modDraft.filter_id,
        param: state.modDraft.param_id,
        in_min: state.modDraft.in_min,
        in_max: state.modDraft.in_max,
        out_min: state.modDraft.out_min,
        out_max: state.modDraft.out_max,
        curve: state.modDraft.curve,
        smoothing: state.modDraft.smoothing,
        enabled: true,
      });
      state.modDraft = null;
      // Pop el wizard y caer en mod-list (que ahora muestra el nuevo).
      // Nuestro nav stack tras step3 es: hub > mod-list > mod-create. Pop dos.
      popView();
    });
    body.appendChild(confirm);
  }

  // ── Projection mapping ─────────────────────────────────────────
  // Throttle de WS dispatch en ms — 50ms = 20Hz, smooth en mobile sin
  // saturar. El último valor del drag se manda igual en pointerup.
  const PROJ_DISPATCH_MS = 50;
  // Densidades cuadradas soportadas por el backend (espejado de
  // SUPPORTED_MESH_SIZES en projection_mapping_renderer.py).
  const PROJ_MESH_SIZES = [2, 3, 5, 9];

  function _identityMesh(rows, cols) {
    const out = [];
    for (let i = 0; i < rows; i++) {
      const row = [];
      for (let j = 0; j < cols; j++) {
        row.push([rows > 1 ? j / (cols - 1) : 0, rows > 1 ? i / (rows - 1) : 0]);
      }
      out.push(row);
    }
    return out;
  }

  function _isIdentityMesh(mesh) {
    if (!mesh || !mesh.length) return true;
    const rows = mesh.length, cols = mesh[0].length;
    const ident = _identityMesh(rows, cols);
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        if (Math.abs(mesh[i][j][0] - ident[i][j][0]) > 1e-3) return false;
        if (Math.abs(mesh[i][j][1] - ident[i][j][1]) > 1e-3) return false;
      }
    }
    return true;
  }

  // Compat: clientes viejos pueden seguir consultando los 4 corners.
  function _isIdentityCorners(corners) {
    return _isIdentityMesh([
      [corners[0], corners[1]],
      [corners[3], corners[2]],
    ]);
  }

  function _projMeshFromSnap() {
    const proj = state.snapshot.projection || {};
    const mp = proj.mesh_points;
    const ms = proj.mesh_size;
    if (Array.isArray(mp) && Array.isArray(ms) && ms.length === 2) {
      // Deep copy para no mutar el snapshot al draggear.
      return mp.map((row) => row.map((p) => [Number(p[0]) || 0, Number(p[1]) || 0]));
    }
    // Fallback: sin snapshot todavía → 2x2 identidad.
    return _identityMesh(2, 2);
  }

  function renderProjection() {
    const body = els.projBody;
    body.innerHTML = "";
    const proj = state.snapshot.projection || {};
    const available = proj.available !== false;
    const meshSize = Array.isArray(proj.mesh_size) ? proj.mesh_size : [2, 2];
    const supported = Array.isArray(proj.supported_sizes) && proj.supported_sizes.length
      ? proj.supported_sizes : PROJ_MESH_SIZES;

    // ── Toggle row (Activar warp) ─────────────────────────────────
    const togRow = document.createElement("div");
    togRow.className = "row proj-toggle-row";
    const togBtn = document.createElement("button");
    togBtn.type = "button";
    togBtn.className = "toggle" + (proj.enabled ? " on" : "");
    togBtn.setAttribute("aria-label", "Activar projection mapping");
    bindToggle(togBtn, !!proj.enabled, (on) => {
      send({ op: "toggle_projection", on: on });
    });
    const togLbl = document.createElement("span");
    togLbl.className = "name";
    togLbl.textContent = available ? "Activar warp" : "Renderer no disponible";
    togRow.appendChild(togBtn);
    togRow.appendChild(togLbl);
    body.appendChild(togRow);

    if (!available) {
      const hint = document.createElement("div");
      hint.className = "empty";
      hint.textContent = "El renderer activo no incluye ProjectionMappingRenderer. Reiniciá el dashboard con la stack v3.";
      body.appendChild(hint);
      return;
    }

    // ── Density picker (2x2 / 3x3 / 5x5 / 9x9) ────────────────────
    // Cambiar densidad borra calibración previa — avisar antes de
    // cambiar SI hay un mesh ya tocado.
    const densRow = document.createElement("div");
    densRow.className = "proj-density-row";
    const densLbl = document.createElement("span");
    densLbl.className = "proj-density-label";
    densLbl.textContent = "Densidad del mesh";
    densRow.appendChild(densLbl);
    const densBtns = document.createElement("div");
    densBtns.className = "proj-density-btns";
    supported.forEach((n) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "proj-density-btn" + (n === meshSize[0] ? " on" : "");
      btn.textContent = n + "x" + n;
      btn.setAttribute("aria-label", "Densidad " + n + " por " + n);
      btn.addEventListener("click", () => {
        if (n === meshSize[0] && n === meshSize[1]) return;
        const dirty = !_isIdentityMesh(_projMeshFromSnap());
        if (dirty && !window.confirm(
          "Cambiar la densidad del mesh borra los corners actuales. ¿Seguir?"
        )) return;
        send({ op: "set_projection_mesh_size", rows: n, cols: n });
      });
      densBtns.appendChild(btn);
    });
    densRow.appendChild(densBtns);
    body.appendChild(densRow);

    // ── Calibration canvas (16:9) ─────────────────────────────────
    const wrap = document.createElement("div");
    wrap.className = "proj-canvas-wrap";
    const VBW = 100;
    const VBH = 56.25;  // 16:9
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + VBW + " " + VBH);
    svg.setAttribute("class", "proj-svg");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    wrap.appendChild(svg);
    body.appendChild(wrap);

    // Inicializar mesh local si no estamos draggeando.
    if (!state.projDrag) {
      state.projMesh = _projMeshFromSnap();
    }

    // Grid de tercios — referencia visual.
    const grid = document.createElementNS("http://www.w3.org/2000/svg", "g");
    grid.setAttribute("class", "proj-grid");
    [0.25, 0.5, 0.75].forEach((t) => {
      const lh = document.createElementNS("http://www.w3.org/2000/svg", "line");
      lh.setAttribute("x1", "0"); lh.setAttribute("y1", String(t * VBH));
      lh.setAttribute("x2", String(VBW)); lh.setAttribute("y2", String(t * VBH));
      grid.appendChild(lh);
      const lv = document.createElementNS("http://www.w3.org/2000/svg", "line");
      lv.setAttribute("x1", String(t * VBW)); lv.setAttribute("y1", "0");
      lv.setAttribute("x2", String(t * VBW)); lv.setAttribute("y2", String(VBH));
      grid.appendChild(lv);
    });
    svg.appendChild(grid);

    // Source rect (sin warp, para referencia).
    const ghost = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    ghost.setAttribute("x", "0"); ghost.setAttribute("y", "0");
    ghost.setAttribute("width", String(VBW)); ghost.setAttribute("height", String(VBH));
    ghost.setAttribute("class", "proj-ghost");
    svg.appendChild(ghost);

    // Mesh edges: lineas horizontales + verticales conectando los puntos.
    // Una <g> con muchas <line>; las refrescamos por modificación de attrs.
    const meshEdges = document.createElementNS("http://www.w3.org/2000/svg", "g");
    meshEdges.setAttribute("class", "proj-mesh-edges");
    svg.appendChild(meshEdges);

    // Handles — un <g> por punto del mesh. Más densidad = handles más chicos
    // visualmente pero el hit area se mantiene grande.
    const [rows, cols] = [state.projMesh.length, state.projMesh[0].length];
    const handleEls = [];
    for (let i = 0; i < rows; i++) {
      const handleRow = [];
      for (let j = 0; j < cols; j++) {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "proj-handle");
        g.setAttribute("data-row", String(i));
        g.setAttribute("data-col", String(j));
        const hit = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        hit.setAttribute("class", "proj-handle-hit");
        // Hit area constante r=6 → 48+ CSS px sin importar la densidad.
        hit.setAttribute("r", "6");
        g.appendChild(hit);
        const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        dot.setAttribute("class", "proj-handle-dot");
        // Dot visible más chico cuando hay más puntos para no taparse.
        dot.setAttribute("r", String(rows >= 5 ? 1.2 : 2));
        g.appendChild(dot);
        // Label solo para los corners — más puntos saturarían visualmente.
        const isCorner = (i === 0 || i === rows - 1) && (j === 0 || j === cols - 1);
        if (isCorner && rows === 2 && cols === 2) {
          const lbl = document.createElementNS("http://www.w3.org/2000/svg", "text");
          lbl.setAttribute("class", "proj-handle-label");
          lbl.setAttribute("dy", "-3.5");
          lbl.setAttribute("text-anchor", "middle");
          const labels = [["TL", "TR"], ["BL", "BR"]];
          lbl.textContent = labels[i][j];
          g.appendChild(lbl);
        }
        svg.appendChild(g);
        handleRow.push(g);
        _attachProjPointer(g, i, j, svg, VBW, VBH);
      }
      handleEls.push(handleRow);
    }

    // Pintar la posición inicial.
    _paintProjMesh(meshEdges, handleEls, state.projMesh, VBW, VBH);

    state.projUI = { svg, meshEdges, handleEls, vbw: VBW, vbh: VBH, rows, cols };

    // ── Action row (Reset + Encoger) ──────────────────────────────
    const actions = document.createElement("div");
    actions.className = "proj-actions";

    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.className = "btn ghost";
    resetBtn.textContent = "Reset";
    resetBtn.addEventListener("click", () => {
      send({ op: "reset_projection" });
    });
    actions.appendChild(resetBtn);

    const centerBtn = document.createElement("button");
    centerBtn.type = "button";
    centerBtn.className = "btn ghost";
    centerBtn.textContent = "Encoger 10%";
    centerBtn.setAttribute("aria-label", "Encoger los puntos del mesh 10% hacia el centro — quick test del warp");
    centerBtn.addEventListener("click", () => {
      // Encogemos PROPORCIONALMENTE todos los puntos del mesh hacia (0.5, 0.5).
      // En 2x2 esto coincide con set_projection_corners; para mesh denso es
      // un test rápido de que el warp se aplica end-to-end.
      const ident = _identityMesh(rows, cols);
      const points = ident.map((row) =>
        row.map(([x, y]) => [
          0.5 + (x - 0.5) * 0.8,
          0.5 + (y - 0.5) * 0.8,
        ])
      );
      send({ op: "set_projection_mesh_points", points: points });
    });
    actions.appendChild(centerBtn);

    body.appendChild(actions);

    // ── Hint ──────────────────────────────────────────────────────
    const hint = document.createElement("div");
    hint.className = "empty proj-hint";
    if (rows === 2 && cols === 2) {
      hint.innerHTML = "Arrastr&aacute; cada <b>esquina</b> hasta hacer encajar la imagen sobre la superficie f&iacute;sica del proyector. " +
                       "Si la superficie no es plana, sub&iacute; la densidad del mesh.";
    } else {
      hint.innerHTML = "Arrastr&aacute; los <b>" + (rows * cols) +
                       " puntos del mesh</b> para ajustar el warp por celdas. " +
                       "Densidad alta = m&aacute;s control pero LUT m&aacute;s caro de recalcular.";
    }
    body.appendChild(hint);
  }

  function refreshProjectionState() {
    // Re-renderizamos solo si NO estamos draggeando — si el usuario está
    // tocando un punto, el snapshot del server lo va a echo back y no
    // queremos que la UI le pelee a su propio drag.
    if (state.projDrag) return;
    const proj = state.snapshot.projection || {};
    if (proj.available === false) {
      renderProjection();
      return;
    }
    // Si cambió la densidad del mesh (otro cliente, o auto-load al boot),
    // hay que reconstruir el SVG entero — ya no caben los mismos handles.
    const ui = state.projUI;
    const newSize = Array.isArray(proj.mesh_size) ? proj.mesh_size : null;
    if (ui && newSize && (ui.rows !== newSize[0] || ui.cols !== newSize[1])) {
      renderProjection();
      return;
    }
    // Refrescar el toggle (otro cliente puede haberlo flippeado).
    const togBtn = els.projBody.querySelector(".proj-toggle-row .toggle");
    if (togBtn) {
      const wasOn = togBtn.classList.contains("on");
      const isOn = !!proj.enabled;
      if (wasOn !== isOn) togBtn.classList.toggle("on", isOn);
    }
    // Refrescar el mesh pintado (cambió desde el server, ej. otra sesión
    // hizo reset). Sin reconstruir el SVG.
    if (ui) {
      state.projMesh = _projMeshFromSnap();
      _paintProjMesh(ui.meshEdges, ui.handleEls, state.projMesh, ui.vbw, ui.vbh);
    }
  }

  function _paintProjMesh(edgesGroup, handleEls, mesh, vbw, vbh) {
    const rows = mesh.length, cols = mesh[0].length;
    // Repintar handles — translate transform por punto.
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols; j++) {
        const [nx, ny] = mesh[i][j];
        handleEls[i][j].setAttribute(
          "transform", "translate(" + (nx * vbw) + " " + (ny * vbh) + ")"
        );
      }
    }
    // Reconstruir las líneas del mesh — N líneas horizontales (cols-1 segm
    // por fila) y M líneas verticales (rows-1 segm por col). En 2x2 son
    // 4 segmentos = el quad clásico.
    edgesGroup.innerHTML = "";
    function line(x1, y1, x2, y2) {
      const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
      ln.setAttribute("x1", String(x1)); ln.setAttribute("y1", String(y1));
      ln.setAttribute("x2", String(x2)); ln.setAttribute("y2", String(y2));
      ln.setAttribute("class", "proj-mesh-edge");
      edgesGroup.appendChild(ln);
    }
    for (let i = 0; i < rows; i++) {
      for (let j = 0; j < cols - 1; j++) {
        const a = mesh[i][j], b = mesh[i][j + 1];
        line(a[0] * vbw, a[1] * vbh, b[0] * vbw, b[1] * vbh);
      }
    }
    for (let j = 0; j < cols; j++) {
      for (let i = 0; i < rows - 1; i++) {
        const a = mesh[i][j], b = mesh[i + 1][j];
        line(a[0] * vbw, a[1] * vbh, b[0] * vbw, b[1] * vbh);
      }
    }
  }

  function _attachProjPointer(handleEl, row, col, svg, vbw, vbh) {
    // Pointer events + setPointerCapture: drag fluido en mobile y desktop
    // con un solo path. Throttle a 20Hz para no saturar el WS.
    let throttleTimer = null;
    let pendingX = null, pendingY = null;

    function flush() {
      if (pendingX === null) return;
      send({
        op: "set_projection_mesh_point",
        row: row, col: col,
        x: pendingX, y: pendingY,
      });
      pendingX = pendingY = null;
    }

    function pointToNorm(ev) {
      const rect = svg.getBoundingClientRect();
      const sx = ((ev.clientX - rect.left) / rect.width) * vbw;
      const sy = ((ev.clientY - rect.top) / rect.height) * vbh;
      let nx = sx / vbw, ny = sy / vbh;
      if (nx < 0) nx = 0; else if (nx > 1) nx = 1;
      if (ny < 0) ny = 0; else if (ny > 1) ny = 1;
      return [nx, ny];
    }

    function isMine() {
      return state.projDrag &&
        state.projDrag.row === row && state.projDrag.col === col;
    }

    handleEl.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      handleEl.setPointerCapture(ev.pointerId);
      handleEl.classList.add("dragging");
      state.projDrag = { row: row, col: col };
    });

    handleEl.addEventListener("pointermove", (ev) => {
      if (!isMine()) return;
      ev.preventDefault();
      const [nx, ny] = pointToNorm(ev);
      state.projMesh[row][col] = [nx, ny];
      const ui = state.projUI;
      if (ui) _paintProjMesh(ui.meshEdges, ui.handleEls, state.projMesh, ui.vbw, ui.vbh);
      pendingX = nx; pendingY = ny;
      if (!throttleTimer) {
        throttleTimer = setTimeout(() => {
          throttleTimer = null;
          flush();
        }, PROJ_DISPATCH_MS);
      }
    });

    function endDrag(ev) {
      if (!isMine()) return;
      try { handleEl.releasePointerCapture(ev.pointerId); } catch (_) {}
      handleEl.classList.remove("dragging");
      if (throttleTimer) { clearTimeout(throttleTimer); throttleTimer = null; }
      flush();
      state.projDrag = null;
    }

    handleEl.addEventListener("pointerup", endDrag);
    handleEl.addEventListener("pointercancel", endDrag);
  }

  // ── Cat list ────────────────────────────────────────────────────
  function renderCat(catId) {
    if (catId === "TRACKING") return renderTrackingCat();
    const list = els.catList;
    list.innerHTML = "";
    // Activos primero — para que el VJ vea de un saque qué corre y pueda
    // editar sin scrollear entre 12 inactivos. WIP siempre al final.
    const filters = FILTERS.filter((f) => f.cat === catId).slice().sort((a, b) => {
      const sa = (state.snapshot.filters && state.snapshot.filters[a.id]) || {};
      const sb = (state.snapshot.filters && state.snapshot.filters[b.id]) || {};
      const ra = (a.wip ? 2 : 0) + (sa.enabled ? 0 : 1);
      const rb = (b.wip ? 2 : 0) + (sb.enabled ? 0 : 1);
      if (ra !== rb) return ra - rb;
      return 0;  // mantener orden estable original dentro de cada bucket
    });
    if (filters.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Sin filtros en esta categor\u00eda.";
      list.appendChild(empty);
      return;
    }
    filters.forEach((f) => {
      const snap = (state.snapshot.filters && state.snapshot.filters[f.id]) || { enabled: false };
      const row = document.createElement("div");
      row.className = "row" + (snap.enabled ? " expanded" : "") + (f.wip ? " wip" : "");
      row.dataset.filter = f.id;

      const toggle = document.createElement("button");
      toggle.className = "toggle" + (snap.enabled ? " on" : "");
      toggle.type = "button";
      toggle.setAttribute("aria-label", "Activar " + f.name);
      bindToggle(toggle, !!snap.enabled, (on) => {
        if (f.wip) return;
        send({ op: "toggle_filter", filter: f.id, on: on });
      });

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = f.name;

      if (f.wip) {
        const badge = document.createElement("span");
        badge.className = "badge-wip";
        badge.textContent = "WIP";
        name.appendChild(badge);
      }

      const chev = document.createElement("span");
      chev.className = "chev";
      chev.textContent = "\u203a";
      if (!f.wip) {
        chev.addEventListener("click", () => pushView({ view: "detail", filter: f.id }));
      }

      row.appendChild(toggle);
      row.appendChild(name);
      row.appendChild(chev);
      list.appendChild(row);
    });
  }

  // ── Detail ──────────────────────────────────────────────────────
  function renderDetail(fid) {
    const f = FILTERS_BY_ID[fid];
    const detail = els.detailBody;
    detail.innerHTML = "";
    if (!f) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Filtro desconocido.";
      detail.appendChild(empty);
      return;
    }

    const head = document.createElement("div");
    head.className = "head";
    const ttl = document.createElement("h2");
    ttl.className = "ttl";
    ttl.textContent = f.name;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = f.cat;
    head.appendChild(ttl);
    head.appendChild(meta);
    detail.appendChild(head);

    // Enable/disable row at the top of detail.
    const snap = (state.snapshot.filters && state.snapshot.filters[f.id]) || { enabled: false, params: {} };
    const enableBlock = document.createElement("div");
    enableBlock.className = "param-block";
    const enableRow = document.createElement("div");
    enableRow.className = "param-row";
    const enableLbl = document.createElement("span");
    enableLbl.className = "lbl";
    enableLbl.textContent = "Activo";
    const enableTgl = document.createElement("button");
    enableTgl.className = "toggle" + (snap.enabled ? " on" : "");
    enableTgl.type = "button";
    bindToggle(enableTgl, !!snap.enabled, (on) => {
      send({ op: "toggle_filter", filter: f.id, on: on });
    });
    enableRow.appendChild(enableLbl);
    enableRow.appendChild(enableTgl);
    enableBlock.appendChild(enableRow);
    detail.appendChild(enableBlock);

    if (f.params.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Sin par\u00e1metros.";
      detail.appendChild(empty);
      return;
    }

    const params = document.createElement("div");
    params.className = "params";
    const modulatedPids = new Set(snap.modulated_params || []);
    // Lookup signal modulando este param (para el badge).
    const modBySigForFilter = {};
    (state.snapshot.modulations || []).forEach((m) => {
      if (m.filter_id === f.id) {
        modBySigForFilter[m.param_id] = m.signal;
      }
    });
    f.params.forEach((p) => {
      const value = (snap.params && snap.params[p.id] !== undefined) ? snap.params[p.id] : p.default;
      const block = buildParamBlock(f.id, p, value);
      if (block && modulatedPids.has(p.id)) {
        block.classList.add("param-modulated");
        const badge = document.createElement("div");
        badge.className = "param-mod-badge";
        badge.textContent = "🔗 " + _shortSignal(modBySigForFilter[p.id] || "");
        block.insertBefore(badge, block.firstChild);
      }
      if (block) params.appendChild(block);
    });
    detail.appendChild(params);
  }

  // ────────────────────────────────────────────────────────────────
  // 6 · Param block builder (one per kind)
  // ────────────────────────────────────────────────────────────────

  function buildParamBlock(fid, p, value) {
    const block = document.createElement("div");
    block.className = "param-block";
    block.dataset.param = p.id;

    if (p.kind === "slider" || p.kind === "stepper" && false) {
      // (stepper handled below — kept slider explicit for clarity)
    }

    if (p.kind === "slider") {
      const el = buildSlider(p, value);
      bindSlider(el, value, p.min, p.max, p.step, (v, dragging) => {
        state.dragging[fid + "." + p.id] = dragging;
        debouncedSetParam(fid, p.id, v);
      });
      block.appendChild(el);
      return block;
    }

    if (p.kind === "angle") {
      // Label row + dial centred below.
      const top = document.createElement("div");
      top.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      top.appendChild(lbl);
      block.appendChild(top);

      const el = buildDial(value);
      bindDial(el, value, (v, dragging) => {
        state.dragging[fid + "." + p.id] = dragging;
        debouncedSetParam(fid, p.id, v);
      });
      block.appendChild(el);
      return block;
    }

    if (p.kind === "stepper") {
      const row = document.createElement("div");
      row.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      const el = buildStepper(value);
      bindStepper(el, value, p.min, p.max, p.step, (v) => {
        // Stepper fires immediately (taps, no drag).
        send({ op: "set_param", filter: fid, param: p.id, value: v });
      });
      row.appendChild(lbl);
      row.appendChild(el);
      block.appendChild(row);
      return block;
    }

    if (p.kind === "select") {
      const top = document.createElement("div");
      top.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      top.appendChild(lbl);
      block.appendChild(top);

      const el = buildSelect(p.options || [], value);
      bindSelect(el, value, p.options || [], (v) => {
        send({ op: "set_param", filter: fid, param: p.id, value: v });
      });
      block.appendChild(el);
      return block;
    }

    if (p.kind === "switch") {
      const row = document.createElement("div");
      row.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      const tgl = document.createElement("button");
      tgl.className = "toggle" + (value ? " on" : "");
      tgl.type = "button";
      bindToggle(tgl, !!value, (on) => {
        send({ op: "set_param", filter: fid, param: p.id, value: on });
      });
      row.appendChild(lbl);
      row.appendChild(tgl);
      block.appendChild(row);
      return block;
    }

    return null;
  }

  // ────────────────────────────────────────────────────────────────
  // 7 · Atom builders (DOM construction, no event wiring)
  // ────────────────────────────────────────────────────────────────

  function buildSlider(p, value) {
    const el = document.createElement("div");
    el.className = "slider";
    el.innerHTML =
      '<div class="top">' +
        '<span class="lbl"></span>' +
        '<span class="val"></span>' +
      '</div>' +
      '<div class="track-wrap">' +
        '<div class="track">' +
          '<div class="fill"></div>' +
          '<div class="pin"></div>' +
        '</div>' +
      '</div>' +
      '<div class="range"><span class="min"></span><span class="max"></span></div>';
    el.querySelector(".lbl").textContent = p.label;
    el.querySelector(".min").textContent = formatNum(p.min, p.step);
    el.querySelector(".max").textContent = formatNum(p.max, p.step);
    return el;
  }

  function buildDial(value) {
    const el = document.createElement("div");
    el.className = "dial";
    el.innerHTML =
      '<div class="face">' +
        '<div class="needle"></div>' +
        '<div class="cap"></div>' +
      '</div>' +
      '<div class="read"></div>';
    return el;
  }

  function buildStepper(value) {
    const el = document.createElement("div");
    el.className = "stepper";
    el.innerHTML =
      '<button type="button" data-act="dec">\u2212</button>' +
      '<span class="v"></span>' +
      '<button type="button" data-act="inc">+</button>';
    return el;
  }

  function buildSelect(options, value) {
    const el = document.createElement("div");
    el.className = "select";
    options.forEach((opt) => {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.value = opt;
      b.textContent = String(opt);
      el.appendChild(b);
    });
    return el;
  }

  // ────────────────────────────────────────────────────────────────
  // 8 · Atom binders (state + interaction)
  // ────────────────────────────────────────────────────────────────

  function bindToggle(el, on, onChange) {
    el.classList.toggle("on", !!on);
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const next = !el.classList.contains("on");
      el.classList.toggle("on", next);
      onChange(next);
    });
  }

  function bindSlider(el, value, min, max, step, onChange) {
    const track = el.querySelector(".track");
    const fill  = el.querySelector(".fill");
    const pin   = el.querySelector(".pin");
    const valEl = el.querySelector(".val");
    const wrap  = el.querySelector(".track-wrap");

    function paint(v) {
      const pct = (max === min) ? 0 : (v - min) / (max - min);
      const clamped = Math.max(0, Math.min(1, pct));
      fill.style.width = (clamped * 100) + "%";
      pin.style.left  = (clamped * 100) + "%";
      valEl.textContent = formatNum(v, step);
    }

    paint(value);
    el._setValue = paint;

    let dragging = false;

    function valueAtClientX(clientX) {
      const r = track.getBoundingClientRect();
      const t = (clientX - r.left) / Math.max(1, r.width);
      const raw = min + Math.max(0, Math.min(1, t)) * (max - min);
      return snapToStep(raw, min, step);
    }

    function down(e) {
      e.preventDefault();
      dragging = true;
      try { wrap.setPointerCapture(e.pointerId); } catch (_) {}
      const v = valueAtClientX(e.clientX);
      paint(v);
      onChange(v, true);
    }
    function move(e) {
      if (!dragging) return;
      const v = valueAtClientX(e.clientX);
      paint(v);
      onChange(v, true);
    }
    function up(e) {
      if (!dragging) return;
      dragging = false;
      try { wrap.releasePointerCapture(e.pointerId); } catch (_) {}
      const v = valueAtClientX(e.clientX);
      paint(v);
      onChange(v, false);
    }

    wrap.addEventListener("pointerdown", down);
    wrap.addEventListener("pointermove", move);
    wrap.addEventListener("pointerup", up);
    wrap.addEventListener("pointercancel", up);
  }

  function bindDial(el, value, onChange) {
    const face   = el.querySelector(".face");
    const needle = el.querySelector(".needle");
    const read   = el.querySelector(".read");

    function paint(v) {
      const deg = ((v % 360) + 360) % 360;
      needle.style.transform = "translate(-50%, -100%) rotate(" + deg + "deg)";
      read.textContent = deg.toFixed(0) + "\u00b0";
    }
    paint(value);
    el._setValue = paint;

    let dragging = false;
    function angleFromEvent(e) {
      const r = face.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      // 0° at top, increase clockwise.
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      let deg = Math.atan2(dx, -dy) * 180 / Math.PI;
      if (deg < 0) deg += 360;
      return Math.round(deg);
    }

    function down(e) {
      e.preventDefault();
      dragging = true;
      try { face.setPointerCapture(e.pointerId); } catch (_) {}
      const v = angleFromEvent(e);
      paint(v);
      onChange(v, true);
    }
    function move(e) {
      if (!dragging) return;
      const v = angleFromEvent(e);
      paint(v);
      onChange(v, true);
    }
    function up(e) {
      if (!dragging) return;
      dragging = false;
      try { face.releasePointerCapture(e.pointerId); } catch (_) {}
      const v = angleFromEvent(e);
      paint(v);
      onChange(v, false);
    }

    face.addEventListener("pointerdown", down);
    face.addEventListener("pointermove", move);
    face.addEventListener("pointerup", up);
    face.addEventListener("pointercancel", up);
  }

  function bindStepper(el, value, min, max, step, onChange) {
    const vEl = el.querySelector(".v");
    let cur = value;

    function paint(v) {
      cur = v;
      vEl.textContent = formatNum(v, step);
    }
    paint(value);
    el._setValue = paint;

    el.querySelector('[data-act="dec"]').addEventListener("click", (e) => {
      e.preventDefault();
      const next = Math.max(min, snapToStep(cur - step, min, step));
      paint(next);
      onChange(next);
    });
    el.querySelector('[data-act="inc"]').addEventListener("click", (e) => {
      e.preventDefault();
      const next = Math.min(max, snapToStep(cur + step, min, step));
      paint(next);
      onChange(next);
    });
  }

  function bindSelect(el, value, options, onChange) {
    function paint(v) {
      el.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("on", b.dataset.value === String(v));
      });
    }
    paint(value);
    el._setValue = paint;

    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", (e) => {
        e.preventDefault();
        const v = b.dataset.value;
        paint(v);
        onChange(v);
      });
    });
  }

  // ────────────────────────────────────────────────────────────────
  // 9 · Helpers
  // ────────────────────────────────────────────────────────────────

  function snapToStep(v, min, step) {
    if (!step) return v;
    const n = Math.round((v - min) / step);
    const out = min + n * step;
    // Avoid float drift like 0.30000000000000004.
    const decimals = (String(step).split(".")[1] || "").length;
    return decimals > 0 ? Number(out.toFixed(decimals)) : out;
  }

  function formatNum(v, step) {
    if (typeof v !== "number") return String(v);
    const decimals = (String(step || 1).split(".")[1] || "").length;
    return decimals > 0 ? v.toFixed(decimals) : String(Math.round(v));
  }

  // ── Modulation helpers ──────────────────────────────────────────
  function _shortSignal(name) {
    // hands.right.palm.y → mano-D.y · face.center.x → cara.x
    if (!name) return "?";
    const parts = name.split(".");
    if (parts[0] === "hands" && parts.length >= 4) {
      const side = parts[1] === "left" ? "I" : "D";
      const axis = parts[parts.length - 1];
      return "mano-" + side + "." + axis;
    }
    if (parts[0] === "face" && parts.length >= 3) {
      return "cara." + parts.slice(2).join(".");
    }
    if (parts[0] === "hands" && parts[1] === "distance") return "manos-dist";
    return name;
  }

  function _shortFilter(fid) {
    const f = FILTERS_BY_ID[fid];
    return f ? f.name : fid;
  }

  function _modShortLabel(m) {
    return _shortFilter(m.filter_id) + "←" + _shortSignal(m.signal);
  }

  function _modLongLabel(m) {
    const fname = _shortFilter(m.filter_id);
    return _shortSignal(m.signal) + " → " + fname + " · " + m.param_id;
  }

  // ────────────────────────────────────────────────────────────────
  // 10 · WS connect + reconnect
  // ────────────────────────────────────────────────────────────────

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = proto + "//" + location.host + "/ws?t=" + encodeURIComponent(TOKEN) + "&v=" + PROTOCOL_VERSION;
    setPill("CONECTANDO", "warn");
    const ws = new WebSocket(url);
    state.ws = ws;

    ws.addEventListener("open", () => {
      state.backoff = RECONNECT_INITIAL_MS;
    });

    ws.addEventListener("message", (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (_) { return; }
      if (msg.type === "state") render(msg);
      else if (msg.type === "ping") send({ op: "pong" });
      else if (msg.type === "error") console.warn("[ws]", msg);
    });

    ws.addEventListener("close", (ev) => {
      if (ev.code === 4401) {
        setPill("AUTH", "warn");
        return;
      }
      setPill("RECONECT", "warn");
      state.reconnectTimer = setTimeout(connect, state.backoff);
      state.backoff = Math.min(state.backoff * 2, RECONNECT_MAX_MS);
    });

    ws.addEventListener("error", () => {
      try { ws.close(); } catch (_) {}
    });
  }

  // ────────────────────────────────────────────────────────────────
  // 11 · Bind static UI (header back, primary btn, hub cards)
  // ────────────────────────────────────────────────────────────────

  function bindUI() {
    els.primaryBtn.addEventListener("click", (e) => {
      e.preventDefault();
      send({ op: state.snapshot.running ? "stop" : "start" });
    });

    if (els.clearBtn) {
      els.clearBtn.addEventListener("click", (e) => {
        e.preventDefault();
        send({ op: "clear_filters" });
      });
    }

    els.backBtn.addEventListener("click", (e) => {
      e.preventDefault();
      popView();
    });

    document.querySelectorAll(".cat").forEach((card) => {
      card.addEventListener("click", () => {
        const cat = card.dataset.cat;
        // MOD y PROJ tienen vistas propias, no la lista de cat genérica.
        if (cat === "MOD") {
          pushView({ view: "mod-list" });
        } else if (cat === "PROJ") {
          pushView({ view: "projection" });
        } else {
          pushView({ view: "cat", cat: cat });
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindUI();
    renderView();
    connect();
  });
})();
