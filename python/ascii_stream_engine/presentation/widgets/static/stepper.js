// Spatial-Iteration-Engine — stepper.
// Click −/+ to adjust the hidden Gradio Number identified by data-target.
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

  function attach(stepper) {
    if (stepper._sieBound) return;
    stepper._sieBound = true;

    const min = parseFloat(stepper.dataset.min);
    const max = parseFloat(stepper.dataset.max);
    const step = parseFloat(stepper.dataset.step) || 1;
    const targetId = stepper.dataset.target;
    const readout = stepper.querySelector(".sie-stepper-val");

    let value = parseFloat(readout.textContent) || 0;

    const setValue = (v, notify) => {
      v = Math.max(min, Math.min(max, v));
      value = v;
      readout.textContent = String(v);
      if (notify) writeGradioValue(targetId, v);
    };

    stepper.querySelectorAll(".sie-stepper-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dir = parseFloat(btn.dataset.dir) || 1;
        setValue(value + dir * step, true);
      });
    });

    // Sync on mount.
    const host = document.getElementById(targetId);
    const input = host?.querySelector("input");
    const initial = input ? parseFloat(input.value) : value;
    setValue(isNaN(initial) ? value : initial, false);
  }

  function scan(root) {
    (root || document).querySelectorAll('.sie-stepper[data-widget="stepper"]').forEach(attach);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => scan());
  } else { scan(); }
  new MutationObserver(() => scan()).observe(document.body, { childList: true, subtree: true });
})();
