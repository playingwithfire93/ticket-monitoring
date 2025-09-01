/* dynamic UI: render cards, search, auto-refresh (fetch /api/monitored-urls)
   + keep slideshow markup in HTML and control it here */
(() => {
  const api = '/api/monitored-urls';

  // DOM elements
  const wrap = document.getElementById('grid-wrap');
  const search = document.getElementById('search');
  const noData = document.getElementById('no-data');
  const lastCheckedEl = document.getElementById('last-checked');
  const arToggle = document.getElementById('toggle-refresh');
  const arState = document.getElementById('ar-state');
  const modal = document.getElementById('modal');
  const modalTitle = document.getElementById('modal-title');
  const modalList = document.getElementById('modal-list');
  const modalClose = document.getElementById('modal-close');

  // slideshow elements (kept in HTML)
  const slideElems = Array.from(document.querySelectorAll('.slide'));
  const prevBtn = document.querySelector('.slide-nav.prev');
  const nextBtn = document.querySelector('.slide-nav.next');
  const dotsWrap = document.querySelector('.slide-dots');

  // basic sanity: abort if required container missing
  if (!wrap) {
    console.error('Missing #grid-wrap — aborting main UI script');
    return;
  }

  // state
  let musicals = Array.isArray(window.INITIAL_MUSICALS) ? window.INITIAL_MUSICALS : [];
  let autoRefresh = false;
  let intervalId = null;

  // ---- cards UI ----
  function buildCard(item) {
    const card = document.createElement('article');
    card.className = 'card';

    const title = document.createElement('div');
    title.className = 'title';
    const h4 = document.createElement('h4');
    h4.textContent = item.musical || item.name || 'Sin nombre';
    const badge = document.createElement('div');
    badge.className = 'badge';
    badge.textContent = (item.urls && item.urls.length) ? `${item.urls.length} URL(s)` : '0';
    title.appendChild(h4);
    title.appendChild(badge);

    const urlList = document.createElement('div');
    urlList.className = 'url-list';
    if (item.urls && item.urls.length) {
      item.urls.slice(0, 3).forEach(u => {
        const a = document.createElement('a');
        a.href = u;
        try { a.textContent = new URL(u).hostname + (u.length > 40 ? '…' : ''); }
        catch (e) { a.textContent = u; }
        a.target = '_blank';
        urlList.appendChild(a);
      });
      if (item.urls.length > 3) {
        const more = document.createElement('button');
        more.className = 'link-btn';
        more.textContent = `Ver ${item.urls.length - 3} más`;
        more.onclick = () => openModal(item);
        urlList.appendChild(more);
      }
    } else {
      const p = document.createElement('div');
      p.className = 'muted';
      p.textContent = 'No URLs';
      urlList.appendChild(p);
    }

    const footer = document.createElement('div');
    footer.className = 'footer';
    const checkBtn = document.createElement('button');
    checkBtn.className = 'btn soft';
    checkBtn.textContent = 'Check now';
    checkBtn.onclick = () => checkNow(item);
    footer.appendChild(checkBtn);

    card.appendChild(title);
    card.appendChild(urlList);
    card.appendChild(footer);
    return card;
  }

  function render(list) {
    wrap.innerHTML = '';
    if (!list || list.length === 0) {
      if (noData) noData.hidden = false;
      return;
    }
    if (noData) noData.hidden = true;
    list.forEach(item => wrap.appendChild(buildCard(item)));
  }

  function openModal(item) {
    if (!modal || !modalTitle || !modalList) return;
    modalTitle.textContent = item.musical || item.name || 'Sin nombre';
    modalList.innerHTML = '';
    (item.urls || []).forEach(u => {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = u;
      a.textContent = u;
      a.target = '_blank';
      li.appendChild(a);
      modalList.appendChild(li);
    });
    modal.setAttribute('aria-hidden', 'false');
  }
  function closeModal() { if (modal) modal.setAttribute('aria-hidden', 'true'); }

  function updateLastChecked() {
    if (lastCheckedEl) lastCheckedEl.textContent = new Date().toLocaleString();
  }

  async function fetchData() {
    try {
      const res = await fetch(api);
      if (!res.ok) throw new Error('Network response not ok');
      const data = await res.json();
      musicals = Array.isArray(data) ? data : musicals;
      render(filter(musicals));
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

  function checkNow(item) {
    if (item.urls && item.urls[0]) window.open(item.urls[0], '_blank');
  }

  // ---- slideshow logic ----
  let currentIndex = 0;
  let slideAutoId = null;
  function showSlide(index) {
    if (!slideElems.length) return;
    currentIndex = (index + slideElems.length) % slideElems.length;
    slideElems.forEach((s, i) => s.style.display = i === currentIndex ? 'block' : 'none');
    updateDots();
  }
  function nextSlide() { showSlide(currentIndex + 1); }
  function prevSlide() { showSlide(currentIndex - 1); }
  function startSlideAuto() { stopSlideAuto(); slideAutoId = setInterval(nextSlide, 5000); }
  function stopSlideAuto() { if (slideAutoId) { clearInterval(slideAutoId); slideAutoId = null; } }

  function createDots() {
    if (!dotsWrap) return;
    dotsWrap.innerHTML = '';
    slideElems.forEach((_, i) => {
      const d = document.createElement('button');
      d.className = 'dot';
      d.setAttribute('aria-label', `Go to slide ${i + 1}`);
      d.onclick = () => { showSlide(i); stopSlideAuto(); };
      dotsWrap.appendChild(d);
    });
    updateDots();
  }
  function updateDots() {
    if (!dotsWrap) return;
    Array.from(dotsWrap.children).forEach((d, i) => d.classList.toggle('active', i === currentIndex));
  }

  // ---- attach events (safe checks) ----
  if (search) search.addEventListener('input', () => render(filter(musicals)));

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

  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

  if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); stopSlideAuto(); });
  if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); stopSlideAuto(); });

  // ---- initialize UI ----
  render(musicals);
  updateLastChecked();

  // slideshow init
  showSlide(0);
  createDots();
  startSlideAuto();

  // background fetch to refresh data shortly after load
  window.addEventListener('load', () => { setTimeout(fetchData, 600); });

})();