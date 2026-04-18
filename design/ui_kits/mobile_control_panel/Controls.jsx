const { useState: useStateC } = React;

/* ============================================================
   Controls — Slider, Toggle, AngleDial, XYPad, ColorWheel,
               Stepper, PresetChips
   All touch-first, min 60px tall.
   ============================================================ */

function Slider({ label, value = 0.5, min = 0, max = 1, unit = "", format, disabled, onChange }) {
  const [v, setV] = useStateC(value);
  const pct = Math.max(0, Math.min(1, (v - min) / (max - min)));
  const display = format ? format(v) : (unit === "%" ? `${Math.round(pct*100)}%` : v.toFixed(2));
  return (
    <div style={{
      padding: "12px 16px", minHeight: 64, display: "flex", flexDirection: "column", gap: 8,
      opacity: disabled ? 0.4 : 1,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span className="mcp-label" style={{ fontSize: 14, color: "var(--mcp-fg)" }}>{label}</span>
        <span className="mcp-num" style={{ fontSize: 14, color: "var(--mcp-cyan)",
          textShadow: disabled ? "none" : "0 0 6px rgba(0,255,242,0.4)" }}>{display}{unit && unit !== "%" ? ` ${unit}` : ""}</span>
      </div>
      <div style={{ position: "relative", height: 10, display: "flex", alignItems: "center" }}>
        <div style={{ height: 4, borderRadius: 2, background: "var(--mcp-line-2)", width: "100%" }} />
        <div style={{
          position: "absolute", left: 0, top: "50%", transform: "translateY(-50%)",
          height: 4, borderRadius: 2, width: `${pct*100}%`, background: "var(--mcp-cyan)",
          boxShadow: "0 0 8px rgba(0,255,242,0.4)",
        }} />
        <div style={{
          position: "absolute", left: `${pct*100}%`, top: "50%",
          transform: "translate(-50%,-50%)",
          width: 22, height: 22, borderRadius: 11,
          background: "#05060b", border: "2px solid var(--mcp-cyan)",
          boxShadow: "0 0 8px rgba(0,255,242,0.5)",
        }} />
      </div>
    </div>
  );
}

function Toggle({ on = false, onToggle }) {
  return (
    <button onClick={onToggle} style={{
      width: 72, height: 34, borderRadius: 4, cursor: "pointer",
      border: `1px solid ${on ? "var(--mcp-cyan)" : "var(--mcp-line-2)"}`,
      background: on ? "var(--mcp-cyan-soft)" : "transparent",
      color: on ? "var(--mcp-cyan)" : "var(--mcp-fg-2)",
      fontFamily: "var(--mcp-mono)", fontSize: 11, letterSpacing: "0.18em", fontWeight: 600,
      textShadow: on ? "0 0 6px rgba(0,255,242,0.6)" : "none",
      boxShadow: on ? "0 0 10px rgba(0,255,242,0.25)" : "none",
      transition: "all var(--mcp-dur) var(--mcp-ease)",
    }}>{on ? "ON" : "OFF"}</button>
  );
}

function AngleDial({ label = "Angle", angle = 134, onChange }) {
  const a = angle;
  const rad = (a - 90) * Math.PI / 180;
  const cx = 70, cy = 70, r = 56;
  const nx = cx + Math.cos(rad) * r;
  const ny = cy + Math.sin(rad) * r;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "12px 0" }}>
      <svg width={140} height={140} viewBox="0 0 140 140">
        <circle cx={cx} cy={cy} r={r+6} fill="none" stroke="var(--mcp-line)" strokeWidth="1"/>
        <circle cx={cx} cy={cy} r={r} fill="#05060b" stroke="var(--mcp-line-2)" strokeWidth="1"/>
        {/* tick marks */}
        {Array.from({length:24}).map((_,i) => {
          const ta = (i/24) * Math.PI * 2 - Math.PI/2;
          const r1 = r - 4, r2 = i % 6 === 0 ? r - 12 : r - 8;
          return <line key={i}
            x1={cx + Math.cos(ta)*r1} y1={cy + Math.sin(ta)*r1}
            x2={cx + Math.cos(ta)*r2} y2={cy + Math.sin(ta)*r2}
            stroke={i % 6 === 0 ? "var(--mcp-fg-2)" : "var(--mcp-line-2)"} strokeWidth="1"/>;
        })}
        {/* arc from 0 to angle */}
        <path d={arcPath(cx, cy, r-2, -90, a-90)} fill="none"
              stroke="var(--mcp-cyan)" strokeWidth="2"
              style={{ filter: "drop-shadow(0 0 4px rgba(0,255,242,0.5))" }}/>
        {/* needle */}
        <line x1={cx} y1={cy} x2={nx} y2={ny}
              stroke="var(--mcp-cyan)" strokeWidth="2" strokeLinecap="round"
              style={{ filter: "drop-shadow(0 0 4px rgba(0,255,242,0.7))" }}/>
        <circle cx={cx} cy={cy} r="4" fill="var(--mcp-cyan)"
                style={{ filter: "drop-shadow(0 0 4px rgba(0,255,242,0.7))" }}/>
        <circle cx={nx} cy={ny} r="5" fill="#05060b" stroke="var(--mcp-cyan)" strokeWidth="2"/>
      </svg>
      <div style={{ textAlign: "center" }}>
        <div className="mcp-kicker">{label}</div>
        <div className="mcp-num" style={{ fontSize: 22, color: "var(--mcp-cyan)",
          textShadow: "0 0 8px rgba(0,255,242,0.5)", marginTop: 2 }}>{a}°</div>
      </div>
    </div>
  );
}

