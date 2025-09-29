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

  // Remove stray overlay "Close" controls that block UI (safe, idempotent)
  try {
    (function removeStrayCloseButtons(){
      const selectors = ['#modal-close','.modal-close','#suggest-close','.np-close'];
      selectors.forEach(sel => document.querySelectorAll(sel).forEach(el => el.remove()));
      // also remove any visible element whose text is exactly "Close"
      document.querySelectorAll('button, a, div').forEach(el=>{
        try { if ((el.textContent||'').trim().toLowerCase() === 'close') el.remove(); } catch(e){}
      });
      // --- NEW: remove suggest-modal overlay if present (we keep inline card #inline-suggest) ---
      try {
        document.querySelectorAll('#suggest-modal, .modal-backdrop').forEach(el => {
          // only remove overlays that appear to be the suggestion modal/backdrop
          if (el.id === 'suggest-modal' || el.querySelector && (el.querySelector('#suggest-form') || el.querySelector('#suggest-close'))) {
            el.remove();
          }
        });
        // defensive: remove any full-screen .modal that contains suggest elements
        document.querySelectorAll('.modal').forEach(el=>{
          if (el.querySelector && (el.querySelector('#suggest-form') || el.querySelector('#suggest-close') || el.querySelector('#suggest-modal'))) el.remove();
        });
      } catch(e){}
      document.body.style.pointerEvents = 'auto';
      document.body.style.overflow = 'auto';
    })();
  } catch (err) { console.warn('cleanup overlay failed', err); }

  // slideshow DOM (no dots/polka anywhere)
  const slideElems = Array.from(document.querySelectorAll('.slide'));
  const prevBtn = document.querySelector('.slide-nav.prev') || document.querySelector('.prev');
  const nextBtn = document.querySelector('.slide-nav.next') || document.querySelector('.next');
  // NOTE: all dots/polka logic removed — no variables, functions or comments referencing "dot(s)" remain

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
  // single consolidated buildSummaryRow (remove any duplicate definitions)
  function buildSummaryRow(item, idx) {
    const tr = document.createElement('tr');
    tr.className = 'summary';
    tr.dataset.idx = idx;

    // expand cell with accessible button + icon span
    const expTd = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'expand-btn';
    btn.type = 'button';
    btn.setAttribute('aria-expanded', 'false');
    btn.title = 'Expandir detalles';

    const icon = document.createElement('span');
    icon.className = 'icon';
    icon.textContent = '+';

    btn.appendChild(icon);
    expTd.appendChild(btn);

    // name cell
    const nameTd = document.createElement('td');
    nameTd.textContent = item.musical || item.name || 'Sin nombre';

    // urls count cell
    const urlsTd = document.createElement('td');
    const span = document.createElement('span');
    span.className = 'count-badge';
    const urlNum = (item.urls && item.urls.length) ? item.urls.length : 0;
    span.textContent = `${urlNum} URL(s)`;
    urlsTd.appendChild(span);

    // changes cell (always show a count; tooltip shows +added / -removed)
    const changesTd = document.createElement('td');
    const k = keyForItem ? keyForItem(item) : JSON.stringify(item);
    const ch = (typeof changesMap !== 'undefined' && changesMap && changesMap[k]) ? changesMap[k] : { added: 0, removed: 0, total: 0 };

    const badge = document.createElement('button');
    badge.className = ch.total > 0 ? 'btn small change-badge' : 'btn small change-none';
    badge.type = 'button';
    badge.title = `Cambios: +${ch.added} / -${ch.removed}`;
    badge.textContent = `${ch.total} cambios`;
    badge.addEventListener('click', (ev) => {
      ev.stopPropagation();
      try { showChangesForItem(item, k); } catch(e) { console.warn('open changes failed', e); }
    });
    changesTd.appendChild(badge);

    tr.appendChild(expTd);
    tr.appendChild(nameTd);
    tr.appendChild(urlsTd);
    tr.appendChild(changesTd);

    // toggle handlers (button and row click)
    function toggleIconAndDetails() {
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      icon.textContent = open ? '+' : '–';
      if (typeof toggleDetails === 'function') toggleDetails(idx);
    }

    btn.addEventListener('click', (e) => { e.stopPropagation(); toggleIconAndDetails(); });
    tr.addEventListener('click', () => { toggleIconAndDetails(); });

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

    // modern expand button (icon only, no numeric badge)
    const expTd = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'expand-btn';
    btn.type = 'button';
    btn.setAttribute('aria-expanded', 'false');
    btn.title = 'Expandir detalles';

    const icon = document.createElement('span');
    icon.className = 'icon';
    icon.textContent = '+'; // toggled in event listener

    // NO url-count element created anymore
    btn.appendChild(icon);
    expTd.appendChild(btn);

    const nameTd = document.createElement('td');
    nameTd.textContent = item.musical || item.name || 'Sin nombre';

    const urlsTd = document.createElement('td');
    const span = document.createElement('span');
    span.className = 'count-badge';
    const urlNum = (item.urls && item.urls.length) ? item.urls.length : 0;
    span.textContent = `${urlNum} URL(s)`;
    urlsTd.appendChild(span);

    const changesTd = document.createElement('td');
    const k = keyForItem ? keyForItem(item) : JSON.stringify(item);
    const ch = (typeof changesMap !== 'undefined' && changesMap) ? changesMap[k] : null;
    if (ch && ch.total > 0) {
      const badge = document.createElement('button');
      badge.className = 'btn small change-badge';
      badge.type = 'button';
      badge.title = `Ver cambios: +${ch.added} / -${ch.removed}`;
      badge.textContent = `${ch.total} cambios`;
      badge.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (typeof markItemAsSeen === 'function') markItemAsSeen(item);
        if (typeof showNotificationPopup === 'function') showNotificationPopup(`Marcado como visto: ${item.musical || item.name}`, 1800);
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

    // toggle behaviour
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      icon.textContent = open ? '+' : '–';
      toggleDetails(idx);
    });

    // allow row click to toggle too
    tr.addEventListener('click', () => {
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      icon.textContent = open ? '+' : '–';
      toggleDetails(idx);
    });

    return tr;
  }

  function buildDetailsRow(item, idx) {
    const tr = document.createElement('tr');
    tr.className = 'details-row hidden';
    tr.dataset.idx = idx;

    const td = document.createElement('td');
    td.colSpan = 4; // span all table columns

    const inner = document.createElement('div');
    inner.className = 'details-inner';

    // load baseline for this item (session snapshot)
    const sessionSnap = loadSessionSnapshot() || [];
    const k = keyForItem(item);
    const baseItem = sessionSnap.find(it => keyForItem(it) === k) || { urls: [] };
    const baseUrls = Array.isArray(baseItem.urls) ? baseItem.urls.slice() : [];
    const curUrls = Array.isArray(item.urls) ? item.urls.slice() : [];

    // union of URLs so we can show removed ones too
    const allUrlsMap = new Map();
    baseUrls.forEach(u => allUrlsMap.set(u, { url: u, inBase: true, inCur: false }));
    curUrls.forEach(u => {
      const entry = allUrlsMap.get(u);
      if (entry) entry.inCur = true; else allUrlsMap.set(u, { url: u, inBase: false, inCur: true });
    });

    // header / summary for details
    const hdr = document.createElement('div');
    hdr.style.display = 'flex';
    hdr.style.alignItems = 'center';
    hdr.style.justifyContent = 'space-between';
    hdr.style.gap = '12px';
    hdr.style.marginBottom = '8px';

    const title = document.createElement('div');
    title.style.fontWeight = '700';
    title.textContent = item.musical || item.name || 'Sin nombre';

    const summary = document.createElement('div');
    const added = [...allUrlsMap.values()].filter(e => e.inCur && !e.inBase).length;
    const removed = [...allUrlsMap.values()].filter(e => e.inBase && !e.inCur).length;
    summary.innerHTML = `<span style="color:#c43ea6;font-weight:700">${added}</span> añadidos &nbsp; <span style="color:#777">${removed}</span> eliminados`;

    hdr.appendChild(title);
    hdr.appendChild(summary);
    inner.appendChild(hdr);

    // details table for urls
    const table = document.createElement('table');
    table.className = 'details-table';
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    table.style.marginTop = '6px';

    // row builder
    function buildUrlRow(entry, index) {
      const r = document.createElement('tr');
      r.style.borderBottom = '1px solid rgba(0,0,0,0.04)';
      r.style.verticalAlign = 'middle';

      const labelTd = document.createElement('td');
      labelTd.style.padding = '10px 8px';
      labelTd.style.width = '36%';

      // friendly label or simple host
      const labelText = labelForUrl(item.musical || item.name, entry.url);
      const a = document.createElement('a');
      a.href = entry.url.startsWith('http') ? entry.url : 'https://' + entry.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.className = 'url-chip';
      a.textContent = labelText;
      a.title = entry.url;
      labelTd.appendChild(a);

      const urlTd = document.createElement('td');
      urlTd.style.padding = '10px 8px';
      urlTd.style.color = '#6b4f5f';
      urlTd.style.fontSize = '0.9rem';
      urlTd.textContent = entry.url;

      const stateTd = document.createElement('td');
      stateTd.style.padding = '10px 8px';
      stateTd.style.textAlign = 'right';
      stateTd.style.width = '18%';

      // status badge
      const badge = document.createElement('span');
      badge.style.padding = '.36rem .6rem';
      badge.style.borderRadius = '999px';
      badge.style.fontWeight = '700';
      badge.style.fontSize = '.85rem';
      if (entry.inCur && !entry.inBase) {
        badge.textContent = 'añadido';
        badge.style.background = 'linear-gradient(90deg,#ff9ac2,#d57cff)';
        badge.style.color = '#fff';
        r.style.background = 'linear-gradient(90deg, rgba(255,245,250,0.6), transparent)';
      } else if (!entry.inCur && entry.inBase) {
        badge.textContent = 'eliminado';
        badge.style.background = 'rgba(220,220,220,0.9)';
        badge.style.color = '#6b6b6b';
        urlTd.style.textDecoration = 'line-through';
        urlTd.style.opacity = '0.7';
      } else {
        badge.textContent = 'sin cambios';
        badge.style.background = 'rgba(240,240,245,0.9)';
        badge.style.color = '#6b6b6b';
      }
      stateTd.appendChild(badge);

      const actionsTd = document.createElement('td');
      actionsTd.style.padding = '10px 8px';
      actionsTd.style.width = '8%';
      actionsTd.style.textAlign = 'right';

      const jsonBtn = document.createElement('button');
      jsonBtn.className = 'btn ghost small';
      jsonBtn.textContent = 'JSON';
      jsonBtn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const payload = {
          url: entry.url,
          inBaseline: !!entry.inBase,
          inCurrent: !!entry.inCur
        };
        // show small ephemeral preformatted box
        const box = document.createElement('div');
        box.style.position = 'fixed';
        box.style.right = '18px';
        box.style.bottom = '18px';
        box.style.maxWidth = '360px';
        box.style.padding = '10px';
        box.style.background = '#fff';
        box.style.border = '1px solid rgba(0,0,0,0.06)';
        box.style.borderRadius = '8px';
        box.style.boxShadow = '0 12px 30px rgba(0,0,0,0.08)';
        box.innerHTML = `<pre style="white-space:pre-wrap;font-size:.8rem;margin:0">${JSON.stringify(payload, null, 2)}</pre>`;
        document.body.appendChild(box);
        setTimeout(()=>box.remove(), 3000);
      });
      actionsTd.appendChild(jsonBtn);

      r.appendChild(labelTd);
      r.appendChild(urlTd);
      r.appendChild(stateTd);
      r.appendChild(actionsTd);
      return r;
    }

    // append rows in a deterministic order: current urls first, then removed ones
    const curSet = new Set(curUrls);
    // current urls (mark added or unchanged)
    curUrls.forEach((u, i) => {
      const entry = allUrlsMap.get(u) || { url: u, inCur: true, inBase: false };
      table.appendChild(buildUrlRow(entry, i));
    });
    // removed urls (present in base but not in current)
    [...allUrlsMap.values()].filter(e => e.inBase && !e.inCur).forEach((entry, i) => {
      table.appendChild(buildUrlRow(entry, i + 1000));
    });

    // optional bulk actions row
    const footer = document.createElement('div');
    footer.style.display = 'flex';
    footer.style.justifyContent = 'space-between';
    footer.style.alignItems = 'center';
    footer.style.marginTop = '10px';

    const markSeenBtn = document.createElement('button');
    markSeenBtn.className = 'btn primary small';
    markSeenBtn.textContent = 'Marcar musical como visto';
    markSeenBtn.addEventListener('click', () => { markItemAsSeen(item); renderTable(filter(musicals)); });

    const exportBtn = document.createElement('button');
    exportBtn.className = 'btn ghost small';
    exportBtn.textContent = 'Exportar JSON';
    exportBtn.addEventListener('click', () => {
      const payload = {
        meta: changesMap && changesMap[k] ? changesMap[k] : null,
        baseline: baseUrls,
        current: curUrls
      };
      // fallback: open a new window with JSON
      const win = window.open('', '_blank');
      win.document.body.innerHTML = `<pre style="white-space:pre-wrap">${JSON.stringify(payload, null, 2)}</pre>`;
    });

    inner.appendChild(table);
    footer.appendChild(markSeenBtn);
    footer.appendChild(exportBtn);
    inner.appendChild(footer);

    td.appendChild(inner);
    tr.appendChild(td);
    return tr;
  }

  // improved renderTable with friendly empty-state + CTAs
  function renderTable(list) {
    tableBody.innerHTML = '';

    // empty/fallback state
    if (!list || list.length === 0) {
      if (noData) {
        noData.hidden = false;
        noData.textContent = 'No hay musicales aún — añade uno ✨';
      }

      const tr = document.createElement('tr');
      tr.className = 'summary empty-state';
      const td = document.createElement('td');
      td.colSpan = 4;
      td.style.padding = '18px';
      td.style.display = 'flex';
      td.style.gap = '12px';
      td.style.alignItems = 'center';
      td.style.justifyContent = 'flex-start';

      const msg = document.createElement('div');
      msg.textContent = 'No hay musicales configurados todavía. Puedes enviar una sugerencia o reintentar la carga.';
      msg.style.color = '#6d4a5b';
      msg.style.fontSize = '14px';

      const addBtn = document.createElement('button');
      addBtn.className = 'btn';
      addBtn.textContent = 'Enviar sugerencia';
      addBtn.style.marginLeft = '6px';
      addBtn.addEventListener('click', () => {
        const inline = document.getElementById('inline-suggest-form');
        if (inline) {
          inline.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const name = inline.querySelector('[name="name"]');
          if (name) name.focus();
        } else {
          const open = document.getElementById('open-suggest') || document.getElementById('suggest-button');
          if (open) open.click();
          window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        }
      });

      const retry = document.createElement('button');
      retry.className = 'btn';
      retry.textContent = 'Reintentar';
      retry.addEventListener('click', () => {
        retry.disabled = true;
        setTimeout(() => { retry.disabled = false; }, 900);
        fetchData();
      });

      td.appendChild(msg);
      td.appendChild(addBtn);
      td.appendChild(retry);
      tr.appendChild(td);
      tableBody.appendChild(tr);
      return;
    }

    // normal render path
    if (noData) noData.hidden = true;
    list.forEach((item, i) => {
      tableBody.appendChild(buildSummaryRow(item, i));
      tableBody.appendChild(buildDetailsRow(item, i));
    });
  }

  // Controlled details behaviour:
  // - abrir una fila mantiene esa fila abierta
  // - abrir otra fila cierra la anterior
  // - pulsar la misma fila no la cierra (se queda abierta hasta abrir otra)
  let openDetailsIdx = null;

  function closeDetails(idx) {
    try {
      const prevDetails = document.querySelector(`tr.details-row[data-idx="${idx}"]`);
      const prevSummary = document.querySelector(`tr.summary[data-idx="${idx}"]`);
      if (prevDetails) prevDetails.classList.add('hidden');
      if (prevSummary) {
        const btn = prevSummary.querySelector('.expand-btn');
        if (btn) btn.setAttribute('aria-expanded', 'false');
        const icon = prevSummary.querySelector('.icon');
        if (icon) icon.textContent = '+';
      }
    } catch (e) { /* ignore */ }
  }

  function openDetails(idx) {
    try {
      // if same index, do nothing (keep open)
      if (openDetailsIdx === idx) return;

      // close previously open
      if (openDetailsIdx !== null) closeDetails(openDetailsIdx);

      // open the requested one
      const details = document.querySelector(`tr.details-row[data-idx="${idx}"]`);
      const summary = document.querySelector(`tr.summary[data-idx="${idx}"]`);
      if (details) details.classList.remove('hidden');
      if (summary) {
        const btn = summary.querySelector('.expand-btn');
        if (btn) btn.setAttribute('aria-expanded', 'true');
        const icon = summary.querySelector('.icon');
        if (icon) icon.textContent = '–';
      }
      openDetailsIdx = idx;
    } catch (e) { console.warn('openDetails error', e); }
  }

  // backward-compatible toggleDetails: now acts as "open this row"
  // (keeps behavior for other code that calls toggleDetails)
  function toggleDetails(idx) {
    openDetails(idx);
  }

  // Optional helper to close everything (if you want a button to collapse all)
  function closeAllDetails() {
    if (openDetailsIdx !== null) {
      closeDetails(openDetailsIdx);
      openDetailsIdx = null;
    }
  }

  // helpers
  function updateLastChecked() { 
    if (lastCheckedEl) {
      try {
        lastCheckedEl.textContent = new Date().toLocaleString();
        // trigger CSS pulse (remove after animation)
        lastCheckedEl.classList.remove('pulse-on');
        // force reflow then add to restart animation
        void lastCheckedEl.offsetWidth;
        lastCheckedEl.classList.add('pulse-on');
        setTimeout(() => lastCheckedEl.classList.remove('pulse-on'), 1400);
      } catch (e) { /* ignore */ }
    }
    // Also ensure the auto-refresh toggle has neon if autoRefresh is enabled
    try {
      if (typeof autoRefresh !== 'undefined' && autoRefresh && arToggle) {
        arToggle.classList.add('neon');
        // keep the AR state text updated (already handled elsewhere)
      } else if (arToggle) {
        arToggle.classList.remove('neon');
      }
    } catch (e) {}
  }
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

  // slideshow controls (now optional random order)
  const RANDOMIZE_SLIDES = true;

  function showSlide(index) {
    if (!slideElems.length) return;
    currentIndex = (index + slideElems.length) % slideElems.length;
    slideElems.forEach((s, i) => s.classList.toggle('active', i === currentIndex));
  }

  function showRandomSlide() {
    if (!slideElems.length) return;
    if (slideElems.length === 1) { showSlide(0); return; }
    let next;
    // pick a random index different from currentIndex
    do { next = Math.floor(Math.random() * slideElems.length); } while (next === currentIndex);
    showSlide(next);
  }

  function nextSlide() { showSlide(currentIndex + 1); }
  function prevSlide() { showSlide(currentIndex - 1); }

  function startSlideAuto() {
    stopSlideAuto();
    slideAutoId = setInterval(RANDOMIZE_SLIDES ? showRandomSlide : nextSlide, 5000);
  }
  function stopSlideAuto() { if (slideAutoId) { clearInterval(slideAutoId); slideAutoId = null; } }

  // events
  if (search) search.addEventListener('input', () => renderTable(filter(musicals)));
  if (arToggle) arToggle.addEventListener('click', () => {
    autoRefresh = !autoRefresh;
    if (arState) arState.textContent = autoRefresh ? 'ON' : 'OFF';
    if (autoRefresh) { intervalId = setInterval(fetchData, 8000); fetchData(); } else { clearInterval(intervalId); }
  });
  if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopSlideAuto(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopSlideAuto(); });

  // --- Safe modal controls: guard against missing elements and provide fallbacks ---
  try {
    // original modal id used by some parts of the UI
    if (modal && modalClose) {
      modalClose.addEventListener('click', () => modal.setAttribute('aria-hidden','true'));
      modal.addEventListener('click', (e) => { if (e.target === modal) modal.setAttribute('aria-hidden','true'); });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.setAttribute('aria-hidden','true'); });
    } else {
      // fallback bindings for the suggestion modal elements actually present in the templates
      const suggestModal = document.getElementById('suggest-modal');
      const suggestClose = document.getElementById('suggest-close');
      const suggestCancel = document.getElementById('suggest-cancel');
      const openSuggest = document.getElementById('open-suggest');

      if (suggestClose) suggestClose.addEventListener('click', () => { suggestModal && (suggestModal.style.display = 'none'); });
      if (suggestCancel) suggestCancel.addEventListener('click', () => { suggestModal && (suggestModal.style.display = 'none'); });
      if (openSuggest && suggestModal) openSuggest.addEventListener('click', () => { suggestModal.style.display = 'block'; suggestModal.setAttribute('aria-hidden','false'); });

      // also allow clicking backdrop to close
      if (suggestModal) {
        suggestModal.addEventListener('click', (e) => { if (e.target === suggestModal) suggestModal.style.display = 'none'; });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') suggestModal.style.display = 'none'; });
      }
    }
  } catch (err) {
    console.error('Modal safe-init failed', err);
  }
  
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
        try { showNotificationPopup(`${added.length} cambios detectados ✨`, 3500); } catch(e) {}
        // NEW: lightweight celebration visual (non-blocking)
        try { celebrate(Math.min(28, Math.max(10, added.length * 6))); } catch(e) {}
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

  // init (use random first slide when enabled)
  renderTable(musicals);
  updateLastChecked();
  if (RANDOMIZE_SLIDES) showRandomSlide(); else showSlide(0);
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

