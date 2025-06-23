from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC
import requests
import hashlib
import json

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
          background: linear-gradient(to right, #ffe6f0, #fff0f7);
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

def hash_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        combined = response.content + json.dumps(dict(response.headers), sort_keys=True).encode()
        content_hash = hashlib.md5(combined).hexdigest()
        return content_hash
    except Exception as e:
        return f"ERROR: {str(e)}"

      
@app.route("/changes")
def changes():
    global previous_states
    updates = []

    for item in URLS:
        label = item["label"]
        url = item["url"]
        current_hash = hash_url_content(url)
        last_hash = previous_states.get(url)
        
        # Compare hashes to detect updates
        status = "Sin cambios ✨"
        if last_hash and last_hash != current_hash:
            status = "¡Actualizado! 🎉"
        elif last_hash is None:
            status = "Primer chequeo 👀"
        
        previous_states[url] = current_hash

        updates.append({
            "label": label,
            "url": url,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat()
        })

    return jsonify(updates)


@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
