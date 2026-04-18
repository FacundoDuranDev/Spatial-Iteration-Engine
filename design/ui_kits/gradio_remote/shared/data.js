// Inventario completo de filtros — portable a cualquier variante
// Estructura: { id, name, category, params: [{id, label, kind, min, max, step, default, unit?, options?}] }

window.FILTERS = [
  // ───────── COLOR ─────────
  { id: 'color_grading', name: 'Color Grading', cat: 'COLOR', params: [
    { id: 'saturation', label: 'Saturation', kind: 'slider', min: 0, max: 2, step: 0.05, default: 1 },
    { id: 'shadow_tint', label: 'Shadow tint', kind: 'color_wheel', default: { h: 210, s: 0.3 } },
    { id: 'highlight_tint', label: 'Highlight tint', kind: 'color_wheel', default: { h: 40, s: 0.3 } },
    { id: 'r_gain', label: 'Red gain', kind: 'slider', min: 0.5, max: 2, step: 0.05, default: 1 },
    { id: 'g_gain', label: 'Green gain', kind: 'slider', min: 0.5, max: 2, step: 0.05, default: 1 },
    { id: 'b_gain', label: 'Blue gain', kind: 'slider', min: 0.5, max: 2, step: 0.05, default: 1 },
  ]},
  { id: 'film_grain', name: 'Film Grain', cat: 'COLOR', params: [
    { id: 'intensity', label: 'Intensity', kind: 'slider', min: 0, max: 0.5, step: 0.01, default: 0.15 },
    { id: 'grain_size', label: 'Grain size', kind: 'stepper', min: 1, max: 4, step: 1, default: 1 },
  ]},
  { id: 'vignette', name: 'Vignette', cat: 'COLOR', params: [
    { id: 'intensity', label: 'Intensity', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.6 },
    { id: 'inner', label: 'Inner radius', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.4 },
  ]},
  { id: 'bloom_cinema', name: 'Bloom Cinematic', cat: 'COLOR', params: [
    { id: 'intensity', label: 'Intensity', kind: 'slider', min: 0, max: 2, step: 0.05, default: 0.5 },
    { id: 'threshold', label: 'Threshold', kind: 'slider', min: 100, max: 255, step: 5, default: 200 },
    { id: 'anamorphic', label: 'Anamorphic ratio', kind: 'slider', min: 1, max: 5, step: 0.5, default: 1 },
  ]},
  { id: 'bloom', name: 'Bloom (Basic)', cat: 'COLOR', params: [
    { id: 'threshold', label: 'Threshold', kind: 'slider', min: 100, max: 255, step: 5, default: 200 },
    { id: 'intensity', label: 'Intensity', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.6 },
  ]},
  { id: 'bc', name: 'Brightness / Contrast', cat: 'COLOR', params: [] },
  { id: 'detail', name: 'Detail Boost', cat: 'COLOR', params: [
    { id: 'clahe', label: 'CLAHE clip', kind: 'slider', min: 0.5, max: 5, step: 0.5, default: 2 },
    { id: 'sharp', label: 'Sharpness', kind: 'slider', min: 0, max: 1, step: 0.1, default: 0.6 },
  ]},

  // ───────── STYLIZE ─────────
  { id: 'toon', name: 'Toon Shading', cat: 'STYLIZE', params: [] },
  { id: 'kuwahara', name: 'Kuwahara', cat: 'STYLIZE', params: [
    { id: 'radius', label: 'Radius', kind: 'stepper', min: 2, max: 8, step: 1, default: 4 },
  ]},
  { id: 'stipple', name: 'Stippling', cat: 'STYLIZE', params: [
    { id: 'density', label: 'Density', kind: 'slider', min: 0.1, max: 1, step: 0.05, default: 0.5 },
    { id: 'dmin', label: 'Min dot size', kind: 'stepper', min: 1, max: 5, step: 1, default: 1 },
    { id: 'dmax', label: 'Max dot size', kind: 'stepper', min: 2, max: 10, step: 1, default: 4 },
  ]},
  { id: 'canny', name: 'Edges (Canny)', cat: 'STYLIZE', params: [
    { id: 'lo', label: 'Low threshold', kind: 'slider', min: 20, max: 200, step: 10, default: 80 },
    { id: 'hi', label: 'High threshold', kind: 'slider', min: 50, max: 300, step: 10, default: 160 },
  ]},
  { id: 'mosaic', name: 'Mosaic', cat: 'STYLIZE', params: [] },
  { id: 'invert', name: 'Invert', cat: 'STYLIZE', params: [] },
  { id: 'edge_smooth', name: 'Edge Smooth', cat: 'STYLIZE', params: [
    { id: 'd', label: 'Diameter', kind: 'stepper', min: 3, max: 15, step: 2, default: 9 },
    { id: 's', label: 'Strength', kind: 'slider', min: 0, max: 1, step: 0.05, default: 1 },
  ]},

  // ───────── DISTORT ─────────
  { id: 'kaleido', name: 'Kaleidoscope', cat: 'DISTORT', params: [
    { id: 'segs', label: 'Segments', kind: 'stepper', min: 2, max: 16, step: 1, default: 6 },
    { id: 'rot', label: 'Rotation', kind: 'angle', min: 0, max: 6.28, default: 0, unit: 'rad' },
  ]},
  { id: 'radial_col', name: 'Radial Collapse', cat: 'DISTORT', params: [
    { id: 'strength', label: 'Strength', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.5 },
    { id: 'falloff', label: 'Falloff', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.3 },
    { id: 'mode', label: 'Mode', kind: 'select', options: ['collapse','expand'], default: 'collapse' },
  ]},
  { id: 'uv_disp', name: 'UV Displacement', cat: 'DISTORT', params: [
    { id: 'fn', label: 'Function', kind: 'select', options: ['sin','cos','spiral','noise'], default: 'sin' },
    { id: 'amp', label: 'Amplitude', kind: 'slider', min: 1, max: 30, step: 1, default: 10 },
    { id: 'freq', label: 'Frequency', kind: 'slider', min: 0.5, max: 10, step: 0.5, default: 2 },
  ]},
  { id: 'temporal_scan', name: 'TemporalScan', cat: 'DISTORT', params: [
    { id: 'buffer', label: 'Buffer size', kind: 'slider', min: 5, max: 60, step: 5, default: 30, unit: 'fr' },
    { id: 'angle', label: 'Scan angle', kind: 'angle', min: 0, max: 360, default: 0, unit: '°' },
  ]},
  { id: 'radial_blur', name: 'Radial Blur', cat: 'DISTORT', params: [
    { id: 'strength', label: 'Strength', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.3 },
    { id: 'samples', label: 'Samples', kind: 'stepper', min: 2, max: 16, step: 1, default: 6 },
  ]},
  { id: 'dof', name: 'Depth of Field', cat: 'DISTORT', params: [
    { id: 'focal', label: 'Focal point', kind: 'xypad', default: { x: 0.5, y: 0.5 } },
    { id: 'radius', label: 'Blur radius', kind: 'stepper', min: 3, max: 31, step: 2, default: 15 },
  ]},
  { id: 'motion_blur', name: 'Motion Blur', cat: 'DISTORT', params: [
    { id: 'strength', label: 'Strength', kind: 'slider', min: 0, max: 3, step: 0.1, default: 1 },
    { id: 'samples', label: 'Samples', kind: 'stepper', min: 2, max: 16, step: 1, default: 5 },
  ]},

  // ───────── GLITCH / FX ─────────
  { id: 'crt', name: 'CRT Glitch', cat: 'GLITCH', params: [
    { id: 'scan', label: 'Scanlines', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.3 },
    { id: 'ab', label: 'Aberration', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.3 },
    { id: 'noise', label: 'Noise', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.1 },
  ]},
  { id: 'chroma', name: 'Chromatic Aberration', cat: 'GLITCH', params: [
    { id: 's', label: 'Strength', kind: 'slider', min: 0, max: 10, step: 0.5, default: 3 },
  ]},
  { id: 'glitch_block', name: 'Glitch Block', cat: 'GLITCH', params: [
    { id: 'corr', label: 'Corruption', kind: 'slider', min: 0, max: 0.5, step: 0.01, default: 0.05 },
    { id: 'rgb', label: 'RGB split', kind: 'stepper', min: 0, max: 15, step: 1, default: 3 },
  ]},
  { id: 'double', name: 'Double Vision', cat: 'GLITCH', params: [
    { id: 'off', label: 'Offset', kind: 'slider', min: 0, max: 30, step: 1, default: 10 },
    { id: 'speed', label: 'Speed', kind: 'slider', min: 0.01, max: 0.3, step: 0.01, default: 0.05 },
  ]},
  { id: 'flare', name: 'Lens Flare', cat: 'GLITCH', params: [
    { id: 'pos', label: 'Position', kind: 'xypad', default: { x: 0.7, y: 0.3 } },
    { id: 'intensity', label: 'Intensity', kind: 'slider', min: 0, max: 1, step: 0.05, default: 0.5 },
    { id: 'streak', label: 'Streak length', kind: 'slider', min: 0, max: 0.8, step: 0.05, default: 0.3 },
  ]},
  { id: 'kinetic', name: 'Kinetic Typography', cat: 'GLITCH', params: [
    { id: 'text', label: 'Text', kind: 'text', default: 'MAX PAYNE' },
    { id: 'size', label: 'Font size', kind: 'slider', min: 16, max: 120, step: 4, default: 48, unit: 'px' },
  ]},
];

