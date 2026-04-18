// Spatial-Iteration-Engine — angle dial widget.
// Binds every ``.sie-angle-dial`` on the page and mirrors its angle into
// the hidden Gradio Number identified by ``data-target``.
(() => {
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const TWO_PI = Math.PI * 2;

  function writeGradioValue(targetId, value) {
    // The hidden gr.Number has elem_id=<target>; the real <input> lives inside.
    const host = document.getElementById(targetId);
    if (!host) return;
    const input = host.querySelector("input[type='number']") || host.querySelector("input");
    if (!input) return;
    input.value = value;
    // React-compatible event sequence so Gradio picks it up.
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function attach(dial) {
    if (dial._sieBound) return;
    dial._sieBound = true;

    const min = parseFloat(dial.dataset.min) || 0;
    const max = parseFloat(dial.dataset.max) || 360;
    const step = parseFloat(dial.dataset.step) || 1;
    const targetId = dial.dataset.target;
    const needle = dial.querySelector(".sie-dial-needle");
    const readout = dial.querySelector(".sie-dial-readout");

    let angle = 0;

    const setAngle = (deg, notify) => {
      const range = max - min;
      angle = min + ((deg - min) % range + range) % range;
      if (step > 0) angle = Math.round(angle / step) * step;
      needle.style.transform = `rotate(${angle}deg)`;
      readout.textContent = `${Math.round(angle)}°`;
      if (notify) writeGradioValue(targetId, angle);
    };

    const pointerAngle = (evt) => {
      const rect = dial.querySelector("svg").getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = evt.clientX - cx;
      const dy = evt.clientY - cy;
      let rad = Math.atan2(dy, dx) + Math.PI / 2;  // 0° = up
      if (rad < 0) rad += TWO_PI;
      return (rad / TWO_PI) * 360;
    };

    let dragging = false;
    const down = (e) => { dragging = true; dial.setPointerCapture?.(e.pointerId); setAngle(pointerAngle(e), true); };
    const move = (e) => { if (dragging) setAngle(pointerAngle(e), true); };
    const up = (e) => { dragging = false; dial.releasePointerCapture?.(e.pointerId); };

    dial.addEventListener("pointerdown", down);
    dial.addEventListener("pointermove", move);
    dial.addEventListener("pointerup", up);
    dial.addEventListener("pointercancel", up);

    // Init from existing value in the hidden input (round-trip on reload).
    const host = document.getElementById(targetId);
    const input = host?.querySelector("input");
    const initial = input ? parseFloat(input.value) : 0;
    setAngle(isNaN(initial) ? 0 : initial, false);
  }

  function scan(root) {
    (root || document).querySelectorAll(".sie-angle-dial").forEach(attach);
  }

  // Initial scan + observe future DOM updates (Gradio re-renders tabs lazily).
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => scan());
  } else {
    scan();
  }
  new MutationObserver(() => scan()).observe(document.body, { childList: true, subtree: true });
})();
