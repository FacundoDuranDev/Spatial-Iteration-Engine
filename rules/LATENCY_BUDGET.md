# Latency Budget

Target: **30 FPS = 33.3 ms per frame budget** on a modern laptop CPU (no dedicated GPU).

---

## Per-Stage Budget

| Stage | Budget (ms) | p95 Max (ms) | Notes |
|---|---|---|---|
| Capture | 2.0 | 5.0 | Camera read via OpenCV |
| Analysis (all combined) | 15.0 | 20.0 | All analyzers combined |
| -- Single analyzer | 5.0 | 8.0 | Face, Hands, or Pose individually |
| Tracking | 2.0 | 3.0 | If enabled |
| Transformation | 2.0 | 4.0 | Spatial warps |
| Filtering (all combined) | 5.0 | 8.0 | All active filters combined |
| Rendering | 3.0 | 5.0 | Frame -> RenderFrame |
| Output | 3.0 | 5.0 | Write to sink |
| Overhead | 1.3 | 2.0 | GIL, scheduling, event bus |
| **TOTAL** | **33.3** | **50.0** | |

---

## Measurement Protocol

- Python: `time.perf_counter()`. Never `time.time()`.
- C++: `std::chrono::steady_clock`. Never `clock()`.
- The existing `LoopProfiler` in `infrastructure/profiling.py` tracks phases: capture, analysis, transformation, filtering, rendering, writing.
- When adding a new stage, MUST register it as a phase in LoopProfiler.

---

## Degradation Strategy

When the system cannot meet the latency budget, apply these mitigations **in order**:

1. **Skip perception on alternating frames** -- Run analyzers every 2nd frame, reuse last analysis result.
2. **Disable tracking** -- Reduces analysis overhead.
3. **Reduce inference resolution** -- Lower `NeuralConfig.inference_resolution`.
4. **Disable non-essential filters** -- Keep only critical filters active.
5. **Reduce target FPS** in `EngineConfig`.

This degradation order is mandatory. Do not implement ad-hoc frame dropping or stage skipping outside of this hierarchy.

---

## Budget for New Filters

When adding a new filter, it MUST fit within the 5ms combined filter budget. Guidelines:

| Filter type | Expected cost | Example |
|---|---|---|
| LUT-based (precomputed) | <0.5ms | Posterize, Color LUT, Vignette |
| Simple pixel operation | <1ms | Invert, Brightness, Feedback blend |
| Remap-based (precomputed LUT) | 1-3ms | Chromatic aberration, Kaleidoscope, Barrel distortion |
| Convolution-based | 2-5ms | Edge glow, Blur, Sharpen |
| Stateful simulation | 3-10ms | Particles, Reaction-diffusion (run at lower resolution) |

If a filter exceeds 5ms alone, it MUST either:

- Run at reduced resolution and upscale the result
- Be implemented in C++ with SIMD/OpenMP
- Be documented as "heavy" and excluded from the default filter set

---

## Budget for New AI Models

A new AI model added to the analysis stage MUST:

- Measure and document its CPU inference latency at the target input resolution
- Fit within the 5ms single-analyzer budget, OR
- Document why it exceeds the budget and what degradation strategy applies
- Never exceed 20ms on CPU at the default resolution