// Ensure modernized styles are enabled on load (idempotent)
document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!document.body.classList.contains('modernized')) {
      document.body.classList.add('modernized');
    }
  } catch (e) { /* noop */ }
});

document.addEventListener('DOMContentLoaded', () => {
  try { document.body.classList.add('modernized'); } catch(e){}
  
  // Reveal .fade-in elements with IntersectionObserver (graceful fallback)
  try {
    const io = new IntersectionObserver((entries, obs) => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll('.fade-in').forEach(el => io.observe(el));
  } catch (err) {
    document.querySelectorAll('.fade-in').forEach(el => el.classList.add('visible'));
  }

  // Wire inline suggestion form (if present)
  const form = document.getElementById('inline-suggest-form');
  if (form && !form.dataset.inited) {
    form.dataset.inited = '1';
    const status = document.getElementById('inline-suggest-status');
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      status.textContent = 'Enviando…';
      const fd = new FormData(form);
      const payload = {
        name: (fd.get('name') || '').trim(),
        email: (fd.get('email') || '').trim(),
        musical: (fd.get('musical') || '').trim(),
        url: (fd.get('url') || '').trim(),
        comment: (fd.get('comment') || '').trim()
      };
      if (!payload.comment && !payload.musical && !payload.url) {
        status.textContent = 'Escribe un comentario o indica el musical/link.';
        return;
      }
      payload.message = [ payload.musical ? `Musical: ${payload.musical}`:null, payload.url ? `Link: ${payload.url}`:null, payload.comment ? `Comentario:\n${payload.comment}`:null ].filter(Boolean).join('\n\n');
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      try {
        const res = await fetch('/suggest', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        const j = await res.json().catch(()=>({ok:false}));
        if (res.ok && j.ok) { status.textContent = '¡Gracias! Enviado.'; form.reset(); }
        else { status.textContent = 'Error: ' + (j.error || j.body || res.statusText || 'no enviado'); }
      } catch(e) {
        status.textContent = 'Error de red';
      } finally { if (btn) btn.disabled = false; setTimeout(()=>status.textContent='',2500); }
    });
  }
});

