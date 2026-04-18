const { useEffect, useRef } = React;

// Renders a procedural ASCII pattern that evolves; mimics the notebook preview.
function PreviewImage({ running, renderMode, charset, gridW, gridH }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    let raf, t = 0;
    const tick = () => {
      t += running ? 0.03 : 0;
      if (!ref.current) return;
      const W = gridW, H = gridH;
      let out = "";
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          const cx = x - W / 2, cy = (y - H / 2) * 2.0;
          const r = Math.sqrt(cx * cx + cy * cy);
          const v = 0.5 + 0.5 * Math.sin(r * 0.28 - t * 2) * Math.cos(cx * 0.08 + t);
          const vv = Math.max(0, Math.min(1, v));
          out += charset[Math.floor(vv * (charset.length - 1))];
        }
        out += "\n";
      }
      ref.current.textContent = out;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, charset, gridW, gridH]);

  if (renderMode === "raw") {
    return (
      <div style={{
        background: "#000", width: "100%", aspectRatio: "16/9", borderRadius: 2,
        border: "1px solid var(--bg-3)",
        backgroundImage: `
          repeating-linear-gradient(0deg, rgba(255,255,255,0.02) 0 1px, transparent 1px 3px),
          radial-gradient(ellipse at 40% 35%, rgba(200,200,200,0.55) 0%, rgba(60,60,60,0.4) 35%, rgba(10,10,10,0.9) 70%)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--fg-3)", fontSize: 11, letterSpacing: "0.12em",
      }}>{running ? "● LIVE · RAW 640×360" : "○ STOPPED"}</div>
    );
  }

  return (
    <div style={{
      background: "#000", padding: "8px 10px", borderRadius: 2,
      border: "1px solid var(--bg-3)", overflow: "hidden", height: 260,
      position: "relative",
    }}>
      <pre ref={ref} style={{
        margin: 0, fontFamily: "var(--font-mono)", fontSize: 8, lineHeight: 1.0,
        color: running ? "var(--accent)" : "var(--fg-3)",
        letterSpacing: 0, whiteSpace: "pre", opacity: running ? 1 : 0.4,
      }} />
      <div style={{
        position: "absolute", top: 8, right: 12, fontSize: 10,
        color: running ? "var(--accent)" : "var(--fg-3)",
        letterSpacing: "0.12em", textShadow: running ? "0 0 8px rgba(157,255,78,.6)" : "none",
      }}>{running ? "● LIVE" : "○ IDLE"} · {gridW}×{gridH}</div>
    </div>
  );
}

Object.assign(window, { PreviewImage });
