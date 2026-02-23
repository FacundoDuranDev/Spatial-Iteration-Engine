# AI Agent Rules

Rules for AI agents (Claude Code, Copilot, etc.) working on this codebase.

---

## 1. Read Before Write

Before modifying any file, the agent MUST read:

- `rules/ARCHITECTURE.md` (what exists)
- `rules/DESIGN_RULES.md` (how things work)
- The specific file being modified
- The port protocol the adapter implements (in `ports/`)

---

## 2. Never Invent Architecture

If the task requires:

- A new directory under `python/ascii_stream_engine/`
- A new protocol in `ports/`
- A new pipeline stage type
- A modification to `engine.py` or `pipeline_orchestrator.py`

Then **STOP**. This is an architectural change. Document the proposal and ask for human review. Do not proceed autonomously.

---

## 3. Follow Existing Patterns Exactly

When creating a new adapter, find the most similar existing adapter and replicate its structure exactly:

- Same import pattern
- Same fallback pattern (try/except ImportError)
- Same class inheritance
- Same method signatures
- Same error handling

Example: To create a new C++ filter, copy `cpp_invert.py` verbatim, then modify only the filter-specific logic.

---

## 4. Color Space Contract

The authoritative color space is **BGR** (OpenCV default).

- Sources produce BGR frames
- Filters operate on BGR frames
- Renderers receive BGR frames
- C++ perception converts BGR->RGB internally before inference
- Never convert the frame's color space in the main pipeline; conversions operate on copies inside specific components

---

## 5. Language Rules

- Code comments: English
- Docstrings: English
- Log messages: English
- Rules documents: English or Spanish (match existing file's language)
- Variable names: English
- Commit messages: English (per `GITFLOW.md` conventional commits)

---

## 6. What Not To Do

- Do not add dependencies without updating `requirements.txt` AND `pyproject.toml`
- Do not create new files in `domain/` for adapter-specific types
- Do not use `print()` for diagnostics; use `logging`
- Do not use global mutable state outside of adapters
- Do not add `__init__.py` re-exports for internal modules
- Do not use `*` imports anywhere
- Do not catch bare `Exception` in ports or domain; only in adapters and application
- Do not store frame references across frames (memory leak risk) unless in an explicit buffer with bounded size
- Do not use `time.sleep()` inside a filter or analyzer
- Do not use asyncio in the pipeline (the engine is threaded, not async)

---

## 7. Testing Contract for New Code

Every new adapter MUST have:

- A unit test that works without hardware (mock camera, no GPU)
- A test that verifies the ImportError fallback path
- A test with a synthetic numpy frame (`np.zeros` or `np.random`)

Test location: mirror the adapter path under `tests/`.
e.g., `adapters/perception/pose.py` -> `tests/test_pose.py`

---

## 8. Pre-Commit Verification

Before declaring a task complete, verify:

1. `python -c "import ascii_stream_engine"` succeeds (with `PYTHONPATH=python:cpp/build`)
2. No new import errors in the fallback paths
3. No new files outside the documented architecture
4. `make format` passes
5. `make lint` passes
6. `make test` passes (or specific relevant tests)

---

## 9. Research and Documentation

- When conducting research (libraries, algorithms, integration strategies), save findings in `research/` with sources and dates.
- `research/` is gitignored -- it is local working memory, not project documentation.
- Permanent decisions and contracts go in `rules/`. Transient findings go in `research/`.
