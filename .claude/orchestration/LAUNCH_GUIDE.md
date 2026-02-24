# Launch Guide — Multi-Team Agent Orchestration

> How to start, monitor, and review the 8-team autonomous development system.

---

## Prerequisites

1. **Conda activated**: `conda activate spatial-iteration-engine`
2. All orchestration files exist: `ls -R .claude/orchestration/`
3. All 8 branches created: `git branch | grep -E "(orchestration/|feature/.*-extensions|feature/innovation)"`
4. `develop` branch is up to date: `git fetch origin develop`
5. Tests pass on develop: `make check`
6. C++ modules built: `make cpp-build` (requires conda active)

### Critical Environment Rule

**Every team agent MUST run `conda activate spatial-iteration-engine` at the start of its session.** Without it, C++ builds fail, tests fail, and imports fail. This is the #1 cause of agent blocking.

### Shared Rules

Every team prompt includes a reference to `.claude/skills/shared/AGENT_RULES.md`. This file contains:
- Build environment setup (conda, PYTHONPATH, make commands)
- Anti-blocking protocol (escalate after 10 min, never spin)
- Communication protocol (progress.md, findings.md)
- Git workflow (conventional commits, branch discipline)
- Performance budgets (33.3ms frame budget)

---

## Team Overview

| # | Team | Branch | Agents | Skill |
|---|------|--------|--------|-------|
| 1 | Coordination | `orchestration/coordination` | 6 | — (reads all skills) |
| 2 | Perception | `feature/perception-extensions` | 6 | `perception-development` |
| 3 | Filters | `feature/filter-extensions` | 6 | `filter-development` |
| 4 | Renderers | `feature/renderer-extensions` | 6 | `renderer-development` |
| 5 | Outputs | `feature/output-extensions` | 6 | `output-development` |
| 6 | Infrastructure | `feature/infra-extensions` | 6 | `infrastructure-development` |
| 7 | Presentation | `feature/presentation-extensions` | 6 | `presentation-development` |
| 8 | Innovation | `feature/innovation-roadmap` | 6 | — (cross-domain research) |

---

## Launch Order

### Phase A: Infrastructure & Innovation (Launch First)

These teams have no dependencies on other teams.

#### 1. Launch Innovation Team

```
Branch: feature/innovation-roadmap
```

**Prompt:**
```
You are the Innovation team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Research and document 20 architecture extension proposals organized into 3 waves.

Read your task plan: .claude/orchestration/teams/innovation/task_plan.md
Read the innovation roadmap template: .claude/orchestration/INNOVATION_ROADMAP.md
Read all skill files: .claude/skills/*/SKILL.md
Read architecture rules: rules/ARCHITECTURE.md, rules/PIPELINE_EXTENSION_RULES.md, rules/LATENCY_BUDGET.md

Use the Task tool to launch parallel research agents for each domain (filters, perception, outputs, renderers, infra).
Use Grep/Glob to survey existing code — count components, find patterns, identify gaps.
Read existing adapter implementations to understand real patterns (not just SKILL.md summaries).

Follow the 7 phases in your task plan sequentially.
Write status updates to: .claude/orchestration/teams/innovation/progress.md
Write research findings to: .claude/orchestration/teams/innovation/findings.md
Write proposals to: .claude/orchestration/INNOVATION_ROADMAP.md

If blocked for >10 min, write ESCALATION in progress.md and move to the next phase.
Do NOT modify any code files. This is a research-only team.
```

#### 2. Launch Infrastructure Team

```
Branch: feature/infra-extensions
```