function arcPath(cx, cy, r, a1deg, a2deg) {
  const a1 = a1deg * Math.PI/180, a2 = a2deg * Math.PI/180;
  const x1 = cx + Math.cos(a1)*r, y1 = cy + Math.sin(a1)*r;
  const x2 = cx + Math.cos(a2)*r, y2 = cy + Math.sin(a2)*r;
  const large = Math.abs(a2deg - a1deg) > 180 ? 1 : 0;
  const sweep = a2deg > a1deg ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} ${sweep} ${x2} ${y2}`;
}

function XYPad({ x = 0.5, y = 0.4, label = "Focus" }) {
  const size = 240;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "8px 0" }}>
      <div className="mcp-kicker">{label}</div>
      <div style={{
        width: size, height: size, position: "relative",
        background: "#05060b", border: "1px solid var(--mcp-line-2)", borderRadius: 6,
        backgroundImage: "linear-gradient(rgba(0,255,242,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,242,0.06) 1px, transparent 1px)",
        backgroundSize: "30px 30px",
      }}>
        {/* crosshair */}
        <div style={{ position: "absolute", top: `${y*100}%`, left: 0, right: 0, height: 1,
          background: "rgba(0,255,242,0.15)" }} />
        <div style={{ position: "absolute", left: `${x*100}%`, top: 0, bottom: 0, width: 1,
          background: "rgba(0,255,242,0.15)" }} />
        {/* thumb */}
        <div style={{
          position: "absolute", left: `${x*100}%`, top: `${y*100}%`,
          transform: "translate(-50%,-50%)",
          width: 32, height: 32, borderRadius: 16,
          border: "2px solid var(--mcp-cyan)", background: "rgba(0,255,242,0.1)",
          boxShadow: "0 0 12px rgba(0,255,242,0.5), inset 0 0 6px rgba(0,255,242,0.3)",
        }}>
          <div style={{ position: "absolute", inset: 12, borderRadius: 4, background: "var(--mcp-cyan)",
            boxShadow: "0 0 6px var(--mcp-cyan)" }}/>
        </div>
      </div>
      <div style={{ display: "flex", gap: 20, fontFamily: "var(--mcp-mono)", fontSize: 12, color: "var(--mcp-fg-2)" }}>
        <span>x <span style={{ color: "var(--mcp-cyan)" }} className="mcp-num">{x.toFixed(2)}</span></span>
        <span>y <span style={{ color: "var(--mcp-cyan)" }} className="mcp-num">{y.toFixed(2)}</span></span>
      </div>
    </div>
  );
}

function ColorWheel({ label = "Tint", hue = 200, sat = 0.7, lightness = 0.5 }) {
  const size = 110;
  const cx = size/2, cy = size/2, r = size/2 - 4;
  const rad = hue * Math.PI/180;
  const tx = cx + Math.cos(rad) * r * sat;
  const ty = cy + Math.sin(rad) * r * sat;
  const color = `hsl(${hue} 90% ${Math.round(lightness*50+25)}%)`;
  // wedge gradient by sampling 24 slices
  const wedges = Array.from({length: 36}).map((_,i) => {
    const a1 = (i/36) * 360 - 90;
    const a2 = ((i+1)/36) * 360 - 90;
    return <path key={i} d={`M ${cx} ${cy} L ${cx + Math.cos(a1*Math.PI/180)*r} ${cy + Math.sin(a1*Math.PI/180)*r} A ${r} ${r} 0 0 1 ${cx + Math.cos(a2*Math.PI/180)*r} ${cy + Math.sin(a2*Math.PI/180)*r} Z`}
               fill={`hsl(${i*10} 85% 55%)`}/>;
  });
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div className="mcp-kicker">{label}</div>
      <div style={{ position: "relative" }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <defs>
            <radialGradient id={`desat-${label}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#05060b" stopOpacity="1"/>
              <stop offset="100%" stopColor="#05060b" stopOpacity="0"/>
            </radialGradient>
          </defs>
          <g>{wedges}</g>
          <circle cx={cx} cy={cy} r={r} fill={`url(#desat-${label})`}/>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--mcp-line-2)"/>
          <circle cx={tx} cy={ty} r="7" fill={color} stroke="#05060b" strokeWidth="2"
                  style={{ filter: `drop-shadow(0 0 6px ${color})` }}/>
          <circle cx={tx} cy={ty} r="9" fill="none" stroke="#fff" strokeWidth="1" opacity="0.9"/>
        </svg>
      </div>
      {/* lightness slider under wheel */}
      <div style={{ width: size, height: 16, borderRadius: 3,
        background: `linear-gradient(90deg, #000, ${color}, #fff)`,
        border: "1px solid var(--mcp-line-2)", position: "relative" }}>
        <div style={{
          position: "absolute", left: `${lightness*100}%`, top: "50%",
          transform: "translate(-50%,-50%)",
          width: 8, height: 20, background: "#fff", borderRadius: 2,
          boxShadow: "0 0 4px rgba(0,0,0,0.8)",
        }}/>
      </div>
    </div>
  );
}

