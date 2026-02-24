# Shared Agent Rules — All Teams

> Every agent in every team MUST read this file before starting work.
> This file is the source of truth for cross-team operational rules.

---

## Build Environment

### Conda Activation (MANDATORY for C++)

```bash
conda activate spatial-iteration-engine
```

**You MUST activate this conda environment before:**
- Running `make cpp-build` or `cd cpp && ./build.sh`
- Running `cmake` commands
- Running any test that imports `filters_cpp`, `perception_cpp`, or `render_bridge`
- Running `make check` or `make test` (C++ modules must be importable)

**Without conda activation:** pybind11 headers, ONNX Runtime, and C++ compiler toolchain will NOT be found. The build will fail silently or with cryptic errors.

**Environment details:**
- Name: `spatial-iteration-engine`
- Python: 3.12
- Provides: cmake, gcc/g++, numpy, pybind11, onnxruntime (optional)

### Build Commands Quick Reference

```bash
conda activate spatial-iteration-engine

# Build C++ modules (filters_cpp, perception_cpp, render_bridge)
make cpp-build
# or: cd cpp && ./build.sh

# Run all checks (format + lint + test)
make check

# Run tests only
make test
# or: PYTHONPATH=python:cpp/build python -m pytest python/ascii_stream_engine/tests/ -v

# Format code
make format

# Lint
make lint
```

### PYTHONPATH

Always set when running tests manually:
```bash
PYTHONPATH=python:cpp/build python -m pytest ...
```

The Makefile sets this automatically.

---

## Anti-Blocking Protocol

### Rule 1: Don't Get Stuck on Trivial Things

If you hit a blocker that takes more than 10 minutes to resolve:

1. **Write ESCALATION** in your team's `progress.md`:
   ```markdown
   ### ESCALATION
   - **Issue:** [describe the problem]
   - **Tried:** [what you attempted]
   - **Impact:** [what's blocked]
   - **Workaround:** [if any]
   ```

2. **Move to the next task/phase** that isn't blocked
3. **Never spin** on the same error repeatedly
4. **Never brute-force** — if an approach isn't working after 2 attempts, try a different approach

### Rule 2: Common Trivial Blockers and Fixes

| Blocker | Fix |
|---------|-----|
| `ImportError: filters_cpp` | `conda activate spatial-iteration-engine && make cpp-build` |
| `ImportError: perception_cpp` | Same as above |
| `ModuleNotFoundError: ascii_stream_engine` | Set `PYTHONPATH=python:cpp/build` |
| `CMake not found` | `conda activate spatial-iteration-engine` |
| `pybind11 not found` | `conda activate spatial-iteration-engine` (provides pybind11) |
| `ONNX Runtime not found` | Build will still succeed — perception uses stubs |
| `Black/isort format errors` | Run `make format` before committing |
| `flake8 errors` | Fix the specific line, don't disable the rule |
| `Test can't find model file` | Skip with `@pytest.mark.skipif`, don't fail hard |
| `Camera not available` | Use `DummySource` in tests, never require hardware |
| `pre-commit hook fails` | Fix the issue, create a NEW commit (never `--amend`) |

### Rule 3: Quality Over Quantity

- It's better to deliver 3 well-tested components than 7 broken ones
- Every component MUST have at least basic tests before moving on
- Run `make check` before declaring a phase complete

---

## Team Structure: Lead + Builders (17 Agents Total)

Each team has **2-3 agents** with distinct roles:

| Role | Responsibility | Active During |
|------|---------------|---------------|
| **Lead** | Research, design, contracts (Phase 1). Integration, registration, `make check` (Phase 7). Also implements components during Phases 2-6. | All phases |
| **Builder A** | Implements assigned components in parallel with Lead. | Phases 2-6 only |
| **Builder B** *(3-agent teams only)* | Implements additional components in parallel. | Phases 2-6 only |

**Agent counts per team:**
- 3 agents: Perception, Filters, Outputs (more independent components)
- 2 agents: Infrastructure, Renderers, Presentation (more sequential work)
- 1 agent: Innovation (research only), Coordination (monitoring only)

### Builder Rules

If you are a **Builder** (not Lead):
- Implement ONLY your assigned components (listed in your prompt)
- Do NOT register components in `__init__.py` — Lead handles Phase 7
- Do NOT run `make check` — Lead handles final integration
- DO write unit tests for each component you build
- DO update `progress.md` when you finish each component
- If you need an API contract, read `findings.md` (Lead writes it in Phase 1)

### Lead Rules

If you are the **Lead**:
- Phase 1: You work alone. Survey code, design contracts, write `findings.md`
- Phases 2-6: Launch Builders via `Task` tool, then implement your own assigned components
- Phase 7: You work alone. Register all components, run `make check`, update CHANGELOG
- You are responsible for assigning components to Builders (see LAUNCH_GUIDE.md for assignments)

