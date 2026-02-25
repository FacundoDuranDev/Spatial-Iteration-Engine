# Team Effects — Filters

## Scope
Fix Physarum, CRT Glitch filter, Geometric Pattern generator, register in __init__

## Tasks
1. Fix Physarum parameters in `physarum.py` — better defaults, adaptive normalization
2. Create CRT Glitch filter scaffold in `crt_glitch.py`
3. Create Geometric Pattern filter scaffold in `geometric_patterns.py`
4. Register new filters in `__init__.py`
5. Basic tests for new filters in `tests/`

## Files
- `adapters/processors/filters/physarum.py` (edit)
- `adapters/processors/filters/crt_glitch.py` (NEW)
- `adapters/processors/filters/geometric_patterns.py` (NEW)
- `adapters/processors/filters/__init__.py` (edit)
- `tests/test_crt_glitch.py` (NEW)
- `tests/test_geometric_patterns.py` (NEW)
