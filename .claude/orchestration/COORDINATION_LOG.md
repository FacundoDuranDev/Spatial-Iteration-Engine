# Coordination Log

## Team Status Dashboard

| Team | Phase | Status | Last Update | Blockers |
|------|-------|--------|-------------|----------|
| Infrastructure | Complete | MERGED | 2026-02-24 | — |
| Perception | Blocked | FAIL — not merged | 2026-02-24 | 5 missing analyzer modules |
| Filters | Complete | MERGED | 2026-02-24 | — |
| Renderers | — | SKIPPED | 2026-02-24 | No new commits (work already on teams/main) |
| Outputs | Complete | MERGED | 2026-02-24 | — |
| Presentation | Complete | MERGED | 2026-02-24 | — |
| Innovation | Research only | Complete | 2026-02-26 | — |
| Architecture | Stale | Not merged | — | Task plan violates FilterPipeline rule |
| Core | Complete | MERGED | 2026-02-24 | — |
| Effects | Complete | MERGED | 2026-02-24 | — |

## Merge Queue

Merge order (mandatory): Infrastructure → Perception → Filters → Renderers → Outputs → Presentation

| # | Branch | Status | Commits | Tests Added | Merged |
|---|--------|--------|---------|-------------|--------|
| 1 | teams/infrastructure | MERGED | 27 | +136 passing | 2026-02-24 |
| 2 | teams/perception | FAIL — aborted | 5 | N/A | NOT MERGED |
| 3 | teams/filters | MERGED | 13 | +60 passing | 2026-02-24 |
| 4 | teams/renderers | SKIPPED | 0 | N/A | N/A |
| 5 | teams/outputs | MERGED | 9 | +74 passing | 2026-02-24 |
| 6 | teams/presentation | MERGED | 10 | +60 passing | 2026-02-24 |

**Final test results after all merges:** 14 failed, 453 passed, 2 skipped (37 deselected)

## Decisions

- **2026-02-24:** Perception branch aborted (`git reset --hard`) due to 5 missing analyzer module files causing `ModuleNotFoundError`. Team must provide `emotion.py`, `hand_gesture.py`, `object_detection.py`, `pose_skeleton.py`, `segmentation.py` or remove the broken imports from `__init__.py`.
- **2026-02-24:** Renderers branch skipped — 0 new commits; renderer work was already on `teams/main` before team branching.
- **2026-02-24:** Outputs conflicts (4 files: ndi_sink.py, webrtc_sink.py + tests) resolved by taking outputs team version (English comments + new capabilities).
- **2026-02-24:** Presentation conflicts (3 files: CHANGELOG, `__init__`, notebook_api) resolved by keeping both teams' entries.
- **2026-02-26:** Architecture team task_plan flagged for violating "Never modify FilterPipeline" rule. Needs redesign before execution.

## Escalations

- **Perception:** 5 analyzer modules referenced in `__init__.py` but never committed. Branch is unmergeable. Requires rework.
- **Pre-existing failures (12):** 4x error_handling (metrics assertions), 8x plugins (abstract FilterPlugin instantiation). Not caused by any team — present on baseline. Needs follow-up fix.
- **OpticalFlowParticles bug:** Intermittent crash on resolution change (stateful buffer not reset). 2 extra test failures in certain run orders.
