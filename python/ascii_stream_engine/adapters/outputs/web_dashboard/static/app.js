/* ════════════════════════════════════════════════════════════════
   SIE · Web dashboard v3 — vanilla JS app
   ────────────────────────────────────────────────────────────────
   Phase A: WS client + handshake + reconnect + state-driven render
   for the start/stop sticky button. Hub cards are clickable but
   nav stack is not wired yet (Phase B).
   ════════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  const PROTOCOL_VERSION = "1";
  const RECONNECT_INITIAL_MS = 250;
  const RECONNECT_MAX_MS = 4000;

  const QS = new URLSearchParams(location.search);
  const TOKEN = QS.get("t") || window.SIE_TOKEN || "";

  const els = {
    pill: document.getElementById("pill"),
    pillLabel: document.getElementById("pill-label"),
    fps: document.getElementById("fps"),
    lat: document.getElementById("lat"),
    primaryBtn: document.getElementById("primary-btn"),
    primaryLabel: document.getElementById("primary-label"),
  };

  const state = {
    ws: null,
    backoff: RECONNECT_INITIAL_MS,
    snapshot: { running: false, fps: 0, lat_ms: 0, filters: {} },
    reconnectTimer: null,
  };

  function setPill(label, mode) {
    els.pillLabel.textContent = label;
    els.pill.classList.remove("on", "warn");
    if (mode === "on") els.pill.classList.add("on");
    if (mode === "warn") els.pill.classList.add("warn");
  }

  function render(snap) {
    state.snapshot = snap;
    els.fps.textContent = (snap.fps || 0).toFixed(1);
    els.lat.textContent = (snap.lat_ms || 0).toFixed(1);
    if (snap.running) {
      setPill("LIVE", "on");
      els.primaryBtn.classList.remove("primary");
      els.primaryBtn.classList.add("danger");
      els.primaryLabel.textContent = "Detener";
      els.primaryBtn.querySelector(".gly").textContent = "■";
    } else {
      setPill("OFFLINE", null);
      els.primaryBtn.classList.add("primary");
      els.primaryBtn.classList.remove("danger");
      els.primaryLabel.textContent = "Iniciar";
      els.primaryBtn.querySelector(".gly").textContent = "▶";
    }
  }

  function send(obj) {
    if (state.ws && state.ws.readyState === 1) {
      state.ws.send(JSON.stringify(obj));
    }
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws?t=${encodeURIComponent(TOKEN)}&v=${PROTOCOL_VERSION}`;
    setPill("CONECTANDO", "warn");
    const ws = new WebSocket(url);
    state.ws = ws;

    ws.addEventListener("open", () => {
      state.backoff = RECONNECT_INITIAL_MS;
      // Pill will be replaced by first 'state' push.
    });

    ws.addEventListener("message", (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === "state") render(msg);
      else if (msg.type === "ping") send({ op: "pong" });
      else if (msg.type === "error") console.warn("[ws]", msg);
    });

    ws.addEventListener("close", (ev) => {
      if (ev.code === 4401) {
        setPill("AUTH", "warn");
        return; // don't reconnect on auth failure
      }
      setPill("RECONECT", "warn");
      state.reconnectTimer = setTimeout(connect, state.backoff);
      state.backoff = Math.min(state.backoff * 2, RECONNECT_MAX_MS);
    });

    ws.addEventListener("error", () => {
      try { ws.close(); } catch {}
    });
  }

  function bindUI() {
    els.primaryBtn.addEventListener("click", (e) => {
      e.preventDefault();
      send({ op: state.snapshot.running ? "stop" : "start" });
    });

    document.querySelectorAll(".cat").forEach((card) => {
      card.addEventListener("click", () => {
        const cat = card.dataset.cat;
        // Phase B: this opens the cat list view.
        console.info("[nav] cat clicked:", cat);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindUI();
    connect();
  });
})();