// Ejecutar en DevTools Console
document.querySelectorAll('#suggest-modal, .modal, .modal-backdrop, .notification-popup, .toast, #tm-test-popup').forEach(el=>el.remove());
document.body.style.pointerEvents = 'auto';
document.body.style.overflow = 'auto';

// Safe helper (do NOT run automatically). Call from the console only if you need to force-remove overlays.
window.cleanupSuggestionOverlays = function cleanupSuggestionOverlays(){
  document.querySelectorAll('#suggest-modal, .modal, .modal-backdrop, .notification-popup, .toast, #tm-test-popup')
    .forEach(el => el.remove());
  document.body.style.pointerEvents = 'auto';
  document.body.style.overflow = 'auto';
};

// Guard server-only telegram helper (prevents require(...) in browser)
if (typeof window === 'undefined') {
  const fetch = require('node-fetch');
  const FormData = require('form-data');

  async function sendTelegramWithJson(botToken, chatId, caption, changes) {
    const jsonString = JSON.stringify(changes, null, 2);
    const form = new FormData();
    form.append('chat_id', chatId);
    form.append('caption', caption);
    form.append('document', Buffer.from(jsonString, 'utf8'), {
      filename: `bom-changes-${new Date().toISOString().replace(/[:.]/g,'-')}.json`,
      contentType: 'application/json'
    });

    const res = await fetch(`https://api.telegram.org/bot${botToken}/sendDocument`, {
      method: 'POST',
      body: form
    });
    if (!res.ok) throw new Error(`Telegram error ${res.status}`);
    return res.json();
  }
}

