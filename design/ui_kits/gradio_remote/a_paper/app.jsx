/* global React, ReactDOM, FILTERS, CATEGORIES, PRESETS, METRICS */
const { useState } = React;

/* ═══════════ PRIMITIVES ═══════════ */

function Toggle({ on = false }) {
  return <div className={'a-toggle' + (on ? ' on' : '')} />;
}

function Slider({ label, value, min, max, step, unit, on = true }) {
  const pct = ((value - min) / (max - min)) * 100;
  const ticks = [];
  for (let i = 0; i <= 20; i++) ticks.push(<i key={i} className={i % 5 === 0 ? 'maj' : ''} />);
  const display = typeof value === 'number'
    ? (step < 1 ? value.toFixed(2) : String(Math.round(value)))
    : value;
  return (
    <div className="a-slider">
      <div className="head">
        <span className="lbl">{label}</span>
        <span className={'val' + (on ? '' : ' off')}>{display}{unit ? ' ' + unit : ''}</span>
      </div>
      <div className="ruler">
        <div className="tiks">{ticks}</div>
        <div className="track" />
        <div className="fill" style={{ width: pct + '%' }} />
        <div className="pin" style={{ left: pct + '%' }} />
      </div>
      <div className="range"><span>{min}</span><span>{max}{unit ? ' ' + unit : ''}</span></div>
    </div>
  );
}

function Stepper({ value }) {
  return (
    <div className="a-stepper">
      <button>−</button><div className="v">{value}</div><button>+</button>
    </div>
  );
}

function AngleDial({ value = 45, unit = '°' }) {
  const deg = unit === 'rad' ? value * 180 / Math.PI : value;
  const ticks = [];
  for (let i = 0; i < 36; i++) {
    const ang = i * 10;
    ticks.push(<div key={i} className={'tick' + (i % 3 === 0 ? ' maj' : '')} style={{ transform: `rotate(${ang}deg)`, transformOrigin: '0.5px 61px' }} />);
  }
  const labels = [0, 90, 180, 270];
  return (
    <div className="a-dial">
      <div className="face">
        {ticks}
        {labels.map(l => {
          const rad = (l - 90) * Math.PI / 180;
          const r = 46;
          const x = 67 + r * Math.cos(rad);
          const y = 67 + r * Math.sin(rad);
          return <span key={l} className="lbl" style={{ left: x, top: y, transform: 'translate(-50%,-50%)' }}>{l}°</span>;
        })}
        <div className="needle" style={{ transform: `translate(-50%, -100%) rotate(${deg}deg)` }} />
        <div className="cap" />
      </div>
    </div>
  );
}

function XYPad({ x = 0.5, y = 0.5, label = 'Focal' }) {
  return (
    <div className="a-xy-wrap">
      <div className="head">
        <span className="lbl">{label}</span>
        <span className="coord">x {x.toFixed(2)} · y {y.toFixed(2)}</span>
      </div>
      <div className="a-xy">
        <div className="grid" />
        <div className="axis x" /><div className="axis y" />
        <div className="cross" style={{ left: x * 100 + '%', top: y * 100 + '%' }} />
      </div>
    </div>
  );
}

function ColorWheelCell({ label, h, s }) {
  const rad = s * 32;
  const x = 54 + rad * Math.cos((h - 90) * Math.PI / 180);
  const y = 54 + rad * Math.sin((h - 90) * Math.PI / 180);
  return (
    <div className="a-wheel-cell">
      <span className="lbl">{label}</span>
      <div className="a-wheel">
        <div className="pip" style={{ left: x + 'px', top: y + 'px' }} />
      </div>
    </div>
  );
}

function SelectRow({ options, value }) {
  return (
    <div className="a-pills" style={{ margin: 0 }}>
      {options.map(o => <button key={o} className={o === value ? 'on' : ''}>{o}</button>)}
    </div>
  );
}

