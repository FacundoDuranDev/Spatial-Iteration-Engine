/* global React, ReactDOM, FILTERS, CATEGORIES, PRESETS, METRICS */
/*
 * gradio_remote v2 — generic mobile control surface.
 * One JSX, themed by the parent .theme-{paper,industrial,stage} class.
 *
 * Views rendered (each variant shows all four side-by-side):
 *   1. Hub          — 6 categories in a 2x3 grid, no scroll
 *   2. Category     — list of filters, expand-inline + chevron-to-detail
 *   3. Filter       — full-screen detail of TemporalScan (all params)
 *   4. Specs        — same generic container with 4 different filters
 *
 * Static mocks: state is hardcoded per view. Renaming/wiring lives in
 * presentation/widgets/ when we port these to production.
 */

const { useState, useEffect, useRef, useCallback } = React;

/* ═══════════ Variant helpers ═══════════════════════════════ */

const CAT_STROKE = {
  COLOR:   'linear-gradient(180deg, #e88, #b6371a)',
  STYLIZE: 'linear-gradient(180deg, #6cb, #2a5d4a)',
  DISTORT: 'linear-gradient(180deg, #b8c, #5a3f7a)',
  GLITCH:  'linear-gradient(180deg, #ec8, #b57f1a)',
  INPUT:   'linear-gradient(180deg, #aaa, #444)',
  OUTPUT:  'linear-gradient(180deg, #888, #222)',
};

// Initial set of "enabled" filters used by the live preview state.
const INITIAL_ENABLED = new Set([
  'color_grading', 'bloom_cinema',  // COLOR (2)
  'temporal_scan',                   // DISTORT (1)
]);

const filtersByCat = (cat) => FILTERS.filter(f => f.cat === cat);

const countActiveInCat = (catId, enabled) =>
  FILTERS.filter(f => f.cat === catId && enabled.has(f.id)).length;

/* ═══════════ Generic param atoms ═══════════════════════════ */

function Toggle({ on = false, onClick }) {
  const handle = (e) => {
    if (!onClick) return;
    e.stopPropagation();
    onClick();
  };
  return (
    <div role="switch" aria-checked={on}
         className={'v2-toggle' + (on ? ' on' : '')}
         onClick={handle} />
  );
}

function Slider({ label, value, min, max, step, unit }) {
  const pct = ((value - min) / (max - min)) * 100;
  const display = step < 1 ? value.toFixed(2) : String(Math.round(value));
  return (
    <div className="v2-slider">
      <div className="top">
        <span className="lbl">{label}</span>
        <span className="val">{display}{unit ? ' ' + unit : ''}</span>
      </div>
      <div className="track">
        <div className="fill" style={{ width: pct + '%' }} />
        <div className="pin" style={{ left: pct + '%' }} />
      </div>
      <div className="range">
        <span>{min}{unit ? ' ' + unit : ''}</span>
        <span>{max}{unit ? ' ' + unit : ''}</span>
      </div>
    </div>
  );
}

function Stepper({ value }) {
  return (
    <div className="v2-stepper">
      <button>−</button><div className="v">{value}</div><button>+</button>
    </div>
  );
}

function StepperRow({ label, value }) {
  return (
    <div className="v2-row-line">
      <span className="lbl">{label}</span>
      <Stepper value={value} />
    </div>
  );
}

function ToggleRow({ label, on }) {
  return (
    <div className="v2-row-line">
      <span className="lbl">{label}</span>
      <Toggle on={on} />
    </div>
  );
}

function SelectRow({ label, options, value }) {
  return (
    <div>
      <div className="lbl" style={{
        fontFamily: 'var(--v2-font-mono)', fontSize: 'var(--v2-fs-xs)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        color: 'var(--v2-text-2)', marginBottom: 8,
      }}>{label}</div>
      <div className="v2-pills">
        {options.map(o => (
          <button key={o} className={o === value ? 'on' : ''}>{o}</button>
        ))}
      </div>
    </div>
  );
}

function AngleDial({ value = 0, unit = '°' }) {
  const deg = unit === 'rad' ? value * 180 / Math.PI : value;
  const ticks = [];
  for (let i = 0; i < 36; i++) {
    ticks.push(
      <div key={i} className={'tick' + (i % 3 === 0 ? ' maj' : '')}
           style={{ transform: `rotate(${i * 10}deg)` }} />
    );
  }
  return (
    <div className="v2-dial">
      <div className="face">
        {ticks}
        <div className="needle" style={{ transform: `translate(-50%, 0) rotate(${deg}deg)` }} />
        <div className="cap" />
      </div>
      <div className="read">{deg.toFixed(0)}°</div>
    </div>
  );
}

