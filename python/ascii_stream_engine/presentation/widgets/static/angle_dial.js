// Spatial-Iteration-Engine — angle dial.
// Ported SVG shape from design/ui_kits/mcp_v2/s2_distort.html.
// Binds every .sie-angle-dial on the page, drags the pointer, and mirrors
// the angle into the hidden Gradio Number identified by data-target.
(() => {
  const TWO_PI = Math.PI * 2;

  function writeGradioValue(targetId, value) {
    const host = document.getElementById(targetId);
    if (!host) return;
    const input = host.querySelector("input[type='number']") || host.querySelector("input");
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // Degrees on this dial: 0 = up, grows clockwise (UI convention).
  // SVG point for a given angle in degrees, at given radius from center (70,70).
  function polar(deg, r) {
    const rad = (deg - 90) * Math.PI / 180;
    return { x: 70 + r * Math.cos(rad), y: 70 + r * Math.sin(rad) };
  }

  // Build an arc path from 0° up to `deg` (clockwise, centered at (70,70), radius 60).
  function arcPath(deg) {
    const start = polar(0, 60);
    const end = polar(deg, 60);
    const large = deg > 180 ? 1 : 0;
    return `M${start.x.toFixed(2)},${start.y.toFixed(2)} A60,60 0 ${large},1 ${end.x.toFixed(2)},${end.y.toFixed(2)}`;
  }

  function buildSVG(dial) {
    dial.innerHTML = `
      <svg viewBox="0 0 140 140" width="140" height="140" aria-hidden="true">
        <g stroke="#262a3c" stroke-width="1">
          <line x1="70" y1="6"   x2="70" y2="14"/>
          <line x1="70" y1="126" x2="70" y2="134"/>
          <line x1="6"  y1="70"  x2="14" y2="70"/>
          <line x1="126" y1="70" x2="134" y2="70"/>
          <line x1="24" y1="24"   x2="30" y2="30"/>
          <line x1="110" y1="24"  x2="116" y2="30"/>
          <line x1="24" y1="116"  x2="30" y2="110"/>
          <line x1="110" y1="116" x2="116" y2="110"/>
        </g>
        <circle cx="70" cy="70" r="60" fill="none" stroke="#1a1d2a" stroke-width="1"/>
        <path data-dial-arc d="" fill="none" stroke="#00fff2" stroke-width="2"
              style="filter: drop-shadow(0 0 4px #00fff2);"/>
        <line data-dial-pointer x1="70" y1="70" x2="70" y2="10"
              stroke="#00fff2" stroke-width="2"
              style="filter: drop-shadow(0 0 4px #00fff2);"/>
        <circle cx="70" cy="70" r="18" fill="#0e1018" stroke="#262a3c"/>
        <circle cx="70" cy="70" r="3" fill="#00fff2"/>
        <circle data-dial-knob cx="70" cy="10" r="8"
                fill="#05060b" stroke="#00fff2" stroke-width="2"
                style="filter: drop-shadow(0 0 6px rgba(0,255,242,0.6));"/>
      </svg>
    `;
  }

  function attach(dial) {
    if (dial._sieBound) return;
    dial._sieBound = true;

    const min = parseFloat(dial.dataset.min) || 0;
    const max = parseFloat(dial.dataset.max) || 360;
    const step = parseFloat(dial.dataset.step) || 1;
    const targetId = dial.dataset.target;

    if (!dial.querySelector("svg")) buildSVG(dial);
    const svg = dial.querySelector("svg");
    const arc = dial.querySelector("[data-dial-arc]");
    const pointer = dial.querySelector("[data-dial-pointer]");
    const knob = dial.querySelector("[data-dial-knob]");
    const readout = dial.parentElement?.querySelector(".sie-dial-readout");

    let angle = 0;

    const setAngle = (deg, notify) => {
      const range = max - min;
      angle = min + ((deg - min) % range + range) % range;
      if (step > 0) angle = Math.round(angle / step) * step;
      const p = polar(angle, 60);
      const pInner = polar(angle, 60);
      const pKnob = polar(angle, 60);
      arc.setAttribute("d", arcPath(angle));
      pointer.setAttribute("x2", pInner.x.toFixed(2));
      pointer.setAttribute("y2", pInner.y.toFixed(2));
      knob.setAttribute("cx", pKnob.x.toFixed(2));
      knob.setAttribute("cy", pKnob.y.toFixed(2));
      if (readout) readout.textContent = `${Math.round(angle)}°`;
      if (notify) writeGradioValue(targetId, angle);
    };

    const pointerAngle = (evt) => {
      const rect = svg.getBoundingClientRect();
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

    const host = document.getElementById(targetId);
    const input = host?.querySelector("input");
    const initial = input ? parseFloat(input.value) : 0;
    setAngle(isNaN(initial) ? 0 : initial, false);
  }

  function scan(root) {
    (root || document).querySelectorAll(".sie-angle-dial").forEach(attach);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => scan());
  } else {
    scan();
  }
  new MutationObserver(() => scan()).observe(document.body, { childList: true, subtree: true });
})();
