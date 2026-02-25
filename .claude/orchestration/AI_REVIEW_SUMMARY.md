# Multi-AI Architecture Review — Summary

> Cross-analysis of assessments from **ChatGPT**, **DeepSeek**, and **Claude Code** (working session).
> Based on the briefing document `BRIEFING_MULTI_AI.md` sent to all three.
> Date: 2025-02 (reviews) / 2026-02-24 (summary + Claude working session)

---

## Quick Consensus

All three AIs agree on these core points:

1. **The project has strong architectural discipline** — hexagonal architecture is well-implemented
2. **Scope is the #1 risk** — 20 features + 17 agents + real-time constraints = execution risk
3. **33.3ms budget is unrealistic** with 5+ ONNX models running simultaneously
4. **BGR-everywhere is a net negative** — the ecosystem (ONNX, PIL, web) is RGB-native
5. **Multi-agent parallel development is high-risk** without strict interface contracts
6. **Config persistence and async perception are the most impactful quick wins**

---

## A. Architecture & Design

### A1. Hexagonal Architecture — Right Choice?

| Aspect | ChatGPT | DeepSeek | Claude (session) |
|--------|---------|----------|-------------------|
| Verdict | Keep, but add internal dataflow graph | Keep for high layers, add ECS-lite internally | Keep — proven working, don't over-engineer |
| Key gain | Strict separation, testability, easy adapter extension | Maintainability, clear contracts | Adapter addition without touching application layer |
| Key loss | No inherent parallelism model | Indirection overhead, cross-component optimization difficulty | Pipeline rigidity for preprocessing |
| Alternative suggested | Lightweight graph executor inside Application | ECS-lite: frames as components, processors as systems | None — prioritize fixing what's broken first |

**Consensus**: Hexagonal stays. Internally, the pipeline could evolve toward a graph/ECS model for parallelism, but only after core features work correctly.

### A2. Immutable Pipeline Order

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Verdict | Make stage GROUPS immutable, allow intra-group ordering | Evolve to declarative processing graph with dependency declarations |
| Key concern | Can't denoise before perception | Same — plus can't parallelize render+output |
| Solution | Declarative stage registry with priority levels | Components declare dependencies, engine optimizes order |

**Consensus**: Stage groups (Source → Perception → Transform → Filter → Render → Output) stay fixed. Allow optional pre-perception filters and intra-group reordering.

### A3. Single-Threaded Execution

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Recommendation | Dedicated perception thread + double buffering | 3-stage pipeline: capture → perception → post-proc |
| Expected gain | Decouple inference from render latency | +50% throughput, +1 frame latency |
| Complexity cost | Moderate (one extra thread) | Higher (lock-free queues, 3 threads) |

**Consensus**: Async perception in a separate thread is the #1 performance improvement. Both suggest double-buffering with latest-result semantics.

### A4. BGR Everywhere

| | ChatGPT | DeepSeek | Claude (session) |
|---|---------|----------|-------------------|
| Verdict | Switch to RGB | Switch to RGB | Fixed BGR→RGB in C++ ONNX runner; face.py uses BGR directly (FaceDetectorYN accepts it) |
| Cost of BGR | ~78MB/s in conversions at 30fps | ~180MB/s at 1080p | Measurable — was causing broken model outputs |
| Migration | Convert once at camera source | Same — one-time cost at input | Partial — C++ now converts, Python face accepts BGR |

**Consensus**: Long-term, standardize on RGB. Short-term, convert at source. The C++ BGR→RGB fix in this session was critical — models were receiving wrong color channels.

---

## B. Performance & Latency

### B5. 33.3ms Budget Realism

| Model | ChatGPT estimate | DeepSeek estimate |
|-------|------------------|-------------------|
| Face landmarks | 5-8ms | 4ms (MediaPipe) |
| Hand landmarks | 5-8ms | — |
| Pose | 5-8ms | — |
| YOLOv8 (CPU) | 12-20ms | 15-25ms |
| Segmentation | 8-15ms | 12ms (Deeplab) |
| **Combined total** | **35-55ms** | **31ms minimum (no filters)** |

**Consensus**: Running all analyzers simultaneously at 30fps is **not feasible on CPU**.

**Agreed solutions**:
- Run heavy analyzers at lower frequency (10-15 FPS)
- Async perception thread (decouple from render)
- Cache and interpolate results between frames
- Analyzer prioritization (not all run every frame)

### B6. GIL Limitations

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Bottleneck threshold | When >2-3 heavy stages active | When Python processing >8ms/frame |
| Current status | Not yet bottleneck if C++ releases GIL | Acceptable (~12-15ms Python = 30-45% one core) |
| Future risk | High-frequency EventBus + per-frame allocations | Event bus + logging should move to separate thread |