/**
 * Return a friendly label for a URL, e.g. "Wicked entradas", "Wicked elenco",
 * falling back to musical name or hostname when no rule matches.
 */
function titleCase(s) {
  return String(s || '').replace(/[-_]/g, ' ').split(/\s+/).map(w => {
    return w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : '';
  }).filter(Boolean).join(' ');
}

/**
 * Friendly label for a URL:
 * - If the hostname matches the musical (e.g. wicked.com + musical "Wicked") -> "Wicked"
 * - If the path implies cast/cast/ el/enco -> "Wicked elenco"
 * - Otherwise falls back to heuristics like "Wicked entradas" or "Wicked · provider"
 */
function labelForUrl(musical, urlStr) {
  try {
    const u = new URL(urlStr.startsWith('http') ? urlStr : 'https://' + urlStr);
    const path = (u.pathname || '/').toLowerCase();
    const host = u.hostname.replace(/^www\./, '').toLowerCase();
    const shortHost = host.split('.')[0];

    const musicalClean = (musical || '').trim();
    const musicalKey = musicalClean.toLowerCase();

    // If musical is provided and host matches musical short name (e.g. wicked.com)
    if (musicalKey && shortHost === musicalKey) {
      // exact site root -> just "Wicked"
      if (!path || path === '/' || path === '/index.html') return titleCase(musicalClean);
      // cast/elenco pages
      if (path.includes('elenco') || path.includes('cast') || path.includes('cast-member')) return `${titleCase(musicalClean)} elenco`;
      // tickets/entradas pages
      if (path.includes('tickets') || path.includes('entradas') || host.includes('ticket')) return `${titleCase(musicalClean)} entradas`;
      // info/details fallback -> just musical
      return titleCase(musicalClean);
    }

    // If musical not provided, but hostname is meaningful, use host as label
    if (!musicalKey && shortHost) {
      if (!path || path === '/' || path === '/index.html') return titleCase(shortHost);
      if (path.includes('elenco') || path.includes('cast')) return `${titleCase(shortHost)} elenco`;
      if (path.includes('tickets') || path.includes('entradas') || host.includes('ticket')) return `${titleCase(shortHost)} entradas`;
      return titleCase(shortHost);
    }

    // Generic heuristics when musical provided but host differs
    if (path.includes('elenco') || path.includes('cast')) return `${titleCase(musicalClean)} elenco`;
    if (path.includes('entradas') || path.includes('tickets') || host.includes('ticket') || host.includes('entradas')) return `${titleCase(musicalClean)} entradas`;

    // Friendly short host suffix (e.g. "Wicked · ticketmaster")
    if (shortHost && /^([a-z0-9\-]{2,})$/.test(shortHost)) {
      return `${titleCase(musicalClean)} · ${shortHost}`;
    }

    // Final fallback
    return titleCase(musicalClean || shortHost || 'Link');
  } catch (e) {
    return titleCase(musical || '');
  }
}