function Param({ p }) {
  if (p.kind === 'slider') return <Slider label={p.label} value={p.default} min={p.min} max={p.max} step={p.step} unit={p.unit} />;
  if (p.kind === 'stepper') return (
    <div className="a-slider" style={{display:'flex', justifyContent:'space-between', alignItems:'center', paddingTop: 14, paddingBottom: 14}}>
      <span className="lbl" style={{fontFamily:'var(--font-display)', fontSize: 15}}>{p.label}</span>
      <Stepper value={p.default} />
    </div>
  );
  if (p.kind === 'select') return (
    <div style={{padding: '12px 0', borderBottom: '1px solid var(--ink-3)'}}>
      <div style={{fontFamily:'var(--font-display)', fontSize: 15, marginBottom: 8}}>{p.label}</div>
      <SelectRow options={p.options} value={p.default} />
    </div>
  );
  if (p.kind === 'text') return (
    <div style={{padding: '12px 0', borderBottom: '1px solid var(--ink-3)'}}>
      <div style={{fontFamily:'var(--font-display)', fontSize: 15, marginBottom: 8}}>{p.label}</div>
      <div className="a-text-input">{p.default}</div>
    </div>
  );
  return null;
}

/* SVG pictograms for category cards */
function CatPicto({ id }) {
  const common = { width: 36, height: 36, viewBox: '0 0 36 36', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5 };
  if (id === 'COLOR') return <svg {...common}><circle cx="12" cy="14" r="8"/><circle cx="22" cy="18" r="8"/><circle cx="18" cy="24" r="8"/></svg>;
  if (id === 'STYLIZE') return <svg {...common}><path d="M4 28 L14 8 L20 20 L32 6"/><circle cx="4" cy="28" r="2" fill="currentColor"/><circle cx="32" cy="6" r="2" fill="currentColor"/></svg>;
  if (id === 'DISTORT') return <svg {...common}><path d="M4 18 Q10 8 18 18 T32 18"/><path d="M4 24 Q10 14 18 24 T32 24"/></svg>;
  if (id === 'GLITCH') return <svg {...common}><rect x="4" y="8" width="14" height="4"/><rect x="10" y="16" width="22" height="4"/><rect x="6" y="24" width="18" height="4"/></svg>;
  if (id === 'INPUT') return <svg {...common}><rect x="6" y="10" width="24" height="16" rx="2"/><circle cx="18" cy="18" r="4"/></svg>;
  if (id === 'OUTPUT') return <svg {...common}><path d="M8 8 L28 18 L8 28 Z"/></svg>;
  return null;
}

function PresetGlyph({ id }) {
  const common = { width: '100%', height: '100%', viewBox: '0 0 120 42', preserveAspectRatio: 'none' };
  if (id === 'bloom') return <svg {...common}><g stroke="rgba(255,255,255,0.5)" fill="none"><circle cx="30" cy="21" r="14"/><circle cx="30" cy="21" r="8"/><circle cx="30" cy="21" r="3" fill="rgba(255,255,255,0.5)"/></g></svg>;
  if (id === 'noir') return <svg {...common}><g stroke="rgba(255,255,255,0.6)" fill="none"><line x1="0" y1="8" x2="120" y2="8"/><line x1="0" y1="14" x2="120" y2="14"/><line x1="0" y1="20" x2="120" y2="20"/><line x1="0" y1="26" x2="120" y2="26"/><line x1="0" y1="32" x2="120" y2="32"/></g></svg>;
  if (id === 'ritual') return <svg {...common}><g stroke="rgba(255,255,255,0.55)" fill="none"><polygon points="60,4 110,38 10,38"/><circle cx="60" cy="28" r="4"/></g></svg>;
  if (id === 'glitch1') return <svg {...common}><g fill="rgba(0,0,0,0.6)"><rect x="10" y="6" width="36" height="6"/><rect x="60" y="14" width="24" height="6"/><rect x="20" y="22" width="60" height="4"/><rect x="80" y="30" width="30" height="6"/></g></svg>;
  if (id === 'paper') return <svg {...common}><g stroke="rgba(0,0,0,0.3)" fill="none"><path d="M0 21 Q 30 10 60 21 T 120 21"/><path d="M0 14 Q 30 4 60 14 T 120 14"/><path d="M0 28 Q 30 18 60 28 T 120 28"/></g></svg>;
  if (id === 'stage') return <svg {...common}><g stroke="rgba(0,0,0,0.7)" fill="none"><rect x="40" y="6" width="40" height="30"/><line x1="40" y1="6" x2="80" y2="36"/><line x1="80" y1="6" x2="40" y2="36"/></g></svg>;
  return null;
}