**Consensus**: GIL is not the current bottleneck, but will become one as more Python-side processing is added. Solution: keep orchestration in Python, move hot paths to C++.

### B7. Frame Copy Budget

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Real cost | 7 filters × 2.6MB = 18MB/frame = 540MB/s | 7 filters × 6MB (1080p) = 42MB/frame = 1.26GB/s |
| "Zero-copy" claim | "Fooling ourselves" | "Illusory" |
| Solution | Shared mutable frame buffer, frame pool allocator | C++ filter chain with in-place operations |

**Consensus**: The zero-copy claim is aspirational, not real. With multiple active filters, memory bandwidth becomes the bottleneck before CPU compute.

---

## C. Development Strategy

### C8. Multi-Agent Risk

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Risk level | High coordination risk | High incoherence risk |
| Top concerns | API drift, semantic misunderstandings, inconsistent coding | Utility duplication, conflicts in shared files, no human review |
| Max concurrent | Not specified | 5-6 agents |
| Key mitigation | Strict interface contracts + automated CI + human checkpoints | Reduce to 3-4 leads, human-in-the-loop for merges |

**Claude session experience**: The orchestration system (17 agents, 8 teams) exists but hasn't been launched. The perception fixes were done directly in this session — more effective than multi-agent approach for targeted bug fixing.

### C9. Team Decomposition

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Current model | Domain-based (perception team, filters team) | Same observation |
| Missing | Cross-cutting concerns team | Same — error handling, testing, init integration |
| Alternative | Add "Quality & Integration" team | Vertical feature teams (e.g., "hand tracking" owns perception + filter + renderer) |

**Consensus**: Domain teams are logical but cross-cutting concerns are orphaned. Need either a dedicated integration team or vertical feature slices.

### C10. Merge Order

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Risk | Downstream teams blocked by upstream | Sequential = brittle + idle time |
| Solution | Publish interface contracts first, use stubs | Trunk-based development with feature flags |

**Consensus**: Define interfaces/stubs upfront. Don't wait for full implementation before downstream teams start.

---

## D. Feature Prioritization

### Top 5 Features (Combined Ranking)

| Rank | ChatGPT | DeepSeek | Overlap |
|------|---------|----------|---------|
| 1 | Hand Gesture Classifier | RTSP Streaming | — |
| 2 | Heatmap Overlay | Config Persistence | Config in both top 3 |
| 3 | RTSP Streaming | Hand Gesture Classifier | Gesture + RTSP in both |
| 4 | Config Persistence | OSC Output | — |
| 5 | Optical Flow Visualization | Optical Flow Particles | Optical flow in both |

**Synthesized Top 5**:
1. **Config Persistence** — both rank it essential, small effort, foundational
2. **Hand Gesture Classifier** — both rank top 3, high demo impact, <1ms
3. **RTSP Streaming** — both rank top 3, real-world deployment enabler
4. **OSC Output** — connects to VJ ecosystem (TouchDesigner, Max/MSP)
5. **Optical Flow** (particles or visualization) — visually impressive, good demo

### Missing Features Identified

| Feature | ChatGPT | DeepSeek |
|---------|---------|----------|
| Audio reactivity | Yes | Yes (critical for VJs) |
| MIDI input | — | Yes (essential for live performance) |
| Multi-camera compositing | Yes | Yes |
| Recording with timeline | Yes | Yes (replay last 30 seconds) |
| GPU acceleration path | Yes | Yes (GLSL shader support) |
| Undo/redo parameter stack | Yes | — |
| Web remote control | — | Yes (REST API) |
| Parameter automation (LFO) | — | Yes |

### Physarum & Boids

**Both agree**: Premature. Cool but complex. Should be Wave 3 after infrastructure, connectivity, and reliability features are solid.

---

## E. Strategic Perspective

### Target User

| | ChatGPT | DeepSeek |
|---|---------|----------|
| Primary | Creative coders / technical artists | Creative coders / generative artists |
| Secondary | — | VJs who adapt via OSC |
| Concern | — | "Identity confusion" between researcher/VJ/coder |

**Consensus**: Primary audience is **creative coders who know Python** and want programmable video with AI. Design API for this audience first.

### Unique Value Proposition

**Both agree**: "Python-native, AI-first, real-time pipeline with notebook-based control and strict architectural modularity." No existing tool offers this exact combination.

### Technology Choice (Python + C++)

**Both agree**: Keep Python + C++ for now. The pybind11 bridge is acceptable. Reevaluate only if orchestration overhead becomes dominant. Consider pre-built wheels for distribution.

