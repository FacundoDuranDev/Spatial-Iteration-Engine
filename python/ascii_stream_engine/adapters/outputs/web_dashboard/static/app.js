/* ════════════════════════════════════════════════════════════════
   SIE · Web dashboard v3 — vanilla JS app
   ────────────────────────────────────────────────────────────────
   Phase B: drill-in nav (hub → cat list → detail) + widget atoms
   wired to the WS protocol (toggle_filter / set_param). Nav stack
   is non-destructive: views toggle .hidden + a 180ms enter anim.

   The REGISTRY const below is hard-embedded (mirror of
   adapters/outputs/web_dashboard/registry.py). It drives RENDERING
   only — the server snapshot remains the source of truth for
   VALUES. Keep both in sync when filters change.
   ════════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  // ────────────────────────────────────────────────────────────────
  // 1 · Registry (mirror of registry.py — labels, kinds, ranges)
  // ────────────────────────────────────────────────────────────────

  const CATEGORIES = [
    { id: "DISTORT", name: "Distorsi\u00f3n" },
    { id: "COLOR",   name: "Color" },
    { id: "GLITCH",  name: "Glitch" },
    { id: "STYLIZE", name: "Estilo" },
  ];

  const FILTERS = [
    {
      id: "temporal_scan",
      name: "TemporalScan",
      cat: "DISTORT",
      wip: false,
      params: [
        { id: "angle",  kind: "angle",   min: 0,   max: 360, step: 1,   default: 0,        label: "\u00c1ngulo de scan" },
        { id: "buffer", kind: "stepper", min: 2,   max: 60,  step: 2,   default: 30,       label: "Buffer (frames)" },
        { id: "curve",  kind: "select",  options: ["linear", "ease"],   default: "linear", label: "Curva" },
      ],
    },
    {
      id: "bc_cpp",
      name: "Brillo / Contraste",
      cat: "COLOR",
      wip: false,
      params: [
        { id: "brightness", kind: "slider", min: -100, max: 100, step: 5,   default: 0,   label: "Brillo" },
        { id: "contrast",   kind: "slider", min: 0.5,  max: 3.0, step: 0.1, default: 1.0, label: "Contraste" },
      ],
    },
    {
      id: "bloom",
      name: "Bloom \u00b7 audio-reactivo",
      cat: "COLOR",
      wip: false,
      params: [
        { id: "intensity",   kind: "slider", min: 0.0, max: 1.0, step: 0.05, default: 0.6, label: "Intensidad" },
        { id: "threshold",   kind: "slider", min: 100, max: 255, step: 5,    default: 200, label: "Umbral" },
        { id: "audio_react", kind: "slider", min: 0.0, max: 3.0, step: 0.1,  default: 1.0, label: "Reactividad audio (Bass)" },
      ],
    },
    {
      id: "chroma",
      name: "Aberraci\u00f3n crom\u00e1tica",
      cat: "GLITCH",
      wip: true,
      params: [],
    },
    {
      id: "invert",
      name: "Invertir",
      cat: "STYLIZE",
      wip: true,
      params: [],
    },
  ];

  const FILTERS_BY_ID = {};
  FILTERS.forEach((f) => { FILTERS_BY_ID[f.id] = f; });

  const REGISTRY = { categories: CATEGORIES, filters: FILTERS, byId: FILTERS_BY_ID };

  // ────────────────────────────────────────────────────────────────
  // 2 · App state + WS client
  // ────────────────────────────────────────────────────────────────

  const PROTOCOL_VERSION = "1";
  const RECONNECT_INITIAL_MS = 250;
  const RECONNECT_MAX_MS = 4000;
  const PARAM_DEBOUNCE_MS = 50;

  const QS = new URLSearchParams(location.search);
  // Prefer the server-injected token (always present, survives reloads
  // and lost query strings). Fall back to ?t=… if a tester opens the
  // page directly.
  const TOKEN = window.SIE_TOKEN || QS.get("t") || "";

  // If we have no token at all, the served HTML must be a stale cache
  // from a build before the token-injection fix. Force a one-shot
  // cache-bust reload so the phone re-fetches `/` and gets the script
  // tag with the current token.
  if (!TOKEN && !QS.get("_cb")) {
    location.replace(location.pathname + "?_cb=" + Date.now());
    return;
  }

  const els = {
    hd:           document.getElementById("hd"),
    hdTitle:      document.getElementById("hd-title"),
    backBtn:      document.getElementById("back-btn"),
    pill:         document.getElementById("pill"),
    pillLabel:    document.getElementById("pill-label"),
    kpis:         document.getElementById("kpis"),
    fps:          document.getElementById("fps"),
    lat:          document.getElementById("lat"),
    primaryBtn:   document.getElementById("primary-btn"),
    primaryLabel: document.getElementById("primary-label"),
    body:         document.getElementById("body"),
    viewHub:      document.getElementById("view-hub"),
    viewCat:      document.getElementById("view-cat"),
    viewDetail:   document.getElementById("view-detail"),
    catList:      document.getElementById("cat-list"),
    detailBody:   document.getElementById("detail-body"),
    hubGrid:      document.getElementById("hub-grid"),
  };

  const state = {
    ws: null,
    backoff: RECONNECT_INITIAL_MS,
    reconnectTimer: null,
    snapshot: { running: false, fps: 0, lat_ms: 0, filters: {} },
    navStack: [{ view: "hub" }],
    // Per-control "user is dragging right now" flag — keyed
    // "filter.param" — so server pushes don't yank the UI.
    dragging: {},
    // Per-(filter, param) debounce timers for set_param.
    paramTimers: {},
  };

  function send(obj) {
    if (state.ws && state.ws.readyState === 1) {
      state.ws.send(JSON.stringify(obj));
    }
  }

  function debouncedSetParam(fid, pid, value) {
    const key = fid + "." + pid;
    if (state.paramTimers[key]) clearTimeout(state.paramTimers[key]);
    state.paramTimers[key] = setTimeout(() => {
      send({ op: "set_param", filter: fid, param: pid, value: value });
      state.paramTimers[key] = null;
    }, PARAM_DEBOUNCE_MS);
  }

  // ────────────────────────────────────────────────────────────────
  // 3 · Top-level chrome (header, KPIs, pill, primary btn)
  // ────────────────────────────────────────────────────────────────

  function setPill(label, mode) {
    els.pillLabel.textContent = label;
    els.pill.classList.remove("on", "warn");
    if (mode === "on") els.pill.classList.add("on");
    if (mode === "warn") els.pill.classList.add("warn");
  }

  function updateChrome(snap) {
    els.fps.textContent = (snap.fps || 0).toFixed(1);
    els.lat.textContent = (snap.lat_ms || 0).toFixed(1);
    if (snap.running) {
      setPill("LIVE", "on");
      els.primaryBtn.classList.remove("primary");
      els.primaryBtn.classList.add("danger");
      els.primaryLabel.textContent = "Detener";
      els.primaryBtn.querySelector(".gly").textContent = "\u25A0";
    } else {
      setPill("OFFLINE", null);
      els.primaryBtn.classList.add("primary");
      els.primaryBtn.classList.remove("danger");
      els.primaryLabel.textContent = "Iniciar";
      els.primaryBtn.querySelector(".gly").textContent = "\u25B6";
    }
    // The pill is hidden in cat / detail views (per brief).
    const cur = currentView();
    els.hd.dataset.view = cur.view;
    if (cur.view === "hub") {
      els.pill.classList.remove("hidden");
      els.kpis.classList.remove("hidden");
      els.backBtn.classList.add("hidden");
      els.hdTitle.textContent = "SIE \u00b7 Control";
    } else {
      // Hide pill + KPIs in drill-down views — back+title need the room.
      els.pill.classList.add("hidden");
      els.kpis.classList.add("hidden");
      els.backBtn.classList.remove("hidden");
      if (cur.view === "cat") {
        const c = CATEGORIES.find((x) => x.id === cur.cat);
        els.hdTitle.textContent = c ? c.name : cur.cat;
      } else if (cur.view === "detail") {
        const f = FILTERS_BY_ID[cur.filter];
        els.hdTitle.textContent = f ? f.name : cur.filter;
      }
    }
  }

  // ────────────────────────────────────────────────────────────────
  // 4 · Nav stack (push / pop / current)
  // ────────────────────────────────────────────────────────────────

  function currentView() { return state.navStack[state.navStack.length - 1]; }

  function showView(view, animate) {
    let target = els.viewHub;
    if (view.view === "cat")    target = els.viewCat;
    if (view.view === "detail") target = els.viewDetail;
    if (state.shownTarget === target && !animate) {
      // Same view as last call (e.g. server tick re-render) — don't
      // re-trigger animations or scroll-to-top, just let the per-view
      // renderer update content in place.
      return;
    }
    [els.viewHub, els.viewCat, els.viewDetail].forEach((v) => v.classList.add("hidden"));
    target.classList.remove("hidden");
    target.classList.remove("enter");
    if (animate) {
      // Force reflow then add .enter for animation.
      void target.offsetWidth;
      target.classList.add("enter");
    }
    els.body.scrollTop = 0;
    state.shownTarget = target;
  }

  function pushView(view) {
    state.navStack.push(view);
    renderView(true);
  }

  function popView() {
    if (state.navStack.length <= 1) return;
    state.navStack.pop();
    renderView(true);
  }

  // ────────────────────────────────────────────────────────────────
  // 5 · Render (top-level dispatcher + per-view renderers)
  // ────────────────────────────────────────────────────────────────

  function render(snap) {
    state.snapshot = snap;
    updateChrome(snap);
    // Cheap diff so we don't rebuild the active view on every 1 Hz tick.
    const fJson = JSON.stringify(snap.filters || {});
    const cur = currentView();
    if (cur.view === "hub") {
      // Hub counts are cheap and reflect any filter change → always refresh.
      renderHub();
    } else if (fJson !== state.lastFiltersJson) {
      // Cat/detail views rebuild only when filters actually changed AND the
      // user is not mid-drag (debounce echo would otherwise yank a slider).
      const interacting = Object.keys(state.dragging).length > 0;
      if (!interacting) {
        if (cur.view === "cat")    renderCat(cur.cat);
        if (cur.view === "detail") renderDetail(cur.filter);
      }
    }
    state.lastFiltersJson = fJson;
  }

  function renderView(animate) {
    const cur = currentView();
    showView(cur, !!animate);
    updateChrome(state.snapshot);
    if (cur.view === "hub")    renderHub();
    if (cur.view === "cat")    renderCat(cur.cat);
    if (cur.view === "detail") renderDetail(cur.filter);
  }

  // ── Hub ─────────────────────────────────────────────────────────
  function renderHub() {
    const counts = {};
    CATEGORIES.forEach((c) => { counts[c.id] = { active: 0, total: 0 }; });
    FILTERS.forEach((f) => {
      if (!counts[f.cat]) return;
      counts[f.cat].total += 1;
      const snap = state.snapshot.filters && state.snapshot.filters[f.id];
      if (snap && snap.enabled) counts[f.cat].active += 1;
    });
    document.querySelectorAll(".meta-count").forEach((el) => {
      const cat = el.dataset.cat;
      const c = counts[cat] || { active: 0, total: 0 };
      el.textContent = c.active + " activos / " + c.total + " total";
      el.classList.toggle("live", c.active > 0);
      const card = el.closest(".cat");
      if (card) card.classList.toggle("has-active", c.active > 0);
    });
  }

  // ── Cat list ────────────────────────────────────────────────────
  function renderCat(catId) {
    const list = els.catList;
    list.innerHTML = "";
    const filters = FILTERS.filter((f) => f.cat === catId);
    if (filters.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Sin filtros en esta categor\u00eda.";
      list.appendChild(empty);
      return;
    }
    filters.forEach((f) => {
      const snap = (state.snapshot.filters && state.snapshot.filters[f.id]) || { enabled: false };
      const row = document.createElement("div");
      row.className = "row" + (snap.enabled ? " expanded" : "") + (f.wip ? " wip" : "");
      row.dataset.filter = f.id;

      const toggle = document.createElement("button");
      toggle.className = "toggle" + (snap.enabled ? " on" : "");
      toggle.type = "button";
      toggle.setAttribute("aria-label", "Activar " + f.name);
      bindToggle(toggle, !!snap.enabled, (on) => {
        if (f.wip) return;
        send({ op: "toggle_filter", filter: f.id, on: on });
      });

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = f.name;

      if (f.wip) {
        const badge = document.createElement("span");
        badge.className = "badge-wip";
        badge.textContent = "WIP";
        name.appendChild(badge);
      }

      const chev = document.createElement("span");
      chev.className = "chev";
      chev.textContent = "\u203a";
      if (!f.wip) {
        chev.addEventListener("click", () => pushView({ view: "detail", filter: f.id }));
      }

      row.appendChild(toggle);
      row.appendChild(name);
      row.appendChild(chev);
      list.appendChild(row);
    });
  }

  // ── Detail ──────────────────────────────────────────────────────
  function renderDetail(fid) {
    const f = FILTERS_BY_ID[fid];
    const detail = els.detailBody;
    detail.innerHTML = "";
    if (!f) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Filtro desconocido.";
      detail.appendChild(empty);
      return;
    }

    const head = document.createElement("div");
    head.className = "head";
    const ttl = document.createElement("h2");
    ttl.className = "ttl";
    ttl.textContent = f.name;
    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent = f.cat;
    head.appendChild(ttl);
    head.appendChild(meta);
    detail.appendChild(head);

    // Enable/disable row at the top of detail.
    const snap = (state.snapshot.filters && state.snapshot.filters[f.id]) || { enabled: false, params: {} };
    const enableBlock = document.createElement("div");
    enableBlock.className = "param-block";
    const enableRow = document.createElement("div");
    enableRow.className = "param-row";
    const enableLbl = document.createElement("span");
    enableLbl.className = "lbl";
    enableLbl.textContent = "Activo";
    const enableTgl = document.createElement("button");
    enableTgl.className = "toggle" + (snap.enabled ? " on" : "");
    enableTgl.type = "button";
    bindToggle(enableTgl, !!snap.enabled, (on) => {
      send({ op: "toggle_filter", filter: f.id, on: on });
    });
    enableRow.appendChild(enableLbl);
    enableRow.appendChild(enableTgl);
    enableBlock.appendChild(enableRow);
    detail.appendChild(enableBlock);

    if (f.params.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Sin par\u00e1metros.";
      detail.appendChild(empty);
      return;
    }

    const params = document.createElement("div");
    params.className = "params";
    f.params.forEach((p) => {
      const value = (snap.params && snap.params[p.id] !== undefined) ? snap.params[p.id] : p.default;
      const block = buildParamBlock(f.id, p, value);
      if (block) params.appendChild(block);
    });
    detail.appendChild(params);
  }

  // ────────────────────────────────────────────────────────────────
  // 6 · Param block builder (one per kind)
  // ────────────────────────────────────────────────────────────────

  function buildParamBlock(fid, p, value) {
    const block = document.createElement("div");
    block.className = "param-block";
    block.dataset.param = p.id;

    if (p.kind === "slider" || p.kind === "stepper" && false) {
      // (stepper handled below — kept slider explicit for clarity)
    }

    if (p.kind === "slider") {
      const el = buildSlider(p, value);
      bindSlider(el, value, p.min, p.max, p.step, (v, dragging) => {
        state.dragging[fid + "." + p.id] = dragging;
        debouncedSetParam(fid, p.id, v);
      });
      block.appendChild(el);
      return block;
    }

    if (p.kind === "angle") {
      // Label row + dial centred below.
      const top = document.createElement("div");
      top.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      top.appendChild(lbl);
      block.appendChild(top);

      const el = buildDial(value);
      bindDial(el, value, (v, dragging) => {
        state.dragging[fid + "." + p.id] = dragging;
        debouncedSetParam(fid, p.id, v);
      });
      block.appendChild(el);
      return block;
    }

    if (p.kind === "stepper") {
      const row = document.createElement("div");
      row.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      const el = buildStepper(value);
      bindStepper(el, value, p.min, p.max, p.step, (v) => {
        // Stepper fires immediately (taps, no drag).
        send({ op: "set_param", filter: fid, param: p.id, value: v });
      });
      row.appendChild(lbl);
      row.appendChild(el);
      block.appendChild(row);
      return block;
    }

    if (p.kind === "select") {
      const top = document.createElement("div");
      top.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      top.appendChild(lbl);
      block.appendChild(top);

      const el = buildSelect(p.options || [], value);
      bindSelect(el, value, p.options || [], (v) => {
        send({ op: "set_param", filter: fid, param: p.id, value: v });
      });
      block.appendChild(el);
      return block;
    }

    if (p.kind === "switch") {
      const row = document.createElement("div");
      row.className = "param-row";
      const lbl = document.createElement("span");
      lbl.className = "lbl";
      lbl.textContent = p.label;
      const tgl = document.createElement("button");
      tgl.className = "toggle" + (value ? " on" : "");
      tgl.type = "button";
      bindToggle(tgl, !!value, (on) => {
        send({ op: "set_param", filter: fid, param: p.id, value: on });
      });
      row.appendChild(lbl);
      row.appendChild(tgl);
      block.appendChild(row);
      return block;
    }

    return null;
  }

  // ────────────────────────────────────────────────────────────────
  // 7 · Atom builders (DOM construction, no event wiring)
  // ────────────────────────────────────────────────────────────────

  function buildSlider(p, value) {
    const el = document.createElement("div");
    el.className = "slider";
    el.innerHTML =
      '<div class="top">' +
        '<span class="lbl"></span>' +
        '<span class="val"></span>' +
      '</div>' +
      '<div class="track-wrap">' +
        '<div class="track">' +
          '<div class="fill"></div>' +
          '<div class="pin"></div>' +
        '</div>' +
      '</div>' +
      '<div class="range"><span class="min"></span><span class="max"></span></div>';
    el.querySelector(".lbl").textContent = p.label;
    el.querySelector(".min").textContent = formatNum(p.min, p.step);
    el.querySelector(".max").textContent = formatNum(p.max, p.step);
    return el;
  }

  function buildDial(value) {
    const el = document.createElement("div");
    el.className = "dial";
    el.innerHTML =
      '<div class="face">' +
        '<div class="needle"></div>' +
        '<div class="cap"></div>' +
      '</div>' +
      '<div class="read"></div>';
    return el;
  }

  function buildStepper(value) {
    const el = document.createElement("div");
    el.className = "stepper";
    el.innerHTML =
      '<button type="button" data-act="dec">\u2212</button>' +
      '<span class="v"></span>' +
      '<button type="button" data-act="inc">+</button>';
    return el;
  }

  function buildSelect(options, value) {
    const el = document.createElement("div");
    el.className = "select";
    options.forEach((opt) => {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.value = opt;
      b.textContent = String(opt);
      el.appendChild(b);
    });
    return el;
  }

  // ────────────────────────────────────────────────────────────────
  // 8 · Atom binders (state + interaction)
  // ────────────────────────────────────────────────────────────────

  function bindToggle(el, on, onChange) {
    el.classList.toggle("on", !!on);
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const next = !el.classList.contains("on");
      el.classList.toggle("on", next);
      onChange(next);
    });
  }

  function bindSlider(el, value, min, max, step, onChange) {
    const track = el.querySelector(".track");
    const fill  = el.querySelector(".fill");
    const pin   = el.querySelector(".pin");
    const valEl = el.querySelector(".val");
    const wrap  = el.querySelector(".track-wrap");

    function paint(v) {
      const pct = (max === min) ? 0 : (v - min) / (max - min);
      const clamped = Math.max(0, Math.min(1, pct));
      fill.style.width = (clamped * 100) + "%";
      pin.style.left  = (clamped * 100) + "%";
      valEl.textContent = formatNum(v, step);
    }

    paint(value);
    el._setValue = paint;

    let dragging = false;

    function valueAtClientX(clientX) {
      const r = track.getBoundingClientRect();
      const t = (clientX - r.left) / Math.max(1, r.width);
      const raw = min + Math.max(0, Math.min(1, t)) * (max - min);
      return snapToStep(raw, min, step);
    }

    function down(e) {
      e.preventDefault();
      dragging = true;
      try { wrap.setPointerCapture(e.pointerId); } catch (_) {}
      const v = valueAtClientX(e.clientX);
      paint(v);
      onChange(v, true);
    }
    function move(e) {
      if (!dragging) return;
      const v = valueAtClientX(e.clientX);
      paint(v);
      onChange(v, true);
    }
    function up(e) {
      if (!dragging) return;
      dragging = false;
      try { wrap.releasePointerCapture(e.pointerId); } catch (_) {}
      const v = valueAtClientX(e.clientX);
      paint(v);
      onChange(v, false);
    }

    wrap.addEventListener("pointerdown", down);
    wrap.addEventListener("pointermove", move);
    wrap.addEventListener("pointerup", up);
    wrap.addEventListener("pointercancel", up);
  }

  function bindDial(el, value, onChange) {
    const face   = el.querySelector(".face");
    const needle = el.querySelector(".needle");
    const read   = el.querySelector(".read");

    function paint(v) {
      const deg = ((v % 360) + 360) % 360;
      needle.style.transform = "translate(-50%, -100%) rotate(" + deg + "deg)";
      read.textContent = deg.toFixed(0) + "\u00b0";
    }
    paint(value);
    el._setValue = paint;

    let dragging = false;
    function angleFromEvent(e) {
      const r = face.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      // 0° at top, increase clockwise.
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      let deg = Math.atan2(dx, -dy) * 180 / Math.PI;
      if (deg < 0) deg += 360;
      return Math.round(deg);
    }

    function down(e) {
      e.preventDefault();
      dragging = true;
      try { face.setPointerCapture(e.pointerId); } catch (_) {}
      const v = angleFromEvent(e);
      paint(v);
      onChange(v, true);
    }
    function move(e) {
      if (!dragging) return;
      const v = angleFromEvent(e);
      paint(v);
      onChange(v, true);
    }
    function up(e) {
      if (!dragging) return;
      dragging = false;
      try { face.releasePointerCapture(e.pointerId); } catch (_) {}
      const v = angleFromEvent(e);
      paint(v);
      onChange(v, false);
    }

    face.addEventListener("pointerdown", down);
    face.addEventListener("pointermove", move);
    face.addEventListener("pointerup", up);
    face.addEventListener("pointercancel", up);
  }

  function bindStepper(el, value, min, max, step, onChange) {
    const vEl = el.querySelector(".v");
    let cur = value;

    function paint(v) {
      cur = v;
      vEl.textContent = formatNum(v, step);
    }
    paint(value);
    el._setValue = paint;

    el.querySelector('[data-act="dec"]').addEventListener("click", (e) => {
      e.preventDefault();
      const next = Math.max(min, snapToStep(cur - step, min, step));
      paint(next);
      onChange(next);
    });
    el.querySelector('[data-act="inc"]').addEventListener("click", (e) => {
      e.preventDefault();
      const next = Math.min(max, snapToStep(cur + step, min, step));
      paint(next);
      onChange(next);
    });
  }

  function bindSelect(el, value, options, onChange) {
    function paint(v) {
      el.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("on", b.dataset.value === String(v));
      });
    }
    paint(value);
    el._setValue = paint;

    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", (e) => {
        e.preventDefault();
        const v = b.dataset.value;
        paint(v);
        onChange(v);
      });
    });
  }

  // ────────────────────────────────────────────────────────────────
  // 9 · Helpers
  // ────────────────────────────────────────────────────────────────

  function snapToStep(v, min, step) {
    if (!step) return v;
    const n = Math.round((v - min) / step);
    const out = min + n * step;
    // Avoid float drift like 0.30000000000000004.
    const decimals = (String(step).split(".")[1] || "").length;
    return decimals > 0 ? Number(out.toFixed(decimals)) : out;
  }

  function formatNum(v, step) {
    if (typeof v !== "number") return String(v);
    const decimals = (String(step || 1).split(".")[1] || "").length;
    return decimals > 0 ? v.toFixed(decimals) : String(Math.round(v));
  }

  // ────────────────────────────────────────────────────────────────
  // 10 · WS connect + reconnect
  // ────────────────────────────────────────────────────────────────

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = proto + "//" + location.host + "/ws?t=" + encodeURIComponent(TOKEN) + "&v=" + PROTOCOL_VERSION;
    setPill("CONECTANDO", "warn");
    const ws = new WebSocket(url);
    state.ws = ws;

    ws.addEventListener("open", () => {
      state.backoff = RECONNECT_INITIAL_MS;
    });

    ws.addEventListener("message", (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (_) { return; }
      if (msg.type === "state") render(msg);
      else if (msg.type === "ping") send({ op: "pong" });
      else if (msg.type === "error") console.warn("[ws]", msg);
    });

    ws.addEventListener("close", (ev) => {
      if (ev.code === 4401) {
        setPill("AUTH", "warn");
        return;
      }
      setPill("RECONECT", "warn");
      state.reconnectTimer = setTimeout(connect, state.backoff);
      state.backoff = Math.min(state.backoff * 2, RECONNECT_MAX_MS);
    });

    ws.addEventListener("error", () => {
      try { ws.close(); } catch (_) {}
    });
  }

  // ────────────────────────────────────────────────────────────────
  // 11 · Bind static UI (header back, primary btn, hub cards)
  // ────────────────────────────────────────────────────────────────

  function bindUI() {
    els.primaryBtn.addEventListener("click", (e) => {
      e.preventDefault();
      send({ op: state.snapshot.running ? "stop" : "start" });
    });

    els.backBtn.addEventListener("click", (e) => {
      e.preventDefault();
      popView();
    });

    document.querySelectorAll(".cat").forEach((card) => {
      card.addEventListener("click", () => {
        const cat = card.dataset.cat;
        pushView({ view: "cat", cat: cat });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindUI();
    renderView();
    connect();
  });
})();