/* ═══════════ PHONE ═══════════ */
function Phone({ label, time = '21:47', children }) {
  return (
    <div>
      <div className="phone">
        <div className="phone-screen a-screen">
          <div className="phone-statusbar a-statusbar">
            <span className="mono">{time}</span>
            <div className="island" />
            <span className="mono">⏺ LIVE</span>
          </div>
          <div className="screen-body">{children}</div>
        </div>
      </div>
      <div className="phone-label">{label}</div>
    </div>
  );
}

/* ═══════════ S1 · HOME ═══════════ */
function S1Home() {
  return <>
    <div className="a-header">
      <div className="pre">
        <span className="folio"><span className="num">I</span> Spatial Iteration · Vol. II</span>
        <span className="a-stamp live"><span className="dot" />REC</span>
      </div>
      <h1>Console,<br/><span className="ital">paper edition.</span></h1>
      <div className="dek">a field manual for the iteration engine — session 03, tuesday night.</div>
      <div className="byline">
        <span>Set № 003</span>
        <span>21:47 · 01:23 in</span>
      </div>
    </div>

    <div className="a-metrics">
      <div className="a-metric">
        <span className="k">Frame rate</span>
        <span className="v">{METRICS.fps}<span className="u">fps</span></span>
        <div className="bar"><i style={{width: '88%'}} /></div>
      </div>
      <div className="a-metric">
        <span className="k">Budget</span>
        <span className="v">{METRICS.used}<span className="u">/{METRICS.budget} ms</span></span>
        <div className="bar"><i style={{width: (METRICS.used/METRICS.budget*100)+'%'}} /></div>
      </div>
      <div className="a-metric">
        <span className="k">Link RTT</span>
        <span className="v">{METRICS.rtt}<span className="u">ms</span></span>
        <div className="bar"><i style={{width: '42%'}} /></div>
      </div>
    </div>

    <div className="a-sec">
      <span className="ch">Chapter</span>
      <span className="no">I · Categories</span>
      <span className="rule" />
      <span className="stat">6 total · 4 active</span>
    </div>

    <div className="a-cards">
      {CATEGORIES.slice(0,4).map((c, i) => (
        <div key={c.id} className={'a-card' + (i === 0 ? ' selected' : '')}>
          <span className="corner-tl" /><span className="corner-br" />
          <div className="picto"><CatPicto id={c.id} /></div>
          <span className="num">№ 0{i+1} — {c.count} filters</span>
          <div className="name">{c.name}<span className="it">{c.id === 'COLOR' ? 'tint & light' : c.id === 'STYLIZE' ? 'form & texture' : c.id === 'DISTORT' ? 'warp & bend' : 'break & repair'}</span></div>
          <div className="foot">
            <span>ch. {i+1}</span>
            <span className="on">{[3,2,4,1][i]} ON</span>
          </div>
        </div>
      ))}
    </div>

    <div className="a-sec">
      <span className="ch">Now Playing</span>
      <span className="no">Preset</span>
      <span className="rule" />
    </div>
    <div className="a-live-preset">
      <div className="color-col" />
      <div className="info">
        <div className="k">Recalled 00:02:14 ago</div>
        <div className="n">Bloom Cinema</div>
        <div className="sub">4 filters · 3 overrides · warm opening</div>
      </div>
      <div className="cta">›</div>
    </div>

    <div className="a-page-num">page one</div>

    <div className="a-footer">
      <div className="perf" />
      <div className="actions">
        <button className="a-btn ghost">STOP<span className="kbd">S</span></button>
        <button className="a-btn primary">PRESETS<span className="kbd">P</span></button>
      </div>
    </div>
  </>;
}

