# Integration Log

## Merge History

| Date | Branch | Into | Commit | Conflicts | Resolution |
|------|--------|------|--------|-----------|------------|
| — | — | — | — | — | — |

## Pre-Merge Checklist

For each merge into `develop`:

- [ ] `make check` passes on the source branch
- [ ] No new flake8 warnings
- [ ] All new code has tests (unit + integration)
- [ ] Analysis dict schema documented (if perception)
- [ ] Registration complete (`__init__.py`, `__all__`)
- [ ] CHANGELOG.md updated under [Unreleased]
- [ ] No modifications to `application/`, `ports/`, `domain/`
- [ ] Latency budget validated (profiler report attached)
- [ ] C++ fallback works (ImportError graceful degradation)
- [ ] Cross-team contracts verified (findings.md reviewed)

## Post-Merge Validation

After each merge:

1. Run `make check` on `develop`
2. Verify no import regressions
3. Run latency benchmark: `python -m pytest -m "not slow" -v`
4. Update COORDINATION_LOG.md merge queue
