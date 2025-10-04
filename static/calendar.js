// Minimal FullCalendar setup: initial view in 2025 and restrict visible range 2025-01-01 → 2026-12-31
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
  let musicalsList = []; // unique musical names
  let selectedSet = new Set();
  let colorsMap = {}; // musical -> color mapping

  // palette: visually distinct but pleasant
  const COLOR_PALETTE = [
    '#FF6B6B', // red
    '#FFB86B', // orange
    '#FFD93D', // yellow
    '#8BE9B4', // mint
    '#69B7FF', // blue
    '#8A79FF', // purple
    '#FF8AD6', // pink
    '#A0E1E0', // teal
    '#D6A2E8', // lilac
    '#F6C6EA'  // light pink
  ];

  function hashString(s) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h;
  }
  function pickColorFor(name) {
    if (!name) return '#999';
    if (colorsMap[name]) return colorsMap[name];
    const idx = Math.abs(hashString(name)) % COLOR_PALETTE.length;
    // choose color and slightly compute text color (dark vs light)
    const bg = COLOR_PALETTE[idx];
    colorsMap[name] = bg;
    return bg;
  }

  // preferred sequence (lowercase) — los que quieres siempre juntos y en ese orden
  const PREFERRED_ORDER = ['wicked', 'the book of mormon'];

  // helper que devuelve una clave numérica para ordenar: preferidos primero (en el orden
  // definido en PREFERRED_ORDER), luego el resto ordenado alfabéticamente.
  function orderKeyForEvent(ev) {
    const name = (ev.extendedProps && (ev.extendedProps.musical || ev.extendedProps.title)) || (ev.musical || ev.title) || '';
    const key = name.toString().toLowerCase().trim();
    const prefIndex = PREFERRED_ORDER.indexOf(key);
    if (prefIndex !== -1) {
      // los preferidos obtienen prioridad 0..N-1
      return { zone: 0, idx: prefIndex, tie: key };
    }
    // resto: zone 1 y orden alfabético (estable)
    return { zone: 1, idx: 0, tie: key };
  }

  // comparator para eventOrder que usa orderKeyForEvent y mantiene orden estable
  function preferredEventComparator(a, b) {
    const A = orderKeyForEvent(a);
    const B = orderKeyForEvent(b);
    if (A.zone !== B.zone) return A.zone - B.zone;
    if (A.zone === 0 && B.zone === 0) {
      // ambos preferidos: usar el índice preferido
      return A.idx - B.idx;
    }
    // mismos zone (1): ordenar por nombre (tie)
    return A.tie.localeCompare(B.tie);
  }

  const calendar = new FullCalendar.Calendar(el, {
    locale: 'es',         // Spanish locale
    firstDay: 1,          // week starts on Monday (Spain)
    initialView: 'dayGridMonth',
    initialDate: isoToday,
    headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek' },
    height: 700,
    validRange: { start: MIN_DATE, end: MAX_DATE },

    // highlight Monday cells and keep them empty
    dayCellDidMount: function(info) {
      // info.date is a Date; 1 === Monday
      if (info.date && info.date.getDay() === 1) {
        info.el.classList.add('fc-monday-off');
      }
    },

    // keep the month cells compact and limit stacked rows (shows "+N" when overflow)
    dayMaxEventRows: 3,
    dayMaxEvents: true,

    // custom ordering: put Wicked first, The Book of Mormon right after, then alphabetical
    eventOrder: preferredEventComparator,

    // render events compactly (smaller font) and use our colored props
    eventContent: function(arg) {
      const title = arg.event.title;
      const txt = document.createElement('div');
      txt.style.fontSize = '12px';
      txt.style.lineHeight = '1';
      txt.style.whiteSpace = 'nowrap';
      txt.style.overflow = 'hidden';
      txt.style.textOverflow = 'ellipsis';
      txt.textContent = title;
      return { domNodes: [txt] };
    },

    events: function(fetchInfo, successCallback, failureCallback) {
      (async () => {
        try {
          if (!allEventsCache) {
            const res = await fetch('/api/events');
            allEventsCache = await res.json();
            buildMusicalDropdown(allEventsCache);
          }
          const filtered = applyFilter(allEventsCache);

          // Expand multi-day events into per-day events, skipping Mondays (leave Mondays empty)
          const expanded = [];
          filtered.forEach(ev => {
            const s = new Date(ev.start);
            const e = ev.end ? new Date(ev.end) : new Date(ev.start);
            s.setHours(0,0,0,0);
            e.setHours(0,0,0,0);
            for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
              // JS: 0=Sun, 1=Mon ... skip Mondays explícitamente
              if (d.getDay() === 1) continue;
              const dayStr = d.toISOString().split('T')[0];
              const key = (ev.musical || ev.title || '').toString();
              const bg = pickColorFor(key);
              const textColor = isLightColor(bg) ? '#111827' : '#ffffff';
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
          });

          // safety: remove any events that accidentally fall on Monday
          const final = expanded.filter(e => {
            const dt = new Date(e.start);
            return dt.getDay() !== 1;
          });

          successCallback(final);
        } catch (e) {
          console.error('fetch /api/events failed', e);
          failureCallback(e);
        }
      })();
    },
    eventDidMount: function(info) {
      // ensure event text color is applied
      if (info.event.extendedProps && info.event.extendedProps.textColor) {
        info.el.style.color = info.event.extendedProps.textColor;
      }
    },
    eventClick: function(info) {
      const title = prompt('Editar título (o escribe DELETE para borrar):', info.event.title);
      if (title === null) return;
      if (title === 'DELETE') {
        fetch('/api/events?id=' + info.event.id, { method: 'DELETE' }).then(()=> { allEventsCache = null; calendar.refetchEvents(); });
        return;
      }
      fetch('/api/events', {
        method: 'PUT',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ id: info.event.id, title, start: info.event.startStr, end: info.event.endStr, allDay: info.event.allDay })
      }).then(()=> { allEventsCache = null; calendar.refetchEvents(); });
    },
    selectable: true,
    select: function(selInfo) {
      const title = prompt('Título del evento (cancel para no crear):');
      if (!title) { calendar.unselect(); return; }
      fetch('/api/events', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ title, start: selInfo.startStr, end: selInfo.endStr || selInfo.startStr, allDay: selInfo.allDay })
      }).then(()=> { allEventsCache = null; calendar.refetchEvents(); });
    }
  });

  calendar.render();

  // Build dropdown items with colored swatches and checkboxes
  function buildMusicalDropdown(events) {
    musicalsList = Array.from(new Set(events.map(e => (e.musical || e.title || '').trim()).filter(Boolean))).sort((a,b)=> a.localeCompare(b));
    dropdown.innerHTML = '';
    // reset colors map so deterministic mapping re-applies in same order
    colorsMap = {};
    musicalsList.forEach(name => {
      const color = pickColorFor(name);
      const div = document.createElement('div');
      div.className = 'mf-item';
      div.tabIndex = 0;
      div.dataset.name = name;
      // swatch + checkbox + label
      div.innerHTML = `
        <span style="width:14px;height:14px;border-radius:3px;display:inline-block;margin-right:8px;background:${color};border:1px solid rgba(0,0,0,0.06);vertical-align:middle"></span>
        <input type="checkbox" aria-label="${escapeHtml(name)}" value="${escapeHtml(name)}">
        <span class="mf-name" style="margin-left:8px">${escapeHtml(name)}</span>
      `;
      dropdown.appendChild(div);
      div.addEventListener('click', (e) => {
        const cb = div.querySelector('input');
        cb.checked = !cb.checked;
        toggleSelection(name, cb.checked);
      });
      div.addEventListener('keydown', (e) => {
        if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); div.click(); }
      });
    });
    updateFilterCount();
  }

  function toggleSelection(name, checked) {
    if (checked) selectedSet.add(name);
    else selectedSet.delete(name);
    updateInputPlaceholder();
    calendar.refetchEvents();
  }

  function getSelectedMusicalsArray() {
    return Array.from(selectedSet);
  }

  function applyFilter(events) {
    const selected = getSelectedMusicalsArray();
    if (!selected || selected.length === 0) {
      updateFilterCount(events.length);
      return events;
    }
    const filtered = events.filter(e => {
      const m = (e.musical || e.title || '').toString();
      return selected.includes(m);
    });
    updateFilterCount(filtered.length);
    return filtered;
  }

  function updateFilterCount(n) {
    if (typeof n === 'undefined') n = allEventsCache ? allEventsCache.length : 0;
    countEl.textContent = `${n} evento(s)`;
  }

  function updateInputPlaceholder() {
    const arr = getSelectedMusicalsArray();
    inputEl.value = arr.length ? `${arr.slice(0,3).join(', ')}${arr.length>3 ? '…':''}` : '';
    inputEl.placeholder = arr.length ? '' : 'Escribe para buscar / Escoge (click)';
  }

  // input search behaviour
  inputEl.addEventListener('input', function() {
    const q = inputEl.value.trim().toLowerCase();
    Array.from(dropdown.children).forEach(item => {
      const name = item.dataset.name.toLowerCase();
      item.style.display = name.includes(q) ? '' : 'none';
    });
    dropdown.style.display = 'block';
  });

  // toggle dropdown on focus/click
  inputEl.addEventListener('focus', () => { dropdown.style.display = 'block'; });
  document.addEventListener('click', (e) => {
    if (!multiWrap.contains(e.target)) dropdown.style.display = 'none';
  });

  // select all / clear
  btnAll.addEventListener('click', function(){
    Array.from(dropdown.querySelectorAll('input')).forEach(cb => { cb.checked = true; selectedSet.add(cb.value); });
    updateInputPlaceholder(); calendar.refetchEvents();
  });
  btnClear.addEventListener('click', function(){
    Array.from(dropdown.querySelectorAll('input')).forEach(cb => { cb.checked = false; });
    selectedSet.clear(); updateInputPlaceholder(); calendar.refetchEvents();
  });

  // helper: approximate luminance to choose readable text color
  function isLightColor(hex) {
    // hex -> r,g,b
    hex = hex.replace('#','');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    const r = parseInt(hex.substr(0,2),16);
    const g = parseInt(hex.substr(2,2),16);
    const b = parseInt(hex.substr(4,2),16);
    // perceived luminance
    const lum = 0.2126*r + 0.7152*g + 0.0722*b;
    return lum > 180;
  }

  // helper
  function escapeHtml(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  // expose refresh
  window.calendarRefresh = function(){ allEventsCache = null; selectedSet.clear(); updateInputPlaceholder(); calendar.refetchEvents(); };
});