/* ═══════════ S2 · FILTER LIST (DISTORT) ═══════════ */
function S2List() {
  const distort = FILTERS.filter(f => f.cat === 'DISTORT');
  const active = { temporal_scan: true, dof: true, kaleido: true };
  const bypass = { motion_blur: true };
  return <>
    <div className="a-header">
      <div className="pre">
        <span className="folio">◂ Back <span className="num">III</span> Distort</span>
        <span className="a-stamp ok"><span className="dot" />3 ON</span>
      </div>
      <h1>Distort,<br/><span className="ital">warp & bend.</span></h1>
      <div className="dek">seven instruments — drag the handle to reorder, tap a row to open.</div>
    </div>

    <div className="a-tabs">
      <div className="t on">Active<span className="n">3</span></div>
      <div className="t">All<span className="n">7</span></div>
      <div className="t">Bypass<span className="n">1</span></div>
      <div className="t">A→Z</div>
    </div>

    {distort.map((f, i) => (
      <div key={f.id} className={'a-row' + (active[f.id] ? ' active' : '') + (bypass[f.id] ? ' bypassed' : '')}>
        <span className="handle">☰ {String(i+1).padStart(2,'0')}</span>
        <div className="nm">{f.name}<span className="sub">{f.params.map(p => p.label).slice(0,2).join(' · ') || 'no params'}</span></div>
        <span className="cost">{(Math.random()*5+0.8).toFixed(1)} ms</span>
        {bypass[f.id] ? <span className="badge">BYP</span> : <span className="badge">{f.params.length}P</span>}
        <Toggle on={!!active[f.id]} />
      </div>
    ))}

    <div className="a-page-num">chapter three · verso</div>

    <div className="a-footer">
      <div className="actions">
        <button className="a-btn ghost">← HOME</button>
        <button className="a-btn">BYPASS ALL</button>
      </div>
    </div>
  </>;
}

/* ═══════════ S3 · FILTER DETAIL (TemporalScan) ═══════════ */
function S3Detail() {
  const f = FILTERS.find(x => x.id === 'temporal_scan');
  return <>
    <div className="a-header">
      <div className="pre">
        <span className="folio">◂ Distort · Fig. 4 of 7</span>
        <Toggle on={true} />
      </div>
      <h1>Temporal<br/><span className="ital">Scan.</span></h1>
      <div className="dek">angular slit-scan sweep — integrates past frames along a rotating axis.</div>
    </div>

    <div className="a-ticket">
      <div className="stub">
        <span>FIG. 04 · DISTORT</span>
        <span className="dot">— — — —</span>
        <span>3.2 MS · 4/7</span>
      </div>
      <div className="body">
        <h2>30 frames<span className="ital"> / ≈ 1.0 s</span></h2>
        <p>buffer length controls how far the slit reaches into the past.</p>
        <div className="kv">
          <div className="c">Angle<b>45°</b></div>
          <div className="c">Cost<b>3.2 ms</b></div>
          <div className="c">Order<b>4th</b></div>
        </div>
      </div>
    </div>

    <div className="a-params">
      <Slider label="Buffer size" value={f.params[0].default} min={f.params[0].min} max={f.params[0].max} step={f.params[0].step} unit="fr" />
    </div>

    <div className="a-dial-wrap">
      <div>
        <div className="head">Scan angle<span className="sub">rotation of the temporal slit</span></div>
        <div className="readout">
          <div className="r">Live<b>045°</b></div>
          <div className="r">Δ<b>+05°</b></div>
          <div className="r">Rate<b>0.8/s</b></div>
        </div>
      </div>
      <AngleDial value={45} unit="°" />
    </div>

    <div className="a-kv">
      <div className="row"><span className="k">Bypass<span className="sub">skip this filter</span></span><span className="v"><b>off</b></span></div>
      <div className="row"><span className="k">Order<span className="sub">position in chain</span></span><span className="v"><b>4 / 7</b></span></div>
      <div className="row"><span className="k">Cost<span className="sub">per frame average</span></span><span className="v"><b>3.2 ms</b></span></div>
    </div>

    <div className="a-page-num">fig. four</div>

    <div className="a-footer">
      <div className="actions">
        <button className="a-btn ghost">RESET</button>
        <button className="a-btn secondary">A/B</button>
        <button className="a-btn primary">DONE</button>
      </div>
    </div>
  </>;
}

