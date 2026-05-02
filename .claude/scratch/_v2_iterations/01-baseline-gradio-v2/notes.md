# Iteration: 01-baseline-gradio-v2
Timestamp: 20260419T195525Z

## What changed and why
v2 Gradio state before pivot. Hub renders, cat list broken, gray bg bleeds, footer chrome breaks layout.

## Files captured
- run_dashboard_mobile_v2.py
- v2_layout.css
- v2_layout.js

## Git status at iteration time
```
 M .claude/skills/shared/AGENT_RULES.md
 M design/ui_kits/gradio_remote/shared/data.js
 M python/ascii_stream_engine/presentation/widgets/README.md
 M python/ascii_stream_engine/presentation/widgets/__init__.py
 M run_dashboard_mobile.py
?? .claude/scratch/
?? .claude/skills/mobile-web-first/
?? design/ui_kits/gradio_remote/v2/
?? m.html
?? python/ascii_stream_engine/presentation/widgets/static/themes/
?? python/ascii_stream_engine/presentation/widgets/static/v2_layout.css
?? python/ascii_stream_engine/presentation/widgets/static/v2_layout.js
?? run_dashboard_mobile_v2.py
```

## How to revert this iteration
```
cp -v /home/fissure/repos/Spatial-Iteration-Engine/.claude/scratch/_v2_iterations/01-baseline-gradio-v2/snapshot/* <original-paths>
```
