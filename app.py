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
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>🎟️ Ticket Monitor Dashboard</title>
      <style>
        /* Same styling as before... */
        /* Keep your existing CSS here */
        /* ... */

        #toast {
          position: fixed;
          bottom: 1rem;
          right: 1rem;
          background-color: #ec4899;
          color: white;
          padding: 1rem 1.5rem;
          border-radius: 12px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
          display: none;
          z-index: 9999;
        }

        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(20px); }
          10% { opacity: 1; transform: translateY(0); }
          90% { opacity: 1; }
          100% { opacity: 0; transform: translateY(20px); }
        }
      </style>
    </head>
    <body>
      <h1>🎭 Ticket monitoring dashboard</h1>

      <div class="dashboard">
        <div class="header">
          <p id="lastChecked" class="last-checked">Last Checked: ...</p>
          <span class="badge">🔄 Auto-refreshing</span>
        </div>

        <div id="changesList" class="grid">
          <div class="card"><span>⏳</span><span>Loading updates...</span></div>
        </div>
      </div>

      <div id="toast">Cambio detectado</div>

      <!-- 🔊 Audio element for notification -->
      <audio id="notifSound" preload="auto">
          <source src="{{ url_for('static', filename='door-bell-sound-99933.mp3') }}" type="audio/mpeg">
      </audio>


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
          const res = await fetch("/changes");
          const data = await res.json();

          document.getElementById("lastChecked").textContent =
            "Last Checked: " + new Date().toLocaleString("es-ES");

          const list = document.getElementById("changesList");
          list.innerHTML = "";

          // 🎯 Update tab title
          if (data.length > 0) {
            document.title = `(${data.length}) Cambios detectados 🎟️`;
          } else {
            document.title = "🎟️ Ticket Monitor Dashboard";
          }

          if (data.length === 0) {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = "<span>✅</span><span>No new changes detected.</span>";
            list.appendChild(card);
          } else {
            const notifSound = document.getElementById("notifSound");
            data.forEach(change => {
              const card = document.createElement("div");
              card.className = "card";
              card.innerHTML = `
                <h3>Cambio detectado</h3>
                <p><a href="${change.url}" target="_blank">${change.url}</a></p>
                <p>${change.timestamp}</p>
              `;
              list.appendChild(card);

              // ✅ Toast and sound
              showToast(`🔔 Cambio en:\n${change.url}`);
              notifSound.play().catch(() => {}); // prevent autoplay errors
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
        content_hash = hashlib.md5(response.content).hexdigest()
        return content_hash
    except Exception as e:
        return f"ERROR: {str(e)}"
@app.route("/changes")  
def changes():
    global previous_states
    updates = []

    for item in URLS:
        url = item["url"]
        current_hash = hash_url_content(url)
        last_hash = previous_states.get(url)

        if last_hash and last_hash != current_hash:
            updates.append({
                "url": url,
                "timestamp": datetime.now(UTC).isoformat()
            })

        # This should be outside the if block
        previous_states[url] = current_hash

    return jsonify(updates)


@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
