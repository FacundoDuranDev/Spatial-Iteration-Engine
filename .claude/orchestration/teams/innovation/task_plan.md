# Innovation Team — Task Plan

> **Branch:** `feature/innovation-roadmap`
> **Skill Reference:** All skills (cross-domain research)
> **Team Size:** 6 agents

## Team Roles

| # | Role | Responsibility |
|---|------|---------------|
| 1 | Strategic Researcher | Survey all extension opportunities, rank by effort/impact |
| 2 | Filters Specialist | 5 filter proposals with algorithms, latency estimates |
| 3 | Perception Specialist | 5 analyzer proposals with ONNX model specs, dict schemas |
| 4 | Output Specialist | 3 output proposals with protocol details, dependency analysis |
| 5 | Renderer Specialist | 2 renderer proposals with visualization techniques |
| 6 | Systems Architect | 5 infrastructure proposals + organize all 20 into 3 waves |

---

## Phase 1: Codebase Survey & Opportunity Identification

**Owner:** Strategic Researcher
**Duration:** 2-3 hours
**Status:** Not Started

### Tasks

- [ ] Read all 6 SKILL.md files to understand each domain's extension points
- [ ] Read `rules/ARCHITECTURE.md` to understand system boundaries
- [ ] Read `rules/PIPELINE_EXTENSION_RULES.md` for extension patterns
- [ ] Read `rules/LATENCY_BUDGET.md` for performance constraints
- [ ] Read `rules/AI_MODEL_INTEGRATION_RULES.md` for model onboarding process
- [ ] Read `rules/MODEL_REGISTRY.md` for existing models
- [ ] Survey existing adapters in each domain:
  - `adapters/processors/filters/` — count and list existing filters
  - `adapters/perception/` — count and list existing analyzers
  - `adapters/renderers/` — count and list existing renderers
  - `adapters/outputs/` — count and list existing outputs
  - `infrastructure/` — count and list existing services
  - `presentation/` — count and list existing panels
- [ ] Identify gaps: what's missing, what's incomplete, what could be enhanced
- [ ] Create initial opportunity list (target: 30+ raw ideas)
- [ ] Write initial survey to `findings.md`

### Deliverables
- `findings.md` updated with codebase survey results
- Raw opportunity list with 30+ ideas
- `progress.md` updated

### Acceptance Criteria
- Every existing component catalogued
- Gaps identified per domain
- No invented architecture (only extensions within existing patterns)

---

## Phase 2: Filter Proposals (5 Proposals)

**Owner:** Filters Specialist
**Duration:** 3-4 hours
**Status:** Not Started

### Tasks

- [ ] Study existing filter patterns: base.py, feedback.py, kaleidoscope.py, cpp_invert.py
- [ ] Identify filter categories not yet covered:
  - Particle systems (no existing particle filter)
  - Artistic rendering (no stippling/pointillism)
  - Mathematical warps (limited displacement options)
  - Simulation-based (no agent-based simulations)
  - Edge-based effects (limited edge processing)
- [ ] Write 5 detailed proposals:

#### Proposal 1: Optical Flow Particles
- Algorithm: Dense optical flow → particle advection
- Category: Stateful particle system
- Estimated latency: 3-8ms Python, 1-3ms C++
- C++ required: optional but recommended for particle update
- Analysis dict usage: optional (pose joints as attractors)

#### Proposal 2: Stippling / Pointillism
- Algorithm: Poisson disk sampling weighted by luminance
- Category: LUT-cached (dot positions)
- Estimated latency: 2-4ms
- C++ required: no
- Pure Python with OpenCV drawing

#### Proposal 3: UV Math Displacement
- Algorithm: Mathematical UV displacement + cv2.remap
- Category: LUT-cached (remap tables)
- Estimated latency: 1-3ms
- Multiple modes: wave, spiral, vortex, radial