**Prompt:**
```
You are the Infrastructure team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Build cross-cutting infrastructure enhancements (config persistence, enhanced EventBus, plugin hot-reload, performance dashboard, web dashboard).

Read your task plan: .claude/orchestration/teams/infrastructure/task_plan.md
Read your skill contract: .claude/skills/infrastructure-development/SKILL.md
Read existing implementations: infrastructure/event_bus.py, infrastructure/profiling.py, infrastructure/metrics.py
Read rules: rules/PERFORMANCE_RULES.md, rules/LATENCY_BUDGET.md

Use the Task tool to parallelize independent implementations (e.g., config persistence and enhanced EventBus can be built simultaneously).
Read existing code BEFORE writing new code — follow established patterns exactly.

Follow the 7 phases in your task plan sequentially.
Write status updates to: .claude/orchestration/teams/infrastructure/progress.md
Write API contracts to: .claude/orchestration/teams/infrastructure/findings.md

Key constraints:
- Dependencies: domain only (never import from adapters, engine, or pipeline)
- All public methods must be thread-safe
- Use time.perf_counter(), never time.time()
- Bound all collections (maxlen, max_samples)
- Run 'make check' before creating PR

If blocked for >10 min, write ESCALATION in progress.md and move to the next available phase.
```

### Phase B: Core Domain Teams (Launch After Infrastructure Starts)

These teams can run in parallel with each other.

#### 3. Launch Perception Team

```
Branch: feature/perception-extensions
```

**Prompt:**
```
You are the Perception team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Build new ONNX-based analyzers (hand gesture, object detection, emotion, pose skeleton, scene segmentation).

Read your task plan: .claude/orchestration/teams/perception/task_plan.md
Read your skill contract: .claude/skills/perception-development/SKILL.md
Read existing implementations: adapters/perception/face.py, adapters/perception/hands.py, adapters/perception/pose.py
Read the C++ runner pattern: cpp/src/perception/face_landmarks.cpp, cpp/src/bridge/pybind_perception.cpp
Read: rules/AI_MODEL_INTEGRATION_RULES.md, rules/MODEL_REGISTRY.md

Use the Task tool to parallelize: e.g., Python implementations for gesture + emotion + object detection can be built simultaneously.
COPY existing patterns exactly — face.py is your template for Python, face_landmarks.cpp for C++.

Follow the 7 phases sequentially.
Write status updates to: .claude/orchestration/teams/perception/progress.md
Write API contracts (analysis dict schemas) to: .claude/orchestration/teams/perception/findings.md

Key constraints:
- Analyzers MUST NOT modify the frame
- Return {} on any failure (never raise)
- Coordinates normalized to 0-1
- C++ inference with py::gil_scoped_release for >0.1ms operations
- Python ImportError fallback for all C++ modules
- Single analyzer budget: 5ms, combined: 15ms

Publish analysis dict schemas to findings.md early — the Filters team depends on them.
If blocked for >10 min, write ESCALATION in progress.md and move to the next available phase.
```

#### 4. Launch Filters Team

```
Branch: feature/filter-extensions
```

**Prompt:**
```
You are the Filters team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Build new image filters (optical flow particles, stippling, UV displacement, edge smoothing, radial collapse, physarum, boids).

Read your task plan: .claude/orchestration/teams/filters/task_plan.md
Read your skill contract: .claude/skills/filter-development/SKILL.md
Read existing implementations: adapters/processors/filters/edges.py (Python pattern), adapters/processors/filters/cpp_invert.py (C++ wrapper pattern)
Read: adapters/processors/filters/base.py, adapters/processors/filters/conversion_cache.py
Read: rules/PIPELINE_EXTENSION_RULES.md, rules/LATENCY_BUDGET.md

Check perception team findings for analysis dict schemas: .claude/orchestration/teams/perception/findings.md

Use the Task tool to parallelize: independent Python filters (stippling, UV displacement, edge smooth) can be built simultaneously.
For C++ filters: conda activate spatial-iteration-engine && make cpp-build after each C++ addition.
COPY existing patterns exactly — edges.py for Python, cpp_invert.py for C++ wrappers.

Follow the 7 phases sequentially.
Write status updates to: .claude/orchestration/teams/filters/progress.md
Write findings to: .claude/orchestration/teams/filters/findings.md

Key constraints:
- Extend BaseFilter, never modify FilterPipeline
- No-op returns frame (same ref, 0 copies)
- Modification: frame.copy(order='C'), operate in-place
- Combined filter budget: 5ms
- Stateful filters: reset(), handle resolution changes
- LUT-cached filters: _params_dirty flag
- C++ for heavy filters (physarum mandatory)
- Register in __init__.py, never touch application/

If blocked for >10 min, write ESCALATION in progress.md and move to the next available phase.
```

