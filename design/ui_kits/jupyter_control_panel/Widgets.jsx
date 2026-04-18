// Shared widget primitives — mimic ipywidgets on our terminal palette.
const { useState } = React;

function Button({ children, variant = "secondary", onClick, disabled }) {
  const base = {
    fontFamily: "var(--font-mono)", fontSize: 13, padding: "8px 16px",
    borderRadius: 2, cursor: disabled ? "not-allowed" : "pointer",
    border: "1px solid", transition: "all 120ms", outline: "none",
  };
  const variants = {
    primary: { background: "var(--accent)", color: "#0a0c0d", borderColor: "var(--accent)", fontWeight: 600 },
    stop: { background: "transparent", color: "#ff5d5d", borderColor: "#ff5d5d" },
    secondary: { background: "var(--bg-1)", color: "var(--fg-0)", borderColor: "var(--bg-3)" },
    ghost: { background: "transparent", color: "var(--fg-1)", borderColor: "transparent" },
  };
  const style = disabled
    ? { ...base, background: "var(--bg-1)", color: "var(--fg-3)", borderColor: "var(--bg-3)" }
    : { ...base, ...variants[variant] };
  return <button style={style} onClick={onClick} disabled={disabled}>{children}</button>;
}

function Field({ label, children }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--fg-2)" }}>{label}</span>
      {children}
    </label>
  );
}

function TextInput({ value, onChange, width = "100%" }) {
  return (
    <input value={value} onChange={e => onChange(e.target.value)}
      style={{
        fontFamily: "var(--font-mono)", fontSize: 13, padding: "7px 10px",
        background: "var(--bg-1)", color: "var(--fg-0)",
        border: "1px solid var(--bg-3)", borderRadius: 2, outline: "none", width,
      }}
      onFocus={e => e.target.style.borderColor = "var(--cyan)"}
      onBlur={e => e.target.style.borderColor = "var(--bg-3)"}
    />
  );
}

function NumberInput({ value, onChange }) {
  return <TextInput value={value} onChange={v => onChange(Number(v) || 0)} width={80} />;
}

function Select({ value, options, onChange }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      style={{
        fontFamily: "var(--font-mono)", fontSize: 13, padding: "7px 10px",
        background: "var(--bg-1)", color: "var(--fg-0)",
        border: "1px solid var(--bg-3)", borderRadius: 2, outline: "none",
      }}>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function Slider({ label, value, min, max, step = 1, onChange, unit }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ fontSize: 11, color: "var(--fg-2)", width: 80, textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ flex: 1, accentColor: "var(--accent)" }} />
      <span style={{ fontSize: 12, color: "var(--accent)", width: 50, textAlign: "right" }}>{value}{unit || ""}</span>
    </div>
  );
}

function Checkbox({ label, checked, onChange, accent = "var(--accent)" }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--fg-1)", cursor: "pointer" }}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)}
        style={{ accentColor: accent, width: 14, height: 14 }} />
      <span>{label}</span>
    </label>
  );
}

function SectionTitle({ children }) {
  return <div style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--fg-0)", fontWeight: 600, marginTop: 4 }}>{children}</div>;
}

function Helper({ children }) {
  return <div style={{ fontSize: 11, color: "var(--fg-2)", lineHeight: 1.4 }}>{children}</div>;
}

Object.assign(window, { Button, Field, TextInput, NumberInput, Select, Slider, Checkbox, SectionTitle, Helper });