#### Proposal 4: Edge-Aware Smoothing
- Algorithm: cv2.bilateralFilter + optional Canny overlay
- Category: Simple (no state, no LUT)
- Estimated latency: 2-5ms
- Lightweight, good for painterly effects

#### Proposal 5: Radial Collapse / Singularity
- Algorithm: Polar coordinate radial compression + cv2.remap
- Category: LUT-cached (remap table), analysis-reactive
- Estimated latency: 1-3ms
- Can use face/hand positions as attractor points

- [ ] For each proposal: document algorithm, parameters, file paths, latency estimate, risks
- [ ] Write proposals to `INNOVATION_ROADMAP.md`

### Deliverables
- 5 filter proposals in INNOVATION_ROADMAP.md
- Algorithm descriptions with pseudocode
- Latency estimates validated against 5ms combined budget

### Acceptance Criteria
- Each proposal follows filter extension rules (BaseFilter, copy semantics, registration)
- Latency estimates realistic for CPU-only execution
- C++ need assessed honestly (only for genuinely heavy computation)

---

## Phase 3: Perception Proposals (5 Proposals)

**Owner:** Perception Specialist
**Duration:** 3-4 hours
**Status:** Not Started

### Tasks

- [ ] Study existing analyzers: face.py, hands.py, pose.py, and C++ runners
- [ ] Study ONNX model integration rules and MODEL_REGISTRY.md
- [ ] Research available lightweight ONNX models for each proposal
- [ ] Write 5 detailed proposals:

#### Proposal 6: Hand Gesture Classifier
- Approach: Geometric analysis of existing hand landmarks (no new model)
- Gestures: open_palm, fist, peace, thumbs_up, pointing, pinch
- Dict key: `analysis["gesture"]`
- Latency: <1ms (pure geometry, no inference)

#### Proposal 7: Object Detection (YOLOv8-nano)
- Model: yolov8n.onnx (6.2MB, 640x640 input)
- Dict key: `analysis["objects"]`
- Post-processing: NMS, bbox normalization
- Latency: 12-18ms (exceeds budget — needs frame skipping)

#### Proposal 11: Emotion Detection
- Model: emotion-ferplus.onnx (~1MB, 48x48 grayscale)
- Depends on: face analyzer (crop face region)
- Dict key: `analysis["emotion"]`
- Latency: 2-4ms

#### Proposal 12: Body Pose with Skeleton
- Approach: Post-processing existing pose output (no new model)
- Adds: confidence scores, connection pairs, body part groups
- Dict key: `analysis["pose"]` (extended)
- Latency: <1ms additional

#### Proposal 18: Scene Segmentation
- Model: PP-HumanSeg or SINet (~5MB, 256x256 input)
- Dict key: `analysis["segmentation"]`
- Outputs: class mask, person mask, confidence map
- Latency: 8-15ms (needs frame skipping)

- [ ] For each: document ONNX model spec, dict schema, file paths, latency
- [ ] Verify models exist and are available for download
- [ ] Document degradation strategy for heavy models

### Deliverables
- 5 analyzer proposals in INNOVATION_ROADMAP.md
- Complete analysis dict schema for each
- Model registry entries for ONNX models
- Download/verification plan for each model

### Acceptance Criteria
- Dict schemas follow existing pattern (analyzer name as key, 0-1 coords)
- Models documented with input/output shapes, size, source
- Latency estimates include degradation strategy for >5ms models

---

## Phase 4: Output & Renderer Proposals (5 Proposals)

**Owner:** Output Specialist + Renderer Specialist
**Duration:** 3-4 hours
**Status:** Not Started

### Tasks

#### Output Specialist — 3 Proposals

- [ ] Study existing outputs: udp_sink.py, notebook_sink.py, rtsp/, webrtc/, ndi/
- [ ] Assess completeness of existing partial implementations
- [ ] Write 3 proposals:

##### Proposal 8: RTSP Streaming
- Approach: Complete existing FfmpegRtspSink
- Protocol: ffmpeg subprocess, H.264 encoding
- Missing: is_open(), get_capabilities(), proper close()
- Latency: 2-3ms (pipe write)

