# openFrameworks Research: Patterns, Addons, and Techniques for Spatial-Iteration-Engine

**Date**: 2026-02-25
**Purpose**: Identify architecture patterns, addons, techniques, and project examples from the openFrameworks ecosystem that could inspire improvements to the Spatial-Iteration-Engine.

---

## Table of Contents

1. [Architecture Patterns](#1-architecture-patterns)
2. [Computer Vision Addons](#2-computer-vision-addons)
3. [Fluid and Flow Simulation](#3-fluid-and-flow-simulation)
4. [Physics and Particle Systems](#4-physics-and-particle-systems)
5. [Video Sharing Protocols](#5-video-sharing-protocols)
6. [Control Protocols (OSC/MIDI)](#6-control-protocols-oscmidi)
7. [GLSL Shader Effects and Post-Processing](#7-glsl-shader-effects-and-post-processing)
8. [Animation and Sequencing](#8-animation-and-sequencing)
9. [Depth Cameras and Point Clouds](#9-depth-cameras-and-point-clouds)
10. [Machine Learning and AI](#10-machine-learning-and-ai)
11. [Audio Analysis and Reactive Visuals](#11-audio-analysis-and-reactive-visuals)
12. [Creative Coding Techniques](#12-creative-coding-techniques)
13. [Notable Projects and Installations](#13-notable-projects-and-installations)
14. [GUI and Visual Programming](#14-gui-and-visual-programming)
15. [High-Performance Video](#15-high-performance-video)
16. [Synthesis: What to Port to Spatial-Iteration-Engine](#16-synthesis-what-to-port-to-spatial-iteration-engine)

---

## 1. Architecture Patterns

### 1.1 The setup() / update() / draw() Lifecycle

openFrameworks uses a clean three-phase lifecycle:

- **setup()** -- Called once at startup. Initializes objects, loads resources, allocates buffers.
- **update()** -- Called every frame before draw(). Updates state, runs CV analysis, processes input. No rendering.
- **draw()** -- Called every frame after update(). All rendering happens here.

**Relevance to SIE**: Our pipeline already separates perception (analysis, no image modification) from filters (modify frame) from rendering. The OF pattern confirms this separation is correct. We could formalize a `setup()` phase for lazy initialization of heavy resources (ONNX models, shader compilation) that currently happens on first frame.

### 1.2 The Addon System

openFrameworks has 1,500+ community addons discovered via [ofxaddons.com](https://ofxaddons.com). Key design principles:

- **Naming convention**: All addons prefixed with `ofx` (e.g., `ofxCv`, `ofxFluid`)
- **Self-contained**: Each addon has `src/`, `libs/`, `example/` directories
- **Dependency declaration**: Addons declare dependencies on other addons in `addon_config.mk`
- **No core modification**: Addons extend without modifying the core framework
- **Discovery registry**: Central website catalogs all addons by category

**Relevance to SIE**: This mirrors our hexagonal architecture where adapters extend without touching application/ports/domain. We could formalize a plugin/addon discovery mechanism. The naming convention and self-contained structure could inspire a more formal plugin spec.

### 1.3 FBO Ping-Pong for Feedback Effects

The technique uses two Frame Buffer Objects (FBOs) that alternate as source and destination:

1. Render scene into FBO-A
2. Apply shader reading FBO-A, write result into FBO-B
3. Apply next shader reading FBO-B, write result into FBO-A
4. Repeat for N passes

Used for: multi-pass blur, reaction-diffusion, fluid simulation, feedback/echo effects.

**Relevance to SIE**: We could implement a `PingPongBuffer` utility in C++ for multi-pass GPU effects. This would enable feedback loops in our filter chain without frame copies. Critical for fluid simulation and reaction-diffusion filters.

### 1.4 The Event System (Observer Pattern)

OF wraps Poco Events to provide:

- `ofEvent<T>` -- Type-safe event with payload
- `ofAddListener(event, object, &method)` -- Subscribe to events
- `ofRemoveListener(event, object, &method)` -- Unsubscribe
- `ofFastEvent<T>` -- Non-thread-safe but faster variant
- Lambda support since OF 0.10.0 via `ofEventListener`

Global events: setup, update, draw, exit, keyPressed, mousePressed, windowResize.

**Relevance to SIE**: We already have an `EventBus` in our infrastructure layer. The OF pattern validates our approach. We could add `FastEvent` variant for hot-path frame events where thread safety is guaranteed by pipeline ordering.

### 1.5 Threading Model

OF threading pattern for camera capture:

- Camera grab runs on a separate thread (inheriting `ofThread`)
- `ofMutex` for shared data protection
- Condition variables for producer-consumer synchronization
- Multi-window: each GL context can have its own thread, but OF warns about renderer state conflicts across threads

**Relevance to SIE**: Similar to our source adapter threading. The OF warnings about GL context conflicts are relevant if we add GPU-accelerated filters -- shader state must be isolated per-thread or serialized.

---

## 2. Computer Vision Addons

### 2.1 ofxCv

| Field | Value |
|-------|-------|
| **URL** | https://github.com/kylemcdonald/ofxCv |
| **Stars** | 666 |
| **Author** | Kyle McDonald |
| **What it does** | Alternative OpenCV wrapper for OF. Uses native OF or OpenCV types directly, with `toCv()` and `toOf()` conversion functions that wrap data without copying. |
| **Key technique** | Zero-copy type conversion between framework types; `imitate()` function for smart buffer allocation that only reallocates when dimensions change. |
| **What to extract** | The `imitate()` pattern for lazy buffer allocation. Our numpy arrays could benefit from a similar utility that avoids reallocation when frame dimensions haven't changed. The 35+ examples cover: face detection, edge detection, optical flow, calibration, contour tracking. |

### 2.2 ofxFaceTracker

| Field | Value |
|-------|-------|
| **URL** | https://github.com/kylemcdonald/ofxFaceTracker |
| **Stars** | 1,400 |
| **Author** | Kyle McDonald |
| **What it does** | CLM (Constrained Local Model) face tracking. Pose estimation (position, scale, 3D orientation), gesture recognition (mouth, eyebrow, eye, jaw), expression classification. |
| **Key technique** | Real-time 68-point facial landmark detection; FaceOSC streams tracking data over OSC for use in other apps; face mesh extraction for face substitution. |
| **What to extract** | Expression classification system (smile, blink, eyebrow raise) as analysis dict keys. FaceOSC-style data streaming for external tool integration. Face mesh extraction for Delaunay triangulation effects. |

### 2.3 ofxFaceTracker2

| Field | Value |
|-------|-------|
| **URL** | https://github.com/HalfdanJ/ofxFaceTracker2 |
| **Stars** | 213 |
| **Author** | Jonas Jongejan |
| **What it does** | Next-gen face tracker using dlib. Multi-face support, background-thread detection, 68-point landmarks, 3D pose estimation. |
| **Key technique** | Face detection runs on background thread (slow but offloaded); landmark detection is fast and runs on main thread. Decoupled detection from tracking. |
| **What to extract** | The decoupled detection/tracking architecture. We could run face detection at lower frequency (every N frames) on a thread, while running landmark tracking at full framerate on the main pipeline. This matches our latency budget constraints. |

---

## 3. Fluid and Flow Simulation

### 3.1 ofxFlowTools

| Field | Value |
|-------|-------|
| **URL** | https://github.com/moostrik/ofxFlowTools |
| **Stars** | 338 |
| **Author** | Matthias Oostrik |
| **What it does** | Combines 2D fluid simulation, optical flow, and particle systems -- all in GLSL shaders. Designed for live camera input to create "psychedelic live visuals." |
| **Key technique** | GPU-accelerated Jos Stam fluid solver combined with optical flow from camera input. Camera motion drives fluid forces. Includes advection, diffusion, pressure solve steps. |
| **What to extract** | The entire optical-flow-to-fluid pipeline. Camera motion could drive fluid forces overlaid on the video feed. This would be a spectacular filter for our engine. Requires GPU (OpenGL compute or CUDA). |

### 3.2 ofxFluid

| Field | Value |
|-------|-------|
| **URL** | https://github.com/patriciogonzalezvivo/ofxFluid |
| **Stars** | 81 |
| **Author** | Patricio Gonzalez Vivo |
| **What it does** | GPU fluid simulation with a collision layer. Based on Mark Harris's GPU Gems article. |
| **Key technique** | Collision mask allows fluid to interact with shapes/boundaries. Uses ping-pong FBO technique for iterative solve. Simpler than ofxFlowTools but more focused. |
| **What to extract** | The collision layer concept: use perception masks (face, hand, body) as collision boundaries for fluid simulation. Fluid flows around detected bodies. |

### 3.3 ofxFX (Shader Framework)

| Field | Value |
|-------|-------|
| **URL** | https://github.com/patriciogonzalezvivo/ofxFX |
| **Stars** | 341 |
| **Author** | Patricio Gonzalez Vivo |
| **What it does** | GPU shader framework. Adapts well-known algorithms to GLSL. Includes Conway's Game of Life, Gray-Scott reaction-diffusion, blur, water ripples, watercolor effects. |
| **Key technique** | Chaining effects with `<<` operator. Configurable ping-pong passes. Supports both GLSL 120 and OpenGL ES. |
| **What to extract** | The `<<` chaining pattern for GPU effects. The reaction-diffusion and Game of Life implementations. The architecture of wrapping a shader + FBO pair as a reusable effect unit. |

---

## 4. Physics and Particle Systems

### 4.1 ofxBox2d

| Field | Value |
|-------|-------|
| **URL** | https://github.com/vanderlin/ofxBox2d |
| **Stars** | 327 |
| **Author** | Todd Vanderlin |
| **What it does** | Box2D physics wrapper for OF. 2D rigid body physics with circles, rectangles, polygons, joints. |
| **Key technique** | Shared-pointer managed physics objects; 12 example projects showing particle systems, complex polygons, joints, custom shapes. |
| **What to extract** | Physics-driven particle effects where detected bodies/hands create forces. Particles could be attracted to or repelled by face landmarks. 2D physics for text/shape animation driven by perception data. |

### 4.2 ofxBullet

| Field | Value |
|-------|-------|
| **URL** | https://github.com/NickHardeman/ofxBullet |
| **Stars** | 153 |
| **Author** | Nick Hardeman |
| **What it does** | Bullet Physics 3D wrapper. Rigid bodies, soft bodies, cloth simulation, joints, custom collision shapes. |
| **Key technique** | Soft body/cloth simulation driven by external forces. Mesh integration for applying physics to 3D models. |
| **What to extract** | Cloth simulation overlaid on video. Soft body deformation driven by hand gestures or audio. 3D particle systems with gravity and collisions. |

### 4.3 ofxParticles (CPU)

| Field | Value |
|-------|-------|
| **URL** | https://github.com/timscaffidi/ofxParticles |
| **Stars** | 20 |
| **Author** | Tim Scaffidi |
| **What it does** | CPU-based particle system. Emitters, gravitation, attraction, rotation, 2D velocity fields, texture rendering. |
| **Key technique** | Velocity field integration -- particles follow a 2D vector field that can be generated from Perlin noise or optical flow. |
| **What to extract** | Velocity field concept: generate a flow field from perception data (optical flow, hand movement) and let particles follow it. Simple CPU implementation suitable for Python/numpy. |

### 4.4 ofxFastParticleSystem (GPU)

| Field | Value |
|-------|-------|
| **URL** | https://github.com/fusefactory/ofxFastParticleSystem |
| **Stars** | 34 |
| **Author** | Fuse Factory |
| **What it does** | GPU-accelerated particle system using GLSL. Separate update and draw shaders. Used in production for the "Dokk" interactive performance. |
| **Key technique** | Modular shader architecture with separate update/draw passes. Multiple shader support for different particle behaviors. Strange attractor example included. |
| **What to extract** | The separate update/draw shader pattern. Particle positions stored in textures, updated via compute/fragment shaders. This is the path for 100K+ particle systems at 30fps. |

---

## 5. Video Sharing Protocols

### 5.1 ofxSyphon

| Field | Value |
|-------|-------|
| **URL** | https://github.com/astellato/ofxSyphon |
| **Stars** | 198 |
| **Platform** | macOS only |
| **What it does** | Shares video between applications via the Syphon framework. Client receives frames as textures; Server publishes textures to the system. |
| **Key technique** | GPU-level texture sharing without CPU readback. Zero-copy frame sharing between OpenGL contexts. Server directory for discovering available sources. |
| **What to extract** | The concept of inter-application frame sharing. We could implement a Syphon/Spout output sink adapter to send our processed frames to VJ software (Resolume, VDMX, TouchDesigner). |

### 5.2 ofxSpout

| Field | Value |
|-------|-------|
| **URL** | https://github.com/elliotwoods/ofxSpout |
| **Stars** | 76 |
| **Platform** | Windows |
| **What it does** | Shares textures between DirectX and OpenGL applications via Spout v2. Sender and Receiver classes. |
| **Key technique** | Cross-graphics-API texture sharing (DirectX <-> OpenGL). Works across 32-bit and 64-bit processes. |
| **What to extract** | Windows equivalent of Syphon. Combined with ofxSyphon, enables cross-platform inter-app video sharing. |

### 5.3 ofxNDI

| Field | Value |
|-------|-------|
| **URL** | https://github.com/leadedge/ofxNDI |
| **Stars** | 149 |
| **Platform** | Cross-platform |
| **What it does** | Network Device Interface -- sends/receives video over IP network. Supports ofFbo, ofTexture, ofPixels, raw buffers. YUV compression for bandwidth efficiency. |
| **Key technique** | Network video streaming with automatic sender-size change handling. PBO (Pixel Buffer Object) readback for GPU-to-CPU transfer optimization. |
| **What to extract** | NDI output sink for network streaming. This would allow our engine to send processed frames to any NDI-compatible receiver on the network. The PBO readback technique is relevant for our GPU-accelerated pipeline. |

---

## 6. Control Protocols (OSC/MIDI)

### 6.1 ofxMidi

| Field | Value |
|-------|-------|
| **URL** | https://github.com/danomatika/ofxMidi |
| **Stars** | 275 |
| **Author** | Dan Wilcox |
| **What it does** | MIDI I/O for openFrameworks. Input listener pattern, output stream interface. Cross-platform via RtMidi. |
| **Key technique** | Listener-based MIDI input (`ofxMidiListener` interface); stream-based output. Supports all standard MIDI messages. |
| **What to extract** | MIDI control adapter for our engine. Map MIDI CC values to filter parameters (brightness, contrast, effect intensity). MIDI note triggers could switch presets or trigger effects. |

### 6.2 ofxOsc (Core Addon)

| Field | Value |
|-------|-------|
| **URL** | Built into OF core; extended version at https://github.com/hideyukisaito/ofxOsc |
| **Stars** | Core addon |
| **What it does** | OSC (Open Sound Control) send/receive. Event-dispatching variant fires events on message receipt. |
| **Key technique** | Event-driven OSC message handling. Can bridge between any OSC-capable application (Max/MSP, SuperCollider, TouchDesigner, Ableton). |
| **What to extract** | OSC input/output adapters. Receive control messages to adjust parameters; send perception data (face landmarks, hand positions) as OSC for external tools. |

### 6.3 ofxRemoteUI

| Field | Value |
|-------|-------|
| **URL** | https://github.com/armadillu/ofxRemoteUI |
| **Stars** | ~100 (est.) |
| **What it does** | Serves variables (bool, float, int, enum, string, color) over UDP/OSC for remote editing. Includes native macOS client. |
| **Key technique** | Variable binding over network. Any parameter becomes remotely controllable. Auto-discovers available parameters. |
| **What to extract** | Remote parameter control for our engine. Expose filter parameters, pipeline settings, and perception thresholds as remotely editable values. |

---

## 7. GLSL Shader Effects and Post-Processing

### 7.1 ofxPostProcessing

| Field | Value |
|-------|-------|
| **URL** | https://github.com/neilmendoza/ofxPostProcessing |
| **Stars** | 351 |
| **Author** | Neil Mendoza |
| **What it does** | Chain of GLSL post-processing effects. Easy to compose multiple effects. |
| **Key technique** | Effect chain pattern: each effect reads from previous FBO and writes to next. Effects are self-contained shader + parameters. |
| **Effects included** | Bloom, Blur (Convolution), Depth of Field (with bokeh), Frei-Chen Edge Detector, FXAA anti-aliasing, Kaleidoscope, Noise Warp, Pixelate, SSAO, Toon/Cel-shading, Godrays, Tilt Shift, Fake Subsurface Scattering |
| **What to extract** | **High priority**. Many of these effects map directly to filters we could implement: Bloom, Edge Detection, Kaleidoscope, Pixelate, Toon shading, Godrays, Tilt Shift. The chain architecture validates our FilterPipeline approach. GPU versions would be dramatically faster than CPU equivalents. |

### 7.2 ofxDeferredShading

| Field | Value |
|-------|-------|
| **URL** | https://github.com/nama-gatsuo/ofxDeferredShading |
| **Stars** | 87 |
| **Author** | nama-gatsuo |
| **What it does** | Modern OpenGL deferred rendering: edge detection, point lights, shadow casting, SSAO, Depth of Field, Bloom (Kawase), volumetric fog. |
| **Key technique** | G-buffer rendering: separate passes for normals, depth, albedo. Multi-pass deferred pipeline enables complex lighting cheaply. |
| **What to extract** | The depth-of-field and volumetric fog techniques. Even without a 3D scene, we could use depth estimation from perception to create selective focus/fog effects on video. |

---

## 8. Animation and Sequencing

### 8.1 ofxTimeline

| Field | Value |
|-------|-------|
| **URL** | https://github.com/YCAMInterlab/ofxTimeline |
| **Stars** | 277 |
| **Author** | YCAM InterLab / James George |
| **What it does** | Timeline UI for composing sequences of parameter changes over time. Curve editing, color tracks, video thumbnails, BPM snapping. |
| **Key technique** | Keyframe animation with multiple track types. XML save/load. Multi-page timelines. Precise millisecond timing. |
| **What to extract** | Timeline-based parameter animation for our presentation layer. Users could keyframe filter parameters over time for pre-composed sequences. BPM sync for music-driven installations. |

### 8.2 ofxTween / ofxEasing

| Field | Value |
|-------|-------|
| **URL** | https://github.com/arturoc/ofxTween (deprecated, use ofxEasing) |
| **Stars** | ~50 |
| **What it does** | Easing/tweening functions for smooth parameter transitions. |
| **Key technique** | Standard easing curves (ease-in, ease-out, bounce, elastic, etc.) for interpolating between values. |
| **What to extract** | Easing functions for smooth parameter transitions when switching presets or responding to events. Simple utility, high impact on visual polish. |

---

## 9. Depth Cameras and Point Clouds

### 9.1 ofxAzureKinect

| Field | Value |
|-------|-------|
| **URL** | https://github.com/prisonerjohn/ofxAzureKinect |
| **Stars** | 74 |
| **Author** | Elie Zananiri |
| **What it does** | Azure Kinect integration. Depth, color, infrared frames. Point cloud VBO. Body tracking with skeleton joints. Multi-sensor support (up to 4). Recording/playback. |
| **Key technique** | Point cloud reconstruction from depth LUTs in shader. Body tracking index texture for per-pixel body segmentation. Multi-device sync (master/subordinate). |
| **What to extract** | Point cloud rendering as an output/renderer mode. Body segmentation from depth index texture. The multi-camera sync pattern for multi-source setups. |

### 9.2 ofxDepthCamera

| Field | Value |
|-------|-------|
| **URL** | https://github.com/mattfelsen/ofxDepthCamera |
| **Stars** | ~30 |
| **What it does** | Device-independent abstraction for multiple depth cameras. Recording, playback, remote streaming. |
| **Key technique** | Unified API across Kinect v1/v2, RealSense, Azure Kinect. Device-independent depth data. |
| **What to extract** | The abstraction pattern for depth sources. We could add a DepthSource port alongside FrameSource for depth cameras, with adapters for different hardware. |

---

## 10. Machine Learning and AI

### 10.1 ofxTensorFlow2

| Field | Value |
|-------|-------|
| **URL** | https://github.com/zkmkarlsruhe/ofxTensorFlow2 |
| **Stars** | 119 |
| **Author** | ZKM Hertz-Lab |
| **What it does** | TensorFlow 2 wrapper for OF. Load and run SavedModel or frozen GraphDef models. CPU and GPU support. |
| **Key technique** | Type conversion utilities between OF types (images, pixels, audio) and TF tensors. Pre-built TF libraries (no Bazel needed). |
| **Example models** | Style transfer (regular + arbitrary), YOLO v4 object detection, MoveNet pose estimation, Pix2Pix image translation, video matting, EfficientNet classification, keyword spotting |
| **What to extract** | **Style transfer** as a filter (both fixed-style and arbitrary-style). **Video matting** for background removal/replacement. **Pix2Pix** for artistic transformation. These are directly implementable as perception analyzers or transformation filters. |

### 10.2 ofxOnnxRuntime

| Field | Value |
|-------|-------|
| **URL** | https://github.com/hanasaan/ofxOnnxRuntime |
| **Stars** | ~15 |
| **What it does** | Thin ONNX Runtime wrapper for OF. |
| **Key technique** | Minimal wrapper pattern -- just enough to load and run ONNX models. |
| **What to extract** | Validates our ONNX Runtime approach. We already use ONNX Runtime via `perception_cpp`. The OF community is moving the same direction. |

---

## 11. Audio Analysis and Reactive Visuals

### 11.1 ofxAudioAnalyzer

| Field | Value |
|-------|-------|
| **URL** | https://github.com/leozimmerman/ofxAudioAnalyzer |
| **Stars** | 189 |
| **Author** | Leo Zimmerman |
| **What it does** | Wraps Essentia library for real-time audio analysis. RMS, pitch, spectral analysis (MFCC, Tristimulus), onset detection, harmonic analysis. |
| **Key technique** | Multi-feature audio analysis in real-time. Extracts perceptual features beyond simple FFT. |
| **What to extract** | Audio-reactive filter parameters. Beat detection could trigger visual effects. Pitch could drive color hue. Spectral features could control particle behavior. This bridges audio and visual processing. |

### 11.2 SonicSculpture

| Field | Value |
|-------|-------|
| **URL** | https://github.com/laserpilot/SonicSculpture |
| **Stars** | ~20 |
| **What it does** | Generates 3D meshes from audio FFT data. Frequency bins are extruded in the time dimension to create 3D shapes. |
| **Key technique** | Time-extruded FFT visualization. Each frame's frequency spectrum becomes a row; accumulated rows form a 3D landscape. |
| **What to extract** | Audio-to-mesh generation as a creative renderer. Could overlay audio-reactive 3D geometry on video. |

### 11.3 ofxPDSP

| Field | Value |
|-------|-------|
| **URL** | https://github.com/npisanti/ofxPDSP |
| **Stars** | ~150 (est.) |
| **What it does** | Audio synthesis and generative music addon. Modular synth design with oscillators, filters, envelopes, sequencers. |
| **Key technique** | Modular audio graph with real-time parameter control. Sequencer with programmable patterns. |
| **What to extract** | Concept of a modular processing graph. Audio synthesis driven by perception data (hand position controls pitch, face expression controls filter). |

---

## 12. Creative Coding Techniques

### 12.1 Slit-Scan / Time Displacement

| Field | Value |
|-------|-------|
| **URL** | https://github.com/obviousjim/ofxSlitScan |
| **Stars** | 37 |
| **Author** | James George |
| **How it works** | Maintains a rolling buffer of video frames. A grayscale warp map determines which frame each pixel samples from. Dark pixels = recent frames, bright pixels = older frames. Creates temporal distortion where different parts of the image show different moments in time. |
| **What to extract** | **High priority**. Implement as a `SlitScanFilter`: maintain a circular buffer of N frames (e.g., 60 = 2 seconds at 30fps). Use a displacement map (could be generated from depth, face distance, or hand position) to sample temporally. Simple numpy implementation: `output[y,x] = buffer[map[y,x], y, x]`. |

### 12.2 Delaunay Triangulation on Face Landmarks

| Field | Value |
|-------|-------|
| **URL** | https://github.com/obviousjim/ofxDelaunay + https://github.com/wouterverweirder/experiment-webcam-triangulation-opticalflow |
| **Stars** | ~40 each |
| **How it works** | Take face landmark points (68 points from face detection), add edge points, compute Delaunay triangulation. Fill each triangle with the average color from that region. Creates a low-poly/faceted portrait effect. Can also use optical flow to move triangle vertices. |
| **What to extract** | **High priority**. `DelaunayFaceFilter`: take face landmarks from perception analysis dict, compute Delaunay triangulation (scipy.spatial.Delaunay), render colored triangles. Performance: 500 points at 60fps in OF, so 68 face points is trivial. Combine with optical flow for dynamic mesh. |

### 12.3 Strange Attractors

| Field | Value |
|-------|-------|
| **URL** | https://github.com/s373/ofxAChaosLib |
| **Stars** | 18 |
| **What it does** | Library of 24 strange attractors: Lorenz, Rossler, Henon, Ikeda, Clifford, Duffing, Navier-Stokes, Lyapunov, and more. |
| **Key technique** | Iterative computation of non-linear dynamical systems. Each attractor produces 2D or 3D point trajectories that create organic, complex patterns. |
| **What to extract** | Attractor-based particle rendering. Use perception data as attractor parameters (face position shifts attractor coefficients). Render attractor trails as overlays on video. |

### 12.4 Reaction-Diffusion

| Field | Value |
|-------|-------|
| **URL** | https://github.com/aanrii/ofxRD |
| **Stars** | 15 |
| **How it works** | Gray-Scott reaction-diffusion computed via GLSL shaders. Two chemicals diffuse and react, creating organic patterns (spots, stripes, coral, labyrinth). Parameters control pattern type. Custom models via XML. |
| **What to extract** | Reaction-diffusion as a GPU filter. Seed the reaction at face/hand positions. The pattern grows organically from detected features. Can be combined with ping-pong FBO technique for iterative computation. |

### 12.5 Cellular Automata

| Field | Value |
|-------|-------|
| **URL** | https://github.com/davidedc/CellularAutomataOfxApp |
| **Stars** | ~5 |
| **How it works** | Conway's Game of Life and variants computed on GPU. Each pixel is a cell; neighbors determine next state. |
| **What to extract** | Cellular automata overlay driven by perception. Initialize cells from edge-detected video. Body silhouette seeds life patterns that evolve over time. GPU implementation via compute shaders for real-time 1080p. |

### 12.6 Voronoi Diagrams

| Field | Value |
|-------|-------|
| **URL** | https://github.com/madc/ofxVoronoi |
| **Stars** | ~30 |
| **How it works** | Fortune's sweep line algorithm for 2D Voronoi tessellation. Lloyd's relaxation for even spacing (stippling). |
| **What to extract** | Voronoi segmentation of video frames. Use face landmarks or random points as Voronoi sites. Each cell filled with average color from that region. Creates a stained-glass or mosaic effect. Combine with perception for dynamic site placement. |

### 12.7 L-Systems

| Field | Value |
|-------|-------|
| **URL** | https://generative-drawing.github.io/ (workshop materials) |
| **How it works** | Lindenmayer systems -- string rewriting rules that generate fractal plant-like structures. Rules define branching, angle, length. |
| **What to extract** | L-system overlays growing from detected hand/face positions. Audio-reactive growth parameters. Useful for generative art overlay renderer. |

---

## 13. Notable Projects and Installations

### 13.1 Face Substitution (Arturo Castro + Kyle McDonald)

| Field | Value |
|-------|-------|
| **URL** | https://github.com/arturoc/FaceSubstitution |
| **Technique** | Real-time face cloning. Track face landmarks, warp source face texture onto target face mesh. Blending algorithm for seamless compositing. |
| **Relevance** | Face swap filter. We have face detection; adding face mesh warping and texture blending would enable this. |

### 13.2 EyeWriter (Zach Lieberman et al., 2010)

| Technique | Low-cost eye tracking using PS3 Eye camera + IR LEDs + openFrameworks |
| **Relevance** | Demonstrates accessible hardware + CV can create powerful tools. Our engine could support similar accessibility applications. |

### 13.3 Starry Night Interactive (Petros Vrellis, 2012)

| Technique | Particle system following Van Gogh's brush stroke patterns. Touch input creates local turbulence in the flow field. |
| **Relevance** | Flow-field particle rendering. Use optical flow or hand tracking to disturb a pre-computed flow field. Particles trace artistic patterns. |

### 13.4 Mosaic (d3cod3)

| Field | Value |
|-------|-------|
| **URL** | https://github.com/d3cod3/Mosaic |
| **Stars** | 499 |
| **What it does** | Visual patching creative-coding platform. Node-based interface, live coding (Lua/GLSL/Bash), Pure Data integration, audio synthesis, projection mapping, multi-window output, OSC/MIDI. |
| **Relevance** | The most complete OF-based creative tool. Its node-based architecture and live-coding approach could inspire a visual pipeline editor for our engine. The projection mapping module shows how to handle multi-output warping. |

### 13.5 Scramble Suit (various artists)

| Technique | Real-time face obfuscation using ofxFaceTracker. Detected face region is replaced with generative patterns, noise, or scrambled pixels. |
| **Relevance** | Privacy/anonymization filter. We could implement face obfuscation as a filter using our existing face detection. |

### 13.6 Drawn (Zach Lieberman, 2006)

| Technique | Users draw shapes that come alive with physics simulation. Ink strokes become physical objects that fall, bounce, interact. |
| **Relevance** | Hand-drawn input + physics simulation. Hand tracking could enable "drawing in air" with physics-driven particle trails. |

### 13.7 Super Hexagon (Terry Cavanagh)

| Technique | Procedurally generated hexagonal obstacle courses. Built originally in openFrameworks. |
| **Relevance** | Demonstrates OF's capability for high-performance real-time graphics. The procedural generation patterns are applicable to generative overlays. |

---

## 14. GUI and Visual Programming

### 14.1 ofxDatGui

| Field | Value |
|-------|-------|
| **URL** | https://github.com/braitsch/ofxDatGui |
| **Stars** | 440 |
| **What it does** | Full-featured GUI: buttons, sliders, text input, color pickers, dropdowns, scroll views, coordinate pads, waveform monitors, variable binding. |
| **What to extract** | The variable binding pattern -- any parameter automatically gets a UI control. We could adopt this for our Jupyter notebook presentation layer: auto-generate widget panels from filter parameter schemas. |

### 14.2 ofxImGui

| Field | Value |
|-------|-------|
| **URL** | https://github.com/jvcleave/ofxImGui |
| **Stars** | ~150 |
| **What it does** | ImGui integration for OF. Immediate-mode GUI for rapid prototyping. |
| **What to extract** | If we ever add a native UI (beyond Jupyter), ImGui via pybind11 (Dear PyGui or imgui[python]) would be the path. Immediate-mode GUI is ideal for real-time parameter tweaking. |

---

## 15. High-Performance Video

### 15.1 ofxHapPlayer

| Field | Value |
|-------|-------|
| **URL** | https://github.com/bangnoise/ofxHapPlayer |
| **Stars** | 158 |
| **What it does** | Hap codec video player. GPU-decoded video for high resolution and high framerate. Cross-platform (macOS, Windows, Linux). |
| **Key technique** | Hap codec stores DXT-compressed frames that decode directly on GPU -- bypasses CPU entirely. Hap Q variant adds quality. Shader needed for Hap Q decompression. |
| **What to extract** | GPU-decoded video source adapter. For pre-recorded video input, Hap codec would dramatically reduce CPU load. Our `VideoSource` adapter could support Hap alongside standard codecs. |

---

## 16. Synthesis: What to Port to Spatial-Iteration-Engine

### Priority 1: High Impact, Moderate Effort (Next Sprint)

| Technique | Source | Implementation Path | Estimated Effort |
|-----------|--------|---------------------|------------------|
| **Slit-Scan Filter** | ofxSlitScan | Python: circular numpy buffer + displacement map | 2-3 days |
| **Delaunay Face Filter** | ofxDelaunay + ofxFaceTracker | Python: scipy.spatial.Delaunay on face landmarks | 2-3 days |
| **Expression Classification** | ofxFaceTracker | Python: derive expressions from face landmark geometry | 1-2 days |
| **Easing Functions** | ofxTween/ofxEasing | Python: utility module for smooth transitions | 1 day |
| **Toon/Cel-Shading Filter** | ofxPostProcessing | Python/C++: edge detect + quantize colors | 1-2 days |
| **Kaleidoscope Filter** | ofxPostProcessing | Python: polar coordinate transform + mirroring | 1 day |

### Priority 2: High Impact, High Effort (Medium-Term)

| Technique | Source | Implementation Path | Estimated Effort |
|-----------|--------|---------------------|------------------|
| **GPU Fluid Simulation** | ofxFlowTools / ofxFluid | C++: GLSL compute shaders via render_bridge | 2 weeks |
| **Reaction-Diffusion Filter** | ofxRD / ofxFX | C++: GLSL fragment shader + ping-pong FBO | 1 week |
| **Style Transfer Filter** | ofxTensorFlow2 | Python: ONNX model for fast style transfer | 1 week |
| **Particle System (GPU)** | ofxFastParticleSystem | C++: GLSL update/draw shaders | 1-2 weeks |
| **NDI Output Sink** | ofxNDI | C++: NDI SDK integration as OutputSink adapter | 1 week |
| **OSC/MIDI Control** | ofxOsc / ofxMidi | Python: python-osc + python-rtmidi adapters | 3-5 days |
| **Video Matting** | ofxTensorFlow2 | Python: ONNX background removal model | 1 week |

### Priority 3: Advanced Capabilities (Long-Term)

| Technique | Source | Implementation Path | Estimated Effort |
|-----------|--------|---------------------|------------------|
| **Syphon/Spout Output** | ofxSyphon / ofxSpout | C++: platform-specific texture sharing | 2 weeks |
| **Point Cloud Renderer** | ofxAzureKinect | C++: depth-to-point-cloud in render_bridge | 2 weeks |
| **Audio-Reactive Parameters** | ofxAudioAnalyzer | Python: audio input + FFT + parameter mapping | 1-2 weeks |
| **Face Substitution** | FaceSubstitution | Python: face mesh warp + texture blend | 2 weeks |
| **Strange Attractor Overlay** | ofxAChaosLib | Python: attractor computation + matplotlib/OpenGL render | 3-5 days |
| **Voronoi Mosaic Filter** | ofxVoronoi | Python: scipy.spatial.Voronoi + fill | 3-5 days |
| **Timeline/Sequencer** | ofxTimeline | Python: keyframe animation system for presentation | 2-3 weeks |
| **Node-Based Pipeline Editor** | Mosaic | Python: visual editor for filter chain composition | 4+ weeks |

### Architecture Improvements Inspired by OF

| Pattern | Source | Benefit |
|---------|--------|---------|
| **Lazy buffer allocation (imitate)** | ofxCv | Avoid numpy reallocation when frame size unchanged |
| **Ping-Pong Buffer utility** | ofxFX / ofxFluid | Enable multi-pass GPU effects without frame copies |
| **Decoupled detection/tracking** | ofxFaceTracker2 | Run detection every N frames; track every frame |
| **Effect chaining operator** | ofxFX `<<` operator | Fluent API for composing GPU filter chains |
| **Variable binding for UI** | ofxDatGui | Auto-generate Jupyter widgets from parameter schemas |
| **Plugin/addon discovery** | ofxaddons.com | Formal plugin registry for community-contributed filters |
| **FaceOSC-style data export** | ofxFaceTracker | Expose perception data via OSC for external tools |

---

## Sources

### Computer Vision
- [ofxCv](https://github.com/kylemcdonald/ofxCv) -- 666 stars
- [ofxFaceTracker](https://github.com/kylemcdonald/ofxFaceTracker) -- 1,400 stars
- [ofxFaceTracker2](https://github.com/HalfdanJ/ofxFaceTracker2) -- 213 stars

### Fluid/Flow Simulation
- [ofxFlowTools](https://github.com/moostrik/ofxFlowTools) -- 338 stars
- [ofxFluid](https://github.com/patriciogonzalezvivo/ofxFluid) -- 81 stars
- [ofxFX](https://github.com/patriciogonzalezvivo/ofxFX) -- 341 stars

### Physics/Particles
- [ofxBox2d](https://github.com/vanderlin/ofxBox2d) -- 327 stars
- [ofxBullet](https://github.com/NickHardeman/ofxBullet) -- 153 stars
- [ofxParticles](https://github.com/timscaffidi/ofxParticles) -- 20 stars
- [ofxFastParticleSystem](https://github.com/fusefactory/ofxFastParticleSystem) -- 34 stars

### Video Sharing
- [ofxSyphon](https://github.com/astellato/ofxSyphon) -- 198 stars
- [ofxSpout](https://github.com/elliotwoods/ofxSpout) -- 76 stars
- [ofxNDI](https://github.com/leadedge/ofxNDI) -- 149 stars

### Control Protocols
- [ofxMidi](https://github.com/danomatika/ofxMidi) -- 275 stars
- [ofxRemoteUI](https://github.com/armadillu/ofxRemoteUI)

### Shader/Post-Processing
- [ofxPostProcessing](https://github.com/neilmendoza/ofxPostProcessing) -- 351 stars
- [ofxDeferredShading](https://github.com/nama-gatsuo/ofxDeferredShading) -- 87 stars

### Animation
- [ofxTimeline](https://github.com/YCAMInterlab/ofxTimeline) -- 277 stars

### Depth Cameras
- [ofxAzureKinect](https://github.com/prisonerjohn/ofxAzureKinect) -- 74 stars

### Machine Learning
- [ofxTensorFlow2](https://github.com/zkmkarlsruhe/ofxTensorFlow2) -- 119 stars
- [ofxOnnxRuntime](https://github.com/hanasaan/ofxOnnxRuntime)

### Audio
- [ofxAudioAnalyzer](https://github.com/leozimmerman/ofxAudioAnalyzer) -- 189 stars

### Creative Coding
- [ofxSlitScan](https://github.com/obviousjim/ofxSlitScan) -- 37 stars
- [ofxDelaunay](https://github.com/obviousjim/ofxDelaunay)
- [ofxAChaosLib](https://github.com/s373/ofxAChaosLib) -- 18 stars
- [ofxRD](https://github.com/aanrii/ofxRD) -- 15 stars
- [ofxVoronoi](https://github.com/madc/ofxVoronoi)

### GUI/Platforms
- [ofxDatGui](https://github.com/braitsch/ofxDatGui) -- 440 stars
- [Mosaic](https://github.com/d3cod3/Mosaic) -- 499 stars

### Video Playback
- [ofxHapPlayer](https://github.com/bangnoise/ofxHapPlayer) -- 158 stars

### Notable Projects
- [FaceSubstitution](https://github.com/arturoc/FaceSubstitution)
- [SonicSculpture](https://github.com/laserpilot/SonicSculpture)

### Architecture Documentation
- [ofBook - How openFrameworks works](https://openframeworks.cc/ofBook/chapters/how_of_works.html)
- [ofBook - Threads](https://openframeworks.cc/ofBook/chapters/threads.html)
- [ofBook - Shaders](https://openframeworks.cc/ofBook/chapters/shaders.html)
- [OF Events Documentation](https://openframeworks.cc/documentation/events/)
- [OF Multi-Window Blog Post](https://blog.openframeworks.cc/post/133404337264/openframeworks-090-multi-window-and-ofmainloop)
- [ofxaddons.com](https://ofxaddons.com)
- [openFrameworks Gallery](https://openframeworks.cc/gallery/)
