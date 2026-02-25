# Team Core — TemporalManager Infrastructure

## Scope
TemporalManager service, config wiring, orchestrator integration

## Tasks
1. Add `enable_temporal: bool = True` to `domain/config.py`
2. Create `application/services/temporal_manager.py` — demand-driven temporal state
3. Register in `application/services/__init__.py`
4. Wire into `application/engine.py` — create TemporalManager, pass to orchestrator
5. Wire into `application/orchestration/pipeline_orchestrator.py` — lifecycle management
6. Tests for TemporalManager in `tests/test_temporal_manager.py`

## Files
- `domain/config.py` (edit)
- `application/services/temporal_manager.py` (NEW)
- `application/services/__init__.py` (edit)
- `application/engine.py` (edit)
- `application/orchestration/pipeline_orchestrator.py` (edit)
- `tests/test_temporal_manager.py` (NEW)
