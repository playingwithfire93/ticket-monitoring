// Minimal FullCalendar setup: initial view in 2025 and restrict visible range 2025-01-01 → 2026-12-31
document.addEventListener('DOMContentLoaded', function() {
  const el = document.getElementById('calendar');
  if (!el || typeof FullCalendar === 'undefined') return;

  const calendar = new FullCalendar.Calendar(el, {
    initialView: 'dayGridMonth',
    initialDate: '2025-01-01',
    headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek' },
    height: 700,
    validRange: { start: '2025-01-01', end: '2026-12-31' },
    events: async function(fetchInfo, successCallback, failureCallback) {
      try {
        const res = await fetch('/api/events');
        const data = await res.json();
        successCallback(data);
      } catch (e) {
        console.error('fetch /api/events failed', e);
        failureCallback(e);
      }
    },
    eventClick: function(info) {
      // quick edit: rename or delete
      const title = prompt('Editar título (o escribe DELETE para borrar):', info.event.title);
      if (title === null) return;
      if (title === 'DELETE') {
        fetch('/api/events?id=' + info.event.id, { method: 'DELETE' }).then(()=> calendar.refetchEvents());
        return;
      }
      fetch('/api/events', {
        method: 'PUT',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ id: info.event.id, title, start: info.event.startStr, end: info.event.endStr, allDay: info.event.allDay })
      }).then(()=> calendar.refetchEvents());
    },
    selectable: true,
    select: function(selInfo) {
      const title = prompt('Título del evento (cancel para no crear):');
      if (!title) { calendar.unselect(); return; }
      fetch('/api/events', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ title, start: selInfo.startStr, end: selInfo.endStr || selInfo.startStr, allDay: selInfo.allDay })
      }).then(()=> calendar.refetchEvents());
    }
  });

  calendar.render();
});