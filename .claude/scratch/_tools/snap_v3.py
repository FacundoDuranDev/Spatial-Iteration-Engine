#!/usr/bin/env python
"""iPhone-14 Playwright snapshot of the v3 web dashboard.

Usage:
    python .claude/scratch/_tools/snap_v3.py <tag> <token>

Outputs:
    .claude/scratch/_screenshots/<tag>/{01-hub,02-running,03-after-stop}.png
    .claude/scratch/_screenshots/<tag>/console.txt
    .claude/scratch/_screenshots/<tag>/dom.html
    .claude/scratch/_screenshots/<tag>/meta.json
"""
from __future__ import annotations
import sys, time, datetime, json, os
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
SHOT = REPO / ".claude" / "scratch" / "_screenshots"


def main():
    if len(sys.argv) < 3:
        print("usage: snap_v3.py <tag> <token>")
        return 2
    tag = sys.argv[1]
    token = sys.argv[2]
    port = os.environ.get("SIE_V3_PORT", "7861")
    url = f"http://127.0.0.1:{port}/?t={token}"
    out = SHOT / tag
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        page = ctx.new_page()
        log = []
        page.on("console", lambda m: log.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: log.append(f"[error] {e}"))

        try:
            page.goto(url, wait_until="load", timeout=15000)
        except Exception as e:
            log.append(f"[goto-failed] {e}")
            (out / "console.txt").write_text("\n".join(log))
            print(f"[snap_v3] goto failed: {e}")
            b.close()
            return 1

        # Wait for the WS handshake + first state to land.
        time.sleep(1.5)
        page.screenshot(path=str(out / "01-hub.png"), full_page=False)

        # Tap Iniciar.
        try:
            page.locator("#primary-btn").click(timeout=2500)
            time.sleep(2.5)  # allow camera open
            page.screenshot(path=str(out / "02-running.png"), full_page=False)
        except Exception as e:
            log.append(f"[start-click-failed] {e}")

        # Tap Detener.
        try:
            page.locator("#primary-btn").click(timeout=2500)
            time.sleep(1.5)
            page.screenshot(path=str(out / "03-after-stop.png"), full_page=False)
        except Exception as e:
            log.append(f"[stop-click-failed] {e}")

        (out / "dom.html").write_text(page.content(), encoding="utf-8")
        (out / "console.txt").write_text("\n".join(log), encoding="utf-8")

        meta = {
            "tag": tag,
            "url": url,
            "viewport": "iPhone 14 (390x844, dpr 3, mobile)",
            "shots": [pp.name for pp in sorted(out.glob("*.png"))],
            "console_lines": len(log),
            "dom_size": (out / "dom.html").stat().st_size,
        }
        (out / "meta.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps(meta, indent=2))
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
