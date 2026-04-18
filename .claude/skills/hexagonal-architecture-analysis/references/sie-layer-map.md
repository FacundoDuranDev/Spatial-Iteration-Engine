# SIE Hexagonal Layer Map — Quick Reference

## Layer Dependencies (Current)

```
presentation/
  └──→ application/, infrastructure/, domain/

adapters/
  ├── sources/        └──→ ports/sources.py, domain/
  ├── perception/     └──→ ports/analyzers.py(?), domain/
  ├── processors/     └──→ ports/processors.py, domain/
  ├── renderers/      └──→ ports/renderers.py, domain/
  └── outputs/        └──→ ports/outputs.py, domain/

application/
  ├── engine.py              └──→ ports/, domain/, infrastructure/
  ├── pipeline/              └──→ ports/, domain/
  │   ├── filter_pipeline.py
  │   ├── filter_context.py       ← STRAIN: wraps dict + temporal
  │   └── analyzer_pipeline.py
  ├── orchestration/         └──→ pipeline/, ports/, domain/
  │   └── pipeline_orchestrator.py  ← HARDCODED stage order
  └── services/              └──→ domain/, infrastructure/
      └── temporal_manager.py      ← STRAIN: layer tension

infrastructure/
  └──→ domain/ only (correct)

ports/
  └──→ domain/ only (correct)

domain/
  └──→ nothing (correct)
```

## Known Strains

| Component | Strain Type | Description |
|-----------|------------|-------------|
| TemporalManager | Layer tension | Lives in application/services/ but acts as infrastructure |
| FilterContext | Port strain | Wraps analysis dict because port protocol is too narrow |
| LandmarksOverlayRenderer | Composition strain | Decorator pattern; doesn't compose with multiple overlays |
| PipelineOrchestrator | Rigidity | Stage order hardcoded; can't add compositing stage |
| analysis dict | Type weakness | `Optional[dict]` with no schema enforcement |
| EdgeFilter | Contract violation | Returns (H,W) instead of (H,W,3) — breaks BGR contract |