/* ═══════════ S4 · PRESETS ═══════════ */
function S4Presets() {
  return <>
    <div className="a-header">
      <div className="pre">
        <span className="folio"><span className="num">IV</span> Library</span>
        <span className="cap" style={{color:'var(--ink-2)'}}>{PRESETS.length} ITEMS</span>
      </div>
      <h1>Presets,<br/><span className="ital">the book of sets.</span></h1>
      <div className="dek">recall an archived moment — or mark this one as a new leaf.</div>
    </div>

    <div className="a-tabs">
      <div className="t on">All<span className="n">{PRESETS.length}</span></div>
      <div className="t">Opening</div>
      <div className="t">Intro</div>
      <div className="t">Encore</div>
      <div className="t">★ Starred</div>
    </div>

    <div className="a-preset-grid">
      {PRESETS.map((p, i) => (
        <div key={p.id} className={'a-preset' + (i === 0 ? ' recalled' : '')}>
          <div className="stripe" style={{ background: p.color }}>
            <div className="glyph"><PresetGlyph id={p.id} /></div>
          </div>
          <div className="body">
            <div className="nm">{p.name}</div>
            <div className="tags">{p.tags.map(t => <span key={t} className="tag">{t}</span>)}</div>
            <div className="ct"><span>{p.count} filters</span><span>№ 0{i+1}</span></div>
          </div>
        </div>
      ))}
    </div>

    <div className="a-page-num">leaves i — vi</div>

    <div className="a-footer">
      <div className="actions">
        <button className="a-btn ghost">+ SAVE AS…</button>
        <button className="a-btn primary">RECALL</button>
      </div>
    </div>
  </>;
}

/* ═══════════ S5 · CONFIG ═══════════ */
function S5Config() {
  return <>
    <div className="a-header">
      <div className="pre">
        <span className="folio"><span className="num">V</span> Apparatus</span>
        <span className="a-stamp live"><span className="dot" />REC</span>
      </div>
      <h1>Session<br/><span className="ital">configuration.</span></h1>
      <div className="dek">input · output · pipeline budget.</div>
    </div>

    <div className="a-sec">
      <span className="ch">Section</span>
      <span className="no">A · Input source</span>
      <span className="rule" />
    </div>

    <div className="a-input-cards">
      <div className="a-input-card on">
        <div className="ico">⦿</div>
        <div className="lbl">Camera</div>
        <div className="sub">720p · 30</div>
      </div>
      <div className="a-input-card">
        <div className="ico">▷</div>
        <div className="lbl">Video</div>
        <div className="sub">file · loop</div>
      </div>
      <div className="a-input-card">
        <div className="ico">≋</div>
        <div className="lbl">RTMP</div>
        <div className="sub">stream in</div>
      </div>
    </div>

    <div className="a-kv">
      <div className="row"><span className="k">Device<span className="sub">source of frames</span></span><span className="v"><b>FaceTime HD</b>index 0</span></div>
      <div className="row"><span className="k">Resolution<span className="sub">pipeline working size</span></span><span className="v"><b>1280 × 720</b>16:9</span></div>
      <div className="row"><span className="k">Codec<span className="sub">output encoding</span></span><span className="v"><b>H.264</b>baseline</span></div>
      <div className="row"><span className="k">Bitrate<span className="sub">target stream</span></span><span className="v"><b>6 Mbps</b>cbr</span></div>
    </div>

    <div className="a-sec">
      <span className="ch">Section</span>
      <span className="no">B · Budget</span>
      <span className="rule" />
      <span className="stat">head 5.5 ms</span>
    </div>

    <div className="a-meter">
      <div className="head"><span>Frame budget</span><span>{METRICS.used} / {METRICS.budget} ms</span></div>
      <div className="bar"><i style={{width: (METRICS.used/METRICS.budget*100)+'%'}} /></div>
      <div className="labels"><span>0</span><span>analysis 15</span><span>render 30</span><span>{METRICS.budget} ms</span></div>
    </div>

    <div className="a-params">
      <Slider label="Target FPS" value={30} min={10} max={60} step={1} unit="fps" />
    </div>

    <div className="a-page-num">apparatus</div>

    <div className="a-footer">
      <div className="actions">
        <button className="a-btn ghost">RESET</button>
        <button className="a-btn primary">APPLY</button>
      </div>
    </div>
  </>;
}