##### Proposal 15: WebRTC Peer
- Approach: Complete existing WebRTCOutput
- Library: aiortc
- Missing: deprecated asyncio patterns, proper cleanup
- Latency: 1-2ms (handoff), ~50ms end-to-end

##### Proposal 16: OSC Output
- Approach: New sink, sends analysis data as OSC messages
- Library: python-osc
- Unique: transmits data, not video
- Latency: <1ms (UDP send)

#### Renderer Specialist — 2 Proposals

- [ ] Study existing renderers: ascii_renderer.py, passthrough_renderer.py, landmarks_overlay.py
- [ ] Write 2 proposals:

##### Proposal 9: Heatmap Overlay
- Approach: Decorator renderer, accumulates detection density
- Uses: analysis dict positions → Gaussian-blurred density → colormap
- Latency: 1-2ms

##### Proposal 19: Optical Flow Visualization
- Approach: Compute Farneback flow, visualize as HSV/arrows/streamlines
- Stateful: maintains previous frame
- Latency: 3-8ms (downsample 2x for flow)

### Deliverables
- 3 output proposals in INNOVATION_ROADMAP.md
- 2 renderer proposals in INNOVATION_ROADMAP.md
- Protocol specifications for streaming outputs
- Dependency analysis (aiortc, python-osc availability)

### Acceptance Criteria
- Output proposals follow OutputSink protocol exactly
- Renderer proposals follow FrameRenderer protocol exactly
- External dependencies documented with fallback strategy

---

## Phase 5: Infrastructure Proposals (5 Proposals)

**Owner:** Systems Architect
**Duration:** 3-4 hours
**Status:** Not Started

### Tasks

- [ ] Study existing infrastructure: event_bus.py, profiling.py, metrics.py, plugins/
- [ ] Identify infrastructure gaps and enhancement opportunities
- [ ] Write 5 proposals:

#### Proposal 10: Config Persistence
- Thread-safe JSON save/load with atomic writes
- Schema versioning, migration on load
- Location: infrastructure/config_persistence.py

#### Proposal 17: Plugin Hot-Reload Improvement
- Fix time.time() violation, add dependency ordering
- Batch reload with collection window
- Cascade reload for dependent plugins

#### Proposal 20: Web Dashboard
- stdlib http.server (no dependencies)
- JSON API: /api/metrics, /api/budget, /api/health
- Optional MJPEG stream at /stream
- Daemon thread, zero pipeline impact

#### Proposal (bonus): Enhanced EventBus
- Priority subscriptions, wildcard matching
- Event filtering (rate limit, dedup)
- Bounded replay buffer
- Backward compatible

#### Proposal (bonus): Distributed Metrics
- UDP-based metrics aggregation from multiple instances
- Compact JSON wire format
- Bounded collection (20 instances, deque(maxlen=100))

- [ ] Organize all 20 proposals into 3 implementation waves
- [ ] Define dependency graph between proposals
- [ ] Estimate total effort across all waves

### Deliverables
- 5 infrastructure proposals in INNOVATION_ROADMAP.md
- Wave organization (3 waves) with dependency rationale
- Complete dependency graph
- Total effort summary

### Acceptance Criteria
- No imports from adapters/engine/pipeline (domain-only deps)
- All collections bounded
- Thread safety documented
- Wave ordering respects dependencies

---

## Phase 6: Cross-Domain Integration Analysis

**Owner:** Strategic Researcher + Systems Architect
**Duration:** 2-3 hours
**Status:** Not Started

### Tasks

- [ ] Map all cross-proposal dependencies:
  - Which filters need which analyzer outputs?
  - Which renderers need which analysis data?
  - Which outputs need which infrastructure?
- [ ] Identify shared patterns across proposals:
  - Optical flow used by both filter [1] and renderer [19]
  - Analysis dict consumed by filters [1, 5], renderers [9], outputs [16]
  - Config persistence [10] used by dashboard [20] and preset manager
