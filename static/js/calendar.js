// Robust FullCalendar client: normaliza nombres, aplica exclusiones y evita errores si la UI de filtro
// no está presente.
document.addEventListener('DOMContentLoaded', function() {
  const el = document.getElementById('calendar');
  const multiWrap = document.getElementById('musical-multi');
  const inputEl = document.getElementById('musical-filter-input');
  const dropdown = document.getElementById('musical-dropdown');
  const btnAll = document.getElementById('filter-all');
  const btnClear = document.getElementById('filter-clear');
  const countEl = document.getElementById('filter-count');

  if (!el) return;

  const MIN_DATE = '2025-01-01';
  const MAX_DATE = '2026-12-31';
  let today = new Date();
  let isoToday = today.toISOString().split('T')[0];
  if (isoToday < MIN_DATE) isoToday = MIN_DATE;
  if (isoToday > MAX_DATE) isoToday = MAX_DATE;

  let allEventsCache = null;
  let exclusionsMap = {}; // normalizedKey -> Set(dates)
  let musicalsList = []; // unique musical names
  let selectedSet = new Set();
  let colorsMap = {}; // musical -> color mapping
  let showPast = false; // whether to include past events
  let showFromToday = false; // whether to jump/start calendar at today

  const COLOR_PALETTE = ['#FF6B6B','#FFB86B','#FFD93D','#8BE9B4','#69B7FF','#8A79FF','#FF8AD6','#A0E1E0','#D6A2E8','#F6C6EA'];

  function hashString(s){ let h=2166136261>>>0; for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)>>>0;} return h; }
  function pickColorFor(name){ if(!name) return '#999'; if(colorsMap[name]) return colorsMap[name]; const idx = Math.abs(hashString(name)) % COLOR_PALETTE.length; colorsMap[name]=COLOR_PALETTE[idx]; return colorsMap[name]; }

  // normalize keys: lowercase, remove accents, punctuation, extra words like "— temporada"
  function normalizeKey(s){
    if(!s) return '';
    let t = String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
    // remove common separators and trailing descriptors
    t = t.replace(/—.*$/,'').replace(/\(.*\)$/,'').replace(/[:–-].*$/,'').trim();
    // keep letters/numbers and spaces only
    t = t.replace(/[^\w\s]/g,' ').replace(/\s+/g,' ').trim();
    return t;
  }

  // parse YYYY-MM-DD as local date
  function parseLocalDate(isoDate){
    if(!isoDate) return null;
    const parts = isoDate.split('-').map(x=>parseInt(x,10));
    if(parts.length<3 || isNaN(parts[0])) return null;
    return new Date(parts[0], (parts[1]||1)-1, parts[2]||1);
  }
  function formatLocalDate(d){ const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0'); const day=String(d.getDate()).padStart(2,'0'); return `${y}-${m}-${day}`; }

  // safe build dropdown only if elements exist
  function buildMusicalDropdown(events){
    if(!dropdown) return;
    musicalsList = Array.from(new Set(events.map(e => (e.musical || e.title || '').trim()).filter(Boolean))).sort((a,b)=> a.localeCompare(b));
    dropdown.innerHTML='';
    colorsMap = {}; // reset to keep mapping deterministic
    musicalsList.forEach(name=>{
      const color = pickColorFor(name);
      const div = document.createElement('div');
      div.className='mf-item';
      div.tabIndex=0;
      div.dataset.name = name;
      div.innerHTML = `<span style="width:14px;height:14px;border-radius:3px;display:inline-block;margin-right:8px;background:${color};border:1px solid rgba(0,0,0,0.06);vertical-align:middle"></span>
                       <input type="checkbox" aria-label="${name}" value="${name}"> <span class="mf-name">${name}</span>`;
      dropdown.appendChild(div);
      div.addEventListener('click', (e)=>{ const cb = div.querySelector('input'); cb.checked = !cb.checked; toggleSelection(name, cb.checked); });
      div.addEventListener('keydown', (e)=>{ if(e.key===' '||e.key==='Enter'){ e.preventDefault(); div.click(); } });
    });
    updateFilterCount();
    // also render compact legend for quick reference
    try{ renderLegend(); }catch(e){}
  }

  function renderLegend(){
    const parent = el.parentNode || document.body;
    let legend = parent.querySelector('.calendar-legend');
    if(!legend){ legend = document.createElement('div'); legend.className='calendar-legend'; parent.insertBefore(legend, el); }
    legend.innerHTML = '';
    musicalsList.slice(0,20).forEach(name => {
      const item = document.createElement('div'); item.className='legend-item';
      const dot = document.createElement('span'); dot.className='legend-dot'; dot.style.background = pickColorFor(name);
      const txt = document.createElement('span'); txt.className='legend-name'; txt.textContent = name;
      item.appendChild(dot); item.appendChild(txt); legend.appendChild(item);
    });
  }

  function toggleSelection(name, checked){ if(checked) selectedSet.add(name); else selectedSet.delete(name); updateInputPlaceholder(); calendar.refetchEvents(); }
  function getSelectedMusicalsArray(){ return Array.from(selectedSet); }
  function updateInputPlaceholder(){ const arr=getSelectedMusicalsArray(); if(!inputEl) return; inputEl.value = arr.length ? `${arr.slice(0,3).join(', ')}${arr.length>3?'…':''}` : ''; inputEl.placeholder = arr.length ? '' : 'Escribe para buscar / Escoge (click)'; }
  function updateFilterCount(n){ if(!countEl) return; if(typeof n === 'undefined') n = allEventsCache ? allEventsCache.length : 0; countEl.textContent = `${n} evento(s)`; }

  function applyFilter(events){
    const selected = getSelectedMusicalsArray();
    if(!selected || selected.length===0){ updateFilterCount(events.length); return events; }
    const filtered = events.filter(e => selected.includes(e.musical || e.title || ''));
    updateFilterCount(filtered.length);
    return filtered;
  }

  // load exclusions.json (if exists) and normalize keys
  async function loadExclusions(){
    try{
      const res = await fetch('/static/data/exclusions.json?ts=' + Date.now());
      if(!res.ok) { exclusionsMap = {}; return; }
      const raw = await res.json();
      exclusionsMap = {};
      for(const k of Object.keys(raw||{})){
        const nk = normalizeKey(k);
        exclusionsMap[nk] = new Set((raw[k]||[]).map(String));
      }
      console.info('exclusions loaded', Object.keys(exclusionsMap));
    }catch(err){ console.warn('no exclusions file', err); exclusionsMap = {}; }
  }

  // preferred ordering: wicked then book of mormon; rest alphabetical
  const PREFERRED_ORDER = ['wicked','the book of mormon'];
  function orderKeyForEvent(ev){
    const name = normalizeKey((ev.extendedProps && (ev.extendedProps.musical || ev.extendedProps.title)) || (ev.musical || ev.title) || '');
    const pi = PREFERRED_ORDER.indexOf(name);
    if(pi !== -1) return { zone:0, idx:pi, tie:name };
    return { zone:1, idx:0, tie:name };
  }
  function preferredEventComparator(a,b){ const A=orderKeyForEvent(a), B=orderKeyForEvent(b); if(A.zone!==B.zone) return A.zone-B.zone; if(A.zone===0) return A.idx-B.idx; return A.tie.localeCompare(B.tie); }

  // create calendar
  const calendar = new FullCalendar.Calendar(el, {
    locale: 'es',
    firstDay: 1,
    initialView: 'dayGridMonth',
    initialDate: isoToday,
    headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,listWeek' },
    height: 700,
    validRange: { start: MIN_DATE, end: MAX_DATE },
    dayMaxEventRows: 3,
    dayMaxEvents: true,
    eventOrder: preferredEventComparator,
    eventContent: function(arg){
      const wrapper = document.createElement('div');
      wrapper.style.display = 'flex';
      wrapper.style.alignItems = 'center';
      wrapper.style.gap = '6px';

      const dot = document.createElement('span');
      dot.className = 'fc-event-dot';
      dot.style.width = '10px';
      dot.style.height = '10px';
      dot.style.borderRadius = '50%';
      dot.style.background = arg.event.backgroundColor || (arg.event.extendedProps && arg.event.extendedProps.color) || '#888';

      const div = document.createElement('div');
      div.style.fontSize='12px';
      div.style.whiteSpace='nowrap'; div.style.overflow='hidden'; div.style.textOverflow='ellipsis';
      div.textContent = arg.event.title;

      wrapper.appendChild(dot);
      wrapper.appendChild(div);
      return { domNodes: [wrapper] };
    },

    // Update day-panel when visible range changes
    datesSet: function(info){
      try{ renderDayPanel(info.start); }catch(e){}
    },
    dateClick: function(info){
      try{ renderDayPanel(info.date); }catch(e){}
    },

    // mark Mondays visually
    dayCellDidMount: function(info){
      // mark Mondays visually
      if(info.date && info.date.getDay() === 1){
        info.el.classList.add('fc-monday-off');
        if(!info.el.querySelector('.monday-label')){
          const lbl = document.createElement('div'); lbl.className='monday-label'; lbl.textContent='Libre'; info.el.appendChild(lbl);
        }
      }
      // highlight today and mark past days
      try{
        const todayStrLocal = formatLocalDate(new Date());
        const thisStr = formatLocalDate(info.date);
        if(thisStr === todayStrLocal){
          info.el.classList.add('fc-today-highlight');
          if(!info.el.querySelector('.today-label')){
            const tl = document.createElement('div'); tl.className='today-label'; tl.textContent='Hoy'; info.el.appendChild(tl);
          }
        }
        // de-emphasize past days (local comparison)
        try{
          const todayObj = parseLocalDate(todayStrLocal);
          const thisObj = parseLocalDate(thisStr);
          if(thisObj && todayObj && thisObj < todayObj){
            info.el.classList.add('fc-past-day');
          }
        }catch(e){}
      }catch(e){}
    },

    events: async function(fetchInfo, successCallback, failureCallback){
      try{
        if(!allEventsCache){
          // load events + exclusions (use server calendar endpoint)
          const res = await fetch('/api/calendar-events');
          allEventsCache = await res.json();
          await loadExclusions();
          buildMusicalDropdown(allEventsCache);
        }
        let filtered = applyFilter(allEventsCache || []);

        // by default, hide events that have already ended (local date before today)
        try{
          if(!showPast){
            const todayDateObj = parseLocalDate(formatLocalDate(new Date()));
            filtered = filtered.filter(ev => {
              const evEnd = parseLocalDate(ev.end || ev.start);
              if(!evEnd) return true;
              return evEnd >= todayDateObj;
            });
          }
        }catch(e){/* ignore filtering errors */}

        // expand multi-day events into per-day events, parse local dates, skip Mondays and exclusions
        const expanded = [];
        for(const ev of filtered){
          const s = parseLocalDate(ev.start);
          const e = parseLocalDate(ev.end || ev.start);
          if(!s || !e) continue;
          const rawName = (ev.musical || ev.title || '');
          const eventKey = normalizeKey(rawName);

          // match exclusions: exact normalized key OR partial contains
          let excludedSet = new Set();
          if(exclusionsMap[eventKey]) excludedSet = exclusionsMap[eventKey];
          else{
            for(const exKey of Object.keys(exclusionsMap)){
              if(!exKey) continue;
              if(eventKey.includes(exKey)){
                excludedSet = exclusionsMap[exKey];
                console.debug('exclusion matched', exKey, '->', eventKey);
                break;
              }
            }
          }

          for(let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)){
            // skip Mondays only
            if(d.getDay() === 1) continue;
            const dayStr = formatLocalDate(d);
            if(excludedSet && excludedSet.has(dayStr)){
              console.debug('skipping excluded date', dayStr, 'for', eventKey);
              continue;
            }
            const key = rawName;
            const bg = pickColorFor(key);
            const textColor = (function(hex){ hex = hex.replace('#',''); if(hex.length===3) hex = hex.split('').map(c=>c+c).join(''); const r=parseInt(hex.substr(0,2),16), g=parseInt(hex.substr(2,2),16), b=parseInt(hex.substr(4,2),16); return (0.2126*r+0.7152*g+0.0722*b) > 180 ? '#111827' : '#ffffff'; })(bg);
            expanded.push(Object.assign({}, ev, {
              id: `${ev.id || Math.random().toString(36).slice(2)}:${dayStr}`,
              start: dayStr,
              end: dayStr,
              allDay: true,
              backgroundColor: bg,
              borderColor: bg,
              textColor
            }));
          }
        }

        // final safety: ensure no Mondays slipped through
        const final = expanded.filter(e => { const dt = parseLocalDate(e.start); return dt && dt.getDay() !== 1; });

        console.debug('events fetched', (allEventsCache||[]).length, 'expanded', final.length);
        successCallback(final);
      }catch(err){
        console.error('fetch /api/events failed', err);
        failureCallback(err);
      }
    },

    eventDidMount: function(info){
      if(info.event.extendedProps && info.event.extendedProps.textColor){
        info.el.style.color = info.event.extendedProps.textColor;
      }
    },

    // Editing is disabled in this build (server exposes read-only calendar endpoint)
    selectable: false
  });

  calendar.render();

  // Day events panel: shows all events for a selected day (defaults to today)
  function renderDayPanel(dateLike){
    try{
      let d = (dateLike instanceof Date) ? dateLike : new Date(dateLike);
      const ds = formatLocalDate(d);
      const parent = el.parentNode || document.body;
      let sidebar = parent.querySelector('.calendar-sidebar');
      if(!sidebar){ sidebar = document.createElement('aside'); sidebar.className='calendar-sidebar'; parent.appendChild(sidebar); }
      let panel = sidebar.querySelector('.calendar-day-panel');
      if(!panel){ panel = document.createElement('div'); panel.className = 'calendar-day-panel'; sidebar.appendChild(panel); }
      panel.innerHTML = '';
      const hdr = document.createElement('div'); hdr.className = 'cdp-header'; hdr.textContent = `Eventos para ${ds}`; panel.appendChild(hdr);
      const list = document.createElement('div'); list.className = 'cdp-list'; panel.appendChild(list);

      const evs = calendar.getEvents().filter(ev => {
        try{
          if(!ev.start) return false;
          const evd = new Date(ev.start);
          const es = formatLocalDate(evd);
          return es === ds;
        }catch(e){return false}
      });

      if(evs.length === 0){ const none = document.createElement('div'); none.className='cdp-none'; none.textContent = 'No hay shows este día.'; list.appendChild(none); return; }

      evs.sort((a,b)=> (a.title || '').localeCompare(b.title || ''));
      evs.forEach(ev => {
        const item = document.createElement('div'); item.className='cdp-item';
        const img = document.createElement('img'); img.className='cdp-thumb'; img.alt = ev.title || 'img';
        const url = (ev.extendedProps && ev.extendedProps.url) || (ev.url || '#');
        const imgSrc = (ev.extendedProps && ev.extendedProps.image) || (`/static/fotos/${(ev.extendedProps && ev.extendedProps.musical)||''}`) || '';
        if(imgSrc) img.src = imgSrc; else img.src = `https://via.placeholder.com/160x90?text=${encodeURIComponent(ev.title||'')}`;
        const meta = document.createElement('div'); meta.className='cdp-meta';
        const title = document.createElement('a'); title.className='cdp-title'; title.textContent = ev.title || 'Evento'; title.href = url || '#'; title.target='_blank';
        const desc = document.createElement('div'); desc.className='cdp-desc'; desc.textContent = (ev.extendedProps && ev.extendedProps.description) || '';
        meta.appendChild(title); meta.appendChild(desc);
        item.appendChild(img); item.appendChild(meta);
        list.appendChild(item);
      });
    }catch(e){ console.warn('renderDayPanel error', e); }
  }

  // initial render for today
  try{ renderDayPanel(new Date()); }catch(e){}

  // add simple controls: show past toggle
  try{
    const parent = el.parentNode || document.body;
    let controls = parent.querySelector('.calendar-controls');
    if(!controls){
      controls = document.createElement('div'); controls.className='calendar-controls';
      parent.insertBefore(controls, el);
    }
    controls.innerHTML = '';
    const cb = document.createElement('input'); cb.type='checkbox'; cb.id='cb-show-past'; cb.checked = showPast;
    const lbl = document.createElement('label'); lbl.htmlFor='cb-show-past'; lbl.textContent = ' Mostrar eventos pasados';
    controls.appendChild(cb); controls.appendChild(lbl);
    cb.addEventListener('change', function(){ showPast = !!cb.checked; allEventsCache = null; calendar.refetchEvents(); });
    // Add 'Start from today' control
    const cb2 = document.createElement('input'); cb2.type = 'checkbox'; cb2.id = 'cb-start-today'; cb2.checked = showFromToday; cb2.style.marginLeft = '12px';
    const lbl2 = document.createElement('label'); lbl2.htmlFor = 'cb-start-today'; lbl2.textContent = ' Empezar en hoy';
    controls.appendChild(cb2); controls.appendChild(lbl2);
    cb2.addEventListener('change', function(){ showFromToday = !!cb2.checked; if(showFromToday){ try{ calendar.gotoDate(new Date()); }catch(e){} } });
    // Add 'Hide past dates' control (collapses past day cells)
    const cb3 = document.createElement('input'); cb3.type = 'checkbox'; cb3.id = 'cb-hide-past'; cb3.checked = false; cb3.style.marginLeft = '12px';
    const lbl3 = document.createElement('label'); lbl3.htmlFor = 'cb-hide-past'; lbl3.textContent = ' Ocultar fechas pasadas';
    controls.appendChild(cb3); controls.appendChild(lbl3);
    cb3.addEventListener('change', function(){
      try{
        if(cb3.checked){ el.classList.add('hide-past-days'); } else { el.classList.remove('hide-past-days'); }
        // ensure visual refresh
        try{ calendar.render(); }catch(e){}
      }catch(e){console.warn('toggle hide past failed', e);}    
    });
  }catch(e){console.warn('no calendar controls', e);}

  // safe UI handlers if present
  if(inputEl){
    inputEl.addEventListener('input', function(){
      const q = inputEl.value.trim().toLowerCase();
      if(!dropdown) return;
      Array.from(dropdown.children).forEach(item => {
        const name = (item.dataset.name||'').toLowerCase();
        item.style.display = name.includes(q) ? '' : 'none';
      });
      dropdown.style.display = 'block';
    });
    inputEl.addEventListener('focus', () => { if(dropdown) dropdown.style.display = 'block'; });
    document.addEventListener('click', (e) => { if(multiWrap && !multiWrap.contains(e.target) && dropdown) dropdown.style.display = 'none'; });
  }

  if(btnAll && dropdown){
    btnAll.addEventListener('click', function(){ Array.from(dropdown.querySelectorAll('input')).forEach(cb=>{ cb.checked=true; selectedSet.add(cb.value); }); updateInputPlaceholder(); calendar.refetchEvents(); });
  }
  if(btnClear && dropdown){
    btnClear.addEventListener('click', function(){ Array.from(dropdown.querySelectorAll('input')).forEach(cb=>cb.checked=false); selectedSet.clear(); updateInputPlaceholder(); calendar.refetchEvents(); });
  }

  window.calendarRefresh = function(){ allEventsCache=null; selectedSet.clear(); updateInputPlaceholder(); calendar.refetchEvents(); };

  // ==================== TOOLTIP FUNCTIONALITY ====================
  (function() {
    const tooltipEl = document.getElementById('musical-tooltip');
    if (!tooltipEl) return;

    let hideTimeout;
    let isMouseOverTooltip = false;
    let isMouseOverEvent = false;

    // Mantener tooltip visible al hacer hover sobre él
    tooltipEl.addEventListener('mouseenter', () => {
      clearTimeout(hideTimeout);
      isMouseOverTooltip = true;
    });

    tooltipEl.addEventListener('mouseleave', () => {
      isMouseOverTooltip = false;
      hideTimeout = setTimeout(() => {
        if (!isMouseOverEvent) {
          tooltipEl.classList.remove('active');
        }
      }, 200);
    });

    // Añadir handlers al calendario existente
    const originalEventDidMount = calendar.eventDidMount;
    calendar.eventDidMount = function(info) {
      if (originalEventDidMount) originalEventDidMount(info);

      // Añadir hover handlers
      info.el.addEventListener('mouseenter', function(e) {
        clearTimeout(hideTimeout);
        isMouseOverEvent = true;
        showTooltip(info.event, e);
      });

      info.el.addEventListener('mouseleave', function() {
        isMouseOverEvent = false;
        hideTimeout = setTimeout(() => {
          if (!isMouseOverTooltip && !isMouseOverEvent) {
            tooltipEl.classList.remove('active');
          }
        }, 300);
      });
    };

    function showTooltip(event, mouseEvent) {
      const props = event.extendedProps || {};
      let image = props.image || '';
      if (!image || image.includes('default.jpg')) {
        image = `https://via.placeholder.com/380x200/ff69b4/ffffff?text=${encodeURIComponent(event.title.substring(0, 20))}`;
      }

      const description = props.description || 'Disfruta de este increíble musical en Madrid';
      const location = props.location || 'Madrid';
      const url = props.url || '#';
      const isAvailable = props.isAvailable !== false;
      const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location + ', Madrid')}`;

      // Clear previous content and build DOM for accessibility and event handling
      tooltipEl.innerHTML = '';
      tooltipEl.setAttribute('role', 'dialog');
      tooltipEl.setAttribute('aria-label', `Detalles ${event.title}`);
      tooltipEl.tabIndex = -1;

      const img = document.createElement('img');
      img.className = 'tooltip-image';
      img.alt = event.title || 'Imagen';
      img.src = image;
      img.loading = 'lazy';
      img.addEventListener('error', function(){ img.src = `https://via.placeholder.com/380x200/ff69b4/ffffff?text=${encodeURIComponent(event.title.substring(0, 20))}`; });

      const content = document.createElement('div'); content.className = 'tooltip-content';
      const h3 = document.createElement('h3'); h3.className = 'tooltip-title'; h3.textContent = event.title;

      const meta = document.createElement('div'); meta.className = 'tooltip-meta';
      const metaLoc = document.createElement('div'); metaLoc.className = 'tooltip-meta-item';
      metaLoc.innerHTML = `<span>📍</span>`;
      const aLoc = document.createElement('a'); aLoc.href = mapsUrl; aLoc.target = '_blank'; aLoc.className = 'tooltip-location-link'; aLoc.textContent = location; aLoc.addEventListener('click', (ev)=>ev.stopPropagation());
      metaLoc.appendChild(aLoc);

      const metaAvail = document.createElement('div'); metaAvail.className = 'tooltip-meta-item';
      metaAvail.innerHTML = `<span>🎫</span>`;
      const availSpan = document.createElement('span'); availSpan.className = `tooltip-badge ${isAvailable ? 'available' : 'sold-out'}`;
      availSpan.textContent = isAvailable ? '✅ Entradas disponibles' : '❌ Agotado';
      metaAvail.appendChild(availSpan);

      meta.appendChild(metaLoc); meta.appendChild(metaAvail);

      const p = document.createElement('p'); p.className = 'tooltip-description'; p.textContent = description;

      const btns = document.createElement('div'); btns.className = 'tooltip-buttons';
      if(url !== '#'){
        const buy = document.createElement('a'); buy.className = 'tooltip-button tooltip-button-primary'; buy.href = url; buy.target = '_blank'; buy.textContent = '🎟️ Comprar Entradas'; buy.addEventListener('click', (ev)=>ev.stopPropagation());
        btns.appendChild(buy);
      }
      const mapsBtn = document.createElement('a'); mapsBtn.className = 'tooltip-button tooltip-button-secondary'; mapsBtn.href = mapsUrl; mapsBtn.target = '_blank'; mapsBtn.textContent = '🗺️ Ver en Google Maps'; mapsBtn.addEventListener('click', (ev)=>ev.stopPropagation());
      btns.appendChild(mapsBtn);

      const closeBtn = document.createElement('button'); closeBtn.className = 'tooltip-close'; closeBtn.setAttribute('aria-label','Cerrar'); closeBtn.innerHTML = '✕';
      closeBtn.addEventListener('click', function(ev){ ev.stopPropagation(); tooltipEl.classList.remove('active'); setTimeout(()=>{ tooltipEl.innerHTML=''; },200); });

      content.appendChild(h3); content.appendChild(meta); content.appendChild(p); content.appendChild(btns);
      tooltipEl.appendChild(img); tooltipEl.appendChild(content); tooltipEl.appendChild(closeBtn);

      // Positioning
      const tooltipWidth = Math.min(420, Math.max(280, tooltipEl.offsetWidth || 340));
      const tooltipHeight = tooltipEl.offsetHeight || 220;
      let left = mouseEvent.pageX + 20;
      let top = mouseEvent.pageY - 100;
      if (left + tooltipWidth > window.innerWidth + window.scrollX) left = mouseEvent.pageX - tooltipWidth - 20;
      if (left < window.scrollX + 10) left = window.scrollX + 10;
      if (top + tooltipHeight > window.innerHeight + window.scrollY) top = window.innerHeight + window.scrollY - tooltipHeight - 10;
      if (top < window.scrollY + 10) top = window.scrollY + 10;
      tooltipEl.style.left = left + 'px'; tooltipEl.style.top = top + 'px';

      // show with small delay to avoid flicker on fast mouse moves
      setTimeout(()=>{ tooltipEl.classList.add('active'); tooltipEl.focus({preventScroll:true}); }, 80);

      // keyboard: Esc hides
      const onKey = function(e){ if(e.key === 'Escape'){ tooltipEl.classList.remove('active'); document.removeEventListener('keydown', onKey); } };
      document.addEventListener('keydown', onKey);
    }
  })();
});