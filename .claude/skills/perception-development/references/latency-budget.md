# Perception Latency Budget

Target: 30 FPS = 33.3ms per frame on laptop CPU.

## Per-Stage Budgets

| Stage | Budget | Notes |
|---|---|---|
| Capture | 2ms | Camera read |
| **Analysis (all)** | **15ms** | All analyzers combined |
| **Single analyzer** | **5ms** | Max per individual analyzer |
| Tracking | 2ms | Operates on analysis dict |
| Transform | 2ms | Spatial warps |
| Filtering (all) | 5ms | All filters combined |
| Rendering | 3ms | Frame -> RenderFrame |
| Output | 3ms | Write to sink |
| Overhead | 1.3ms | Event bus, profiling |

## Measurement

- Python: `time.perf_counter()` (NOT `time.time()`)
- C++: `std::chrono::steady_clock`
- Profile with `LoopProfiler` in infrastructure

## Degradation Strategy (mandatory order)

When budget exceeded:
1. Skip perception on alternating frames
2. Disable tracking
3. Reduce inference resolution
4. Disable non-essential filters
5. Reduce target FPS

## Model Latency Requirements

- New AI models MUST fit within 5ms single-analyzer budget
- If exceeds 5ms, document exception and justify
- NEVER exceed 20ms on CPU
- Current YOLOv8n-pose: ~15-25ms (documented exception, uses frame skipping)
