from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC
import requests
import hashlib
import json
from bs4 import BeautifulSoup
from bs4.element import Comment

app = Flask(__name__)
previous_states = {}

@app.route("/")
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>🎟️ Ticket Monitor</title>
      <style>
        body {
          font-family: 'Segoe UI', sans-serif;
          background-color: #DFDBE5;
          background-image: url("data:image/svg+xml,%3Csvg width='24' height='24' viewBox='0 0 24 24' xmlns='http://www.w3.org/2000/svg'%3E%3Ctitle%3Ehoundstooth%3C/title%3E%3Cg fill='%23f9629f' fill-opacity='0.4' fill-rule='evenodd'%3E%3Cpath d='M0 18h6l6-6v6h6l-6 6H0M24 18v6h-6M24 0l-6 6h-6l6-6M12 0v6L0 18v-6l6-6H0V0'/%3E%3C/g%3E%3C/svg%3E");
          margin: 0;
          padding: 2rem;
          color: #4b006e;
        }
        h1 {
          font-size: 2.2rem;
          text-align: center;
          color: #d63384;
          text-shadow: 0 1px 2px rgba(0,0,0,0.1);
          margin-bottom: 1.5rem;
        }
        .dashboard {
          max-width: 840px;
          margin: 0 auto;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }
        .last-checked {
          font-size: 0.9rem;
          color: #b84e8c;
        }
        .badge {
          background: linear-gradient(45deg, #f472b6, #e879f9);
          color: white;
          padding: 0.4rem 0.8rem;
          border-radius: 1rem;
          font-size: 0.75rem;
          font-weight: bold;
          box-shadow: 0 2px 4px rgba(0,0,0,0.15);
          animation: pulse 2s infinite ease-in-out;
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.08); }
        }
        .grid {
          display: grid;
          gap: 1rem;
        }
        .card {
          background: #fff0f7;
          border: 2px dashed #f472b6;
          padding: 1rem;
          border-radius: 1rem;
          box-shadow: 0 4px 12px rgba(0,0,0,0.08);
          transition: transform 0.2s ease, box-shadow 0.3s ease;
        }
        .card:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
        }
        .card h3 {
          margin-top: 0;
          margin-bottom: 0.5rem;
          font-size: 1.2rem;
          color: #e11d48;
        }
        .card p {
          margin: 0.2rem 0;
          font-size: 0.9rem;
          color: #9d174d;
        }
        .card:nth-child(even) {
  background-color: #fff7fb;
}
.card.updated {
  animation: flashBorder 1.2s ease;
}