#### 5. Launch Renderers Team

```
Branch: feature/renderer-extensions
```

**Prompt:**
```
You are the Renderers team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Build new renderers (heatmap overlay, optical flow viz, deformed grid, segmentation mask, multi-view).

Read your task plan: .claude/orchestration/teams/renderers/task_plan.md
Read your skill contract: .claude/skills/renderer-development/SKILL.md
Read existing implementations: adapters/renderers/passthrough_renderer.py (basic pattern), adapters/renderers/landmarks_overlay_renderer.py (overlay/decorator pattern)
Read: ports/renderers.py (FrameRenderer protocol), domain/types.py (RenderFrame dataclass)

Use the Task tool to parallelize: heatmap, optical flow, and segmentation mask renderers are independent.
COPY passthrough_renderer.py for basic renderers, landmarks_overlay_renderer.py for overlays.

Follow the 7 phases sequentially.
Write status updates to: .claude/orchestration/teams/renderers/progress.md
Write findings to: .claude/orchestration/teams/renderers/findings.md

Key constraints:
- Implement FrameRenderer protocol (output_size + render)
- Output: RenderFrame(image=PIL.Image.Image[RGB], text, lines, metadata)
- Color flow: BGR input → copy → draw → cvtColor BGR2RGB → PIL RGB
- Max 1 frame copy, latency budget: 3ms
- Analysis coords are 0-1, multiply by (w,h) for pixels
- Decorator pattern for overlays

Publish RenderFrame contracts to findings.md — the Outputs team depends on them.
If blocked for >10 min, write ESCALATION in progress.md and move to the next available phase.
```

#### 6. Launch Outputs Team

```
Branch: feature/output-extensions
```

**Prompt:**
```
You are the Outputs team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Complete and build output sinks (RTSP, WebRTC, OSC, video recorder, NDI).

Read your task plan: .claude/orchestration/teams/outputs/task_plan.md
Read your skill contract: .claude/skills/output-development/SKILL.md
Read existing implementations: adapters/outputs/udp.py (subprocess/ffmpeg pattern), adapters/outputs/preview_sink.py (simple sink pattern)
Read: adapters/outputs/composite.py (fan-out pattern), ports/outputs.py (OutputSink protocol)

Check renderer team findings: .claude/orchestration/teams/renderers/findings.md

Use the Task tool to parallelize: RTSP, OSC, and video recorder sinks are independent.
COPY udp.py for ffmpeg-based sinks, preview_sink.py for simple sinks.

Follow the 7 phases sequentially.
Write status updates to: .claude/orchestration/teams/outputs/progress.md
Write findings to: .claude/orchestration/teams/outputs/findings.md

Key constraints:
- Implement OutputSink protocol (open/write/close/is_open/get_capabilities)
- close() MUST be idempotent
- write() is silent no-op if closed (never raise on transient failures)
- Latency budget: 3ms
- Subprocess pattern: close stdin → wait → terminate → kill (no zombie processes)
- Optional deps guarded with try/except ImportError
- Register in outputs/__init__.py

If blocked for >10 min, write ESCALATION in progress.md and move to the next available phase.
```

#### 7. Launch Presentation Team

```
Branch: feature/presentation-extensions
```

