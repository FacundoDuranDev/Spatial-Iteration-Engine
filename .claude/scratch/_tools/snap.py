#!/usr/bin/env python
"""Take iPhone-14-emulated screenshots of the v2 dashboard and the static
mockup. Designed to be run repeatedly during iteration.

Usage:
    python .claude/scratch/_tools/snap.py [tag]

Outputs:
    .claude/scratch/_screenshots/<tag>/{home,cat,detail}.png
    .claude/scratch/_screenshots/<tag>/console.txt   (browser console)
    .claude/scratch/_screenshots/<tag>/dom.html      (rendered DOM)

If <tag> is omitted, uses the timestamp.
"""
from __future__ import annotations
import sys, time, datetime, json, os
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
SHOT = REPO / ".claude" / "scratch" / "_screenshots"

DASHBOARD_URL = "http://127.0.0.1:7860/"

def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = SHOT / tag
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        # Emulate iPhone 14: 390x844, dpr 3, mobile, touch.
        ctx = b.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
        )
        page = ctx.new_page()
        log = []
        page.on("console", lambda msg: log.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: log.append(f"[error] {err}"))

        try:
            # Gradio's WS keeps networkidle perpetually busy → use 'load'.
            page.goto(DASHBOARD_URL, wait_until="load", timeout=20000)
        except Exception as e:
            log.append(f"[goto-failed] {e}")
            (out / "console.txt").write_text("\n".join(log))
            print(f"[snap] {tag}: goto failed: {e}")
            b.close()
            return 1

        # Give Gradio a beat to mount widgets and bind JS.
        time.sleep(3.5)

        # 1. Home (hub view)
        page.screenshot(path=str(out / "01-hub.png"), full_page=False)

        # Grab a copy of the rendered DOM so we can diff & inspect classes.
        (out / "dom.html").write_text(page.content(), encoding="utf-8")

        # 2. Try to navigate into a category by clicking the first cat-btn.
        try:
            page.locator(".siev2-cat-btn, .siev2-cat-btn button").first.click(timeout=4000)
            time.sleep(1.5)
            page.screenshot(path=str(out / "02-cat.png"), full_page=False)
        except Exception as e:
            log.append(f"[click-cat-failed] {e}")

        # 3. Try to open a filter detail.
        try:
            page.locator(".siev2-open-btn, .siev2-open-btn button").first.click(timeout=4000)
            time.sleep(1.5)
            page.screenshot(path=str(out / "03-detail.png"), full_page=False)
        except Exception as e:
            log.append(f"[click-detail-failed] {e}")

        # 4. Full-page (desktop, wider viewport) capture for layout debugging.
        page.set_viewport_size({"width": 440, "height": 1800})
        time.sleep(0.5)
        page.screenshot(path=str(out / "04-fullpage.png"), full_page=True)

        (out / "console.txt").write_text("\n".join(log), encoding="utf-8")

        # Tiny meta-summary for quick reading.
        meta = {
            "tag": tag,
            "url": DASHBOARD_URL,
            "viewport": "iPhone 14 (390x844)",
            "shots": [str(p.name) for p in sorted(out.glob("*.png"))],
            "console_lines": len(log),
            "dom_size": (out / "dom.html").stat().st_size,
        }
        (out / "meta.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps(meta, indent=2))
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
