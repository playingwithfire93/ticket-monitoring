/* ...existing code... */
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

  // slideshow DOM (single declaration)
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
        const chip = document.createElement('div');
        chip.className = 'url-chip';
        chip.title = u;

        const hostSpan = document.createElement('span');
        hostSpan.className = 'url-host';
        try {
          hostSpan.textContent = new URL(u).hostname + (u.length > 60 ? '…' : '');
        } catch (e) {
          hostSpan.textContent = u;
        }

        const actions = document.createElement('div');
        actions.className = 'url-actions';

        const openBtn = document.createElement('button');
        openBtn.className = 'open-btn';
        openBtn.type = 'button';
        openBtn.textContent = 'Abrir';
        openBtn.addEventListener('click', (ev) => { ev.stopPropagation(); window.open(u, '_blank'); });

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.type = 'button';
        copyBtn.textContent = 'Copiar';