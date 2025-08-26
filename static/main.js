async function update() {
  const res = await fetch("/status");
  const data = await res.json();
  document.getElementById("lastChecked").textContent =
    "Last Checked: " + new Date(data.last_checked).toLocaleString("es-ES");

  const list = document.getElementById("changesList");
  list.innerHTML = "";

  if (data.changes.length === 0) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = "<span>✅</span><span>No new changes detected.</span>";
    list.appendChild(card);
  } else {
    data.changes.forEach(change => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `<span>🎫</span><span>${change}</span>`;
      list.appendChild(card);
    });
  }
}

update();
setInterval(update, 10000);
