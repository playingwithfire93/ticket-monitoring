/* consolidated main.js: safe guards, table + collapsible rows, url chips, slideshow */
(() => {
  const api = '/api/monitored-urls';

  // DOM
  const tableBody = document.getElementById('table-body');
  const search = document.getElementById('search');
  const noData = document.getElementById('no-data');
  const lastCheckedEl = document.getElementById('last-checked');
  const arToggle = document.getElementById('toggle-refresh');
  const arState = document.getElementById('ar-state');
  const modal = document.getElementById('modal');
  const modalTitle = document.getElementById('modal-title');
  const modalList = document.getElementById('modal-list');
  const modalClose = document.getElementById('modal-close');

  // slideshow DOM
  const slideElems = Array.from(document.querySelectorAll('.slide'));
  const prevBtn = document.querySelector('.slide-nav.prev') || document.querySelector('.prev');
  const nextBtn = document.querySelector('.slide-nav.next') || document.querySelector('.next');
  // NOTE: slide "dots" removed completely — no DOM created or updated for dots.
  // (createDots/updateDots/dotsWrap intentionally omitted)

  if (!tableBody) { console.error('Missing #table-body — aborting'); return; }

  // state
  let musicals = Array.isArray(window.INITIAL_MUSICALS) ? window.INITIAL_MUSICALS : [];
  let autoRefresh = false;
  let intervalId = null;
  let currentIndex = 0;
  let slideAutoId = null;

  // session snapshot key (keeps baseline for "since you logged in")
  const SESSION_SNAP_KEY = 'tm_session_snapshot_v1';

  // load session baseline (taken at first full data load)
  function loadSessionSnapshot(){
    try {
      const raw = sessionStorage.getItem(SESSION_SNAP_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function saveSessionSnapshot(obj){
    try { sessionStorage.setItem(SESSION_SNAP_KEY, JSON.stringify(obj)); } catch(e){/*ignore*/ }
  }

  // compute a simple key for an item
  function keyForItem(item){
    return (item.id !== undefined ? String(item.id) : (item.musical || item.name || 'unnamed')).toLowerCase();
  }

  // compute changes map comparing baseline -> current
  function computeChangesMap(baselineList = [], currentList = []){
    const baseMap = new Map();
    baselineList.forEach(it => baseMap.set(keyForItem(it), (it.urls || []).slice()));
    const changes = {};
    currentList.forEach(it => {
      const k = keyForItem(it);
      const curUrls = (it.urls || []).slice();
      const prevUrls = baseMap.get(k) || [];
      // detect adds/removes (simple set diff)
      const prevSet = new Set(prevUrls);
      const curSet = new Set(curUrls);
      let added = 0, removed = 0;
      curUrls.forEach(u => { if (!prevSet.has(u)) added++; });
      prevUrls.forEach(u => { if (!curSet.has(u)) removed++; });
      const total = added + removed;
      if (total > 0) changes[k] = { added, removed, total };
    });
    return changes; // keyed by item key
  }

  // mark a single item as seen: update session snapshot for that key
  function markItemAsSeen(item){
    const snap = loadSessionSnapshot() || [];
    const k = keyForItem(item);
    // replace or add
    const newSnap = snap.filter(it => keyForItem(it) !== k);
    newSnap.push(item);
    saveSessionSnapshot(newSnap);
    // recompute changesMap for UI refresh
    changesMap = computeChangesMap(newSnap, musicals);
    renderTable(filter(musicals));
  }

  // global changes map (key -> {added,removed,total})
  let changesMap = {};

  // --- replace buildSummaryRow to show changes badge instead of actions ---
  function buildSummaryRow(item, idx) {
    const tr = document.createElement('tr');
    tr.className = 'summary';
    tr.dataset.idx = idx;

    const expTd = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'expand-btn';
    btn.textContent = '+';
    btn.title = 'Expandir';
    btn.setAttribute('aria-expanded', 'false');
    expTd.appendChild(btn);

    const nameTd = document.createElement('td');
    nameTd.textContent = item.musical || item.name || 'Sin nombre';

    const urlsTd = document.createElement('td');
    const count = (item.urls && item.urls.length) ? item.urls.length : 0;
    const span = document.createElement('span');
    span.className = 'count-badge';
    span.textContent = `${count} URL(s)`;
    urlsTd.appendChild(span);

    // changes column (shows added/removed totals since session baseline)
    const changesTd = document.createElement('td');
    const k = keyForItem(item);
    const ch = changesMap[k];
    if (ch && ch.total > 0) {
      const badge = document.createElement('button');
      badge.className = 'btn small change-badge';
      badge.type = 'button';
      badge.title = `Ver cambios: +${ch.added} / -${ch.removed}`;
      badge.textContent = `${ch.total} cambios`; 
      badge.addEventListener('click', (ev) => {
        ev.stopPropagation();
        // mark as seen and re-render
        markItemAsSeen(item);
        showNotificationPopup(`Marcado como visto: ${item.musical || item.name}`, 1800);
      });
      changesTd.appendChild(badge);
    } else {
      const none = document.createElement('span');
      none.className = 'no-changes';
      none.textContent = '—';
      changesTd.appendChild(none);
    }

    // assemble row (no open-all action column)
    tr.appendChild(expTd);
    tr.appendChild(nameTd);
    tr.appendChild(urlsTd);
    tr.appendChild(changesTd);

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      btn.textContent = open ? '+' : '–';
      toggleDetails(idx);
    });

    return tr;
  }

  // update fetchData to set baseline on first load and compute changes
  async function fetchData() {
    try {
      const res = await fetch(api);
      if (!res.ok) throw new Error('Network response not ok');
      const data = await res.json();
      musicals = Array.isArray(data) ? data : musicals;

      // if no session baseline, take it now (first visit in this tab)
      let sessionSnap = loadSessionSnapshot();
      if (!sessionSnap) {
        saveSessionSnapshot(musicals);
        sessionSnap = loadSessionSnapshot();
      }

      // compute changes relative to session baseline
      changesMap = computeChangesMap(sessionSnap || [], musicals);

      renderTable(filter(musicals));
      updateLastChecked();
    } catch (e) {
      console.error('fetchData', e);
    }
  }

  // ensure initial render sets baseline if needed
  (function initSessionBaseline(){
    const sessionSnap = loadSessionSnapshot();
    if (!sessionSnap && Array.isArray(musicals) && musicals.length) {
      saveSessionSnapshot(musicals);
    }
    changesMap = computeChangesMap(loadSessionSnapshot() || [], musicals || []);
  })();

  /* Replace duplicate buildSummaryRow + buildDetailsRow with the "changes" column version */
  function buildSummaryRow(item, idx) {
    const tr = document.createElement('tr');
    tr.className = 'summary';
    tr.dataset.idx = idx;

    const expTd = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'expand-btn';
    btn.textContent = '+';
    btn.title = 'Expandir';
    btn.setAttribute('aria-expanded', 'false');
    expTd.appendChild(btn);

    const nameTd = document.createElement('td');
    nameTd.textContent = item.musical || item.name || 'Sin nombre';

    const urlsTd = document.createElement('td');
    const count = (item.urls && item.urls.length) ? item.urls.length : 0;
    const span = document.createElement('span');
    span.className = 'count-badge';
    span.textContent = `${count} URL(s)`;
    urlsTd.appendChild(span);

    // changes column (shows added/removed totals since session baseline)
    const changesTd = document.createElement('td');
    const k = keyForItem(item);
    const ch = changesMap[k];
    if (ch && ch.total > 0) {
      const badge = document.createElement('button');
      badge.className = 'btn small change-badge';
      badge.type = 'button';
      badge.title = `Ver cambios: +${ch.added} / -${ch.removed}`;
      badge.textContent = `${ch.total} cambios`;
      badge.addEventListener('click', (ev) => {
        ev.stopPropagation();
        markItemAsSeen(item);
        showNotificationPopup(`Marcado como visto: ${item.musical || item.name}`, 1800);
      });
      changesTd.appendChild(badge);
    } else {
      const none = document.createElement('span');
      none.className = 'no-changes';
      none.textContent = '—';
      changesTd.appendChild(none);
    }

    tr.appendChild(expTd);
    tr.appendChild(nameTd);
    tr.appendChild(urlsTd);
    tr.appendChild(changesTd);

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      btn.textContent = open ? '+' : '–';
      toggleDetails(idx);
    });

    return tr;
  }

  function buildDetailsRow(item, idx) {
    const tr = document.createElement('tr');
    tr.className = 'details-row hidden';
    tr.dataset.idx = idx;

    const td = document.createElement('td');
    td.colSpan = 3; // ensure matches table header columns

    const inner = document.createElement('div');
    inner.className = 'details-inner';

    if (item.urls && item.urls.length) {
      item.urls.forEach(u => {
        const a = document.createElement('a');
        a.className = 'url-chip';
        a.href = u;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.title = u;

        const hostSpan = document.createElement('span');
        hostSpan.className = 'url-host';
        try {
          hostSpan.textContent = new URL(u).hostname + (u.length > 60 ? '…' : '');
        } catch (e) {
          hostSpan.textContent = u;
        }

        a.appendChild(hostSpan);
        inner.appendChild(a);
      });
    } else {
      const p = document.createElement('div');
      p.textContent = 'No URLs';
      inner.appendChild(p);
    }

    td.appendChild(inner);
    tr.appendChild(td);
    return tr;
  }

  function renderTable(list) {
    tableBody.innerHTML = '';
    if (!list || list.length === 0) { if (noData) noData.hidden = false; return; }
    if (noData) noData.hidden = true;
    list.forEach((item, i) => {
      tableBody.appendChild(buildSummaryRow(item, i));
      tableBody.appendChild(buildDetailsRow(item, i));
    });
  }

  function toggleDetails(idx) {
    const details = tableBody.querySelector(`tr.details-row[data-idx="${idx}"]`);
    const btn = tableBody.querySelector(`tr.summary[data-idx="${idx}"] .expand-btn`);
    if (!details) return;
    const isHidden = details.classList.contains('hidden');

    // collapse any open rows first
    Array.from(tableBody.querySelectorAll('tr.details-row')).forEach(r => r.classList.add('hidden'));
    Array.from(tableBody.querySelectorAll('.expand-btn')).forEach(b => { b.textContent = '+'; b.setAttribute('aria-expanded','false'); });

    if (isHidden) {
      details.classList.remove('hidden');
      if (btn) { btn.textContent = '–'; btn.setAttribute('aria-expanded','true'); }
      // sparkle effect
      const inner = details.querySelector('.details-inner');
      if (inner) {
        inner.classList.add('sparkle');
        // remove sparkle after animation finishes
        setTimeout(() => inner.classList.remove('sparkle'), 900);
      }
    } else {
      details.classList.add('hidden');
      if (btn) { btn.textContent = '+'; btn.setAttribute('aria-expanded','false'); }
    }
  }

  // helpers
  function updateLastChecked() { if (lastCheckedEl) lastCheckedEl.textContent = new Date().toLocaleString(); }
  async function fetchData() {
    try {
      const res = await fetch(api);
      if (!res.ok) throw new Error('Network response not ok');
      const data = await res.json();
      musicals = Array.isArray(data) ? data : musicals;
      renderTable(filter(musicals));
      updateLastChecked();
    } catch (e) { console.error('fetchData', e); }
  }
  function filter(list) {
    const q = (search && search.value ? search.value : '').trim().toLowerCase();
    if (!q) return list;
    return list.filter(it => (it.musical || it.name || '').toLowerCase().includes(q));
  }

  // Notification popup + optional Telegram forwarder
  (() => {
    // toggle from console or set true here
    window.SEND_TELEGRAM_ON_NOTIFY = false;

    function createToastElement() {
      let t = document.querySelector('.toast');
      if (!t) {
        t = document.createElement('div');
        t.className = 'toast';
        t.style.position = 'fixed';
        t.style.left = '50%';
        t.style.transform = 'translateX(-50%)';
        t.style.bottom = '22px';
        t.style.padding = '8px 14px';
        t.style.background = 'linear-gradient(90deg,#fff6fb,#fff0f6)';
        t.style.border = '1px solid rgba(255,200,230,0.9)';
        t.style.borderRadius = '10px';
        t.style.boxShadow = '0 12px 36px rgba(255,80,150,0.08)';
        t.style.zIndex = 99998;
        document.body.appendChild(t);
      }
      return t;
    }

    function showToast(msg, ms = 1300) {
      const t = createToastElement();
      t.textContent = msg;
      t.style.opacity = '1';
      t.style.visibility = 'visible';
      clearTimeout(t._hideId);
      t._hideId = setTimeout(() => {
        t.style.opacity = '0';
        t.style.visibility = 'hidden';
      }, ms);
      // also show bottom-right popup
      showNotificationPopup(msg, ms + 800);
    }

    function showNotificationPopup(message, ms = 2200) {
      let np = document.querySelector('.notification-popup');
      if (!np) {
        np = document.createElement('div');
        np.className = 'notification-popup';
        np.style.position = 'fixed';
        np.style.right = '18px';
        np.style.bottom = '18px';
        np.style.zIndex = '99999';
        np.style.maxWidth = '380px';
        np.style.padding = '12px 14px';
        np.style.borderRadius = '12px';
        np.style.background = 'linear-gradient(90deg,#fff6fb,#fff0f6)';
        np.style.border = '1px solid rgba(255,200,230,0.85)';
        np.style.boxShadow = '0 18px 40px rgba(255,80,150,0.12)';
        np.innerHTML = '<div style="font-weight:700;color:#ff2f8f;margin-bottom:6px">Notification</div><div class="np-body" style="color:#3b2b36"></div><button class="np-close" aria-label="Close" style="position:absolute;right:8px;top:8px;background:transparent;border:0;font-size:14px;cursor:pointer;color:#ff2f8f">✕</button>';
        document.body.appendChild(np);
        np.querySelector('.np-close').addEventListener('click', () => hidePopup(np));
      }
      np.querySelector('.np-body').textContent = message;
      np.classList.add('show');
      np.style.opacity = '1';
      np.style.transform = 'translateY(0)';
      clearTimeout(np._hideId);
      np._hideId = setTimeout(() => hidePopup(np), ms);

      // optional: forward to server to send Telegram
      if (window.SEND_TELEGRAM_ON_NOTIFY) {
        fetch('/api/notify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message })
        }).catch((err) => {
          console.warn('Forward to /api/notify failed', err);
        });
      }
    }

    function hidePopup(el) {
      if (!el) el = document.querySelector('.notification-popup');
      if (!el) return;
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      clearTimeout(el._hideId);
      setTimeout(() => {
        if (el && el.parentNode) el.parentNode.removeChild(el);
      }, 360);
    }

    // expose helpers for quick manual testing in console
    window.showToast = showToast;
    window.showNotificationPopup = showNotificationPopup;
    window.hideNotificationPopup = hidePopup;
    window.testNotify = (msg = 'Test notification') => {
      showToast(msg);
      // also try server test route (fire-and-forget)
      try {
        fetch('/admin/test-telegram', { method: 'GET' }).then(r => r.json()).then(j => console.log('admin/test-telegram:', j)).catch(e => console.warn(e));
      } catch (e) { /* ignore */ }
    };

    // auto-log JS errors to console (helps debugging)
    window.addEventListener('error', (ev) => {
      console.error('Uncaught error:', ev.error || ev.message);
    });

  })();

  // slideshow
  function showSlide(index) {
    if (!slideElems.length) return;
    currentIndex = (index + slideElems.length) % slideElems.length;
    slideElems.forEach((s, i) => s.classList.toggle('active', i === currentIndex));
  }
  function nextSlide(){ showSlide(currentIndex + 1); }
  function prevSlide(){ showSlide(currentIndex - 1); }

  // NOTE: marker helpers (creation/update) removed — no decorative markers will be created.
  function startSlideAuto(){ stopSlideAuto(); slideAutoId = setInterval(nextSlide, 5000); }
  function stopSlideAuto(){ if (slideAutoId) { clearInterval(slideAutoId); slideAutoId = null; } }

  // events
  if (search) search.addEventListener('input', () => renderTable(filter(musicals)));
  if (arToggle) arToggle.addEventListener('click', () => {
    autoRefresh = !autoRefresh;
    if (arState) arState.textContent = autoRefresh ? 'ON' : 'OFF';
    if (autoRefresh) { intervalId = setInterval(fetchData, 8000); fetchData(); } else { clearInterval(intervalId); }
  });
  if (modalClose) modalClose.addEventListener('click', () => modal.setAttribute('aria-hidden','true'));
  if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) modal.setAttribute('aria-hidden','true'); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.setAttribute('aria-hidden','true'); });
  if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopSlideAuto(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopSlideAuto(); });

  { 
    // ----- Audio + new-change detection state -----
    let prevChangeKeys = new Set();
    let initialLoadDone = false;

    // preload the provided bell sound
    const notifierAudio = new Audio('/static/door-bell-sound-99933.mp3');
    notifierAudio.preload = 'auto';
    notifierAudio.volume = 0.9;

    // attempt a one-time unlock on first user gesture (some browsers block autoplay)
    document.addEventListener('click', () => {
      // play briefly then stop so subsequent .play() is allowed
      notifierAudio.play().then(() => {
        notifierAudio.pause();
        notifierAudio.currentTime = 0;
      }).catch(() => {/* ignore if blocked */});
    }, { once: true });

    function notifyIfNewChanges(newChangesMap) {
      const newKeys = new Set(Object.keys(newChangesMap || {}));
      const added = [...newKeys].filter(k => !prevChangeKeys.has(k));
      if (initialLoadDone && added.length > 0) {
        // play bell and show popup
        try { notifierAudio.play().catch(()=>{}); } catch(e){/*ignore*/ }
        try { showNotificationPopup(`${added.length} cambios detectados ✨`, 3500); } catch(e){/*ignore*/ }
      }
      prevChangeKeys = newKeys;
      initialLoadDone = true;
    }

    // ---- replace/ensure single fetchData that computes changes and triggers notify ----
    async function fetchData() {
      try {
        const res = await fetch(api);
        if (!res.ok) throw new Error('Network response not ok');
        const data = await res.json();
        musicals = Array.isArray(data) ? data : musicals;

        // ensure session baseline exists for this tab
        let sessionSnap = loadSessionSnapshot();
        if (!sessionSnap) {
          saveSessionSnapshot(musicals);
          sessionSnap = loadSessionSnapshot();
        }

        // compute changes relative to session baseline
        changesMap = computeChangesMap(sessionSnap || [], musicals);

        // notify (sound + popup) if new changes since last fetch
        notifyIfNewChanges(changesMap);

        renderTable(filter(musicals));
        updateLastChecked();
      } catch (e) {
        console.error('fetchData', e);
      }
    }

    // ensure initial baseline state is respected on load
    (function ensureInitialBaseline() {
      const sessionSnap = loadSessionSnapshot();
      if (!sessionSnap && Array.isArray(musicals) && musicals.length) {
        saveSessionSnapshot(musicals);
      }
      changesMap = computeChangesMap(loadSessionSnapshot() || [], musicals || []);
      // set prevChangeKeys to current keys so initial load doesn't trigger sound
      prevChangeKeys = new Set(Object.keys(changesMap || {}));
      initialLoadDone = true;
    })();
  }

  // init
  renderTable(musicals);
  updateLastChecked();
  showSlide(0);
  startSlideAuto();

  // ensure auto-refresh is ALWAYS ON
  autoRefresh = true;
  if (arState) arState.textContent = 'ON';
  if (arToggle) { 
    arToggle.disabled = true;          // prevent toggling
    arToggle.title = 'Auto-refresh fixed ON';
  }
  if (!intervalId) intervalId = setInterval(fetchData, 8000);
  // initial fetch immediately
  setTimeout(fetchData, 200);

  window.addEventListener('load', () => { setTimeout(fetchData, 600); });
  window.plusSlides = (n) => { showSlide(currentIndex + n); stopSlideAuto(); };
})();

