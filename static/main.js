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
  const dotsWrap = document.querySelector('.slide-dots');

  if (!tableBody) { console.error('Missing #table-body — aborting'); return; }

  // state
  let musicals = Array.isArray(window.INITIAL_MUSICALS) ? window.INITIAL_MUSICALS : [];
  let autoRefresh = false;
  let intervalId = null;
  let currentIndex = 0;
  let slideAutoId = null;

  // ---- table rows ----
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

    const actionsTd = document.createElement('td');
    const openAll = document.createElement('button');
    openAll.className = 'btn small';
    openAll.textContent = 'Abrir 1ª';
    openAll.onclick = (e) => { e.stopPropagation(); if (item.urls && item.urls[0]) window.open(item.urls[0], '_blank'); };
    actionsTd.appendChild(openAll);

    tr.appendChild(expTd);
    tr.appendChild(nameTd);
    tr.appendChild(urlsTd);
    tr.appendChild(actionsTd);

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
  td.colSpan = 4;
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
    Array.from(tableBody.querySelectorAll('tr.details-row')).forEach(r => r.classList.add('hidden'));
    Array.from(tableBody.querySelectorAll('.expand-btn')).forEach(b => { b.textContent = '+'; b.setAttribute('aria-expanded','false'); });
    if (isHidden) { details.classList.remove('hidden'); if (btn) { btn.textContent = '–'; btn.setAttribute('aria-expanded','true'); } }
    else { details.classList.add('hidden'); if (btn) { btn.textContent = '+'; btn.setAttribute('aria-expanded','false'); } }
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
  function showToast(msg, ms = 1300) {
    let t = document.querySelector('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show'); clearTimeout(t._hideId); t._hideId = setTimeout(()=> t.classList.remove('show'), ms);
  }

  // slideshow
  function showSlide(index) {
    if (!slideElems.length) return;
    currentIndex = (index + slideElems.length) % slideElems.length;
    slideElems.forEach((s, i) => s.classList.toggle('active', i === currentIndex));
    updateDots();
  }
  function nextSlide(){ showSlide(currentIndex + 1); }
  function prevSlide(){ showSlide(currentIndex - 1); }
  function createDots(){ if(!dotsWrap) return; dotsWrap.innerHTML = ''; slideElems.forEach((_, i) => { const d = document.createElement('button'); d.className = 'dot'; d.setAttribute('aria-label', `Go to slide ${i+1}`); d.addEventListener('click', () => { showSlide(i); stopSlideAuto(); }); dotsWrap.appendChild(d); }); updateDots(); }
  function updateDots(){ if(!dotsWrap) return; Array.from(dotsWrap.children).forEach((d, i) => d.classList.toggle('active', i === currentIndex)); }
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

  // init
  renderTable(musicals);
  updateLastChecked();
  showSlide(0);
  createDots();
  startSlideAuto();
  window.addEventListener('load', () => { setTimeout(fetchData, 600); });
  window.plusSlides = (n) => { showSlide(currentIndex + n); stopSlideAuto(); };
})();