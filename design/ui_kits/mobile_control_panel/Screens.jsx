const { useState: useStateSc } = React;

/* ============================================================
   Screen 1 — Hub / Home
   ============================================================ */
function HubScreen() {
  const cats = [
    { name: "COLOR", kind: "color", active: 3, total: 7 },
    { name: "STYLIZE", kind: "stylize", active: 2, total: 9 },
    { name: "DISTORT", kind: "distort", active: 4, total: 8 },
    { name: "GLITCH / FX", kind: "glitch", active: 1, total: 9 },
    { name: "PERCEPTION", kind: "perception", active: 2, total: 6 },
    { name: "CONFIG", kind: "config", active: 0, total: 0 },
  ];
  return (
    <MobileFrame label="Screen 1 — Hub">
      <Header running fps={28} />
      <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
        <div style={{ marginBottom: 16 }}>
          <div className="mcp-kicker">Session</div>
          <div style={{
            fontFamily: "var(--mcp-mono)", fontSize: 24, fontWeight: 700,
            color: "var(--mcp-fg)", marginTop: 4, letterSpacing: "-0.01em",
          }}>Live · <span style={{ color: "var(--mcp-cyan)", textShadow: "0 0 8px rgba(0,255,242,0.4)" }}>12 on</span></div>
          <div style={{ fontFamily: "var(--mcp-sans)", fontSize: 12, color: "var(--mcp-fg-2)", marginTop: 4 }}>
            Tap a category to tune its filters.
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {cats.map(c => <CategoryCard key={c.name} {...c}/>)}
        </div>
      </div>
      <Footer running preset="MP3_NOIR" />
    </MobileFrame>
  );
}

/* ============================================================
   Screen 2 — DISTORT detail (TemporalScan + DoF expanded)
   ============================================================ */
function DistortScreen() {
  return (
    <MobileFrame label="Screen 2 — Distort">
      <Header running fps={28} back title="DISTORT · 8 filters" />
      <div style={{ flex: 1, overflow: "auto", padding: "12px 12px 8px", display: "flex", flexDirection: "column", gap: 10 }}>
        <FilterRow name="Kaleidoscope" on/>
        <FilterRow name="Radial Collapse"/>
        <FilterRow name="TemporalScan" on expanded>
          <AngleDial label="Scan Angle" angle={134}/>
          <Slider label="Speed" value={0.42}/>
          <Slider label="Trail Length" value={0.68}/>
        </FilterRow>
        <FilterRow name="Radial Blur" on/>
        <FilterRow name="Depth of Field" on expanded>
          <XYPad label="Focus Point" x={0.58} y={0.42}/>
          <Slider label="Aperture" value={0.35} format={v => v.toFixed(2)}/>
          <Slider label="Bokeh Size" value={0.72}/>
        </FilterRow>
        <FilterRow name="Motion Blur"/>
        <FilterRow name="UV Displacement"/>
        <FilterRow name="Hand Spatial Warp"/>
      </div>
      <Footer running preset="MP3_NOIR" />
    </MobileFrame>
  );
}

/* ============================================================
   Screen 3 — COLOR detail (Color Grading expanded)
   ============================================================ */