@keyframes flashBorder {
  0% { border-color: #f43f5e; box-shadow: 0 0 0 0 rgba(244,63,94,0.7); }
  50% { border-color: #fb7185; box-shadow: 0 0 8px 4px rgba(244,63,94,0.3); }
  100% { border-color: #ec4899; box-shadow: none; }
}

        #toast {
          position: fixed;
          bottom: 1rem;
          right: 1rem;
          background: #ec4899;
          color: white;
          padding: 1rem 1.5rem;
          border-radius: 1rem;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
          display: none;
          z-index: 9999;
          animation: fadeInOut 0.6s ease-in-out forwards;
        }
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(20px); }
          10% { opacity: 1; transform: translateY(0); }
          90% { opacity: 1; }
          100% { opacity: 0; transform: translateY(20px); }
          @keyframes glow {
            0% { box-shadow: 0 0 10px #ec4899; }
            100% { box-shadow: none; }
          }
          .card.recent-change {
            animation: glow 1s ease-in-out 3;
          }

        }
        #loadingIndicator {
          text-align: center;
          font-style: italic;
          color: #c026d3;
          margin-top: 1rem;
        }
      </style>
    </head>
    <body>
      <h1>🌸✨ Ticket Monitoring Dashboard ✨🌸</h1>
      <div class="dashboard">
        <div class="header">
          <p id="lastChecked" class="last-checked">Last Checked: ...</p>
          <span class="badge">💖 Auto-refreshing</span>
        </div>
        <div id="changesList" class="grid">
          <div class="card"><span>⏳</span> <span>Loading updates...</span></div>
        </div>
      </div>
      <div id="toast">Cambio detectado</div>
      <audio id="notifSound" preload="auto">
        <source src="{{ url_for('static', filename='door-bell-sound-99933.mp3') }}" type="audio/mpeg">
      </audio>
      <p id="loadingIndicator">🔎 Checking for updates...</p>

      <script>
        function showToast(message) {
          const toast = document.getElementById("toast");
          toast.textContent = message;
          toast.style.display = "block";
          toast.style.animation = "fadeInOut 4s ease-in-out forwards";
          setTimeout(() => {
            toast.style.display = "none";
          }, 4000);
        }

        async function update() {
          document.getElementById("loadingIndicator").style.display = "block";
          const res = await fetch("/changes");
          const data = await res.json();
          document.getElementById("loadingIndicator").style.display = "none";

          document.getElementById("lastChecked").textContent =
            "Última revisión: " + new Date().toLocaleString("es-ES");

          const list = document.getElementById("changesList");
          list.innerHTML = "";

          if (data.length === 0) {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = "<span>✅</span><span> Todo está fabuloso. Sin cambios detectados.</span>";
            list.appendChild(card);
            document.title = `(${data.length}) 🎟️ Cambios detectados`;

          } else {
            const notifSound = document.getElementById("notifSound");
            data.forEach(change => {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <h3>${change.label}</h3>
    <p><a href="${change.url}" target="_blank">${change.url}</a></p>
    <p>${change.status}</p>
    <p>🕒 ${new Date(change.timestamp).toLocaleString("es-ES")}</p>
  `;
  if (change.status.includes("Actualizado")) {
    card.style.borderColor = "#ec4899";
    card.style.backgroundColor = "#ffe4f1";
    card.classList.add("recent-change");
    showToast(`🎀 Cambio en:\n${change.url}`);
    notifSound.play().catch(() => {});
    if ("vibrate" in navigator) navigator.vibrate([120, 60, 120]);
  }
  list.appendChild(card);


  // ✅ Now safe to access `change.url` here
  showToast(`🎀 Cambio en:\n${change.url}`);
  notifSound.play().catch(() => {});
  if ("vibrate" in navigator) navigator.vibrate([120, 60, 120]);
});


          }
        }

        update();
        setInterval(update, 10000);
      </script>
    </body>
    </html>
    """)



URLS = [
    {"label": "test", "url": "https://httpbin.org/get/"},
    {"label": "Wicked", "url": "https://wickedelmusical.com/"},
    {"label": "Wicked elenco", "url": "https://wickedelmusical.com/elenco"},
    {"label": "Wicked entradas", "url": "https://tickets.wickedelmusical.com/espectaculo/wicked-el-musical/W01"},
    {"label": "Houdini", "url": "https://www.houdinielmusical.com"},
    {"label": "Los Miserables", "url": "https://miserableselmusical.es/"},
    {"label": "Los Miserables elenco", "url": "https://miserableselmusical.es/elenco"},
    {"label": "Los Miserables entradas", "url": "https://tickets.miserableselmusical.es/espectaculo/los-miserables/M01"},
    {"label": "The Book of Mormon", "url": "https://thebookofmormonelmusical.es"},
    {"label": "Mormon elenco", "url": "https://thebookofmormonelmusical.es/elenco/"},
    {"label": "Mormon entradas", "url": "https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01"},
    {"label": "Buscando a Audrey", "url": "https://buscandoaaudrey.com"}
]
from bs4 import BeautifulSoup

def hash_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove tags that usually include changing content
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
            tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove common dynamic elements by class/id (add more as needed)
        dynamic_selectors = [
            ".date_info", ".timestamp", "#ad", ".ads", ".cookie-banner", "#cookies", ".tracker"
        ]
        for selector in dynamic_selectors:
            for tag in soup.select(selector):
                tag.decompose()

        # Normalize whitespace and strip
        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())  # remove excessive whitespace

        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"



def extract_normalized_date_info(url):
    """Get normalized text content from .date_info element."""
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    date_info = soup.select_one('.date_info')
    if not date_info:
        return None

    text = date_info.get_text(strip=True)
    return ' '.join(text.split()).lower()

      

results = []

def check_sites():
    global results
    new_results = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in URLS:
        url = item["url"]
        label = item["label"]
        try:
            res = requests.get(url, timeout=10)
            if "date_info" in res.text:
                new_results.append(f"[{now}] {label} ({url}) ✅ Found .date_info")
            else:
                new_results.append(f"[{now}] {label} ({url}) ❌ MISSING .date_info")
        except Exception as e:
            new_results.append(f"[{now}] {label} ({url}) ❌ ERROR: {e}")

    results[:] = new_results

@app.route("/diagnostic")
def diagnostic():
    check_sites()
    return "<pre>" + "\n".join(results) + "</pre>"


@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