/* quick test helper: call /admin/test-telegram and show a popup with the result */
(() => {
  function makePopup(text, ok = true, ms = 3500) {
    let p = document.getElementById('tm-test-popup');
    if (!p) {
      p = document.createElement('div');
      p.id = 'tm-test-popup';
      p.style.position = 'fixed';
      p.style.right = '18px';
      p.style.bottom = '18px';
      p.style.zIndex = 999999;
      p.style.maxWidth = '360px';
      p.style.padding = '12px 14px';
      p.style.borderRadius = '12px';
      p.style.boxShadow = '0 18px 40px rgba(0,0,0,0.08)';
      p.style.fontWeight = '600';
      p.style.fontSize = '14px';
      p.style.backdropFilter = 'blur(4px)';
      document.body.appendChild(p);
    }
    p.textContent = text;
    p.style.background = ok ? 'linear-gradient(90deg,#fff6fb,#fff0f6)' : 'linear-gradient(90deg,#fff6f6,#ffecec)';
    p.style.border = ok ? '1px solid rgba(255,200,230,0.9)' : '1px solid rgba(255,160,160,0.9)';
    p.style.opacity = '1';
    clearTimeout(p._hide);
    p._hide = setTimeout(() => {
      p.style.opacity = '0';
      setTimeout(() => { if (p && p.parentNode) p.parentNode.removeChild(p); }, 300);
    }, ms);
  }

  // call server test endpoint and show popup
  window.sendTestPopup = async function(message = '') {
    try {
      const opts = message ? { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({message}) } : {};
      const res = await fetch('/admin/test-telegram', opts);
      const j = await res.json().catch(() => ({ ok: false, resp: { raw: 'invalid-json' } }));
      if (res.ok && j.ok) {
        makePopup('Telegram test sent ✓', true);
      } else {
        const errMsg = (j && j.resp && j.resp.description) ? j.resp.description : (j && j.resp ? JSON.stringify(j.resp) : 'Unknown error');
        makePopup('Telegram test failed: ' + errMsg, false, 7000);
      }
      // also log full response for debugging
      console.log('/admin/test-telegram =>', res.status, j);
    } catch (e) {
      console.error('test-telegram error', e);
      makePopup('Network error when calling test endpoint', false, 7000);
    }
  };

  // optional: listen to socketio telegram_test events if the page connects via Socket.IO
  if (window.io) {
    try {
      const sock = io(); // requires socket.io client script to be loaded
      sock.on('telegram_test', (data) => {
        if (data && data.ok) makePopup('Telegram server says: sent ✓', true);
        else makePopup('Telegram server reported error', false, 6000);
        console.log('socket telegram_test', data);
      });
    } catch (e) { /* ignore if socket.io not configured */ }
  }
})();

/* NOTE: All "polka/dots" removal runs were deleted — dots support removed at source. */