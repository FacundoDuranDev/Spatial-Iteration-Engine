const { useState } = React;

function NetworkTab({ state, set, onApply }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <SectionTitle>Servidor en red</SectionTitle>
      <Helper>Local = 127.0.0.1 · Broadcast/Multicast para UDP.</Helper>
      <Field label="Modo red">
        <Select value={state.mode} options={["Local", "Broadcast", "Multicast", "IP directa"]}
          onChange={v => {
            const hostMap = { "Local": "127.0.0.1", "Broadcast": "255.255.255.255", "Multicast": "239.0.0.1" };
            set({ mode: v, host: hostMap[v] ?? state.host });
          }} />
      </Field>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
        <Field label="Host"><TextInput value={state.host} onChange={v => set({ host: v })} /></Field>
        <Field label="Puerto"><TextInput value={state.port} onChange={v => set({ port: Number(v) || 0 })} /></Field>
      </div>
      <div><Button onClick={onApply}>Aplicar red</Button></div>
    </div>
  );
}

function EngineTab({ running, onStart, onStop, cameraIdx, setCameraIdx, onApplyCamera }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <SectionTitle>Motor</SectionTitle>
      <Helper>Inicia para ver el preview en la celda de arriba.</Helper>
      <div style={{ display: "flex", gap: 10 }}>
        <Button variant="primary" onClick={onStart} disabled={running}>▶ Iniciar</Button>
        <Button variant="stop" onClick={onStop} disabled={!running}>■ Detener</Button>
      </div>
      <SectionTitle>Cámara</SectionTitle>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
        <Field label="Cámara"><TextInput value={cameraIdx} onChange={v => setCameraIdx(Number(v) || 0)} width={80} /></Field>
        <Button onClick={onApplyCamera}>Aplicar cámara</Button>
      </div>
    </div>
  );
}

function FiltersTab({ filters, toggle, clear }) {
  const names = Object.keys(filters);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <SectionTitle>Filtros de imagen</SectionTitle>
      <Helper>Se aplican antes del render (ASCII/RAW). Puedes combinar varios.</Helper>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
        {names.map(n => (
          <Checkbox key={n} label={n} checked={filters[n]} onChange={v => toggle(n, v)} />
        ))}
      </div>
      <div><Button onClick={clear}>Quitar todos</Button></div>
    </div>
  );
}

function ViewTab({ state, set, onApply }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <SectionTitle>Vista (ASCII / RAW)</SectionTitle>
      <Helper>Video</Helper>
      <Slider label="FPS" value={state.fps} min={10} max={60} onChange={v => set({ fps: v })} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Slider label="Grid W" value={state.gridW} min={60} max={200} onChange={v => set({ gridW: v })} />
        <Slider label="Grid H" value={state.gridH} min={20} max={120} onChange={v => set({ gridH: v })} />
      </div>
      <Helper>Apariencia</Helper>
      <Field label="Charset">
        <Select value={state.charsetName} options={["Simple", "Medio", "Denso"]}
          onChange={v => set({ charsetName: v })} />
      </Field>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Slider label="Contraste" value={state.contrast} min={5} max={30} step={1} onChange={v => set({ contrast: v })} unit="/10" />
        <Slider label="Brillo" value={state.brightness} min={-50} max={50} onChange={v => set({ brightness: v })} />
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 4 }}>
        <Checkbox label="ASCII" checked={state.renderMode === "ascii"} onChange={() => set({ renderMode: "ascii" })} />
        <Checkbox label="RAW (sin ASCII)" checked={state.renderMode === "raw"} onChange={() => set({ renderMode: "raw" })} />
      </div>
      <div><Button onClick={onApply}>Aplicar ajustes</Button></div>
    </div>
  );
}

function AITab({ state, set, onApply }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <SectionTitle>Percepción (IA)</SectionTitle>
      <div style={{
        padding: "8px 10px", background: "rgba(255,180,84,.08)",
        border: "1px solid var(--amber)", borderRadius: 2,
        fontSize: 11, color: "#ffd89c", lineHeight: 1.5,
      }}>
        <b>Sin módulo de percepción nativo.</b> Arranca Jupyter con
        <code style={{ color: "var(--amber)", margin: "0 4px" }}>PYTHONPATH=python:cpp/build</code>
        (tras <code style={{ color: "var(--amber)", margin: "0 4px" }}>bash cpp/build.sh</code>)
        para que la detección y el overlay funcionen.
      </div>
      <div style={{ display: "flex", gap: 16 }}>
        <Checkbox label="Cara" checked={state.face} onChange={v => set({ face: v })} accent="var(--magenta)" />
        <Checkbox label="Manos" checked={state.hands} onChange={v => set({ hands: v })} accent="var(--magenta)" />
        <Checkbox label="Pose" checked={state.pose} onChange={v => set({ pose: v })} accent="var(--magenta)" />
      </div>
      <Field label="Visualización">
        <Select value={state.viz} options={["Normal (según ASCII/RAW)", "Overlay landmarks"]}
          onChange={v => set({ viz: v })} />
      </Field>
      <div><Button onClick={onApply}>Aplicar IA</Button></div>
      <SectionTitle>Estado del detector</SectionTitle>
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--fg-1)",
        padding: 10, background: "var(--bg-0)", border: "1px solid var(--bg-3)", borderRadius: 2,
      }}>
        <div>Cara: <span style={{ color: state.face ? "var(--magenta)" : "var(--fg-3)" }}>{state.face ? "468 pts" : "—"}</span></div>
        <div>Manos: <span style={{ color: state.hands ? "var(--magenta)" : "var(--fg-3)" }}>{state.hands ? "42 pts" : "—"}</span></div>
        <div>Pose: <span style={{ color: state.pose ? "var(--magenta)" : "var(--fg-3)" }}>{state.pose ? "33 pts" : "—"}</span></div>
      </div>
    </div>
  );
}

Object.assign(window, { NetworkTab, EngineTab, FiltersTab, ViewTab, AITab });