function Stepper({ label, value = 5, min = 1, max = 12 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "12px 16px", minHeight: 60 }}>
      <span className="mcp-label">{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 2,
        border: "1px solid var(--mcp-line-2)", borderRadius: 6, overflow: "hidden" }}>
        <button style={stepBtn}>−</button>
        <div style={{
          width: 48, textAlign: "center", fontFamily: "var(--mcp-mono)",
          fontSize: 16, color: "var(--mcp-cyan)", padding: "8px 0",
          textShadow: "0 0 4px rgba(0,255,242,0.4)",
        }} className="mcp-num">{value}</div>
        <button style={stepBtn}>+</button>
      </div>
    </div>
  );
}
const stepBtn = {
  width: 44, height: 40, background: "transparent", border: "none",
  color: "var(--mcp-fg)", fontFamily: "var(--mcp-mono)", fontSize: 20,
  cursor: "pointer",
};

function PresetChips({ items = ["MP3_NOIR","MP3_BLOOM","LIVE_SET_01","RITUAL","ASCII_RAW","CRT_DRIFT"], active = 0 }) {
  return (
    <div style={{ display: "flex", gap: 8, overflowX: "auto", padding: "10px 16px", scrollbarWidth: "none" }}>
      {items.map((item, i) => (
        <div key={item} style={{
          flexShrink: 0, padding: "8px 14px", borderRadius: 999,
          fontFamily: "var(--mcp-mono)", fontSize: 12, letterSpacing: "0.08em",
          border: `1px solid ${i === active ? "var(--mcp-cyan)" : "var(--mcp-line-2)"}`,
          background: i === active ? "var(--mcp-cyan-soft)" : "transparent",
          color: i === active ? "var(--mcp-cyan)" : "var(--mcp-fg-1)",
          textShadow: i === active ? "0 0 6px rgba(0,255,242,0.4)" : "none",
        }}>{item}</div>
      ))}
    </div>
  );
}

/* ============================================================
   FilterRow — expandable card (one filter)
   ============================================================ */
function FilterRow({ name, on = false, expanded = false, children }) {
  return (
    <div style={{
      border: "1px solid var(--mcp-line)", borderRadius: "var(--mcp-r-m)",
      background: expanded ? "var(--mcp-bg-2)" : "var(--mcp-bg-1)",
      overflow: "hidden", transition: "all var(--mcp-dur) var(--mcp-ease)",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "16px", minHeight: 60,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: "var(--mcp-mono)", fontSize: 13, fontWeight: 600,
            letterSpacing: "0.12em", color: on ? "var(--mcp-fg)" : "var(--mcp-fg-1)",
            textTransform: "uppercase",
          }}>{name}</div>
        </div>
        <Toggle on={on}/>
        <button style={{
          width: 36, height: 36, background: "transparent",
          border: "1px solid var(--mcp-line-2)", borderRadius: 6,
          color: "var(--mcp-fg-2)", fontFamily: "var(--mcp-mono)", fontSize: 14,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
        }}>{expanded ? "−" : "+"}</button>
      </div>
      {expanded && (
        <div style={{
          borderTop: "1px dashed var(--mcp-line-2)",
          padding: "8px 4px 12px", marginLeft: 4,
          borderLeft: "2px solid var(--mcp-cyan)",
          background: "rgba(0,255,242,0.02)",
        }}>
          {children}
        </div>
      )}
    </div>
  );
}

Object.assign(window, {
  Slider, Toggle, AngleDial, XYPad, ColorWheel, Stepper, PresetChips, FilterRow,
});
