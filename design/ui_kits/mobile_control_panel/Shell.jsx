const { useState } = React;

/* ============================================================
   MobileFrame — simple phone portrait bezel, 390×844
   ============================================================ */
function MobileFrame({ children, label }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
      {label && (
        <div style={{
          fontFamily: "var(--mcp-mono)", fontSize: 10, letterSpacing: "0.18em",
          textTransform: "uppercase", color: "#7a7f9e",
        }}>{label}</div>
      )}
      <div className="mcp mcp-scanlines" style={{
        width: 390, height: 844, borderRadius: 44,
        border: "8px solid #0a0a10",
        boxShadow: "0 0 0 2px #1a1a24, 0 40px 80px rgba(0,0,0,0.6), 0 0 40px rgba(0,255,242,0.05)",
        overflow: "hidden", position: "relative",
        display: "flex", flexDirection: "column",
      }}>
        {/* notch */}
        <div style={{
          position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)",
          width: 120, height: 30, borderRadius: 16, background: "#000", zIndex: 100,
        }} />
        {/* status bar */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "14px 28px 6px", fontFamily: "var(--mcp-mono)", fontSize: 13,
          fontWeight: 600, color: "#e8ebf5", zIndex: 10, position: "relative",
        }}>
          <span>9:41</span>
          <span style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 11 }}>
            <span style={{ letterSpacing: "0.05em" }}>●●●●</span>
            <span>100%</span>
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ============================================================
   Status pill — used in sticky header
   ============================================================ */
function StatusPill({ running, fps }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      padding: "6px 12px", borderRadius: 999,
      border: `1px solid ${running ? "var(--mcp-cyan)" : "var(--mcp-fg-3)"}`,
      background: running ? "var(--mcp-cyan-soft)" : "transparent",
      fontFamily: "var(--mcp-mono)", fontSize: 11, letterSpacing: "0.1em",
      color: running ? "var(--mcp-cyan)" : "var(--mcp-fg-2)",
      textShadow: running ? "0 0 6px rgba(0,255,242,0.5)" : "none",
      textTransform: "uppercase",
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: running ? "var(--mcp-cyan)" : "var(--mcp-fg-3)",
        boxShadow: running ? "0 0 6px var(--mcp-cyan)" : "none",
      }} />
      {running ? `Running ${fps} FPS` : "Stopped"}
    </div>
  );
}

/* ============================================================
   Header — sticky top bar
   ============================================================ */