/* ═══════════ S6 · STOPPED ═══════════ */
function S6Stopped() {
  return <>
    <div className="a-stopped-hero">
      <div className="kicker">Engine halted · 00:03:41 ago</div>
      <div className="big">the console<br/>rests <em>silent.</em></div>
      <div className="meta">
        <span>last preset · Bloom Cinema</span>
        <span>·</span>
        <span>01:23:12 session</span>
      </div>
    </div>

    <div className="a-sec">
      <span className="ch">Chapter</span>
      <span className="no">VI · Recent sets</span>
      <span className="rule" />
      <span className="stat">last 3</span>
    </div>

    <div className="a-recent">
      {[
        {t:'21:43', n:'Bloom Cinema', d:'4 filters · held 12:04'},
        {t:'21:28', n:'Ritual', d:'6 filters · held 06:10'},
        {t:'21:19', n:'Noir', d:'3 filters · held 04:53'},
      ].map((r,i) => (
        <div key={i} className="r">
          <span className="time">{r.t}</span>
          <div className="nm">{r.n}<span className="sub">{r.d}</span></div>
          <span className="ch">›</span>
        </div>
      ))}
    </div>

    <div className="a-sec">
      <span className="ch">Ledger</span>
      <span className="no">Session totals</span>
      <span className="rule" />
    </div>

    <div className="a-kv">
      <div className="row"><span className="k">Frames processed</span><span className="v"><b>148,720</b></span></div>
      <div className="row"><span className="k">Drops</span><span className="v"><b>12</b>0.008 %</span></div>
      <div className="row"><span className="k">Peak frame ms</span><span className="v"><b>31.8 ms</b>at 21:38</span></div>
      <div className="row"><span className="k">Preset changes</span><span className="v"><b>9</b></span></div>
    </div>

    <div className="a-page-num">end of set</div>

    <div className="a-footer">
      <div className="actions">
        <button className="a-btn ghost">EXPORT LOG</button>
        <button className="a-btn primary">RESUME</button>
      </div>
    </div>
  </>;
}

/* ═══════════ CANVAS ═══════════ */
function PaperCanvas() {
  return (
    <div className="page-wrapper">
      <div className="page-title">Variant A · Paper Console</div>
      <div className="page-sub">Editorial console: papel crema, tinta sepia, bermellón reservado para acciones críticas. Cada pantalla es un capítulo con número romano, folio, stamp de estado y número de página al pie. Cartas seleccionables para categorías e input source; ticket-stub para filter detail; grid de presets con pictograma distintivo por preset. Tipografía Fraunces (display, italic para cursivas editoriales) + IBM Plex Sans (UI) + IBM Plex Mono (datos).</div>
      <div className="phones">
        <Phone label="01 · Home"><S1Home /></Phone>
        <Phone label="02 · Filter list"><S2List /></Phone>
        <Phone label="03 · Filter detail"><S3Detail /></Phone>
        <Phone label="04 · Presets"><S4Presets /></Phone>
        <Phone label="05 · Config"><S5Config /></Phone>
        <Phone label="06 · Stopped"><S6Stopped /></Phone>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<PaperCanvas />);