- [ ] Assess overall system impact:
  - Memory footprint of all 20 proposals combined
  - CPU budget with all proposals active simultaneously
  - Which proposals are mutually exclusive (can't all run at once)
- [ ] Define recommended configurations:
  - "Artistic" mode: filters [1, 2, 3, 5] + basic analyzers
  - "Analysis" mode: analyzers [6, 7, 11, 12] + heatmap renderer
  - "Performance" mode: minimal filters + frame skipping
  - "Broadcast" mode: RTSP [8] + NDI + recorder
- [ ] Write integration analysis to findings.md

### Deliverables
- Cross-proposal dependency map
- System impact assessment
- Recommended configuration profiles
- Updated findings.md

### Acceptance Criteria
- Every cross-proposal dependency identified
- CPU/memory impact estimated
- No unrealistic "all at once" assumptions

---

## Phase 7: Final Roadmap & PR Preparation

**Owner:** All team members
**Duration:** 2-3 hours
**Status:** Not Started

### Tasks

- [ ] Finalize INNOVATION_ROADMAP.md with all 20 proposals
- [ ] Verify all proposals have:
  - [ ] Effort rating (S/M/L)
  - [ ] Impact rating (1-5)
  - [ ] Wave assignment (1/2/3)
  - [ ] File paths for implementation
  - [ ] Latency estimates
  - [ ] Dependency list
  - [ ] Risk assessment
- [ ] Add summary matrix (20 rows, all fields)
- [ ] Add dependency graph (text-based)
- [ ] Add effort summary (total days, per domain)
- [ ] Update progress.md with final status
- [ ] Update findings.md with final cross-domain analysis
- [ ] Run spell check and formatting review
- [ ] Create PR to develop with:
  - Title: "feat(innovation): 20 architecture extension proposals"
  - Body: summary table + wave overview

### Deliverables
- Final INNOVATION_ROADMAP.md (20 proposals, 3 waves)
- Final findings.md (cross-domain analysis)
- Final progress.md (all phases complete)
- PR ready for review

### Acceptance Criteria
- Exactly 20 proposals, no more, no less
- 3 waves with clear dependency ordering
- Every proposal actionable (team can start implementing from the proposal alone)
- No proposals that require architecture changes not in rules/

---

## File Inventory

### New Files
| File | Phase | Description |
|------|-------|-------------|
| `.claude/orchestration/INNOVATION_ROADMAP.md` | 2-5, 7 | Main deliverable |
| `.claude/orchestration/teams/innovation/progress.md` | All | Status tracking |
| `.claude/orchestration/teams/innovation/findings.md` | 1, 6 | Research results |

### Read-Only Reference Files
| File | Purpose |
|------|---------|
| `.claude/skills/*/SKILL.md` | Domain contracts |
| `rules/ARCHITECTURE.md` | System boundaries |
| `rules/PIPELINE_EXTENSION_RULES.md` | Extension patterns |
| `rules/LATENCY_BUDGET.md` | Performance constraints |
| `rules/AI_MODEL_INTEGRATION_RULES.md` | Model onboarding |
| `rules/MODEL_REGISTRY.md` | Existing models |
| `rules/PERFORMANCE_RULES.md` | Performance rules |

---

## Phase Dependencies

```
Phase 1 (Survey) ─────────────────────────────┐
    │                                          │
    ├── Phase 2 (Filters) ──────┐              │
    ├── Phase 3 (Perception) ───┤              │
    ├── Phase 4 (Outputs+Rend) ─┤              │
    └── Phase 5 (Infra) ────────┤              │
                                │              │
                                ▼              ▼
                          Phase 6 (Integration Analysis)
                                │
                                ▼
                          Phase 7 (Final Roadmap + PR)
```

Phases 2-5 are **fully parallelizable** after Phase 1 completes.
