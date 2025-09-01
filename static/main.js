// Replace render logic with table + collapsible rows; keep slideshow and fetch logic.
(() => {
  const api = '/api/monitored-urls';
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

  // slideshow pieces left unchanged (assume they exist)
  const slideElems = Array.from(document.querySelectorAll('.slide'));
  const prevBtn = document.querySelector('.prev');
  const nextBtn = document.querySelector('.next');
  const dotsWrap = document.querySelector('.slide-dots');

  if (!tableBody) { console.error('Missing #table-body — aborting'); return; }

  let musicals = Array.isArray(window.INITIAL_MUSICALS) ? window.INITIAL_MUSICALS : [];
  let autoRefresh = false;
  let intervalId = null;
  let currentIndex = 0;
  let slideAutoId = null;

  function buildSummaryRow(item, idx) {
    const tr = document.createElement('tr');
    tr.className = 'summary';
    tr.dataset.idx = idx;

    const expTd = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'expand-btn';
    btn.textContent = '+';
    btn.title = 'Expandir';
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
    openAll.className = 'btn soft';
    openAll.textContent = 'Abrir 1ª';
    openAll.onclick = (e) => { e.stopPropagation(); if (item.urls && item.urls[0]) window.open(item.urls[0], '_blank'); };
    actionsTd.appendChild(openAll);

    // click anywhere on summary toggles
    tr.appendChild(expTd);
    tr.appendChild(nameTd);
    tr.appendChild(urlsTd);
    tr.appendChild(actionsTd);

    // toggle handler
    tr.addEventListener('click', () => toggleDetails(idx, btn));

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
        a.href = u;
        a.textContent = u;
        a.target = '_blank';
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
    if (!list || list.length === 0) {
      if (noData) noData.hidden = false;
      return;
    }
    if (noData) noData.hidden = true;

    list.forEach((item, i) => {
      const summary = buildSummaryRow(item, i);
      const details = buildDetailsRow(item, i);
      tableBody.appendChild(summary);
      tableBody.appendChild(details);
    });
  }

  function toggleDetails(idx, btn) {
    const details = tableBody.querySelector(`tr.details-row[data-idx="${idx}"]`);
    const summary = tableBody.querySelector(`tr.summary[data-idx="${idx}"]`);
    if (!details || !summary) return;
    const isHidden = details.classList.contains('hidden');
    // collapse any open rows first (optional behavior: single open row)
    Array.from(tableBody.querySelectorAll('tr.details-row')).forEach(r => r.classList.add('hidden'));
    Array.from(tableBody.querySelectorAll('button.expand-btn')).forEach(b => b.textContent = '+');
    if (isHidden) {
      details.classList.remove('hidden');
      if (btn) btn.textContent = '–';
    } else {
      details.classList.add('hidden');
      if (btn) btn.textContent = '+';
    }
  }

  function updateLastChecked() {
    if (lastCheckedEl) lastCheckedEl.textContent = new Date().toLocaleString();
  }

  async function fetchData() {
    try {
      const res = await fetch(api);
      if (!res.ok) throw new Error('Network response not ok');
      const data = await res.json();
      musicals = Array.isArray(data) ? data : musicals;
      renderTable(filter(musicals));
      updateLastChecked();
    } catch (e) {
      console.error('fetchData', e);
    }
  }

  function filter(list) {
    const q = (search && search.value ? search.value : '').trim().toLowerCase();
    if (!q) return list;
    return list.filter(it => (it.musical || it.name || '').toLowerCase().includes(q));
  }

  // slideshow minimal control (keeps your existing HTML slides)
  function showSlide(index) {
    if (!slideElems.length) return;
    currentIndex = (index + slideElems.length) % slideElems.length;
    slideElems.forEach((s, i) => s.style.display = i === currentIndex ? 'block' : 'none');
  }
  function nextSlide() { showSlide(currentIndex + 1); }
  function prevSlide() { showSlide(currentIndex - 1); }
  function startSlideAuto() { stopSlideAuto(); slideAutoId = setInterval(nextSlide, 5000); }
  function stopSlideAuto() { if (slideAutoId) { clearInterval(slideAutoId); slideAutoId = null; } }

  // events
  if (search) search.addEventListener('input', () => renderTable(filter(musicals)));

  if (arToggle) {
    arToggle.addEventListener('click', () => {
      autoRefresh = !autoRefresh;
      if (arState) arState.textContent = autoRefresh ? 'ON' : 'OFF';
      if (autoRefresh) {
        intervalId = setInterval(fetchData, 8000);
        fetchData();
      } else {
        clearInterval(intervalId);
      }
    });
  }

  if (modalClose) modalClose.addEventListener('click', () => modal.setAttribute('aria-hidden','true'));
  if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) modal.setAttribute('aria-hidden','true'); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') modal.setAttribute('aria-hidden','true'); });

  if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopSlideAuto(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopSlideAuto(); });

  // init
  renderTable(musicals);
  updateLastChecked();
  showSlide(0);
  startSlideAuto();
  window.addEventListener('load', () => { setTimeout(fetchData, 600); });

  // expose simple slide controls for inline HTML arrows (kept from your template)
  window.plusSlides = (n) => { showSlide(currentIndex + n); stopSlideAuto(); };
})();