window.CATEGORIES = [
  { id: 'COLOR',   name: 'Color',   count: 7, stroke: 'linear-gradient(180deg,#c66,#b6371a)' },
  { id: 'STYLIZE', name: 'Stylize', count: 7, stroke: 'linear-gradient(180deg,#6a8,#2a5d4a)' },
  { id: 'DISTORT', name: 'Distort', count: 7, stroke: 'linear-gradient(180deg,#a8a,#5a3f7a)' },
  { id: 'GLITCH',  name: 'Glitch',  count: 6, stroke: 'linear-gradient(180deg,#ec8,#b57f1a)' },
  { id: 'INPUT',   name: 'Input',   count: 1, stroke: 'linear-gradient(180deg,#888,#444)' },
  { id: 'OUTPUT',  name: 'Output',  count: 1, stroke: 'linear-gradient(180deg,#666,#222)' },
];

window.PRESETS = [
  { id: 'bloom',   name: 'Bloom Cinema',   tags: ['opening','warm'],   color: '#b6371a', count: 4 },
  { id: 'noir',    name: 'Noir',           tags: ['intro','mono'],     color: '#1a1a1a', count: 3 },
  { id: 'ritual',  name: 'Ritual',         tags: ['ceremony','slow'],  color: '#5a3f7a', count: 6 },
  { id: 'glitch1', name: 'Glitch One',     tags: ['encore','fx'],      color: '#ffd400', count: 5 },
  { id: 'paper',   name: 'Paper Skin',     tags: ['calm','day'],       color: '#d9c9a8', count: 4 },
  { id: 'stage',   name: 'Stage Blackout', tags: ['transition'],       color: '#22f1d0', count: 2 },
];

window.METRICS = {
  fps: 29.4, budget: 33.3, used: 27.8, rtt: 42, resolution: '1280×720', codec: 'H.264'
};