---

## Maximizing Agent Capabilities

### Parallel Work Within Teams

Leads launch Builders as parallel agents using the Task tool:

```
# Lead launches Builder A and Builder B, then works on their own components
# Each agent works on independent files — no shared file editing
```

**Parallelize when:**
- Multiple files to create that don't depend on each other
- Different components assigned to different Builders
- Tests to write for different components

**Don't parallelize when:**
- One component depends on another's output
- You're editing the same file from multiple agents
- Registration steps that modify `__init__.py` (Lead only, Phase 7)

### Use Worktrees for Isolation

Each team works in its own branch. If you need to reference another team's work:

```bash
# Read from another team's branch without switching
git show feature/perception-extensions:path/to/file.py
```

### Use the Skill System

Every team has a domain-specific SKILL.md. Before implementing anything:

1. **Read your SKILL.md** — it has exact code patterns to copy
2. **Read existing implementations** — follow the same patterns exactly
3. **Read rules/** — ARCHITECTURE.md, PIPELINE_EXTENSION_RULES.md, LATENCY_BUDGET.md

### Use Glob/Grep Efficiently

```bash
# Find all implementations of a pattern
# Use Grep tool, not bash grep
```

Search for patterns in existing code before writing new code. The existing codebase is your best documentation.

---

## Communication Protocol

### Write to Your Team's Files

```
.claude/orchestration/teams/<your-team>/
├── progress.md    — YOUR status updates (write after each phase)
├── findings.md    — YOUR API contracts and discoveries (write as you learn)
└── task_plan.md   — YOUR tasks (read-only, written by coordination)
```

### Read from Other Teams

```
.claude/orchestration/teams/<other-team>/findings.md  — Their API contracts
.claude/orchestration/INNOVATION_ROADMAP.md            — Future work context
.claude/orchestration/COORDINATION_LOG.md              — Global status
```

### Cross-Team Dependencies

| If you need... | Read from... |
|----------------|-------------|
| Analysis dict keys | `teams/perception/findings.md` |
| RenderFrame contract | `teams/renderers/findings.md` |
| EventBus API changes | `teams/infrastructure/findings.md` |
| New panel APIs | `teams/presentation/findings.md` |
| Output capabilities | `teams/outputs/findings.md` |
| Filter parameters | `teams/filters/findings.md` |

---

## Git Workflow

### Conventional Commits (Enforced by Hook)

```
type(scope): description

Types: feat, fix, docs, refactor, perf, test, build, chore
Scope: your domain (perception, filters, renderers, outputs, infra, presentation)
```

Examples:
```
feat(perception): add hand gesture classifier analyzer
fix(filters): handle resolution change in optical flow particles
test(outputs): add RTSP sink lifecycle tests
perf(filters): move physarum simulation to C++
```

### Branch Discipline

- Work ONLY on your team's branch
- **NEVER run `git push`** — it will prompt for a passphrase and block your session forever. All work stays local.
- Never push to `main` or `develop` directly
- Don't merge — let Coordination handle merge order
- Commits are LOCAL ONLY. The user will push and create PRs in the morning.

---

## Existing Component Inventory

Know what already exists before building:

| Domain | Count | Components |
|--------|-------|-----------|
| Filters (Python) | 5 | brightness, edges, detail, invert, conversion_cache |
| Filters (C++) | 4 | brightness_contrast, channel_swap, grayscale, invert |
| Analyzers | 3 | face (cv2 — temporary), hands (mediapipe — temporary), pose (OnnxRunner — target) |
| Renderers | 4 | ascii, passthrough, landmarks_overlay, cpp_deformed |
| Outputs | 5 | udp, preview, notebook_preview, ascii_recorder, composite |
| Infrastructure | 5 | event_bus, logging, metrics, profiling, message_queue |
| Presentation | 1 | notebook_api (4 builder functions) |
| Sources | 2 | camera, video_file |

**Total: 29 existing components.** Your new work extends this, never replaces it.

**Perception hybrid state:** Face uses cv2.FaceDetectorYN, hands uses mediapipe, pose uses our C++ OnnxRunner. All are C++ under the hood but through different APIs. Migration to unified OnnxRunner for all 3 is planned — see `perception-development/SKILL.md` for details. New analyzers MUST use the OnnxRunner pattern (copy `pose.py`).

---

## Performance Mindset

| Budget | Limit |
|--------|-------|
| Total frame | 33.3ms (30 FPS) |
| Capture | 2ms |
| All analyzers combined | 15ms |
| Single analyzer | 5ms |
| All filters combined | 5ms |
| Rendering | 3ms |
| Output | 3ms |

**When in doubt:** Profile with `time.perf_counter()`, compare to budget, document results.

---

## Language

All code, comments, docstrings, commit messages, and documentation in **English**.
The project has some Spanish in existing docs — new work should be in English.
