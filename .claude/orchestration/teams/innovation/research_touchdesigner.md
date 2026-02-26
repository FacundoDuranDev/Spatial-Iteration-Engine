# TouchDesigner Research: Patterns and Repos for Spatial-Iteration-Engine

**Date:** 2026-02-25
**Purpose:** Catalog TouchDesigner open-source projects, architecture patterns, and techniques
that could inspire improvements for the Spatial-Iteration-Engine real-time audiovisual pipeline.

---

## Table of Contents

1. [GitHub Repositories by Category](#1-github-repositories-by-category)
2. [Architecture Patterns (TOP/CHOP/SOP Data Flow)](#2-architecture-patterns)
3. [Specific Techniques Worth Porting](#3-specific-techniques-worth-porting)
4. [Community Resources and Key Artists](#4-community-resources)
5. [Actionable Recommendations for SIE](#5-actionable-recommendations-for-sie)

---

## 1. GitHub Repositories by Category

### 1.1 Computer Vision Integration

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [torinmb/mediapipe-touchdesigner](https://github.com/torinmb/mediapipe-touchdesigner) | ~2,100 | GPU-accelerated MediaPipe plugin. Face, hand, pose tracking via embedded Chromium browser hosting MediaPipe vision tasks. DAT outputs per task, TOP output with overlays. | **Multi-task vision output schema**: Each vision task (face, hand, pose, object) outputs to its own structured data table (DAT) plus a composited overlay image (TOP). SIE already has separate analyzers, but could adopt a unified overlay compositor that merges all perception results into a single debug frame. |
| [patrickhartono/TDYolo](https://github.com/patrickhartono/TDYolo) | ~50 | YOLOv11 object detection plugin. Real-time bounding boxes + class labels. CUDA/MPS/CPU fallback. Dynamic class filtering, top-N detection with confidence sorting. ~50 FPS on Apple M4. | **Dynamic class filtering at runtime**: UI-configurable object type selection and top-N detection limiting. SIE perception analyzers currently detect everything -- we could add runtime class filters to reduce wasted computation. Also, the multi-GPU enumeration and automatic fallback (CUDA -> MPS -> CPU) is a pattern SIE should replicate. |
| [olegchomp/TDDepthAnything](https://github.com/olegchomp/TDDepthAnything) | ~120 | Depth Anything V2 monocular depth estimation in TouchDesigner via TensorRT. Thread Manager integration for async inference. | **Monocular depth as perception stage**: Depth maps from a single camera open up 3D-aware effects (fog, parallax, selective blur by depth). SIE could add a DepthAnalyzer using ONNX Runtime with Depth Anything V2 weights. The async thread pattern for heavy inference is also applicable. |
| [cronin4392/TouchDesigner-OpenCV-OSC](https://github.com/cronin4392/TouchDesigner-OpenCV-OSC) | ~40 | Sends raw OpenCV data to TouchDesigner over OSC. Runs CV in external Python, bridges via UDP. | **External process CV bridge**: When perception is too heavy for the main loop, offload to an external process and receive results via OSC/UDP. SIE could use this pattern for expensive models that exceed the 33ms frame budget. |

### 1.2 Real-Time Video Effects and GLSL Shaders

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [ogrew/TD-PostEffectShader](https://github.com/ogrew/TD-PostEffectShader) | ~90 | 25+ post-processing GLSL shaders: bloom, gaussian blur, radial blur, RGB split, chromatic aberration, mosaic, posterize, halftone, pixel art, vignette, sobel edge, kuwahara, kaleidoscope, water ripple, distortion, dot screen, frosted glass, barrel distortion, sharpen, scroll, waver. MIT licensed. | **GLSL shader library as filter adapters**: Each shader is self-contained with clearly defined uniforms. SIE could port these as C++ filter adapters (via OpenGL compute or as numpy-based fallbacks). Priority targets: bloom, chromatic aberration, halftone, kaleidoscope, pixel art, kuwahara (artistic oil-paint effect). |
| [kamindustries/touchFluid](https://github.com/kamindustries/touchFluid) | ~223 | 2D Semi-Lagrangian fluid solver in GLSL. Vorticity confinement, temperature, buoyancy, obstacle support. Both .toe and .tox formats. | **GPU fluid simulation as filter**: The GLSL fragment shaders (advection, divergence, pressure solve, vorticity) are portable. SIE could implement a FluidFilter that uses the camera input as a velocity/density source, creating reactive fluid overlays. The shader files are directly extractable. |
| [satoruhiga/TouchDesigner-ShaderBuilder](https://github.com/satoruhiga/TouchDesigner-ShaderBuilder) | ~125 | On-the-fly GLSL shader editing with PBR support. Hot-reload shader code while running. | **Hot-reload shader pipeline**: A development-time feature where filter GLSL code can be edited and reloaded without restarting the engine. SIE could implement a file-watcher on shader source files that triggers recompilation. |
| [raganmd/BOS-in-TouchDesigner](https://github.com/raganmd/BOS-in-TouchDesigner) | ~181 | Port of "The Book of Shaders" to TouchDesigner. Educational shader examples covering noise, fractals, patterns, color theory. | **Shader recipe book**: Each chapter is a standalone shader technique. Particularly useful: Perlin/Simplex noise, Voronoi, fractal Brownian motion, color blending modes. These are building blocks for generative filters in SIE. |
| [raganmd/learningGLSL](https://github.com/raganmd/learningGLSL) | ~142 | GLSL learning examples organized by concept. Covers vertex and fragment shaders, uniforms, textures. | **GLSL reference implementations**: Clean, well-documented shader code for common operations. Useful as reference when implementing SIE's shader-based filters. |
| [marcinbiegun/isf-touchdesigner](https://github.com/marcinbiegun/isf-touchdesigner) | ~30 | Parses ISF (Interactive Shader Format) files and converts to TouchDesigner GLSL. Works with 90% of shaders from interactiveshaderformat.com. | **ISF shader compatibility layer**: ISF is a standardized shader format with 200+ generators and filters at isf.video. SIE could implement an ISF parser to instantly gain access to this entire shader library. ISF defines inputs, outputs, and parameters in JSON metadata alongside GLSL. |

### 1.3 Audio-Reactive Visuals

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [JonathanDCohen/TDAudioAnalysis](https://github.com/JonathanDCohen/TDAudioAnalysis) | ~30 | Reusable components for sound-reactive visuals. FFT analysis, frequency band isolation, beat detection, envelope following. | **Audio analysis as CHOP-style channel data**: Decomposes audio into frequency bands (bass/mid/high), extracts envelope, detects beats. SIE could add an AudioAnalyzer that produces normalized channel data (0-1 floats) for bass_energy, mid_energy, high_energy, beat_detected, bpm_estimate. These channels then modulate filter parameters. |
| [struct78/aurora](https://github.com/struct78/aurora) | ~20 | Audio reactive visualization. Breaks audio into mids/highs/lows via filter operators, maps to 3D geometry and color. | **Three-band frequency mapping**: Simple but effective pattern of splitting audio into three bands and mapping each to a different visual parameter (e.g., bass -> scale, mid -> rotation, high -> color shift). Directly applicable to SIE's filter parameter modulation. |
| [LucieMrc/TD_audioreact_love_EN](https://github.com/LucieMrc/TD_audioreact_love_EN) | ~15 | Tutorial: generative audio-reactive visuals. Uses noise TOP driven by audio spectrum. | **Audio-driven noise parameters**: Uses audio amplitude to modulate noise generator parameters (frequency, amplitude, offset), creating visuals that breathe with music. SIE could expose filter parameters as "modulatable" and allow audio channels to drive them. |
| [edap/visualsTemplateTouchDesignerOF](https://github.com/edap/visualsTemplateTouchDesignerOF) | ~25 | Template linking TouchDesigner audio analysis to openFrameworks rendering via OSC. | **OSC bridge for audio data**: Separates audio analysis from visual rendering. SIE could receive audio analysis data via OSC from external tools (Ableton, SuperCollider, PureData) rather than implementing audio capture itself. |

### 1.4 Particle Systems, Fluid Simulations, Reaction-Diffusion

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [kamindustries/touchFluid](https://github.com/kamindustries/touchFluid) | ~223 | (See above) 2D fluid solver with GLSL shaders. | Advection, divergence, pressure Jacobi iteration shaders are directly portable. |
| [guidoschmidt/sketchbook.touchdesigner](https://github.com/guidoschmidt/Touchdesigner.Experiments) | ~15 | Reaction-diffusion implementation as .toe file. Uses feedback loop with two-chemical Gray-Scott model. | **Reaction-diffusion as feedback filter**: The pattern is: read previous frame -> apply diffusion kernel -> apply reaction equations -> write new frame. In SIE, this becomes a stateful filter that maintains a buffer between frames. Key parameters: feed rate, kill rate, diffusion rates for chemicals A and B. |
| [DBraun/TouchDesigner_Shared](https://github.com/DBraun/TouchDesigner_Shared) | ~961 | Collection of 50+ toxes: Physarum (slime mold), boids/flocking with GLSL compute, optical flow particles, curl noise 4D, jump flood algorithm, dither effects. | **Physarum simulation**: Agent-based slime mold simulation on GPU. Each pixel-agent senses, rotates, deposits, and diffuses. Creates organic trail patterns. SIE could implement this as a generative filter. **Boids flocking**: Uses spatial binning + GLSL compute for N-body flocking. **Curl noise**: 4D curl noise for smooth, divergence-free particle motion. All three are high-value generative effects. |
| [wes10645/TouchDesigner-Blob-Rendering-](https://github.com/wes10645/TouchDesigner-Blob-Rendering-) | ~5 | Procedural blob rendering with noise-driven deformation and chromatic edge processing. | **Noise-driven mesh deformation**: Uses layered noise to deform geometry, then applies edge-detection-based chromatic effects. The noise deformation shader is extractable. |

### 1.5 Projection Mapping and Depth Camera

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [stosumarte/FreenectTD](https://github.com/stosumarte/FreenectTD) | ~10 | Kinect support for TouchDesigner on Mac via libfreenect/libfreenect2. Outputs RGB, depth maps, point clouds, IR streams. | **Multi-stream depth camera adapter**: A single source that produces multiple synchronized streams (RGB + depth + IR). SIE's FrameSource protocol could be extended to optionally provide depth alongside BGR frames. |
| [ElPepe101/Kinect-TouchDesigner-point-cloud](https://github.com/ElPepe101/Kinect-TouchDesigner-point-cloud) | ~15 | Kinect point cloud visualization. Ceiling-mounted scanning + silhouette projection. | **Point cloud from depth**: Converting depth maps to 3D point clouds for visualization. SIE could add a PointCloudRenderer. |

### 1.6 Network Streaming

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [Theoriz/Web2NDI_SyphonSpout_TouchDesigner](https://github.com/Theoriz/Web2NDI_SyphonSpout_TouchDesigner) | ~20 | Outputs web pages to Syphon/Spout/NDI. Multi-protocol output from a single source. | **Multi-protocol output sink**: SIE could implement NDI and Spout output sinks so frames can be consumed by VJ software (Resolume, MadMapper, OBS). NDI is particularly valuable for network streaming. |
| [TouchDesigner/WebRTC-Remote-Panel-Web-Demo](https://github.com/TouchDesigner/WebRTC-Remote-Panel-Web-Demo) | ~30 | Official React app receiving WebRTC video from TouchDesigner with bidirectional mouse/keyboard events. | **WebRTC output + remote control**: SIE could stream processed frames via WebRTC to any browser, with the browser sending control events back. This would replace/complement the Jupyter notebook UI with a web dashboard. |

### 1.7 OSC/MIDI Integration

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [michintosh/TD-Open-Stage-Control](https://github.com/michintosh/TD-Open-Stage-Control) | ~15 | OSC communication between TouchDesigner and Open Stage Control for live performance. | **OSC parameter control**: Expose all engine parameters via OSC so external controllers (tablets, phones, hardware) can adjust filters, perception thresholds, and rendering in real-time. |
| [ejfox/hand-midi-controller](https://github.com/ejfox/hand-midi-controller) | ~25 | Hand tracking -> MIDI controller. MediaPipe hand landmarks mapped to MIDI CC values. | **Perception-to-control bridge**: Use hand/pose detection results to generate control signals (MIDI/OSC). SIE's perception output could drive parameter changes -- e.g., hand openness controls blur amount. |
| [saimgulay/TouchDesigner-AdvancedAudioOscillatorCHOP](https://github.com/saimgulay/TouchDesigner-AdvancedAudioOscillatorCHOP) | ~10 | Multi-channel oscillator with waveform mixing, BLEP, wavetable synthesis. MIDI and OSC input. | **Oscillator-based parameter modulation**: LFOs and oscillators that modulate visual parameters on a timeline. SIE could add a ParameterModulator that generates sine/saw/square waves to animate filter parameters automatically. |

### 1.8 AI / Generative Art Integration

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [olegchomp/TouchDiffusion](https://github.com/olegchomp/TouchDiffusion) | ~260 | Real-time Stable Diffusion via StreamDiffusion in TouchDesigner. Text-to-image, image-to-image, video-to-video. | **Real-time diffusion as transformation stage**: StreamDiffusion achieves 10-50x speedup over standard diffusion. SIE could integrate StreamDiffusion as a TransformationFilter that transforms frames in real-time using text prompts. Requires GPU with 8GB+ VRAM. |
| [olegchomp/TDComfyUI](https://github.com/olegchomp/TDComfyUI) | ~236 | TouchDesigner interface for ComfyUI. Connects TD to ComfyUI's node-based AI workflow engine. | **External AI workflow bridge**: Rather than embedding AI models, connect to ComfyUI as an external service. SIE could implement a ComfyUIAdapter that sends frames to ComfyUI and receives processed results, keeping the main pipeline lightweight. |
| [motius/remote-stream-diffusion-td](https://github.com/motius/remote-stream-diffusion-td) | ~15 | StreamDiffusion on remote machine, piped into local TD session. | **Remote GPU inference**: Offload heavy AI processing to a separate machine. SIE could implement a RemoteInferenceAdapter that sends frames to a GPU server and receives results, enabling real-time AI effects even on modest hardware. |

### 1.9 Python Bridges and Tools

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [IntentDev/touchpy](https://github.com/IntentDev/touchpy) | ~50 | High-performance Python toolset using Vulkan, CUDA, and TouchEngine. GPU-to-GPU zero-copy data transfers between Python and TouchDesigner. | **Zero-copy GPU data transfer**: Uses Vulkan interop and CUDA to move texture data between processes without CPU roundtrip. SIE's pybind11 bridge currently copies numpy arrays. We could investigate CUDA array interface or DLPack for zero-copy GPU tensor sharing between Python and C++. |
| [8beeeaaat/touchdesigner-mcp](https://github.com/8beeeaaat/touchdesigner-mcp) | ~50 | MCP (Model Context Protocol) server for TouchDesigner. AI agents can interact with TD via WebServer DAT. | **AI agent control interface**: An LLM-accessible API for controlling the engine. SIE could expose an MCP server that lets AI assistants inspect pipeline state, adjust parameters, and trigger actions. |
| [function-store/FunctionStore_tools](https://github.com/function-store/FunctionStore_tools) | ~100 | Workflow tools: operator templates, parameter promotion, UI customization, search palette, borderless mode. | **Workflow acceleration patterns**: Operator templates with preferred defaults, quick parameter promotion to parent component. SIE could implement filter presets and quick parameter binding. |

### 1.10 Raymarching and SDF

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [t3kt/raytk](https://github.com/t3kt/raytk) | ~333 | Raymarching shader toolkit. Constructs raymarching shaders from node networks. SDF primitives, boolean operations, domain repetition, materials, lighting. | **SDF-based 3D rendering without meshes**: Signed Distance Functions enable complex 3D scenes rendered entirely in fragment shaders. SIE could add a RaymarchRenderer that renders SDF scenes composited onto camera frames -- useful for AR-style overlays. Key operations: sphere/box/torus SDFs, smooth union/intersection, domain repetition. |
| [yeataro/TD-Raymarching-System](https://github.com/yeataro/TD-Raymarching-System) | ~30 | Object-based raymarching integrating with existing TD render pipeline. | **Compositable SDF rendering**: Integrates raymarched elements into a standard render pipeline rather than replacing it. SIE could composite SDF renders on top of camera frames. |

### 1.11 Lighting and Live Performance

| Repository | Stars | What It Does | Extractable Pattern |
|---|---|---|---|
| [EnviralDesign/GeoPix](https://github.com/EnviralDesign/GeoPix) | ~150 | Full open-source lighting control and pre-visualization. Maps video content onto LED strips, DMX lights, video surfaces. MIT licensed. | **Multi-output mapping**: A single visual pipeline maps to multiple heterogeneous outputs (LED strips, projectors, screens) with per-output spatial transformation. SIE could implement a MappingOutputSink that transforms rendered frames to match physical display geometries. |
| [maxbecq/ricolivetd](https://github.com/maxbecq/ricolivetd) | ~10 | Lightweight Ableton Live <-> TouchDesigner bridge via UDP/OSC. | **DAW sync**: Synchronize visual parameters with music production software timeline. SIE could receive beat/bar/transport data from Ableton to drive time-synced visual changes. |

---

## 2. Architecture Patterns

### 2.1 TouchDesigner's Operator Family System

TouchDesigner organizes all processing into six operator families, each handling a specific data domain:

| Family | Color | Data Type | SIE Equivalent |
|---|---|---|---|
| **TOP** (Texture Operator) | Blue-purple | 2D textures/images on GPU | Filters, Renderers |
| **CHOP** (Channel Operator) | Green | Numeric channels/signals (audio, control data, motion) | No direct equivalent -- this is a gap |
| **SOP** (Surface Operator) | Light blue | 3D geometry (points, polygons, NURBS, particles) | No direct equivalent |
| **DAT** (Data Operator) | Purple | Tables, text, scripts, JSON | Config, analysis dicts |
| **MAT** (Material Operator) | Yellow | Shaders/materials for 3D rendering | No direct equivalent |
| **COMP** (Component Operator) | Gray | Containers, panels, UI, 3D scenes | Presentation layer |

**Key insight**: Operators within the same family wire together directly. Cross-family data conversion requires explicit bridge operators (CHOP-to-TOP, SOP-to-CHOP, etc.).

### 2.2 Data Flow Model -- What SIE Can Learn

1. **Everything is numeric**: Geometry = lists of XYZ positions, audio = signal samples, images = pixel values. Different families are just different views of numeric data. TD makes conversion between views explicit.

2. **Pull-based evaluation**: Operators only cook (evaluate) when their output is requested downstream. This is lazy evaluation. SIE currently uses push-based (source pushes frames through pipeline). A hybrid model could skip stages when their output is not needed (e.g., skip perception if no filter uses analysis data).

3. **Parallel operator families**: TOPs run on GPU, CHOPs run on CPU, SOPs can use GPU compute. They execute in parallel when independent. SIE could separate GPU work (filters) from CPU work (perception, tracking) into parallel execution paths.

4. **Feedback loops are first-class**: The Feedback TOP captures the previous frame's output and feeds it back as input. This enables accumulation effects, trails, reaction-diffusion, etc. SIE currently has no feedback mechanism -- frames are processed and discarded. Adding a FrameHistory buffer that filters can read from would enable an entire class of temporal effects.

5. **Parameter exposure and animation**: Every operator parameter can be promoted to a parent component, bound to a CHOP channel, or driven by a Python expression. This makes everything modulatable. SIE's filter parameters are currently static per-configuration. A modulation system where parameters can be driven by audio, time, or perception data would be transformative.

### 2.3 The CHOP Gap in SIE

TouchDesigner's most unique contribution is **CHOPs** -- a dedicated signal processing layer. CHOPs handle:
- Audio input/output and FFT analysis
- MIDI/OSC input mapping
- Math operations on channels (filter, lag, limit, math, trigger)
- LFO generation (sine, noise, ramp)
- Envelope detection
- Logic operations (boolean, threshold, gate)

SIE has no equivalent. Adding a **ChannelBus** -- a system of named numeric channels (0.0-1.0 normalized) that flow alongside the video pipeline -- would enable:
- Audio-reactive visuals (audio FFT -> channel -> filter parameter)
- MIDI/OSC control (hardware -> channel -> filter parameter)
- Perception-driven modulation (hand openness -> channel -> effect intensity)
- Time-based animation (LFO -> channel -> parameter oscillation)

### 2.4 TouchEngine -- Headless Component Execution

TouchEngine allows loading .tox components and rendering them headlessly from any application (C API + Vulkan/DX/OpenGL support). Key patterns:
- **External timing**: The host controls when frames cook, not TD's internal clock
- **Parameter discovery**: Inputs/outputs are enumerated at load time
- **Zero-copy texture sharing**: GPU textures passed by reference, not copied

SIE equivalent: If SIE could export filter chains as loadable "filter packs" that other applications (OBS, Resolume, Unity) could load and execute, it would massively increase adoption.

---

## 3. Specific Techniques Worth Porting

### 3.1 Feedback Loops with Transform (HIGH PRIORITY)

**How it works in TD**: Feedback TOP -> Level TOP (fade) -> Transform TOP (translate/rotate/scale) -> Composite TOP (blend with new input) -> output (also feeds back into Feedback TOP).

**SIE implementation**:
```
FrameHistory buffer (stores previous output)
  -> FadeFilter (multiply by 0.95 to decay)
  -> TransformFilter (rotate 0.5 degrees, scale 1.01)
  -> CompositeFilter (blend with current camera frame)
  -> output (also stored to FrameHistory)
```

**Parameters to expose**: decay_rate, rotate_speed, scale_factor, translate_x/y, blend_mode
**Use cases**: Motion trails, echo effects, infinite zoom, kaleidoscopic recursion

### 3.2 Audio Spectrum to Visual Mapping (HIGH PRIORITY)

**How it works in TD**: Audio In CHOP -> Audio Spectrum CHOP (FFT, 2048 samples) -> Math CHOP (normalize) -> Select CHOP (isolate bands) -> drives TOP parameters.

**SIE implementation**:
```python
class AudioAnalyzer:
    """New perception-layer analyzer for audio input."""
    def analyze(self, audio_buffer: np.ndarray) -> dict:
        spectrum = np.fft.rfft(audio_buffer * window)
        magnitudes = np.abs(spectrum)
        return {
            "bass_energy": float(np.mean(magnitudes[bass_range])),
            "mid_energy": float(np.mean(magnitudes[mid_range])),
            "high_energy": float(np.mean(magnitudes[high_range])),
            "beat_detected": bool(onset_detection(magnitudes)),
            "spectrum": magnitudes.tolist(),  # full spectrum for detailed mapping
        }
```

### 3.3 Noise-Based Displacement (HIGH PRIORITY)

**How it works in TD**: Noise TOP -> Displace TOP (uses noise as UV offset map for source image).

**SIE implementation**: A `DisplaceFilter` that generates Perlin/Simplex noise and uses it to offset pixel lookups:
```python
def apply(self, frame: np.ndarray, analysis: dict) -> np.ndarray:
    noise_map = generate_simplex_noise(frame.shape[:2], self.frequency, self.time)
    displaced = cv2.remap(frame, map_x + noise_map * self.amplitude,
                          map_y + noise_map * self.amplitude, cv2.INTER_LINEAR)
    return displaced
```

**Parameters**: noise_frequency, noise_amplitude, noise_speed, noise_octaves

### 3.4 Instancing Systems (MEDIUM PRIORITY)

**How it works in TD**: A single geometry (SOP) is replicated at positions defined by a CHOP or texture. Position, scale, rotation, color per instance.

**SIE implementation**: A `ParticleOverlayFilter` that renders multiple copies of a sprite/shape at positions determined by perception data:
- Instances at detected face positions
- Instances at hand landmark positions
- Instances driven by audio frequency bins (graphic equalizer visualization)

### 3.5 Projection Mapping Patterns (MEDIUM PRIORITY)

**How it works in TD**: Stoner (perspective warping), Kantan Mapper (quad-based mapping), camera-as-projector technique.

**SIE implementation**: A `PerspectiveWarpOutputSink` that applies a 4-point perspective transform before output, allowing the rendered frame to be projected onto non-rectangular surfaces. Uses cv2.getPerspectiveTransform() and cv2.warpPerspective().

### 3.6 Reaction-Diffusion (MEDIUM PRIORITY)

**How it works in TD**: Two-texture feedback loop implementing Gray-Scott equations. Chemical A and B diffuse and react per pixel.

**SIE implementation**: A stateful `ReactionDiffusionFilter`:
```
Each frame:
  1. Read previous state (chemicals A, B) from internal buffer
  2. Apply diffusion (gaussian blur A, gaussian blur B)
  3. Apply reaction: A' = A + (Da*laplacian(A) - A*B^2 + f*(1-A))
                       B' = B + (Db*laplacian(B) + A*B^2 - (k+f)*B)
  4. Map (A, B) to color via palette
  5. Composite with camera frame
  6. Store state for next frame
```

### 3.7 Depth-Camera Integration (LOW PRIORITY -- hardware dependent)

**Pattern**: Extend FrameSource to optionally return depth alongside RGB. Use depth for:
- Selective processing by distance (blur background, sharpen foreground)
- 3D particle emission from surfaces
- Occlusion-aware AR overlays

---

## 4. Community Resources

### 4.1 Key Artists and Their Open-Source Contributions

| Artist/Studio | Focus | GitHub/Resources | Value to SIE |
|---|---|---|---|
| **Torin Blankensmith** (blankensmithing) | MediaPipe plugin, Shader Park, creative tools | [github.com/torinmb](https://github.com/torinmb) | Created the most popular TD CV plugin. His approach to packaging perception into reusable components is a model for SIE's analyzer architecture. |
| **David Braun** (doitrealtime) | Compute shaders, simulations, shared components | [github.com/DBraun](https://github.com/DBraun) | 961-star component library. His Physarum, boids, and curl noise implementations are directly portable reference code. |
| **Matthew Ragan** (raganmd) | Education, tools, GLSL tutorials | [github.com/raganmd](https://github.com/raganmd) | Book of Shaders port (181 stars), GLSL learning repo (142 stars), tool collection. Excellent shader reference material. |
| **Bileam Tschepe** (elekktronaut) | Audio-reactive art, organic generative systems | [YouTube/Patreon](https://www.elekktronaut.com/) | Techniques for mapping audio to organic visual systems. Tutorial-quality documentation of audio-reactive patterns. |
| **Lyell Hintz** (DotSimulate) | StreamDiffusion, real-time AI art | Community posts, StreamDiffusionTD | Pioneering real-time diffusion in live performance. Pattern: external AI service feeding into visual pipeline. |
| **Oleg Chomp** (olegchomp) | AI integrations (Diffusion, ComfyUI, Depth) | [github.com/olegchomp](https://github.com/olegchomp) | Three major AI-integration repos. His approach of wrapping AI services in TD-native interfaces is applicable to SIE adapter design. |
| **Kurt Kaminski** (kamindustries) | Fluid simulation, GPU particles | [github.com/kamindustries](https://github.com/kamindustries) | touchFluid (223 stars) has clean, extractable GLSL fluid shaders. Also has a CUDA fluid variant. |
| **Lucas M Morgan** (EnviralDesign) | Lighting control, multi-output mapping | [github.com/EnviralDesign](https://github.com/EnviralDesign) | GeoPix MIT-licensed codebase is a reference for multi-output rendering and spatial mapping. |

### 4.2 Curated Resource Lists

| Resource | URL | Description |
|---|---|---|
| awesome-touchdesigner (monkeymonk) | [github.com/monkeymonk/awesome-touchdesigner](https://github.com/monkeymonk/awesome-touchdesigner) | Comprehensive curated list: plugins, tutorials, community projects, marketplace links. Updated regularly. |
| awesome-touchdesigner (danielsamson) | [github.com/danielsamson/awesome-touchdesigner](https://github.com/danielsamson/awesome-touchdesigner) | Videos, books, companies, and projects list. |
| AllTouchDesigner | [alltd.org](https://alltd.org) | Tutorial aggregator with tag-based browsing (feedback, particles, GLSL, etc.) |
| Interactive Immersive HQ | [interactiveimmersive.io](https://interactiveimmersive.io) | Professional tutorials and courses. Their operator-explained series is excellent for understanding TD architecture. |

### 4.3 ISF (Interactive Shader Format) Ecosystem

| Resource | URL | Description |
|---|---|---|
| ISF Shader Gallery | [isf.video](https://isf.video/) | 200+ community shaders with standardized format. Each shader has JSON metadata defining inputs/outputs. |
| ISF Files repo | [github.com/Vidvox/ISF-Files](https://github.com/Vidvox/ISF-Files) | Official ISF shader collection. Generators + filters. GLSL with JSON parameter definitions. |
| ISF Spec | [github.com/mrRay/ISF_Spec](https://github.com/mrRay/ISF_Spec) | Specification document for ISF format. |

ISF is particularly interesting because it solves the "shader packaging" problem -- each shader is a self-contained file with parameter definitions. SIE could adopt this format or something similar for user-contributed filters.

---

## 5. Actionable Recommendations for SIE

### 5.1 Immediate Wins (can implement now, within current architecture)

| Priority | Recommendation | Inspiration Source | Effort |
|---|---|---|---|
| **P0** | **Add FrameHistory buffer** for feedback-loop filters | TD Feedback TOP pattern | 1-2 days |
| **P0** | **Port 5 post-effect shaders** from ogrew/TD-PostEffectShader (bloom, chromatic aberration, halftone, kaleidoscope, kuwahara) | ogrew/TD-PostEffectShader | 3-5 days |
| **P1** | **Add DisplaceFilter** using Simplex noise | TD Noise TOP + Displace TOP pattern | 1-2 days |
| **P1** | **Add runtime class filtering** to perception analyzers | TDYolo dynamic class filter pattern | 1 day |
| **P1** | **Add OSC input adapter** for external parameter control | TD-Open-Stage-Control, OSC bridge pattern | 2-3 days |

### 5.2 Medium-Term Enhancements (new capabilities, still within hexagonal architecture)

| Priority | Recommendation | Inspiration Source | Effort |
|---|---|---|---|
| **P1** | **Implement ChannelBus** -- named float channels flowing alongside video pipeline, enabling audio/MIDI/perception-driven parameter modulation | TD CHOP system | 1-2 weeks |
| **P1** | **Add AudioAnalyzer** -- FFT-based audio analysis producing bass/mid/high energy channels | TDAudioAnalysis, TD Audio Spectrum CHOP | 3-5 days |
| **P2** | **Add NDI output sink** for network streaming to VJ software | Web2NDI pattern, Spout/NDI architecture | 3-5 days |
| **P2** | **Add WebRTC output sink** for browser-based monitoring/control | TD WebRTC Remote Panel | 1 week |
| **P2** | **Implement fluid simulation filter** porting GLSL from touchFluid | kamindustries/touchFluid | 1 week |
| **P2** | **Add Depth Anything analyzer** for monocular depth estimation | TDDepthAnything | 3-5 days |

### 5.3 Longer-Term Architecture Improvements

| Priority | Recommendation | Inspiration Source | Effort |
|---|---|---|---|
| **P2** | **ISF shader compatibility layer** -- parse ISF format, expose 200+ community shaders as filters | isf-touchdesigner, ISF spec | 2-3 weeks |
| **P2** | **Parameter modulation system** -- LFOs, envelopes, expressions that drive filter parameters over time | TD parameter animation, CHOP-to-parameter binding | 2 weeks |
| **P3** | **Lazy/pull-based pipeline evaluation** -- skip stages when output not needed | TD pull-based cook model | 2-3 weeks |
| **P3** | **External AI workflow bridge** (ComfyUI/StreamDiffusion) | TDComfyUI, TouchDiffusion | 2-3 weeks |
| **P3** | **Zero-copy GPU tensor sharing** via DLPack between Python and C++ | TouchPy Vulkan/CUDA zero-copy pattern | 3-4 weeks |

### 5.4 Cross-Cutting Patterns to Adopt

1. **Feedback is a first-class concept**: The single biggest architectural gap. Every creative coder's first question will be "can I do feedback?" Adding a FrameHistory mechanism unlocks trails, echoes, reaction-diffusion, fluid sim, and accumulation effects.

2. **Parameters are modulatable**: Static parameters are a dead end for live performance. Every filter parameter should accept a `modulation_source` (audio channel, LFO, perception value, OSC input) that dynamically overrides the static value.

3. **Multi-protocol output**: Supporting NDI/Spout/WebRTC output alongside the current renderer makes SIE interoperable with the broader creative coding ecosystem (Resolume, MadMapper, OBS, Unity).

4. **Separate perception from control**: Perception analyzes frames. A separate "control mapping" layer translates perception results into parameter changes. This separation (which TD achieves via CHOP) keeps the perception pipeline clean and reusable.

5. **Shader standardization**: Adopting ISF or a similar self-describing shader format would allow community contribution of filters without modifying SIE core code.

---

## Appendix: Repository Quick-Reference

All repositories mentioned, sorted by stars (approximate):

| Stars | Repository | Category |
|---|---|---|
| ~2,100 | torinmb/mediapipe-touchdesigner | Computer Vision |
| ~961 | DBraun/TouchDesigner_Shared | Components/Effects |
| ~333 | t3kt/raytk | Raymarching/SDF |
| ~260 | olegchomp/TouchDiffusion | AI/Generative |
| ~236 | olegchomp/TDComfyUI | AI/Generative |
| ~223 | kamindustries/touchFluid | Fluid Simulation |
| ~181 | raganmd/BOS-in-TouchDesigner | Shaders/Education |
| ~150 | EnviralDesign/GeoPix | Lighting Control |
| ~142 | raganmd/learningGLSL | Shaders/Education |
| ~125 | satoruhiga/TouchDesigner-ShaderBuilder | Shader Tools |
| ~120 | olegchomp/TDDepthAnything | AI/Depth |
| ~100 | function-store/FunctionStore_tools | Workflow Tools |
| ~90 | ogrew/TD-PostEffectShader | GLSL Effects |
| ~60 | L05/TouchDesigner | Tools/Examples |
| ~50 | IntentDev/touchpy | Python Bridge |
| ~50 | patrickhartono/TDYolo | Computer Vision |
| ~50 | 8beeeaaat/touchdesigner-mcp | AI/Automation |
| ~40 | cronin4392/TouchDesigner-OpenCV-OSC | Computer Vision |
| ~30 | marcinbiegun/isf-touchdesigner | Shader Format |
| ~30 | JonathanDCohen/TDAudioAnalysis | Audio Analysis |
| ~30 | TouchDesigner/WebRTC-Remote-Panel-Web-Demo | Streaming |
| ~25 | ejfox/hand-midi-controller | MIDI/Control |
| ~20 | Theoriz/Web2NDI_SyphonSpout_TouchDesigner | Streaming |
| ~20 | struct78/aurora | Audio-Reactive |
| ~15 | guidoschmidt/sketchbook.touchdesigner | Experiments |
| ~15 | LucieMrc/TD_audioreact_love_EN | Audio-Reactive |
| ~15 | motius/remote-stream-diffusion-td | AI/Remote |
| ~10 | stosumarte/FreenectTD | Depth Camera |
| ~10 | maxbecq/ricolivetd | DAW Sync |
