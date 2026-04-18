// Spatial-Iteration-Engine — slider row.
// Drag the track to set a value; writes to the hidden Gradio Number
// identified by data-target. Keeps fill, handle, and readout in sync.
(() => {
  function writeGradioValue(targetId, value) {
    const host = document.getElementById(targetId);
    if (!host) return;
    const input = host.querySelector("input[type='number']") || host.querySelector("input");
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function attach(slider) {
    if (slider._sieBound) return;
    slider._sieBound = true;

    const min = parseFloat(slider.dataset.min);
    const max = parseFloat(slider.dataset.max);
    const step = parseFloat(slider.dataset.step) || 0.01;
    const unit = slider.dataset.unit || "";
    const targetId = slider.dataset.target;
    const track = slider.querySelector(".sie-slider-track");
    const fill = slider.querySelector(".sie-slider-fill");
    const handle = slider.querySelector(".sie-slider-handle");
    const readout = slider.querySelector(".sie-slider-val");

    let value = min;
    const decimals = (() => {
      const s = String(step);
      const i = s.indexOf(".");
      return i < 0 ? 0 : s.length - i - 1;
    })();
    const fmt = (v) => (decimals ? v.toFixed(decimals) : String(Math.round(v))) + unit;

    const setValue = (v, notify) => {
      v = Math.max(min, Math.min(max, v));
      v = Math.round(v / step) * step;
      value = v;
      const frac = (v - min) / (max - min);
      fill.style.width = `${frac * 100}%`;
      handle.style.left = `${frac * 100}%`;
      readout.textContent = fmt(v);
      if (notify) writeGradioValue(targetId, v);
    };

    const valueFromEvent = (evt) => {
      const rect = track.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (evt.clientX - rect.left) / rect.width));
      return min + frac * (max - min);
    };

    let dragging = false;
    const down = (e) => {
      dragging = true; slider.classList.add("sie-dragging");
      track.setPointerCapture?.(e.pointerId);
      setValue(valueFromEvent(e), true);
    };
    const move = (e) => { if (dragging) setValue(valueFromEvent(e), true); };
    const up = (e) => {
      dragging = false; slider.classList.remove("sie-dragging");
      track.releasePointerCapture?.(e.pointerId);
    };
    track.addEventListener("pointerdown", down);
    track.addEventListener("pointermove", move);
    track.addEventListener("pointerup", up);
    track.addEventListener("pointercancel", up);

    // Init from the hidden input value so server-side state is respected on
    // page refresh.
    const host = document.getElementById(targetId);
    const input = host?.querySelector("input");
    const initial = input ? parseFloat(input.value) : min;
    setValue(isNaN(initial) ? min : initial, false);
  }

  function scan(root) {
    (root || document).querySelectorAll('.sie-slider[data-widget="slider"]').forEach(attach);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => scan());
  } else { scan(); }
  new MutationObserver(() => scan()).observe(document.body, { childList: true, subtree: true });
})();