function ColorScreen() {
  return (
    <MobileFrame label="Screen 3 — Color">
      <Header running fps={28} back title="COLOR · 7 filters" />
      <div style={{ flex: 1, overflow: "auto", padding: "12px 12px 8px", display: "flex", flexDirection: "column", gap: 10 }}>
        <FilterRow name="Color Grading" on expanded>
          <div style={{ display: "flex", justifyContent: "space-around", padding: "8px 0 4px" }}>
            <ColorWheel label="Shadows" hue={210} sat={0.6} lightness={0.3}/>
            <ColorWheel label="Highlights" hue={40} sat={0.7} lightness={0.7}/>
          </div>
          <Slider label="Saturation" value={0.62}/>
          <Slider label="Vibrance" value={0.45}/>
          <Slider label="Temperature" value={0.38} format={v => `${Math.round((v-0.5)*2000)} K`}/>
          <Slider label="Tint Balance" value={0.5}/>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", minHeight: 52 }}>
            <span className="mcp-label" style={{ flex: 1 }}>Preserve Luminance</span>
            <Toggle on/>
          </div>
        </FilterRow>
        <FilterRow name="Film Grain" on/>
        <FilterRow name="Vignette"/>
        <FilterRow name="Brightness / Contrast" on/>
        <FilterRow name="Detail Boost"/>
        <FilterRow name="Bloom"/>
        <FilterRow name="Bloom Cinematic"/>
      </div>
      <Footer running preset="MP3_BLOOM" />
    </MobileFrame>
  );
}

/* ============================================================
   Screen 4 — Spec sheet
   ============================================================ */
function SpecScreen() {
  return (
    <MobileFrame label="Screen 4 — Spec">
      <div style={{ flex: 1, overflow: "auto", padding: 18,
        fontFamily: "var(--mcp-sans)", color: "var(--mcp-fg)" }}>
        <div style={{ fontFamily: "var(--mcp-mono)", fontSize: 14, fontWeight: 700,
          letterSpacing: "0.1em", color: "var(--mcp-fg)", paddingTop: 30 }}>SPEC SHEET</div>

        {/* Palette */}
        <SpecSection title="Palette">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            <Swatch name="bg" hex="#05060b"/>
            <Swatch name="bg-1" hex="#0b0d16"/>
            <Swatch name="fg" hex="#e8ebf5"/>
            <Swatch name="fg-2" hex="#7a7f9e"/>
            <Swatch name="cyan" hex="#00fff2" glow="cyan"/>
            <Swatch name="magenta" hex="#ff2bd6" glow="mag"/>
            <Swatch name="amber" hex="#ffcf4a"/>
            <Swatch name="line" hex="#272c47"/>
          </div>
        </SpecSection>

        {/* Type */}
        <SpecSection title="Type">
          <TypeRow label="H1 · mono 700" size={22} mono>SPATIAL/ITERATION</TypeRow>
          <TypeRow label="H2 · mono 600" size={16} mono>DISTORT · 8 FILTERS</TypeRow>
          <TypeRow label="Label · sans 400" size={14}>Focus Point</TypeRow>
          <TypeRow label="Value · mono 500" size={14} mono cyan>134°</TypeRow>
          <TypeRow label="Kicker · mono 10 · 0.18em" size={10} mono caps>PRESET ▾</TypeRow>
        </SpecSection>

        {/* Spacing */}
        <SpecSection title="Spacing · 4pt">
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
            {[4,8,12,16,20,24,32].map(s => (
              <div key={s} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                <div style={{ width: s, height: s, background: "var(--mcp-cyan)",
                  boxShadow: "0 0 4px rgba(0,255,242,0.4)" }}/>
                <span className="mcp-num" style={{ fontSize: 10, color: "var(--mcp-fg-2)" }}>{s}</span>
              </div>
            ))}
          </div>
        </SpecSection>

        {/* Component states */}
        <SpecSection title="Toggle · states">
          <StateRow states={[
            { label: "default", node: <Toggle on={false}/> },
            { label: "on", node: <Toggle on={true}/> },
            { label: "pressed", node: <div style={{ transform: "scale(0.95)" }}><Toggle on={true}/></div> },
            { label: "disabled", node: <div style={{ opacity: 0.35 }}><Toggle on={false}/></div> },
          ]}/>
        </SpecSection>

        <SpecSection title="Button · START / STOP">
          <div style={{ display: "grid", gap: 8 }}>
            <MiniBtn kind="start">▶ START</MiniBtn>
            <MiniBtn kind="stop">■ STOP</MiniBtn>
            <MiniBtn kind="disabled">▶ START</MiniBtn>
          </div>
        </SpecSection>

        <SpecSection title="Slider track · hue">
          <div style={{ padding: "0 0 8px" }}>
            <div style={{ position: "relative", height: 4, background: "var(--mcp-line-2)", borderRadius: 2 }}>
              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: "60%",
                background: "var(--mcp-cyan)", borderRadius: 2, boxShadow: "0 0 6px rgba(0,255,242,0.5)" }}/>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6,
              fontFamily: "var(--mcp-mono)", fontSize: 10, color: "var(--mcp-fg-2)" }}>
              <span>0%</span><span style={{ color: "var(--mcp-cyan)" }}>60%</span><span>100%</span>
            </div>
          </div>
        </SpecSection>

        <div style={{ height: 12 }}/>
      </div>
    </MobileFrame>
  );
}

