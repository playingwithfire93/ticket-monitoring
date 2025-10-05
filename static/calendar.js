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
    headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek' },
    height: 700,
    validRange: { start: MIN_DATE, end: MAX_DATE },
    dayMaxEventRows: 3,
    dayMaxEvents: true,
    eventOrder: preferredEventComparator,
    eventContent: function(arg){
      const div = document.createElement('div');
      div.style.fontSize='12px';
      div.style.whiteSpace='nowrap'; div.style.overflow='hidden'; div.style.textOverflow='ellipsis';
      div.textContent = arg.event.title;
      return { domNodes: [div] };
    },

    // mark Mondays visually
    dayCellDidMount: function(info){
      if(info.date && info.date.getDay() === 1){
        info.el.classList.add('fc-monday-off');
        if(!info.el.querySelector('.monday-label')){
          const lbl = document.createElement('div'); lbl.className='monday-label'; lbl.textContent='Libre'; info.el.appendChild(lbl);
        }
      }
    },

    events: async function(fetchInfo, successCallback, failureCallback){
      try{
        if(!allEventsCache){
          // load events + exclusions
          const res = await fetch('/api/events');
          allEventsCache = await res.json();
          await loadExclusions();
          buildMusicalDropdown(allEventsCache);
        }
        const filtered = applyFilter(allEventsCache || []);

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

    eventClick: function(info){
      const title = prompt('Editar título (o escribe DELETE para borrar):', info.event.title);
      if(title === null) return;
      if(title === 'DELETE'){
        fetch('/api/events?id=' + info.event.id, { method: 'DELETE' }).then(()=>{ allEventsCache=null; calendar.refetchEvents(); });
        return;
      }
      fetch('/api/events', { method: 'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ id: info.event.id, title, start: info.event.startStr, end: info.event.endStr, allDay: info.event.allDay }) }).then(()=>{ allEventsCache=null; calendar.refetchEvents(); });
    },

    selectable: true,
    select: function(selInfo){
      const title = prompt('Título del evento (cancel para no crear):');
      if(!title){ calendar.unselect(); return; }
      fetch('/api/events', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ title, start: selInfo.startStr, end: selInfo.endStr || selInfo.startStr, allDay: selInfo.allDay }) }).then(()=>{ allEventsCache=null; calendar.refetchEvents(); });
    }
  });

  calendar.render();

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
});