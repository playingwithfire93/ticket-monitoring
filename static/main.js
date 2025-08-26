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

// Slideshow logic
let slideIndex = 1;
showSlides(slideIndex);

function plusSlides(n) {
  showSlides(slideIndex += n);
}

function showSlides(n) {
  let i;
  let slides = document.getElementsByClassName("slide");
  if (slides.length === 0) return;
  if (n > slides.length) {slideIndex = 1}
  if (n < 1) {slideIndex = slides.length}
  for (i = 0; i < slides.length; i++) {
    slides[i].style.display = "none";
  }
  slides[slideIndex-1].style.display = "block";
}

// Auto slideshow
setInterval(() => plusSlides(1), 5000);

// Suggestion form AJAX
const suggestionForm = document.getElementById('suggestion-form');
if (suggestionForm) {
  suggestionForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const formData = new FormData(suggestionForm);
    const payload = {
      siteName: formData.get('siteName'),
      siteUrl: formData.get('siteUrl'),
      reason: formData.get('reason')
    };
    const res = await fetch('/api/suggest-site', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    alert(result.message || result.error || 'Sugerencia enviada');
    suggestionForm.reset();
  });
}

update();
setInterval(update, 10000);