// Replace the code that creates the URL anchor text / chip with this pattern:
//
// previous code (example):
//   const a = document.createElement('a');
//   a.href = url;
//   a.textContent = url; // <-- replace this
//
// new pattern:
function createUrlChip(musical, url) {
  const a = document.createElement('a');
  a.className = 'url-chip';
  a.href = url.startsWith('http') ? url : 'https://' + url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.textContent = labelForUrl(musical || 'Link', url);
  return a;
}

// Example usage where you iterate item.urls:
// urls.forEach(u => {
//   const chip = createUrlChip(item.musical || item.name || 'Musical', u);
//   urlsTd.appendChild(chip);
// });

/* helper: show changes for an item (modal if available, fallback overlay) */
function showChangesForItem(item, key) {
  const sess = loadSessionSnapshot() || [];
  const base = (sess.find(it => keyForItem(it) === key) || { urls: [] }).urls || [];
  const cur = (musicals.find(it => keyForItem(it) === key) || { urls: [] }).urls || [];

  const prevSet = new Set(base);
  const curSet = new Set(cur);
  const addedList = cur.filter(u => !prevSet.has(u));
  const removedList = base.filter(u => !curSet.has(u));
  const meta = changesMap && changesMap[key] ? changesMap[key] : { added: addedList.length, removed: removedList.length, total: addedList.length + removedList.length };

  // build content
  const makeList = (arr) => arr.length ? `<ul style="margin:6px 0 10px 18px">${arr.map(u => `<li><a href="${(u.startsWith('http')?u:'https://'+u)}" target="_blank" rel="noopener noreferrer">${u}</a></li>`).join('')}</ul>` : '<div style="opacity:.8;font-size:.95rem">— ninguno —</div>';

  const html = `
    <div style="font-weight:700;margin-bottom:8px">${(item.musical || item.name || 'Item')}</div>
    <div style="font-size:.95rem;margin-bottom:8px">Cambios: <strong style="color:#c43ea6">${meta.total}</strong> ( +${meta.added} / -${meta.removed} )</div>
    <div style="margin-bottom:8px"><strong>Añadidos</strong>${makeList(addedList)}</div>
    <div style="margin-bottom:8px"><strong>Eliminados</strong>${makeList(removedList)}</div>
    <details style="margin-top:8px;border-top:1px dashed rgba(0,0,0,.04);padding-top:8px"><summary style="cursor:pointer">Ver JSON</summary><pre style="white-space:pre-wrap;font-size:.85rem;margin-top:8px;background:#fff;padding:8px;border-radius:8px;border:1px solid rgba(0,0,0,0.04)">${JSON.stringify({ meta, added: addedList, removed: removedList, baseline: base, current: cur }, null, 2)}</pre></details>
    <div style="display:flex;gap:8px;margin-top:12px">
      <button id="changes-mark-seen" class="btn small change-badge" style="padding:.4rem .6rem">Marcar como visto</button>
      <button id="changes-close" class="btn ghost" style="padding:.35rem .55rem">Cerrar</button>
    </div>
  `;

  // prefer existing modal
  if (modal && modalTitle && modalList) {
    try {
      modalTitle.textContent = `${item.musical || item.name || 'Item'} — Cambios`;
      modalList.innerHTML = html;
      modal.setAttribute('aria-hidden','false');
      modal.style.display = 'block';
      // wire close / mark seen
      const closeBtn = document.getElementById('changes-close');
      const markBtn = document.getElementById('changes-mark-seen');
      if (closeBtn) closeBtn.addEventListener('click', () => { modal.setAttribute('aria-hidden','true'); modal.style.display='none'; });
      if (markBtn) markBtn.addEventListener('click', () => { markItemAsSeen(item); modal.setAttribute('aria-hidden','true'); modal.style.display='none'; renderTable(filter(musicals)); });
    } catch (e) {
      console.warn('showChangesForItem modal failed', e);
    }
    return;
  }

  // fallback: ephemeral overlay
  const overlay = document.createElement('div');
  overlay.style.position = 'fixed';
  overlay.style.left = '0';
  overlay.style.top = '0';
  overlay.style.width = '100vw';
  overlay.style.height = '100vh';
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';
  overlay.style.zIndex = 999999;
  overlay.style.background = 'rgba(12,8,12,0.36)';

  const box = document.createElement('div');
  box.style.maxWidth = '820px';
  box.style.width = '92%';
  box.style.background = 'linear-gradient(90deg,#fff,#fffefc)';
  box.style.border = '1px solid rgba(0,0,0,0.06)';
  box.style.borderRadius = '12px';
  box.style.padding = '16px';
  box.style.boxShadow = '0 20px 50px rgba(0,0,0,0.12)';
  box.innerHTML = html;
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  // wire buttons
  overlay.querySelector('#changes-close')?.addEventListener('click', () => overlay.remove());
  overlay.querySelector('#changes-mark-seen')?.addEventListener('click', () => { markItemAsSeen(item); overlay.remove(); renderTable(filter(musicals)); });
}