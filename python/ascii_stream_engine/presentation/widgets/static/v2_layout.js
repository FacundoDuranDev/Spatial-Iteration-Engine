/* Mobile dashboard v2 — client-side navigation.
 * Pure DOM class + data-attribute manipulation; CSS does the show/hide.
 * No Python round-trip on tap (tap latency stays under ~16ms).
 *
 * Wires up:
 *   - Hub category cards (data-cat)              -> nav('cat', cat)
 *   - Filter list rows  (.sie-v2-row .chev)      -> nav('detail', filterId)
 *   - Back buttons       (.back[data-nav])        -> back()
 *   - Start/Stop button  (#sie-v2-runbtn)         -> dispatches click on hidden Gradio button
 *
 * URL hash is updated so refresh persists view (#hub | #cat/COLOR | #detail/temporal_scan).
 * Browser back pops the in-app stack instead of leaving the dashboard.
 */
(function () {
  const log = (...args) => console.debug('[sie-v2]', ...args);

  function nav(view, param) {
    const root = document.getElementById('sie-v2-nav');
    if (!root) return;
    root.classList.remove('s-hub', 's-cat', 's-detail');
    root.classList.add('s-' + view);
    if (view === 'cat')    root.dataset.cat = param || '';
    if (view === 'detail') root.dataset.filter = param || '';
    if (view === 'hub') {
      delete root.dataset.cat; delete root.dataset.filter;
    }
    const hash = '#' + view + (param ? '/' + param : '');
    if (window.location.hash !== hash) {
      window.history.pushState({ view, param }, '', hash);
    }
    log('nav ->', view, param);
  }

  function back() {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      nav('hub');
    }
  }

  function applyFromHash() {
    const h = window.location.hash.replace(/^#/, '');
    if (!h || h === 'hub') { nav('hub'); return; }
    const [view, param] = h.split('/');
    if (view === 'cat' || view === 'detail') nav(view, param);
    else nav('hub');
  }

  function bind() {
    const root = document.getElementById('sie-v2-root');
    if (!root || root.dataset.bound === '1') return;
    root.dataset.bound = '1';
    document.body.classList.add('sie-v2-active');

    // Category cards
    root.querySelectorAll('.sie-v2-cat[data-nav-cat]').forEach(el => {
      el.addEventListener('click', () => nav('cat', el.dataset.navCat));
    });

    // Filter row chevrons -> detail
    root.querySelectorAll('.sie-v2-row [data-nav-filter]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        nav('detail', el.dataset.navFilter);
      });
    });

    // Tap on row body (not toggle, not chev) also opens detail.
    root.querySelectorAll('.sie-v2-row .head[data-nav-filter]').forEach(el => {
      el.addEventListener('click', (e) => {
        // Ignore clicks bubbling up from the toggle widget.
        if (e.target.closest('.sie-toggle, .sie-v2-row .chev')) return;
        nav('detail', el.dataset.navFilter);
      });
    });

    // Back buttons
    root.querySelectorAll('[data-nav-back]').forEach(el => {
      el.addEventListener('click', back);
    });

    // Browser back -> intercept and use our nav.
    window.addEventListener('popstate', () => applyFromHash());

    // Restore from URL hash on load.
    applyFromHash();

    // Wire the Start/Stop button to the hidden Gradio button in the same DOM.
    const runBtn = document.getElementById('sie-v2-runbtn');
    if (runBtn && !runBtn.dataset.bound) {
      runBtn.dataset.bound = '1';
      runBtn.addEventListener('click', () => {
        const hidden = document.querySelector('#sie-v2-hidden-startstop button');
        if (hidden) hidden.click();
      });
    }

    log('bound ✓');
  }

  // Gradio re-renders lazily; observe the body for our root showing up.
  const obs = new MutationObserver(() => bind());
  obs.observe(document.body, { childList: true, subtree: true });

  // Initial attempt (page load).
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }

  // Update header KPIs / running pill from a hidden Gradio JSON output.
  // The Python side dispatches input/change on #sie-v2-state-json; we read it
  // and patch the chrome.
  function applyState() {
    const el = document.querySelector('#sie-v2-state-json textarea');
    if (!el) return;
    let s;
    try { s = JSON.parse(el.value || '{}'); } catch (_) { return; }
    // Pill
    const pill = document.getElementById('sie-v2-pill');
    if (pill) {
      pill.classList.toggle('on', !!s.running);
      pill.querySelector('.lbl').textContent = s.running ? 'Live' : 'Stopped';
    }
    // KPIs
    const fps = document.getElementById('sie-v2-kpi-fps');
    const lat = document.getElementById('sie-v2-kpi-lat');
    const rtt = document.getElementById('sie-v2-kpi-rtt');
    if (fps) fps.textContent = s.running ? (s.fps != null ? s.fps.toFixed(1) : '—') : '—';
    if (lat) lat.textContent = s.running ? (s.lat != null ? s.lat.toFixed(1) : '—') : '—';
    if (rtt) rtt.textContent = s.rtt != null ? String(Math.round(s.rtt)) : '—';
    // Run button
    const runBtn = document.getElementById('sie-v2-runbtn');
    if (runBtn) {
      runBtn.classList.toggle('primary', !s.running);
      runBtn.classList.toggle('danger', !!s.running);
      runBtn.querySelector('.gly').textContent = s.running ? '■' : '▶';
      runBtn.querySelector('.lbl').textContent = s.running ? 'Detener' : 'Iniciar';
    }
    // Per-cat live counts
    const counts = s.cat_counts || {};
    document.querySelectorAll('.sie-v2-cat[data-nav-cat]').forEach(card => {
      const cat = card.dataset.navCat;
      const n = counts[cat] || 0;
      card.classList.toggle('has-active', n > 0);
      const meta = card.querySelector('.meta .live');
      if (meta) {
        meta.textContent = n > 0 ? n + ' on' : '—';
        meta.classList.toggle('live', n > 0);
      }
    });
  }
  // Poll the hidden state JSON every 800ms — cheap, avoids
  // depending on Gradio internals.
  setInterval(applyState, 800);

  // Expose for debugging.
  window.SIE_V2 = { nav, back, applyState };
})();