function SpecSection({ title, children }) {
  return (
    <div style={{ marginTop: 18 }}>
      <div className="mcp-kicker" style={{ marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  );
}
function Swatch({ name, hex, glow }) {
  const shadow = glow === "cyan" ? "0 0 8px rgba(0,255,242,0.5)"
               : glow === "mag"  ? "0 0 8px rgba(255,43,214,0.5)" : "none";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8,
      padding: "6px 8px", border: "1px solid var(--mcp-line)", borderRadius: 6 }}>
      <div style={{ width: 22, height: 22, background: hex, borderRadius: 3, boxShadow: shadow, flexShrink: 0 }}/>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontFamily: "var(--mcp-sans)", fontSize: 11, color: "var(--mcp-fg)" }}>{name}</div>
        <div className="mcp-num" style={{ fontSize: 10, color: "var(--mcp-fg-2)" }}>{hex}</div>
      </div>
    </div>
  );
}
function TypeRow({ label, size, mono, caps, cyan, children }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
      padding: "6px 0", borderBottom: "1px dashed var(--mcp-line)" }}>
      <span style={{
        fontFamily: mono ? "var(--mcp-mono)" : "var(--mcp-sans)",
        fontSize: size, color: cyan ? "var(--mcp-cyan)" : "var(--mcp-fg)",
        textTransform: caps ? "uppercase" : "none",
        letterSpacing: caps ? "0.18em" : "0",
        textShadow: cyan ? "0 0 6px rgba(0,255,242,0.4)" : "none",
      }}>{children}</span>
      <span style={{ fontFamily: "var(--mcp-mono)", fontSize: 10, color: "var(--mcp-fg-2)" }}>{label}</span>
    </div>
  );
}
function StateRow({ states }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      {states.map(s => (
        <div key={s.label} style={{ padding: 10, border: "1px solid var(--mcp-line)",
          borderRadius: 6, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
          {s.node}
          <span className="mcp-kicker">{s.label}</span>
        </div>
      ))}
    </div>
  );
}
function MiniBtn({ kind, children }) {
  const isStart = kind === "start", isStop = kind === "stop", isDisabled = kind === "disabled";
  return (
    <div style={{
      height: 44, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--mcp-mono)", fontSize: 13, fontWeight: 700, letterSpacing: "0.2em",
      background: isStart ? "var(--mcp-cyan)" : "transparent",
      color: isStart ? "#05060b" : isStop ? "var(--mcp-mag)" : "var(--mcp-fg-3)",
      border: isStart ? "1px solid var(--mcp-cyan)"
            : isStop ? "1px solid var(--mcp-mag)" : "1px solid var(--mcp-line-2)",
      boxShadow: isStart ? "0 0 20px rgba(0,255,242,0.4)" : isStop ? "0 0 12px rgba(255,43,214,0.25)" : "none",
      textShadow: isStop ? "0 0 6px rgba(255,43,214,0.5)" : "none",
      opacity: isDisabled ? 0.4 : 1,
    }}>{children}</div>
  );
}

Object.assign(window, { HubScreen, DistortScreen, ColorScreen, SpecScreen });