function XYPad({ x = 0.5, y = 0.5, label = 'Position' }) {
  return (
    <div className="v2-xy-wrap">
      <div className="v2-row-line" style={{ minHeight: 'auto' }}>
        <span className="lbl">{label}</span>
        <span style={{
          fontFamily: 'var(--v2-font-mono)', fontSize: 'var(--v2-fs-sm)',
          color: 'var(--v2-accent)',
        }}>x {x.toFixed(2)} · y {y.toFixed(2)}</span>
      </div>
      <div className="v2-xy">
        <div className="grid" />
        <div className="axis x" /><div className="axis y" />
        <div className="cross" style={{ left: x * 100 + '%', top: y * 100 + '%' }} />
      </div>
    </div>
  );
}

function ColorWheelPair({ a, b }) {
  return (
    <div className="v2-color-row">
      {[a, b].map((w, i) => {
        const rad = w.s * 32;
        const x = 48 + rad * Math.cos((w.h - 90) * Math.PI / 180);
        const y = 48 + rad * Math.sin((w.h - 90) * Math.PI / 180);
        return (
          <div className="v2-wheel-cell" key={i}>
            <span className="lbl">{w.label}</span>
            <div className="v2-wheel">
              <div className="pip" style={{ left: x + 'px', top: y + 'px' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TextInput({ label, value }) {
  return (
    <div>
      <div className="lbl" style={{
        fontFamily: 'var(--v2-font-mono)', fontSize: 'var(--v2-fs-xs)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        color: 'var(--v2-text-2)', marginBottom: 8,
      }}>{label}</div>
      <input className="v2-text-input" defaultValue={value} />
    </div>
  );
}

/*
 * Generic param renderer. Single switch over kind. Adding a new kind
 * is one branch here + one CSS class — no per-filter view files.
 */
function Param({ p }) {
  const k = p.kind;
  if (k === 'slider')  return <Slider {...p} value={p.default} />;
  if (k === 'stepper') return <StepperRow label={p.label} value={p.default} />;
  if (k === 'select')  return <SelectRow label={p.label} options={p.options} value={p.default} />;
  if (k === 'angle')   return (
    <div>
      <div className="lbl" style={{
        fontFamily: 'var(--v2-font-mono)', fontSize: 'var(--v2-fs-xs)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        color: 'var(--v2-text-2)', marginBottom: 8, textAlign: 'center',
      }}>{p.label}</div>
      <AngleDial value={p.default} unit={p.unit} />
    </div>
  );
  if (k === 'xypad') return <XYPad x={p.default.x} y={p.default.y} label={p.label} />;
  if (k === 'color_wheel') {
    return null; // rendered as a pair via the parent (see filter detail)
  }
  if (k === 'text') return <TextInput label={p.label} value={p.default} />;
  return <div className="lbl">{p.label}: {String(p.default)}</div>;
}

/* ═══════════ Phone frame chrome ════════════════════════════ */

function Phone({ children, label, theme }) {
  return (
    <div>
      <div className="phone">
        <div className="phone-screen">
          <div className="phone-statusbar">
            <span className="mono" style={{ fontFamily: 'var(--v2-font-mono, ui-monospace)' }}>9:41</span>
            <div className="island" />
            <span className="icons mono" style={{ fontFamily: 'var(--v2-font-mono, ui-monospace)' }}>5G ▮</span>
          </div>
          <div className={'v2-screen theme-' + theme}>
            {children}
          </div>
        </div>
      </div>
      <div className="phone-label">{label}</div>
    </div>
  );
}

/* ═══════════ View 1 — Hub ══════════════════════════════════ */

function HubScreen({ enabled = INITIAL_ENABLED, running = false, onToggleRun, onCategory }) {
  return (
    <>
      <header className="v2-hd">
        <div className="ttl">SIE · Mobile</div>
        <div className={'pill' + (running ? ' on' : '')}>
          <span className="dot" />{running ? 'Live' : 'Stopped'}
        </div>
      </header>

      <div className="v2-kpis" style={{ padding: '6px 16px 0' }}>
        <span className="kpi"><b>{running ? METRICS.fps : '—'}</b> FPS</span>
        <span className="sep">·</span>
        <span className="kpi"><b>{running ? METRICS.used : '—'}</b> / {METRICS.budget} ms</span>
        <span className="sep">·</span>
        <span className="kpi">RTT <b>{running ? METRICS.rtt : '—'}</b> ms</span>
      </div>

      <div className="v2-hub-grid">
        {CATEGORIES.map(c => {
          const active = countActiveInCat(c.id, enabled);
          return (
            <div key={c.id}
                 className={'v2-cat' + (active > 0 ? ' has-active' : '')}
                 style={{ '--cat-stroke': CAT_STROKE[c.id] || 'transparent' }}
                 onClick={() => onCategory && onCategory(c.id)}
                 role="button" tabIndex={0}>
              <div className="cap">{c.id}</div>
              <div className="name">{c.name}</div>
              <div className="meta">
                <span>{c.count} filtros</span>
                <span className={active > 0 ? 'live' : ''}>
                  {active > 0 ? `${active} on` : '—'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <footer className="v2-ft">
        <button className={'v2-btn ' + (running ? 'danger' : 'primary')}
                onClick={() => onToggleRun && onToggleRun()}>
          <span className="gly">{running ? '■' : '▶'}</span>{' '}
          {running ? 'Detener' : 'Iniciar'}
        </button>
        <button className="v2-btn ghost">RITUAL <small>preset</small></button>
      </footer>
    </>
  );
}

/* ═══════════ View 2 — Category list ════════════════════════ */

function CategoryScreen({ catId = 'DISTORT', enabled = INITIAL_ENABLED, onToggle, onBack, onFilter }) {
  const cat = CATEGORIES.find(c => c.id === catId);
  const items = filtersByCat(catId);
  // Expand the first active filter by default (or none).
  const firstOn = items.find(f => enabled.has(f.id));
  const [expandedId, setExpandedId] = useState(firstOn ? firstOn.id : null);
  const activeCount = items.filter(f => enabled.has(f.id)).length;

  return (
    <>
      <header className="v2-hd">
        <button className="back" aria-label="Volver" onClick={onBack}>‹</button>
        <div className="ttl">{cat ? cat.name : catId}</div>
        <div className="pill mono">{items.length} · {activeCount} on</div>
      </header>

      <div className="v2-body">
        <div className="v2-list">
          {items.map(f => {
            const expanded = f.id === expandedId;
            const on = enabled.has(f.id);
            return (
              <div key={f.id} className={'v2-row' + (expanded ? ' expanded' : '')}>
                <div className="head"
                     onClick={() => setExpandedId(expanded ? null : f.id)}
                     role="button" tabIndex={0}>
                  <Toggle on={on} onClick={() => onToggle && onToggle(f.id)} />
                  <span className="name">{f.name}</span>
                  <span className="grip" onClick={(e) => e.stopPropagation()}>⋮⋮</span>
                  <span className="chev" title="Abrir detalle"
                        onClick={(e) => {
                          e.stopPropagation();
                          onFilter && onFilter(f.id);
                        }}>⤢</span>
                </div>
                {expanded && (
                  <div className="body">
                    {f.params.length === 0 && (
                      <div className="empty">Sin parámetros configurables.</div>
                    )}
                    {f.params.slice(0, 2).map(p => (
                      <Param key={p.id} p={p} />
                    ))}
                    {f.params.length > 2 && (
                      <button className="v2-btn ghost"
                              style={{ alignSelf: 'flex-start' }}
                              onClick={() => onFilter && onFilter(f.id)}>
                        Ver {f.params.length - 2} más →
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <footer className="v2-ft">
        <button className="v2-btn ghost">+ Agregar</button>
        <button className="v2-btn primary">Guardar preset</button>
      </footer>
    </>
  );
}

/* ═══════════ View 3 — Filter detail ════════════════════════ */

function FilterDetailScreen({ filterId = 'temporal_scan', enabled = INITIAL_ENABLED, onToggle, onBack }) {
  const f = FILTERS.find(x => x.id === filterId);
  if (!f) return (
    <>
      <header className="v2-hd">
        <button className="back" onClick={onBack}>‹</button>
        <div className="ttl">Filtro no encontrado</div>
      </header>
    </>
  );
  const cat = CATEGORIES.find(c => c.id === f.cat);
  const on = enabled.has(f.id);

  return (
    <>
      <header className="v2-hd">
        <button className="back" aria-label="Volver" onClick={onBack}>‹</button>
        <div className="ttl">{f.name}</div>
        <div className={'pill' + (on ? ' on' : '')}>
          <span className="dot" />{on ? 'ON' : 'OFF'}
        </div>
      </header>

      <div className="v2-body">
        <div className="v2-detail">
          <div className="meta">
            <span>cat <b>{cat ? cat.name : f.cat}</b></span>
            <span>·</span>
            <span>id <b>{f.id}</b></span>
            <span>·</span>
            <span>{f.params.length} params</span>
          </div>

          <div className="v2-row-line">
            <span className="lbl" style={{ fontFamily: 'var(--v2-font-display, var(--v2-font-ui))' }}>
              Enabled
            </span>
            <Toggle on={on} onClick={() => onToggle && onToggle(f.id)} />
          </div>

          {f.params.length > 0 && <div className="group-cap">Parameters</div>}
          {f.params.length === 0 && (
            <div className="empty">Este filtro no expone parámetros configurables.</div>
          )}
          {f.params.map(p => <Param key={p.id} p={p} />)}
        </div>
      </div>

      <footer className="v2-ft">
        <button className="v2-btn ghost" onClick={onBack}>Volver</button>
        <button className="v2-btn primary" onClick={onBack}>Listo</button>
      </footer>
    </>
  );
}

/* ═══════════ View 4 — Specs (showcase 4 filters) ═══════════ */

function SpecsScreen({ onBack }) {
  // pick 4 filters that demonstrate varying complexity
  const cases = [
    { ttl: '1 PARAM (toggle-only)', filter: FILTERS.find(f => f.id === 'invert') },
    { ttl: '3 PARAMS (typical)',     filter: FILTERS.find(f => f.id === 'crt') },
    { ttl: 'WITH ANGLE + SLIDER',    filter: FILTERS.find(f => f.id === 'temporal_scan') },
    { ttl: '6 PARAMS (color_grading)', filter: FILTERS.find(f => f.id === 'color_grading') },
  ];

  return (
    <>
      <header className="v2-hd">
        {onBack && <button className="back" aria-label="Volver" onClick={onBack}>‹</button>}
        <div className="ttl">Generic detail · spec sheet</div>
      </header>
      <div className="v2-body">
        <div className="v2-specs">
          {cases.map(({ ttl, filter }) => (
            <div className="case" key={filter.id}>
              <div className="ttl">{ttl} · {filter.name}</div>
              <div className="inside">
                {filter.params.length === 0 && (
                  <ToggleRow label="Enabled" on={true} />
                )}
                {filter.id === 'color_grading' ? (
                  <>
                    {/* compose color_grading: slider + 2 wheels (paired) + 3 sliders */}
                    <Param p={filter.params[0]} />
                    <ColorWheelPair
                      a={{ label: 'Shadow tint',   h: 210, s: 0.3 }}
                      b={{ label: 'Highlight tint', h: 40,  s: 0.3 }} />
                    <Param p={filter.params[3]} />
                    <Param p={filter.params[4]} />
                    <Param p={filter.params[5]} />
                  </>
                ) : (
                  filter.params.map(p => <Param key={p.id} p={p} />)
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/* ═══════════ Page composer ═════════════════════════════════ */

function ThemeColumn({ theme, label }) {
  return (
    <div className="col">
      <h2>{label}</h2>
      <div className="row-of-phones">
        <Phone label="1 · Hub" theme={theme}><HubScreen /></Phone>
        <Phone label="2 · Category" theme={theme}><CategoryScreen /></Phone>
        <Phone label="3 · Filter detail" theme={theme}><FilterDetailScreen /></Phone>
        <Phone label="4 · Specs" theme={theme}><SpecsScreen /></Phone>
      </div>
    </div>
  );
}

/* ═══════════ Single-phone preview mode ═════════════════════
 * Open in the real phone via:
 *   /v2/index.html?view=hub|cat|detail|specs&theme=paper|industrial|stage
 * Renders ONE screen full-viewport for actual touch testing.
 * ═══════════════════════════════════════════════════════════ */

function SingleView({ initialView, theme }) {
  // ── Navigation stack ───────────────────────────────────────
  // Each entry: { view, params }. Push on drill-in; pop on back.
  const [stack, setStack] = useState([{ view: initialView, params: {} }]);
  const top = stack[stack.length - 1];

  const push = useCallback((view, params = {}) => {
    setStack(s => [...s, { view, params }]);
  }, []);
  const pop = useCallback(() => {
    setStack(s => s.length > 1 ? s.slice(0, -1) : s);
  }, []);

  // ── Engine-ish state ───────────────────────────────────────
  const [enabled, setEnabled] = useState(() => new Set(INITIAL_ENABLED));
  const [running, setRunning] = useState(false);

  const toggleFilter = useCallback((id) => {
    setEnabled(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);
  const toggleRun = useCallback(() => setRunning(r => !r), []);

  // ── Sync URL hash so reload + native back button work ─────
  useEffect(() => {
    const h = '#' + top.view + (top.params.catId ? '/' + top.params.catId : '')
                + (top.params.filterId ? '/' + top.params.filterId : '');
    if (window.location.hash !== h) {
      window.history.replaceState(null, '', h);
    }
  }, [top.view, top.params.catId, top.params.filterId]);

  // Native browser back — pop our stack instead of leaving the page.
  useEffect(() => {
    const handler = (e) => {
      setStack(s => {
        if (s.length > 1) { e.preventDefault?.(); return s.slice(0, -1); }
        return s;
      });
    };
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, []);

  // ── Body background = theme bg (kills dark page outside the screen) ─
  useEffect(() => {
    document.body.style.background = ({
      paper: '#f1e7d0',
      industrial: '#1c1d1f',
      stage: '#000000',
    })[theme] || '#111';
    return () => { document.body.style.background = '#111'; };
  }, [theme]);

  // ── Render top of stack ────────────────────────────────────
  let screen;
  if (top.view === 'hub') {
    screen = <HubScreen
      enabled={enabled} running={running}
      onToggleRun={toggleRun}
      onCategory={(catId) => push('cat', { catId })} />;
  } else if (top.view === 'cat') {
    screen = <CategoryScreen
      catId={top.params.catId || 'DISTORT'}
      enabled={enabled} onToggle={toggleFilter}
      onBack={pop}
      onFilter={(filterId) => push('detail', { filterId })} />;
  } else if (top.view === 'detail') {
    screen = <FilterDetailScreen
      filterId={top.params.filterId || 'temporal_scan'}
      enabled={enabled} onToggle={toggleFilter}
      onBack={pop} />;
  } else if (top.view === 'specs') {
    screen = <SpecsScreen onBack={stack.length > 1 ? pop : null} />;
  } else {
    screen = <HubScreen enabled={enabled} running={running}
      onToggleRun={toggleRun}
      onCategory={(catId) => push('cat', { catId })} />;
  }

  return (
    <div className={'v2-screen theme-' + theme}
         style={{ width: '100vw', minHeight: '100dvh', height: '100dvh' }}>
      {screen}
    </div>
  );
}

function App() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view');
  const theme = params.get('theme') || 'stage';
  if (view) return <SingleView initialView={view} theme={theme} />;

  return (
    <div className="v2-stack" style={{ flexDirection: 'column' }}>
      <div style={{ padding: '20px 16px 0', color: '#ddd', fontFamily: 'ui-monospace,monospace' }}>
        <h1 style={{ margin: 0, fontSize: 18, letterSpacing: '0.2em', textTransform: 'uppercase' }}>
          gradio_remote v2 — generic filter UI, 3 variants × 4 views
        </h1>
        <p style={{ margin: '8px 0 0', color: '#888', fontSize: 13, maxWidth: 900 }}>
          Same JSX renders all 12 phones. Tokens swap via .theme-* on the screen
          root. The "Filter detail" container takes any entry from data.js and
          composes it from the same atoms — drop-in for new filters.
        </p>
        <p style={{ margin: '8px 0 0', color: '#888', fontSize: 13 }}>
          Para abrir UNA vista en el celu:&nbsp;
          <code style={{ color: '#22f1d0' }}>?view=hub&amp;theme=stage</code>&nbsp;
          (view ∈ hub/cat/detail/specs · theme ∈ paper/industrial/stage)
        </p>
      </div>
      <ThemeColumn theme="paper" label="A · Paper Console" />
      <ThemeColumn theme="industrial" label="B · Industrial Minimal" />
      <ThemeColumn theme="stage" label="C · High-Contrast Stage" />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