**Prompt:**
```
You are the Presentation team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Build new Jupyter notebook panels (diagnostics, perception control, filter designer, output manager, performance monitor, preset manager).

Read your task plan: .claude/orchestration/teams/presentation/task_plan.md
Read your skill contract: .claude/skills/presentation-development/SKILL.md
Read existing implementation: presentation/notebook_api.py (ALL existing panels — study build_general_control_panel() carefully)
Read: examples/full_control_panel.ipynb (reference notebook)

Check infrastructure findings: .claude/orchestration/teams/infrastructure/findings.md

Use the Task tool to parallelize: diagnostics panel, filter designer panel, and output manager panel are independent.
COPY patterns from build_general_control_panel() — Tab structure, status bar, stop-modify-restart callbacks.

Follow the 7 phases sequentially.
Write status updates to: .claude/orchestration/teams/presentation/progress.md
Write findings to: .claude/orchestration/teams/presentation/findings.md

Key constraints:
- Only use StreamEngine public API (never private _ attributes)
- Stop-Modify-Restart for pipeline-affecting changes
- Every build_* returns Dict of widgets
- Guard all imports with try/except
- Never implement filter/renderer/analyzer logic in presentation

If blocked for >10 min, write ESCALATION in progress.md and move to the next available phase.
```

### Phase C: Coordination Team (Launch Last, After All Others Running)

#### 8. Launch Coordination Team

```
Branch: orchestration/coordination
```

**Prompt:**
```
You are the Coordination team for the Spatial-Iteration-Engine project.

FIRST: Read .claude/skills/shared/AGENT_RULES.md (shared rules for ALL teams).
THEN: conda activate spatial-iteration-engine

Your mission: Monitor all 7 domain teams, manage merge order, resolve blockers, and maintain the coordination log.

Read the coordination log: .claude/orchestration/COORDINATION_LOG.md
Read the integration log: .claude/orchestration/INTEGRATION_LOG.md
Read all team progress files: .claude/orchestration/teams/*/progress.md
Read all team findings files: .claude/orchestration/teams/*/findings.md
Read all skill files: .claude/skills/*/SKILL.md (understand what each team is building)

Your responsibilities:
1. Monitor progress.md files from all teams every 30 minutes (use Glob + Read in parallel)
2. Update COORDINATION_LOG.md team status dashboard
3. Resolve cross-team dependencies:
   - Perception → Filters: analysis dict schema alignment
   - Renderers → Outputs: RenderFrame contract alignment
   - Infrastructure → All: EventBus, metrics APIs
4. Manage merge queue (Infrastructure → Perception → Filters → Renderers → Outputs → Presentation)
5. Resolve ESCALATIONs written by teams
6. Coordinate with Innovation team on roadmap
7. Run 'make check' on team branches to validate before approving PRs

Use the Task tool to monitor multiple teams in parallel — don't check one at a time.
If a team is stuck, read their branch code to understand the issue before advising.

Do NOT write application code. Your output is coordination documents + merge/test operations.
Write all decisions to COORDINATION_LOG.md.
Write merge history to INTEGRATION_LOG.md.

If a team is blocked and you cannot resolve it, write the issue to COORDINATION_LOG.md under Escalations for morning review.
```

---

## Pre-Sleep Checklist

Before leaving teams to work overnight:

- [ ] All 8 teams launched and confirmed running
- [ ] First progress.md update visible from each team (Phase 1 started)
- [ ] Infrastructure team has started Phase 1 (other teams may need its findings)
- [ ] Innovation team has started its codebase survey
- [ ] Coordination team is reading progress files
- [ ] `git stash` or commit any local changes on `feature/team-organization`
- [ ] Verify no merge conflicts between team branches (all fork from same develop commit)

---

## Morning Review Checklist

### 1. Read Coordination Summary (5 min)

```bash
cat .claude/orchestration/COORDINATION_LOG.md
```

Check: team status dashboard, escalations, merge queue.

### 2. Review Each Team's Progress (10 min)

```bash
for team in perception filters renderers outputs infrastructure presentation innovation; do
  echo "=== $team ==="
  head -20 .claude/orchestration/teams/$team/progress.md
  echo ""
done
```

Look for: phase completion, ESCALATION markers, blockers.

### 3. Run Tests on Each Branch (10 min)

```bash
# Test each branch
for branch in feature/infra-extensions feature/perception-extensions feature/filter-extensions feature/renderer-extensions feature/output-extensions feature/presentation-extensions; do
  echo "=== Testing $branch ==="
  git stash
  git checkout $branch
  make check
  echo ""
done
git checkout feature/team-organization
git stash pop
```

