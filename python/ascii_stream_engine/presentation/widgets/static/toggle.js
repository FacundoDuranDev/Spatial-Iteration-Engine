// Spatial-Iteration-Engine — toggle pill.
// Click / tap flips the .sie-on class and writes a boolean to the hidden
// Gradio checkbox identified by data-target.
(() => {
  function writeGradioValue(targetId, value) {
    const host = document.getElementById(targetId);
    if (!host) return;
    const input = host.querySelector("input[type='checkbox']");
    if (!input) return;
    if (input.checked !== value) {
      input.checked = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function attach(el) {
    if (el._sieBound) return;
    el._sieBound = true;
    const targetId = el.dataset.target;

    const flip = () => {
      const on = !el.classList.contains("sie-on");
      el.classList.toggle("sie-on", on);
      el.setAttribute("aria-checked", String(on));
      writeGradioValue(targetId, on);
    };
    el.addEventListener("click", flip);
    el.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); }
    });

    // Sync visual state from the hidden input on mount (and when Gradio
    // reconciles components after a callback).
    const host = document.getElementById(targetId);
    const input = host?.querySelector("input[type='checkbox']");
    if (input) {
      const sync = () => {
        el.classList.toggle("sie-on", !!input.checked);
        el.setAttribute("aria-checked", String(!!input.checked));
      };
      sync();
      input.addEventListener("change", sync);
    }
  }

  function scan(root) {
    (root || document).querySelectorAll('.sie-toggle[data-widget="toggle"]').forEach(attach);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => scan());
  } else { scan(); }
  new MutationObserver(() => scan()).observe(document.body, { childList: true, subtree: true });
})();