---

## Top Risks (Combined)

| # | Risk | ChatGPT | DeepSeek |
|---|------|---------|----------|
| 1 | **Scope explosion** | Yes — across architecture, AI, plugins, orchestration | Yes — 20 features + 3 waves is massive |
| 2 | **Performance wall** | Yes — multiple heavy analyzers collapse budget | Yes — demo-only without major optimization |
| 3 | **Multi-agent integration failure** | Yes — parallel development without review | Yes — code quality will vary wildly |

## Top Quick Wins (Combined)

| # | Quick Win | ChatGPT | DeepSeek | Effort |
|---|-----------|---------|----------|--------|
| 1 | **Config persistence** | Yes | Yes | S (1 day) |
| 2 | **Async perception thread** | Yes | — | M (3 days) |
| 3 | **Automated CI** (lint + tests) | Yes | — | M (2 days) |
| 4 | **OSC output** | — | Yes | S (2 days) |
| 5 | **Profiler dashboard** | — | Yes | M (3 days) |

---

## Claude Code Session — What Was Actually Done (2026-02-24)

While ChatGPT and DeepSeek provided strategic analysis, this Claude session **fixed the broken perception pipeline**:

### Bugs Found & Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Face detection only in center | Full frame fed to landmark model (expects cropped face) | Rewrote `face.py` → `cv2.FaceDetectorYN` with YuNet model |
| Hand detection broken | Full frame fed to landmark model (expects cropped hand) | Rewrote `hands.py` → `mediapipe.solutions.hands` |
| Pose keypoints on diagonal | C++ ONNX runner: BGR channels not swapped + YOLOv8 output not transposed | Fixed `onnx_runner.cpp`: BGR→RGB swap + transpose detection |
| Pose confidence too strict | Threshold 0.5 missed valid detections (YOLOv8 outputs ~0.25-0.5 for drawings) | Lowered to 0.25 (YOLOv8 standard) |

### Verified Results

| Analyzer | Test Image | Result |
|----------|-----------|--------|
| Pose | Vitruvian Man (drawing) | 17/17 keypoints, correctly positioned |
| Pose | Bus photo (real people) | 17/17 keypoints, skeleton aligned perfectly |
| Pose | Hands photo (half body) | 13/17 (legs out of frame = correctly ZERO) |
| Face | All test images | Bounding box + 5 landmarks correct, even on drawings |
| Face | Confidence | 0.867 (drawing) to 0.942 (photo) |

### Key Insight

The strategic reviews from ChatGPT/DeepSeek are valuable for roadmap planning, but the **immediate blocker was that perception didn't work at all**. Face and hand analyzers were architecturally wrong (feeding full frames to crop-expecting models), and the C++ runner had two preprocessing bugs. These had to be fixed before any feature expansion makes sense.

---

## Actionable Next Steps (Prioritized)

Based on all three AI reviews + working session findings:

### Immediate (This Week)
- [x] Fix perception pipeline (face, hands, pose) — **DONE**
- [ ] Config persistence (JSON save/load) — both AIs rank #1 quick win
- [ ] Automated CI (lint + tests on commit) — prevent regression

### Short-term (Next 2 Weeks)
- [ ] Async perception thread with double buffering
- [ ] Hand gesture classifier (rule-based from landmarks, <1ms)
- [ ] OSC output (connect to VJ ecosystem)
- [ ] Profiler dashboard (real-time latency breakdown)

### Medium-term (Month)
- [ ] RTSP streaming output
- [ ] RGB standardization (convert at source, not at every stage)
- [ ] Optical flow filter (particles or visualization)
- [ ] Heatmap overlay renderer

### Strategic Decisions Needed
- [ ] Decide primary target user (creative coder vs VJ vs researcher)
- [ ] Decide on async architecture (1 thread vs 3-stage pipeline)
- [ ] Decide on multi-agent strategy (17 agents vs 3-4 focused leads)
- [ ] Define strict interface contracts before any parallel development

---

## Skills Impact

The current `.claude/skills/` may need updates based on these findings:

1. **perception-development**: Now uses `cv2.FaceDetectorYN` and `mediapipe` instead of C++ for face/hands. Skill should reflect new dependencies and patterns.
2. **filter-development**: Frame copy budget is a real concern. Skill should enforce in-place operations where possible.
3. **output-development**: RTSP and OSC are top priorities. Skill should include streaming patterns.
4. **infrastructure-development**: Config persistence and async perception are next. Skill should cover threading model.
5. **All skills**: BGR→RGB decision pending. If standardized to RGB, all skills need updating.
