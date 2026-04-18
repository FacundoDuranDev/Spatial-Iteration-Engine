const { useEffect, useRef, useState } = React;

const CHARSET = " .:-=+*#%@";

function AsciiCanvas({ running, w, h, glow }) {
  const ref = useRef(null);
  useEffect(() => {
    let raf, t = 0;
    const tick = () => {
      if (running) t += 0.025;
      if (!ref.current) return;
      let out = "";
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const cx = (x - w / 2) / (w / 2);
          const cy = (y - h / 2) / (h / 2) * 1.8;
          const head = Math.exp(-((cx) ** 2 * 8 + (cy + 0.55) ** 2 * 10));
          const torso = Math.exp(-((cx) ** 2 * 4 + (cy - 0.2) ** 2 * 3));
          const swirl = 0.25 * Math.sin(Math.atan2(cy, cx) * 3 + t * 1.5 - Math.sqrt(cx * cx + cy * cy) * 3);
          let v = head + torso * 0.85 + swirl;
          v = Math.max(0, Math.min(1, v));
          out += CHARSET[Math.floor(v * (CHARSET.length - 1))];
        }
        out += "\n";
      }
      ref.current.textContent = out;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, w, h]);

  return (
    <pre ref={ref} style={{
      margin: 0, fontFamily: "var(--font-mono)", fontSize: 9, lineHeight: 1.0,
      color: "var(--accent)", letterSpacing: 0, whiteSpace: "pre",
      textShadow: running ? `0 0 ${glow}px rgba(157,255,78,${0.35 + glow * 0.04})` : "none",
      opacity: running ? 1 : 0.35,
    }} />
  );
}

function OverlayHUD({ running, host, port, fps }) {
  return (
    <div style={{
      position: "absolute", inset: 0, pointerEvents: "none",
      padding: 12, fontFamily: "var(--font-mono)", fontSize: 10,
      letterSpacing: "0.08em", color: "var(--fg-2)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <div>
          <div style={{ color: running ? "var(--accent)" : "var(--fg-3)", textShadow: running ? "0 0 6px rgba(157,255,78,0.6)" : "none" }}>
            {running ? "● STREAMING" : "○ NO SIGNAL"}
          </div>
          <div>udp://@{host}:{port}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ color: "var(--cyan)" }}>{fps.toFixed(1)} fps</div>
        </div>
      </div>
      <div style={{ position: "absolute", left: 12, bottom: 12, opacity: 0.6 }}>
        REC · {new Date().toISOString().slice(0, 19).replace("T", " ")}
      </div>
    </div>
  );
}

function FpsSparkline({ data, target = 30 }) {
  const W = 280, H = 54;
  const maxY = 40, minY = 18;
  const y = v => H - ((v - minY) / (maxY - minY)) * (H - 8) - 4;
  const xs = i => (i / (data.length - 1)) * W;
  const linePath = data.map((v, i) => `${i === 0 ? 'M' : 'L'}${xs(i)},${y(v)}`).join(' ');
  const areaPath = linePath + ` L${W},${H} L0,${H} Z`;
  const last = data[data.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: "block" }}>
      <line x1="0" x2={W} y1={y(target)} y2={y(target)} stroke="#21272b" />
      <path d={areaPath} fill="rgba(157,255,78,0.12)" />
      <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth="1.2" />
      <circle cx={xs(data.length - 1)} cy={y(last)} r="2.5" fill="var(--accent)" />
    </svg>
  );
}

function MetricRow({ k, v, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px dashed var(--bg-3)", fontSize: 11 }}>
      <span style={{ color: "var(--fg-2)" }}>{k}</span>
      <span style={{ color: color || "var(--fg-0)", fontFamily: "var(--font-mono)" }}>{v}</span>
    </div>
  );
}

function PanelHeader({ dot, children }) {
  return (
    <div style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-2)", display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: dot, display: "inline-block" }} />
      {children}
    </div>
  );
}