### 4. Merge in Order (5 min per merge)

```bash
git checkout develop

# 1. Infrastructure first
git merge feature/infra-extensions --no-ff -m "feat(infra): merge infrastructure extensions"
make check

# 2. Perception
git merge feature/perception-extensions --no-ff -m "feat(perception): merge perception extensions"
make check

# 3. Filters
git merge feature/filter-extensions --no-ff -m "feat(filters): merge filter extensions"
make check

# 4. Renderers
git merge feature/renderer-extensions --no-ff -m "feat(renderers): merge renderer extensions"
make check

# 5. Outputs
git merge feature/output-extensions --no-ff -m "feat(outputs): merge output extensions"
make check

# 6. Presentation
git merge feature/presentation-extensions --no-ff -m "feat(presentation): merge presentation extensions"
make check
```

### 5. Handle Escalations

Read COORDINATION_LOG.md escalations section. For each:
1. Understand the blocker
2. Decide on resolution
3. Implement fix or defer to next cycle

---

## Troubleshooting

### Team Not Making Progress
- Check progress.md — look for ESCALATION markers
- Check if the team is waiting on another team's findings.md
- Verify the branch exists and has commits: `git log --oneline <branch> -5`

### Merge Conflicts
- Always merge in the prescribed order (Infrastructure first)
- If conflicts arise, the Coordination team should have noted them
- Resolve manually, run `make check`, continue

### Test Failures After Merge
- Check which team's code caused the failure
- Revert the merge: `git merge --abort` or `git reset --hard HEAD~1`
- Fix on the team's branch, re-test, re-merge

### Team Wrote ESCALATION
- Read the escalation in their progress.md
- Check COORDINATION_LOG.md for Coordination team's analysis
- Provide guidance or unblock the team

---

## Worktree Strategy (Alternative to Branch Switching)

For parallel execution without branch switching, use git worktrees:

```bash
# Create worktrees for each team
for team in coordination perception filters renderers outputs infrastructure presentation innovation; do
  branch=$(case $team in
    coordination) echo "orchestration/coordination";;
    perception) echo "feature/perception-extensions";;
    filters) echo "feature/filter-extensions";;
    renderers) echo "feature/renderer-extensions";;
    outputs) echo "feature/output-extensions";;
    infrastructure) echo "feature/infra-extensions";;
    presentation) echo "feature/presentation-extensions";;
    innovation) echo "feature/innovation-roadmap";;
  esac)
  git worktree add ".claude/worktrees/$team" "$branch"
done
```

Each team agent then works in its own worktree directory:
```
.claude/worktrees/perception/    → feature/perception-extensions
.claude/worktrees/filters/       → feature/filter-extensions
.claude/worktrees/renderers/     → feature/renderer-extensions
...
```

Clean up after merging:
```bash
for team in coordination perception filters renderers outputs infrastructure presentation innovation; do
  git worktree remove ".claude/worktrees/$team"
done
```

---

## Communication Protocol Summary

```
┌─────────────┐     task_plan.md      ┌──────────────┐
│ Coordination │ ──────────────────▶  │ Domain Teams  │
│    Team      │                      │ (6 teams)     │
│              │ ◀────────────────── │              │
│              │    progress.md       │              │
└──────┬───────┘                      └──────┬───────┘
       │                                      │
       │  COORDINATION_LOG.md                 │  findings.md
       │  INTEGRATION_LOG.md                  │  (cross-team)
       ▼                                      ▼
┌─────────────┐                      ┌──────────────┐
│   Morning   │                      │  Innovation   │
│   Review    │ ◀─────────────────── │    Team       │
│   (User)    │  INNOVATION_ROADMAP  │              │
└─────────────┘                      └──────────────┘
```

All communication is file-based. No direct agent-to-agent messaging.
Teams read findings.md from their dependencies. Teams write progress.md for monitoring.