function Header({ running = true, fps = 28, title = "SPATIAL/ITERATION", back, onBack }) {
  return (
    <div style={{
      padding: "10px 16px 14px", borderBottom: "1px solid var(--mcp-line)",
      display: "flex", alignItems: "center", gap: 10,
      background: "var(--mcp-bg)", zIndex: 5,
    }}>
      {back ? (
        <button onClick={onBack} style={{
          width: 36, height: 36, borderRadius: 8, border: "1px solid var(--mcp-line-2)",
          background: "transparent", color: "var(--mcp-fg)", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--mcp-mono)", fontSize: 18,
        }}>‹</button>
      ) : (
        <div style={{ width: 10, height: 10 }}>
          <div style={{ width: 10, height: 10, border: "1px solid var(--mcp-cyan)", transform: "rotate(45deg)" }} />
        </div>
      )}
      <div style={{ flex: 1, fontFamily: "var(--mcp-mono)", fontSize: 12, fontWeight: 600,
        letterSpacing: "0.12em", color: "var(--mcp-fg)" }}>{title}</div>
      <StatusPill running={running} fps={fps} />
      <button style={{
        width: 36, height: 36, borderRadius: 8, border: "1px solid var(--mcp-line-2)",
        background: "transparent", color: "var(--mcp-fg-2)", cursor: "pointer",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.3"/>
          <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M3.5 12.5l1.4-1.4M11.1 4.9l1.4-1.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
        </svg>
      </button>
    </div>
  );
}

/* ============================================================
   Footer — sticky bottom bar. Start/Stop + preset dropdown
   ============================================================ */
function Footer({ running = true, onToggle, preset = "MP3_NOIR" }) {
  return (
    <div style={{
      padding: "12px 16px 20px", borderTop: "1px solid var(--mcp-line)",
      display: "flex", gap: 10, background: "var(--mcp-bg)",
      position: "sticky", bottom: 0, zIndex: 5,
    }}>
      <button onClick={onToggle} style={{
        flex: 1.2, height: 56, borderRadius: 10, cursor: "pointer",
        fontFamily: "var(--mcp-mono)", fontSize: 14, fontWeight: 700, letterSpacing: "0.2em",
        background: running ? "transparent" : "var(--mcp-cyan)",
        color: running ? "var(--mcp-mag)" : "#05060b",
        border: running ? "1px solid var(--mcp-mag)" : "1px solid var(--mcp-cyan)",
        textShadow: running ? "0 0 8px rgba(255,43,214,0.5)" : "none",
        boxShadow: running ? "0 0 16px rgba(255,43,214,0.2)" : "0 0 20px rgba(0,255,242,0.4)",
        transition: "all var(--mcp-dur) var(--mcp-ease)",
      }}>{running ? "■ STOP" : "▶ START"}</button>

      <button style={{
        flex: 1, height: 56, borderRadius: 10, cursor: "pointer",
        border: "1px solid var(--mcp-line-2)", background: "var(--mcp-bg-1)",
        color: "var(--mcp-fg)", textAlign: "left", padding: "0 14px",
        display: "flex", flexDirection: "column", justifyContent: "center",
      }}>
        <span style={{ fontFamily: "var(--mcp-mono)", fontSize: 9, letterSpacing: "0.2em",
          color: "var(--mcp-fg-2)", textTransform: "uppercase" }}>PRESET ▾</span>
        <span style={{ fontFamily: "var(--mcp-mono)", fontSize: 13, color: "var(--mcp-cyan)",
          letterSpacing: "0.08em", marginTop: 2 }}>{preset}</span>
      </button>
    </div>
  );
}

/* ============================================================
   Preview chip — tiny abstract generative hint per category
   Rendered as an inline SVG, no bitmap.
   ============================================================ */
function PreviewChip({ kind }) {
  const size = 44;
  const common = { width: size, height: size, viewBox: "0 0 44 44" };
  if (kind === "color") return (
    <svg {...common}>
      <defs>
        <linearGradient id="cg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ff2bd6"/>
          <stop offset="100%" stopColor="#00fff2"/>
        </linearGradient>
      </defs>
      <rect width="44" height="44" rx="6" fill="#0b0d16"/>
      <circle cx="17" cy="22" r="9" fill="url(#cg)" opacity="0.8"/>
      <circle cx="27" cy="22" r="9" fill="url(#cg)" opacity="0.5" style={{ mixBlendMode: "screen" }}/>
    </svg>
  );
  if (kind === "stylize") return (
    <svg {...common}>
      <rect width="44" height="44" rx="6" fill="#0b0d16"/>
      {[0,1,2,3,4,5,6].map(i => (
        <line key={i} x1={4} x2={40} y1={6 + i*5} y2={6 + i*5} stroke="#00fff2" strokeWidth="0.8" opacity={0.3 + (i%3)*0.2}/>
      ))}
      <path d="M8 34 L22 12 L36 34" fill="none" stroke="#ff2bd6" strokeWidth="1.2"/>
    </svg>
  );
  if (kind === "distort") return (
    <svg {...common}>
      <rect width="44" height="44" rx="6" fill="#0b0d16"/>
      {[0,1,2,3,4].map(i => (
        <path key={i} d={`M4 ${10 + i*6} Q22 ${10 + i*6 + (i%2?-4:4)} 40 ${10 + i*6}`}
              fill="none" stroke="#00fff2" strokeWidth="0.8" opacity={0.4 + i*0.1}/>
      ))}
    </svg>
  );
  if (kind === "glitch") return (
    <svg {...common}>
      <rect width="44" height="44" rx="6" fill="#0b0d16"/>
      <rect x="6" y="12" width="32" height="4" fill="#ff2bd6" opacity="0.6"/>
      <rect x="10" y="20" width="24" height="2" fill="#00fff2" opacity="0.8"/>
      <rect x="4" y="26" width="18" height="3" fill="#ff2bd6" opacity="0.4"/>
      <rect x="20" y="32" width="22" height="2" fill="#00fff2"/>
    </svg>
  );
  if (kind === "perception") return (
    <svg {...common}>
      <rect width="44" height="44" rx="6" fill="#0b0d16"/>
      {Array.from({length:14}).map((_,i) => {
        const a = i/14 * Math.PI*2;
        return <circle key={i} cx={22 + Math.cos(a)*12} cy={22 + Math.sin(a)*12} r="1.2" fill="#ff2bd6" opacity="0.9"/>
      })}
      <circle cx="22" cy="22" r="2" fill="#00fff2"/>
    </svg>
  );
  // config
  return (
    <svg {...common}>
      <rect width="44" height="44" rx="6" fill="#0b0d16"/>
      <circle cx="22" cy="22" r="8" fill="none" stroke="#00fff2" strokeWidth="1.2"/>
      <circle cx="22" cy="22" r="3" fill="#00fff2"/>
      {[0,1,2,3,4,5].map(i => {
        const a = (i/6) * Math.PI*2;
        return <line key={i} x1={22+Math.cos(a)*11} y1={22+Math.sin(a)*11}
                     x2={22+Math.cos(a)*14} y2={22+Math.sin(a)*14}
                     stroke="#00fff2" strokeWidth="1.5"/>
      })}
    </svg>
  );
}

/* ============================================================
   CategoryCard — Hub grid tile
   ============================================================ */
function CategoryCard({ name, active, total, kind, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: 14, background: "var(--mcp-bg-1)",
      border: "1px solid var(--mcp-line)", borderRadius: "var(--mcp-r-m)",
      cursor: "pointer", textAlign: "left", color: "var(--mcp-fg)",
      display: "flex", flexDirection: "column", gap: 14, aspectRatio: "1 / 1.05",
      transition: "all var(--mcp-dur) var(--mcp-ease)",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <PreviewChip kind={kind} />
        <div style={{
          fontFamily: "var(--mcp-mono)", fontSize: 11, color: "var(--mcp-cyan)",
          background: "var(--mcp-cyan-soft)", padding: "3px 8px", borderRadius: 999,
          border: "1px solid rgba(0,255,242,0.25)",
        }}>{active} / {total}</div>
      </div>
      <div style={{ marginTop: "auto" }}>
        <div style={{
          fontFamily: "var(--mcp-mono)", fontSize: 16, fontWeight: 700,
          letterSpacing: "0.06em", color: "var(--mcp-fg)", textTransform: "uppercase",
        }}>{name}</div>
        <div style={{
          fontFamily: "var(--mcp-sans)", fontSize: 11, color: "var(--mcp-fg-2)",
          marginTop: 4,
        }}>{active === 0 ? "none on" : `${active} active`}</div>
      </div>
    </button>
  );
}

Object.assign(window, { MobileFrame, StatusPill, Header, Footer, PreviewChip, CategoryCard });