function Viewer() {
  const [running, setRunning] = useState(true);
  const [grid, setGrid] = useState("120×30");
  const [glow, setGlow] = useState(6);
  const [w, h] = grid.split("×").map(Number);
  const [fps, setFps] = useState(29.8);
  const [fpsHistory, setFpsHistory] = useState(() => {
    const arr = [];
    for (let i = 0; i < 50; i++) {
      let v = 30 + Math.sin(i * 0.3) * 1.5 + (Math.random() - 0.5) * 2;
      if (i > 14 && i < 22) v -= 5;
      arr.push(Math.max(18, Math.min(40, v)));
    }
    return arr;
  });

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      const next = 28 + Math.random() * 3;
      setFps(next);
      setFpsHistory(h => [...h.slice(1), next]);
    }, 600);
    return () => clearInterval(id);
  }, [running]);

  const avgFps = (fpsHistory.reduce((a, b) => a + b, 0) / fpsHistory.length).toFixed(1);
  const minFps = Math.min(...fpsHistory).toFixed(1);

  return (
    <div style={{ maxWidth: 980, margin: "32px auto", padding: "0 20px", fontFamily: "var(--font-sans)" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 16 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "var(--fg-0)" }}>ASCII Stream Viewer</div>
        <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-3)" }}>VLC · UDP sink</div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 14 }}>
        {/* Main viewer (VLC-like window) */}
        <div style={{ background: "var(--bg-1)", border: "1px solid var(--bg-3)", borderRadius: 4, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderBottom: "1px solid var(--bg-3)", background: "var(--bg-2)" }}>
            <div style={{ display: "flex", gap: 6 }}>
              <span style={{ width: 10, height: 10, background: "var(--bg-3)" }} />
              <span style={{ width: 10, height: 10, background: "var(--bg-3)" }} />
              <span style={{ width: 10, height: 10, background: "var(--bg-3)" }} />
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-2)", marginLeft: 8 }}>
              VLC media player — udp://@127.0.0.1:1234
            </div>
            <div style={{ marginLeft: "auto", fontSize: 10, letterSpacing: "0.12em", color: "var(--fg-3)", textTransform: "uppercase" }}>
              {running ? <span style={{ color: "var(--accent)" }}>● recv</span> : <span>○ idle</span>}
            </div>
          </div>

          <div style={{ position: "relative", background: "#000", padding: 18, minHeight: 360 }}>
            <AsciiCanvas running={running} w={w} h={h} glow={glow} />
            <OverlayHUD running={running} host="127.0.0.1" port={1234} fps={fps} />
          </div>

          {/* Viewer controls only — playback + viewer preferences */}
          <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "10px 14px", borderTop: "1px solid var(--bg-3)" }}>
            <button onClick={() => setRunning(r => !r)} style={{
              fontFamily: "var(--font-mono)", fontSize: 13, padding: "6px 16px",
              background: running ? "transparent" : "var(--accent)",
              color: running ? "#ff5d5d" : "#0a0c0d",
              border: `1px solid ${running ? "#ff5d5d" : "var(--accent)"}`,
              borderRadius: 2, cursor: "pointer", fontWeight: 600, minWidth: 110,
            }}>{running ? "■ Detener" : "▶ Iniciar"}</button>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 10, letterSpacing: "0.12em", color: "var(--fg-2)", textTransform: "uppercase" }}>Grid</span>
              <select value={grid} onChange={e => setGrid(e.target.value)} style={{
                fontFamily: "var(--font-mono)", fontSize: 12, padding: "5px 8px",
                background: "var(--bg-1)", color: "var(--fg-0)",
                border: "1px solid var(--bg-3)", borderRadius: 2, outline: "none",
              }}>
                <option>80×24</option><option>100×28</option><option>120×30</option><option>160×40</option>
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
              <span style={{ fontSize: 10, letterSpacing: "0.12em", color: "var(--fg-2)", textTransform: "uppercase" }}>Glow</span>
              <input type="range" min="0" max="14" value={glow} onChange={e => setGlow(+e.target.value)}
                     style={{ flex: 1, maxWidth: 140, accentColor: "var(--accent)" }} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)", width: 24, textAlign: "right" }}>{glow}</span>
            </div>
          </div>
        </div>

        {/* Right rail — metrics & info */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ padding: 12, background: "var(--bg-1)", border: "1px solid var(--bg-3)", borderRadius: 3 }}>
            <PanelHeader dot="var(--accent)">FPS · últimos 30s</PanelHeader>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "var(--accent)", lineHeight: 1 }}>{fps.toFixed(1)}</div>
              <div style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.08em" }}>avg {avgFps} · min {minFps}</div>
            </div>
            <FpsSparkline data={fpsHistory} />
          </div>

          <div style={{ padding: 12, background: "var(--bg-1)", border: "1px solid var(--bg-3)", borderRadius: 3 }}>
            <PanelHeader dot="var(--magenta)">Detector</PanelHeader>
            <MetricRow k="Cara" v="468 pts" color="var(--magenta)" />
            <MetricRow k="Manos" v="42 pts" color="var(--amber)" />
            <MetricRow k="Pose" v="—" color="var(--fg-3)" />
          </div>

          <div style={{ padding: 12, background: "var(--bg-1)", border: "1px solid var(--bg-3)", borderRadius: 3 }}>
            <PanelHeader dot="var(--cyan)">Backend</PanelHeader>
            <MetricRow k="Captura" v="V4L2" color="var(--cyan)" />
            <MetricRow k="OpenCV" v="4.8.0" />
            <MetricRow k="Sink" v="udp://:1234" />
            <MetricRow k="Latencia" v="32 ms" />
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Viewer });
