from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO
import os
from datetime import datetime, UTC
import requests
import hashlib
import json
from bs4 import BeautifulSoup
from bs4.element import Comment
from telegram import Bot

app = Flask(__name__)
socketio = SocketIO(app)
previous_states = {}
TELEGRAM_TOKEN = '7763897628:AAEQVDEOBfHmWHbyfeF_Cx99KrJW2ILlaw0'
CHAT_ID = '553863319'

def send_telegram_text(url, changes, timestamp):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🎭 Ticket Alert!\n"
            f"🌐 URL: {url}\n"
            f"🕒 Cambio detectado: {timestamp}\n"
            f"📄 Cambios:\n{changes[:3500]}"
        )
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("✅ Telegram message sent!")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

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
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  h1 {
    font-size: 2.2rem;
    text-align: center;
    color: #d63384;
    text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    margin-bottom: 1.5rem;
    width: 100%;
  }
  .dashboard {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 1rem;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .header {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 1rem;
    gap: 2rem;
    width: 100%;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 2.2rem;
    width: 100%;
    justify-items: center;      /* Centra las tarjetas en su celda */
    align-items: start;
    justify-content: center;    /* Centra el grid completo */
  }
  
  .card {
    perspective: 1200px;
    width: 17em;
    min-height: 220px;
    max-width: 320px; /* o el valor que prefieras */
    min-width: 0;
    border-radius: 1.2rem;
    overflow: hidden;
    background: linear-gradient(135deg, #ffe4f1 0%, #fbc2eb 50%, #f9a8d4 100%);
    border: 1.5px solid #ec4899;
    box-shadow: 0 8px 32px 0 rgba(236, 72, 153, 0.13), 0 1.5px 8px 0 rgba(255, 192, 203, 0.13);
    margin: 0.7rem 0;
    display: flex;
    align-items: stretch;
    justify-content: center;
  }
  .autorefresh-glow {
    animation: glow 1.2s ease-in-out infinite alternate;
    box-shadow: 0 0 16px #ec4899, 0 0 4px #fff0f6;
  }
  .card-inner {
    position: relative;
    width: 100%;
    height: 100%;
    transition: transform 0.7s cubic-bezier(.4,2,.6,1);
    transform-style: preserve-3d;
    border-radius: 1.2rem;
    min-height: 220px;
  }
  .card:hover .card-inner {
    transform: rotateY(180deg);
  }
  .card-front, .card-back {
    position: absolute;
    width: 100%;
    height: 100%;
    backface-visibility: hidden;
    border-radius: 1.2rem;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card-front {
    background: #fff7fb;
    z-index: 2;
  }
  .musical-img {
    width: 100%;
    height: 100%;
    background-size: cover;
    background-position: center;
    border-radius: 1.2rem;
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 0; /* <-- Asegura que la imagen esté detrás */
    transition: filter 0.3s;
  }
  .card-back {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-weight: 500;
    padding: 1.2rem 1rem;
    height: 100%;
    z-index: 2; /* sube el z-index */
    position: relative; /* crea stacking context */
    background: rgba(255,255,255,0.96); /* fondo blanco semitransparente */
  }
  .card-back h3,
  .card-back p,
  .card-back a {
    width: 100%;
    text-align: center;
    margin-left: auto;
    margin-right: auto;
  }
  .card-back h3 {
    color: #ec4899;
    font-weight: 700;
    margin-bottom: 0.5em;
  }
  .card-back p, .card-back a {
    color: #b91c5c;
    margin: 0.2em 0;
    word-break: break-all;
    font-size: 0.95em;
  }
  .card-back a {
    display: block;
    width: 100%;
    max-width: 100%;
    overflow-wrap: anywhere;
    word-break: break-all;
    color: #b91c5c;
    text-align: center;
    font-size: 0.95em;
    margin: 0.2em 0;
    background: none;
    border: none;
    text-decoration: underline;
  }
  .card-overlay {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(255,255,255,0.96);
    color: #d63384;
    border-radius: 1.2rem;
    opacity: 0;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: opacity 0.3s;
    padding: 1.2rem 1rem;
    text-align: center;
    font-weight: 500;
  }
  .card a { 
    word-break: break-all;
    overflow-wrap: anywhere;
    display: inline-block;
    max-width: 100%;
    text-align: center;
  }
  .card:hover {
    transform: translateY(-8px) scale(1.04);
    box-shadow: 0 16px 40px 0 rgba(236, 72, 153, 0.28), 0 2px 12px 0 rgba(255, 192, 203, 0.22);
    border-color: #ec4899;
  }
  .card h3 {
    color: #ec4899;
    font-weight: 700;
    letter-spacing: 0.5px;
  }
  .card p {
    margin: 0.2rem 0;
    font-size: 0.95rem;
    color: #9d174d;
    width: 100%;
  }
  .card-front-text {
    position: relative;
    z-index: 1; /* <-- El texto va encima de la imagen */
    width: 100%;
    text-align: center;
    background: rgba(255,255,255,0.85);
    padding: 0.5em 0.2em;
    border-radius: 0 0 1.2rem 1.2rem;
    margin-top: auto;
  }
  .card:nth-child(even) {
    background-color: #fff7fb;
  }
  .card.updated {
    animation: flashBorder 1.2s ease;
  }
  .card .status-dot {
    position: absolute;
    top: 1rem;
    right: 1rem;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #ec4899;
    box-shadow: 0 0 8px #ec4899aa;
  }
  .card.updated .status-dot {
    background: #22c55e;
    box-shadow: 0 0 8px #22c55e99;
  }
  @keyframes flashBorder {
    0% { border-color: #f43f5e; box-shadow: 0 0 0 0 rgba(244,63,94,0.7); }
    50% { border-color: #fb7185; box-shadow: 0 0 8px 4px rgba(244,63,94,0.3); }
    100% { border-color: #ec4899; box-shadow: none; }
  }
  @keyframes glow {
    0% { box-shadow: 0 0 10px #ec4899; }
    100% { box-shadow: none; }
  }
  .card.recent-change {
    animation: glow 1s ease-in-out 3;
  }
  #toast-container {
    position: fixed;
    top: 1.5rem;
    right: 1.5rem;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    align-items: flex-end;
  }
  .toast {
    background: #ec4899;
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 1rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    min-width: 220px;
    max-width: 350px;
    font-size: 1rem;
    display: flex;
    align-items: center;
    animation: fadeInOut 0.6s ease-in-out;
    position: relative;
  }
  .toast button {
    margin-left: 1em;
    background: none;
    border: none;
    color: white;
    font-size: 1.2em;
    cursor: pointer;
    position: absolute;
    top: 0.5em;
    right: 0.7em;
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
    width: 100%;
  }
  @media (max-width: 900px) {
    .grid { grid-template-columns: repeat(2, 1fr); }
  }
  @media (max-width: 600px) {
    .grid { grid-template-columns: 1fr; }
  }
  </style>
</head>
<body>
  <div id="toast-container"></div>
  <h1>🌸✨ Ticket Monitoring Dashboard ✨🌸</h1>
  <div class="dashboard">
    <div class="header">
      <p id="lastChecked" class="last-checked">Last Checked: ...</p>
      <div class="card autorefresh-glow" style="padding:0.5rem 0.5rem; max-width:180px; min-height:auto; background:#ffe4f1; border-color:#ec4899;">
        💖 Auto-refreshing
      </div>
    </div>
    <div id="changesList" class="grid">
      <div class="card"><span>⏳</span> <span>Loading updates...</span></div>
    </div>
  </div>
  <audio id="notifSound" preload="auto">
    <source src="{{ url_for('static', filename='door-bell-sound-99933.mp3') }}" type="audio/mpeg">
  </audio>
  <p id="loadingIndicator">🔎 Checking for updates...</p>
  <script>
  // --- Add this block at the top of your <script> ---
  const musicalImages = {
    "Wicked": "{{ url_for('static', filename='wicked-reparto-673ca639117ae.avif') }}",
    "Wicked elenco": "{{ url_for('static', filename='wicked-reparto-673ca639117ae.avif') }}",
    "Wicked entradas": "{{ url_for('static', filename='wicked-reparto-673ca639117ae.avif') }}",
    "Houdini": "{{ url_for('static', filename='cartel_movil4.webp') }}",
    "Los Miserables": "{{ url_for('static', filename='les-mis-banner.jpg') }}",
    "Los Miserables elenco": "{{ url_for('static', filename='les-mis-banner.jpg') }}",
    "Los Miserables entradas": "{{ url_for('static', filename='les-mis-banner.jpg') }}",
    "The Book of Mormon": "{{ url_for('static', filename='foto.webp') }}",
    "The Book of Mormon elenco": "{{ url_for('static', filename='foto.webp') }}",
    "The Book of Mormon entradas": "{{ url_for('static', filename='foto.webp') }}",
    "Buscando a Audrey": "{{ url_for('static', filename='audrey-hepburn-in-breakfast-at-tiffanys.jpg') }}",
    "default": "{{ url_for('static', filename='default.jpg') }}"
  };
  if ("Notification" in window && Notification.permission !== "granted") {
    Notification.requestPermission();
  }

  function showToast(message, url = null) {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = url
      ? `<span><a href="${url}" target="_blank" style="color:white;text-decoration:underline;">${message}</a></span>
         <button onclick="this.parentElement.remove();removeToastFromSession('${encodeURIComponent(message)}')">&times;</button>`
      : `<span>${message}</span>
         <button onclick="this.parentElement.remove();removeToastFromSession('${encodeURIComponent(message)}')">&times;</button>`;
    container.appendChild(toast);

    // Browser notification (as before)
    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      const notification = new Notification("🎟️ Ticket Monitor", { 
        body: message.replace(/\\n/g, " "),
        data: { url: url }
      });
      notification.onclick = function(event) {
        event.preventDefault();
        if (notification.data && notification.data.url) {
          window.open(notification.data.url, "_blank");
        } else {
          window.focus();
        }
        this.close();
      };
    }

    // Save to sessionStorage
    let toasts = JSON.parse(sessionStorage.getItem("toasts") || "[]");
    if (!toasts.includes(message)) {
      toasts.push(message);
      sessionStorage.setItem("toasts", JSON.stringify(toasts));
    }
  }

  function removeToastFromSession(message) {
    let toasts = JSON.parse(sessionStorage.getItem("toasts") || "[]");
    toasts = toasts.filter(m => m !== decodeURIComponent(message));
    sessionStorage.setItem("toasts", JSON.stringify(toasts));
  }

  // On page load, restore toasts visually only
  window.addEventListener("DOMContentLoaded", () => {
    let toasts = JSON.parse(sessionStorage.getItem("toasts") || "[]");
    const container = document.getElementById("toast-container");
    toasts.forEach(msg => {
      const toast = document.createElement("div");
      toast.className = "toast";
      toast.innerHTML = `
        <span>${msg}</span>
        <button onclick="this.parentElement.remove();removeToastFromSession('${encodeURIComponent(msg)}')">&times;</button>
      `;
      container.appendChild(toast);
    });
  });

  let totalCambios = 0;

  async function update() {
    document.getElementById("loadingIndicator").style.display = "block";
    try {
      const res = await fetch("/changes");
      if (!res.ok) throw new Error("Network error");
      const data = await res.json();
      document.getElementById("loadingIndicator").style.display = "none";
      document.getElementById("lastChecked").textContent =
        "Última revisión: " + new Date().toLocaleString("es-ES");
      const list = document.getElementById("changesList");
      list.innerHTML = "";

      const cambios = data.filter(change => change.status.includes("Actualizado")).length;
      totalCambios += cambios;
      document.title = `(${totalCambios}) 🎟️ Ticket Monitor`;

      if (data.length === 0) {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = "<span>✅</span><span> Todo está fabuloso. Sin cambios detectados.</span>";
        list.appendChild(card);
      } else {
        const notifSound = document.getElementById("notifSound");
        data.forEach(change => {
          const card = document.createElement("div");
          card.className = "card";
          const imgSrc = musicalImages[change.label] || musicalImages["default"];
          card.innerHTML = `
            <div class="card-inner">
              <div class="card-front">
                <div class="musical-img" style="background-image:url('${imgSrc}')"></div>
                <div class="card-front-text">
                  <h3>${change.label}</h3>
                  <p>${change.status}</p>
                </div>
              </div>
              <div class="card-back">
                <h3>${change.label}</h3>
                <a href="${change.url}" target="_blank">${change.url}</a>
                <p>${change.status}</p>
                <p>🕒 ${new Date(change.timestamp).toLocaleString("es-ES")}</p>
              </div>
            </div>
          `;
          if (change.status.includes("Actualizado")) {
            card.style.borderColor = "#ec4899";
            card.style.backgroundColor = "#ffe4f1";
            card.classList.add("recent-change");
            showToast(`🎀 Cambio en:\n${change.url}`, change.url);
            notifSound.play().catch(() => {});
            if ("vibrate" in navigator) navigator.vibrate([120, 60, 120]);
          }
          list.appendChild(card);
        });
      }
    } catch (e) {
      document.getElementById("loadingIndicator").textContent = "❌ Error cargando actualizaciones";
      console.error(e);
    }
  }
  update();
  setInterval(update, 10000);
  </script>
</body>
</html>
""")

URLS = [
    #{"label": "test", "url": "https://httpbin.org/get/"},
    {"label": "Wicked", "url": "https://wickedelmusical.com/"},
    {"label": "Wicked elenco", "url": "https://wickedelmusical.com/elenco"},
    {"label": "Wicked entradas", "url": "https://tickets.wickedelmusical.com/espectaculo/wicked-el-musical/W01"},
    
    {"label": "Los Miserables", "url": "https://miserableselmusical.es/"},
    {"label": "Los Miserables elenco", "url": "https://miserableselmusical.es/elenco"},
    {"label": "Los Miserables entradas", "url": "https://tickets.miserableselmusical.es/espectaculo/los-miserables/M01"},
    {"label": "The Book of Mormon", "url": "https://thebookofmormonelmusical.es"},
    {"label": "The Book of Mormon elenco", "url": "https://thebookofmormonelmusical.es/elenco/"},
    {"label": "The Book of Mormon entradas", "url": "https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01"},
    {"label": "Buscando a Audrey", "url": "https://buscandoaaudrey.com"},
    {"label": "Houdini", "url": "https://www.houdinielmusical.com"}
]
from bs4 import BeautifulSoup
def broadcast_change(url, data):
    socketio.emit('update', {'url': url, 'data': data})
    
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

@app.route("/changes")
def changes():
    global previous_states
    changes_list = []
    now = datetime.now(UTC).isoformat()

    for item in URLS:
        label = item["label"]
        url = item["url"]

        # For test URL, always mark as updated
        if "httpbin.org" in url:
            status = "¡Actualizado! 🎉"
            state = str(datetime.now())
        else:
            state = extract_normalized_date_info(url)
            if state is None:
                state = hash_url_content(url)

            last_state = previous_states.get(url)
            if last_state is None:
                status = "Primer chequeo 👀"
            elif last_state != state:
                status = "¡Actualizado! 🎉"
                send_telegram_text(url, "Cambio detectado en la web", now)
                broadcast_change(url, status)  # <-- Add this line
            else:
                status = "Sin cambios ✨"

        previous_states[url] = state

        changes_list.append({
            "label": label,
            "url": url,
            "status": status,
            "timestamp": now
        })

    return jsonify(changes_list)

@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)