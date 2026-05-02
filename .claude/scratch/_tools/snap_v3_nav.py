#!/usr/bin/env python
"""iPhone-14 Playwright deep test of v3 dashboard with drill-in nav.

Flow:
  1) hub
  2) tap COLOR -> cat list
  3) tap chevron on Bloom -> detail
  4) toggle Bloom on
  5) drag intensity slider
  6) back to cat
  7) back to hub
  8) tap GLITCH (WIP card)

Usage:
    python .claude/scratch/_tools/snap_v3_nav.py <tag> <token>
"""
from __future__ import annotations
import sys, time, json, os
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
SHOT = REPO / ".claude" / "scratch" / "_screenshots"


def main():
    if len(sys.argv) < 3:
        print("usage: snap_v3_nav.py <tag> <token>")
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
            return 1

        time.sleep(1.5)
        page.screenshot(path=str(out / "01-hub.png"))

        # 2. Tap COLOR cat
        try:
            page.locator(".cat[data-cat='COLOR']").first.click(timeout=2500)
            time.sleep(0.6)
            page.screenshot(path=str(out / "02-cat-color.png"))
        except Exception as e:
            log.append(f"[click-color] {e}")

        # 3. Tap chevron on Bloom (look for filter row)
        try:
            # Try clicking the row's chevron — selector may vary, try a few.
            row = page.locator(".list .row").nth(1)  # bloom is 2nd in COLOR (after BC)
            row.locator(".chev, [data-act='open'], .open").first.click(timeout=2500)
            time.sleep(0.6)
            page.screenshot(path=str(out / "03-detail-bloom.png"))
        except Exception as e:
            log.append(f"[open-detail] {e}")
            try:
                # Fallback: just click row
                page.locator(".list .row").nth(1).click(timeout=2000)
                time.sleep(0.6)
                page.screenshot(path=str(out / "03-detail-bloom.png"))
            except Exception as e2:
                log.append(f"[open-detail-fallback] {e2}")

        # 4. Toggle Bloom on (look for toggle in detail or in row)
        try:
            page.locator(".toggle, [data-act='toggle']").first.click(timeout=2000)
            time.sleep(0.6)
            page.screenshot(path=str(out / "04-bloom-on.png"))
        except Exception as e:
            log.append(f"[toggle-bloom] {e}")

        # 5. Try dragging the intensity slider
        try:
            slider = page.locator(".slider").first
            box = slider.bounding_box()
            if box:
                start_x = box["x"] + box["width"] * 0.2
                end_x = box["x"] + box["width"] * 0.7
                y = box["y"] + box["height"] / 2
                page.mouse.move(start_x, y)
                page.mouse.down()
                page.mouse.move(end_x, y, steps=10)
                page.mouse.up()
                time.sleep(0.5)
                page.screenshot(path=str(out / "05-slider-dragged.png"))
        except Exception as e:
            log.append(f"[drag-slider] {e}")

        # 6. Back to cat
        try:
            page.locator("#back-btn").click(timeout=2000)
            time.sleep(0.6)
            page.screenshot(path=str(out / "06-back-cat.png"))
        except Exception as e:
            log.append(f"[back1] {e}")

        # 7. Back to hub
        try:
            page.locator("#back-btn").click(timeout=2000)
            time.sleep(0.6)
            page.screenshot(path=str(out / "07-back-hub.png"))
        except Exception as e:
            log.append(f"[back2] {e}")

        # 8. Tap GLITCH (chroma is WIP)
        try:
            page.locator(".cat[data-cat='GLITCH']").first.click(timeout=2000)
            time.sleep(0.6)
            page.screenshot(path=str(out / "08-cat-glitch.png"))
        except Exception as e:
            log.append(f"[click-glitch] {e}")

        (out / "dom.html").write_text(page.content(), encoding="utf-8")
        (out / "console.txt").write_text("\n".join(log), encoding="utf-8")

        meta = {
            "tag": tag,
            "url": url,
            "viewport": "iPhone 14 (390x844)",
            "shots": [pp.name for pp in sorted(out.glob("*.png"))],
            "console_lines": len(log),
        }
        (out / "meta.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps(meta, indent=2))
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
