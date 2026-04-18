const { useState } = React;

const CHARSETS = {
  Simple: " .:-=+*#",
  Medio: " .:-=+*#%@",
  Denso: ' .\'`^",:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$',
};

function StatusBar({ kind, children }) {
  const palette = {
    ok: { bg: "rgba(157,255,78,.08)", bd: "var(--accent)", fg: "#c9f9a8", dot: "var(--accent)", glow: "0 0 8px var(--accent)" },
    info: { bg: "rgba(94,207,255,.08)", bd: "var(--cyan)", fg: "#a5e3ff", dot: "var(--cyan)", glow: "none" },
    warn: { bg: "rgba(255,180,84,.08)", bd: "var(--amber)", fg: "#ffd89c", dot: "var(--amber)", glow: "none" },
    idle: { bg: "var(--bg-1)", bd: "var(--bg-3)", fg: "var(--fg-2)", dot: "var(--fg-3)", glow: "none" },
  }[kind] || {};
  return (
    <div style={{
      padding: "8px 12px", borderRadius: 2, fontSize: 12,
      border: `1px solid ${palette.bd}`, background: palette.bg, color: palette.fg,
      display: "flex", alignItems: "center", gap: 8,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: palette.dot, boxShadow: palette.glow, flexShrink: 0 }} />
      {children}
    </div>
  );
}

function ControlPanel() {
  const [tab, setTab] = useState("Motor");
  const [running, setRunning] = useState(false);
  const [cameraIdx, setCameraIdx] = useState(0);
  const [status, setStatus] = useState({ kind: "idle", msg: "Listo. Usa las pestañas y pulsa Start en Motor." });

  const [net, setNet] = useState({ mode: "Local", host: "127.0.0.1", port: 1234 });
  const [view, setView] = useState({ fps: 30, gridW: 120, gridH: 30, charsetName: "Medio", contrast: 10, brightness: 0, renderMode: "ascii" });
  const [filters, setFilters] = useState({ "Edges": false, "Brightness/Contrast": false, "Invert": false, "Invert (C++)": false, "Detail Boost": false });
  const [ai, setAi] = useState({ face: false, hands: false, pose: false, viz: "Normal (según ASCII/RAW)" });

  const setNetP = p => setNet(s => ({ ...s, ...p }));
  const setViewP = p => setView(s => ({ ...s, ...p }));
  const setAiP = p => setAi(s => ({ ...s, ...p }));

  const activeFilters = Object.keys(filters).filter(k => filters[k]);

  return (
    <div style={{
      width: 760, margin: "40px auto", padding: 16,
      background: "var(--bg-0)", border: "1px solid var(--bg-3)", borderRadius: 4,
      fontFamily: "var(--font-sans)",
    }}>
      {/* Notebook cell chrome */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 4px 12px 4px", borderBottom: "1px solid var(--bg-3)", marginBottom: 14 }}>
        <span style={{ fontSize: 11, color: "var(--fg-3)", fontFamily: "var(--font-mono)" }}>In [ 4 ]:</span>
        <span style={{ fontSize: 11, color: "var(--fg-2)", fontFamily: "var(--font-mono)" }}>build_general_control_panel(engine)</span>
        <span style={{ marginLeft: "auto", fontSize: 10, letterSpacing: "0.12em", color: "var(--fg-3)", textTransform: "uppercase" }}>Jupyter · Python 3.13</span>
      </div>

      {/* Preview */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-2)", marginBottom: 6 }}>Preview</div>
        <PreviewImage running={running} renderMode={view.renderMode} charset={CHARSETS[view.charsetName]} gridW={view.gridW} gridH={view.gridH} />
      </div>

      {/* Status */}
      <div style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-2)", marginBottom: 6 }}>Estado</div>
      <div style={{ marginBottom: 14 }}><StatusBar kind={status.kind}>{status.msg}</StatusBar></div>

      {/* Controls */}
      <div style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-2)", marginBottom: 6 }}>Controles</div>
      <div style={{ background: "var(--bg-1)", border: "1px solid var(--bg-3)", borderRadius: 2 }}>
        <div style={{ display: "flex", borderBottom: "1px solid var(--bg-3)" }}>
          {["Red", "Motor", "Filtros", "Vista", "IA"].map(t => (
            <div key={t} onClick={() => setTab(t)} style={{
              padding: "10px 16px", fontSize: 12, cursor: "pointer",
              color: tab === t ? "var(--fg-0)" : "var(--fg-2)",
              borderBottom: `2px solid ${tab === t ? "var(--accent)" : "transparent"}`,
              fontFamily: "var(--font-mono)",
              marginBottom: -1,
            }}>{t}</div>
          ))}
          <div style={{ marginLeft: "auto", padding: "10px 14px", fontSize: 11, color: "var(--fg-3)", fontFamily: "var(--font-mono)" }}>
            {activeFilters.length > 0 ? `${activeFilters.length} filtro${activeFilters.length > 1 ? "s" : ""}` : "sin filtros"}
          </div>
        </div>
        <div style={{ padding: 18 }}>
          {tab === "Red" && <NetworkTab state={net} set={setNetP} onApply={() => setStatus({ kind: "info", msg: `Red aplicada: ${net.mode} → ${net.host}:${net.port}` })} />}
          {tab === "Motor" && <EngineTab running={running} cameraIdx={cameraIdx} setCameraIdx={setCameraIdx}
            onStart={() => { setRunning(true); setStatus({ kind: "ok", msg: "● Motor en marcha. El preview se actualiza en la celda de arriba." }); }}
            onStop={() => { setRunning(false); setStatus({ kind: "idle", msg: "○ Motor detenido." }); }}
            onApplyCamera={() => setStatus({ kind: "ok", msg: `Cámara cambiada a índice ${cameraIdx}.` })} />}
          {tab === "Filtros" && <FiltersTab filters={filters}
            toggle={(n, v) => {
              const next = { ...filters, [n]: v };
              setFilters(next);
              const active = Object.keys(next).filter(k => next[k]);
              setStatus(active.length
                ? { kind: "ok", msg: `Filtros activos: ${active.join(", ")}` }
                : { kind: "info", msg: "Sin filtros: imagen normal." });
            }}
            clear={() => {
              setFilters(Object.fromEntries(Object.keys(filters).map(k => [k, false])));
              setStatus({ kind: "info", msg: "Sin filtros: imagen normal." });
            }} />}
          {tab === "Vista" && <ViewTab state={view} set={setViewP}
            onApply={() => setStatus({ kind: "ok", msg: "Ajustes de vista aplicados." })} />}
          {tab === "IA" && <AITab state={ai} set={setAiP}
            onApply={() => setStatus({ kind: ai.viz === "Overlay landmarks" ? "ok" : "info",
              msg: ai.viz === "Overlay landmarks"
                ? "IA: overlay de landmarks activo."
                : "IA: visualización normal (según pestaña Vista)." })} />}
        </div>
      </div>

      {/* Footer */}
      <div style={{ marginTop: 12, fontSize: 10, color: "var(--fg-3)", fontFamily: "var(--font-mono)", display: "flex", gap: 14 }}>
        <span>render: {view.renderMode}</span>
        <span>·</span>
        <span>host: {net.host}:{net.port}</span>
        <span>·</span>
        <span>fps: {view.fps}</span>
        <span>·</span>
        <span style={{ color: running ? "var(--accent)" : "var(--fg-3)" }}>{running ? "● live" : "○ idle"}</span>
      </div>
    </div>
  );
}

Object.assign(window, { ControlPanel });
