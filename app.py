import eventlet
eventlet.monkey_patch()

import hashlib
import json
from datetime import UTC, datetime
import requests
from bs4 import BeautifulSoup
from bs4.element import Comment
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO
import time
import os
from twilio.rest import Client
from dotenv import load_dotenv
import difflib

load_dotenv()

# Track previous states for change detection
previous_states = {}
previous_contents = {}
change_counts = {}
new_changes_detected = True

def send_whatsapp_message(label, url, to):
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        from_='whatsapp:+14155238886',
        content_sid='HXb5b62575e6e4ff6129ad7c8efe1f983e',  # reemplaza por el content_sid de tu plantilla aprobada
        content_variables=json.dumps({
            "1": label,  # Ejemplo: "Wicked"
            "2": url     # Ejemplo: "https://wickedelmusical.com/"
        }),
        to=f'whatsapp:{to}'
    )
    return message.sid

def send_telegram_message(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")  # Pon tu token en .env
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")  # Pon tu chat_id en .env
    if not token or not chat_id:
        print("Telegram token or chat_id not set")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram notification failed:", e)
        
# Real ticket monitoring URLs
URLS = [
    #{"label": "ddf", "url": "https://httpbin.org/get"},
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

def hash_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
            tag.decompose()
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        dynamic_selectors = [
            ".date_info", ".timestamp", "#ad", ".ads", ".cookie-banner", "#cookies", ".tracker"
        ]
        for selector in dynamic_selectors:
            for tag in soup.select(selector):
                tag.decompose()
        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())
        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"

def extract_normalized_date_info(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    date_info = soup.select_one('.date_info')
    if not date_info:
        return None
    text = date_info.get_text(strip=True)
    return ' '.join(text.split()).lower()

def find_differences(old_text, new_text):
    diff = difflib.unified_diff(
        old_text.splitlines(), 
        new_text.splitlines(), 
        fromfile='anterior', 
        tofile='actual', 
        lineterm=""
    )
    return "\n".join(diff)

def hash_audrey_content(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
            tag.decompose()
        for tag in soup.select(".banner, .dynamic, .cookie-banner, .ads, .date, .timestamp"):
            tag.decompose()
        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())
        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"

app = Flask(__name__)
socketio = SocketIO(app)

def broadcast_change(url, data):
    socketio.emit('update', {'url': url, 'data': data})

latest_changes = []

def scrape_all_sites():
    global previous_states, previous_contents, change_counts
    changes_list = []
    now = datetime.now(UTC).isoformat()
    for item in URLS:
        label = item["label"]
        url = item["url"]
        current_content = ""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
                tag.decompose()
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            current_content = soup.get_text(separator=" ", strip=True)
        except Exception as e:
            current_content = f"Error al obtener contenido: {str(e)}"
        if "buscandoaaudrey.com" in url:
            state = hash_audrey_content(url)
        else:
            state = extract_normalized_date_info(url)
            if state is None:
                state = hash_url_content(url)
            state = extract_normalized_date_info(url)
            if state is None:
                state = hash_url_content(url)
        last_state = previous_states.get(url)
        last_content = previous_contents.get(url, "")
        change_details = ""
        differences = ""
        if last_state is None:
            status = "Primer chequeo 👀"
            change_details = "Primera vez que se monitorea este sitio web"
            differences = "No hay contenido anterior para comparar"
            change_counts[url] = 0
        elif last_state != state:
            status = "¡Actualizado! 🎉"
            change_details = "Se detectaron cambios en el contenido del sitio web"
            change_counts[url] = change_counts.get(url, 0) + 1
            if last_content and current_content != last_content:
                differences = find_differences(last_content, current_content)
            else:
                differences = "Contenido modificado pero no se pudieron detectar diferencias específicas"
            broadcast_change(url, status)
            try:
                send_whatsapp_message(
                  label,           # nombre del show
                  url,             # enlace
                  '+34602502302'   # tu número WhatsApp
              )
                send_telegram_message(
            f"🎟 <b>{label}</b> ha cambiado!\n🔗 <a href='{url}'>{url}</a>"
        )
            except Exception as e:
                print("WhatsApp notification failed:", e)
        else:
            status = "Sin cambios ✨"
            change_details = "El contenido permanece igual desde la última verificación"
            differences = "Sin diferencias detectadas"
            if url not in change_counts:
                change_counts[url] = 0
        previous_states[url] = state
        previous_contents[url] = current_content
        changes_list.append({
            "label": label,
            "url": url,
            "status": status,
            "timestamp": now,
            "hash_actual": state,
            "hash_anterior": last_state,
            "detalles_cambio": change_details,
            "contenido_completo": current_content,
            "contenido_anterior": last_content,
            "diferencias_detectadas": differences,
            "longitud_contenido": len(current_content),
            "change_count": change_counts[url],
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        })
    print("latest_changes updated:", changes_list)
    return changes_list

def background_checker():
    global latest_changes
    while True:
        try:
            latest_changes = scrape_all_sites()
        except Exception as e:
            print("Error in background_checker:", e)
        time.sleep(30)

# Start background checker using SocketIO's method
socketio.start_background_task(background_checker)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ticket Monitor Dashboard</title>
  <style>
    body {
      font-family: 'Georgia', serif;
      margin: 0;
      padding: 0;
      min-height: 100vh;
      /* Remove static background */
      /* background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fecfef 100%); */
      overflow-x: hidden;
    }
    .animated-bg {
      position: fixed;
      top: 0; left: 0; width: 100vw; height: 100vh;
      z-index: -2;
      background: linear-gradient(120deg, #ffb6e6 0%, #fecfef 50%, #ffb6e6 100%);
      background-size: 200% 200%;
      animation: bgMove 10s ease-in-out infinite alternate;
    }
    @keyframes bgMove {
      0% { background-position: 0% 50%; }
      100% { background-position: 100% 50%; }
    }
    .floating-sparkle {
      position: absolute;
      font-size: 2em;
      pointer-events: none;
      opacity: 0.7;
      animation: floatSparkle 8s linear infinite;
    }
    .floating-sparkle.s1 { left: 10vw; top: 20vh; animation-delay: 0s; }
    .floating-sparkle.s2 { left: 80vw; top: 30vh; animation-delay: 2s; }
    .floating-sparkle.s3 { left: 50vw; top: 70vh; animation-delay: 4s; }
    .floating-sparkle.s4 { left: 30vw; top: 80vh; animation-delay: 1s; }
    .floating-sparkle.s5 { left: 70vw; top: 10vh; animation-delay: 3s; }
    @keyframes floatSparkle {
      0% { transform: translateY(0) scale(1) rotate(0deg); opacity: 0.7; }
      50% { transform: translateY(-40px) scale(1.2) rotate(10deg); opacity: 1; }
      100% { transform: translateY(0) scale(1) rotate(-10deg); opacity: 0.7; }
    }
    h1 {
      text-align: center;
      color: #d63384;
      font-size: 2.5em;
      text-shadow: 2px 2px 4px rgba(214, 51, 132, 0.3);
      margin: 20px 0;
      font-weight: bold;
    }
    .slideshow-container {
      max-width: 1100px; /* was 800px */
      margin: 30px auto;
      position: relative;
      border-radius: 28px;
      overflow: hidden;
      box-shadow: 0 8px 25px rgba(214, 51, 132, 0.3);
      border: 3px solid #ff69b4;
      background: linear-gradient(
        120deg,
        #ffe0f7 0%,
        #ffb6e6 25%,
        #ff69b4 50%,
        #ffc0cb 75%,
        #ffe0f7 100%
      );
      background-size: 400% 400%;
      animation: sliderMove 8s linear infinite alternate;
    }

@keyframes sliderMove {
  0% { background-position: 0% 50%; }
  100% { background-position: 100% 50%; }
}
    .slide {
      display: none;
      width: 100%;
    }
    /* Make the images taller too */
.slide img {
  width: 100%;
  height: 520px; /* was 400px */
  object-fit: contain;
  display: block;
  margin: 0 auto;
}
    table {
      width: 90%;
      margin: 20px auto;
      border-collapse: collapse;
      background: rgba(255, 255, 255, 0.9);
      border-radius: 15px;
      overflow: hidden;
      box-shadow: 0 8px 25px rgba(214, 51, 132, 0.2);
      border: 2px solid #ff69b4;
    }
    th, td {
      padding: 15px;
      border-bottom: 1px solid #ffb3d9;
      text-align: left;
      font-weight: 500;
    }
    th {
      background: linear-gradient(135deg, #ff69b4, #d63384);
      color: #fff;
      font-weight: bold;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    tr:hover {
      background: #ffe6f2;
      transform: scale(1.02);
      transition: all 0.3s ease;
    }
    td {
      color: #8b2c5c;
    }
    .sparkle {
      position: absolute;
      color: #ff69b4;
      animation: sparkle 2s infinite;
    }
    @keyframes sparkle {
      0%, 100% { opacity: 0; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1.2); }
    }
    .notification-popup {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: linear-gradient(135deg, #ff69b4, #ffc0cb);
      border: 3px solid #d63384;
      border-radius: 20px;
      padding: 30px;
      box-shadow: 0 10px 30px rgba(214, 51, 132, 0.4);
      z-index: 1000;
      text-align: center;
      color: #fff;
      display: none;
      max-width: 400px;
    }
    .notification-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.5);
      z-index: 999;
      display: none;
    }
    .popup-button {
      background: #fff;
      color: #d63384;
      border: 2px solid #d63384;
      padding: 10px 20px;
      border-radius: 15px;
      margin: 10px;
      cursor: pointer;
      font-weight: bold;
      text-decoration: none;
      display: inline-block;
    }
    .popup-button:hover {
      background: #d63384;
      color: #fff;
    }
    .status-updated {
      background: linear-gradient(135deg, #ff69b4, #ffc0cb);
      color: #fff;
      padding: 5px 10px;
      border-radius: 15px;
      font-weight: bold;
    }
    .status-no-change {
      color: #8b2c5c;
    }
    .last-checked {
      text-align: center;
      color: #d63384;
      font-weight: bold;
      margin: 20px 0;
    }
    .change-badge {
      background: linear-gradient(135deg, #ff69b4, #d63384); /* Igual que th */
      color: white;
      border-radius: 12px;
      padding: 2px 8px;
      font-size: 0.8em;
      font-weight: bold;
      margin-left: 8px;
      display: inline-block;
      min-width: 20px;
      text-align: center;
      box-shadow: 0 2px 4px rgba(255, 107, 107, 0.3);
      text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    .change-badge.zero {
      background: #ddd;
      color: #666;
    }
    .json-popup {
      position: fixed;
      top: 5%;
      left: 5%;
      width: 90%;
      height: 90%;
      background: white;
      border: 3px solid #d63384;
      border-radius: 20px;
      z-index: 2000;
      display: none;
      overflow: hidden;
    }
    .json-popup-header {
      background: linear-gradient(135deg, #ff69b4, #d63384);
      color: white;
      padding: 15px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .json-popup-content {
      height: calc(100% - 80px);
      overflow: auto;
      padding: 20px;
      background: #f8f9fa;
    }
    .json-code {
      background: #2d3748;
      color: #e2e8f0;
      padding: 20px;
      border-radius: 10px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      line-height: 1.4;
      white-space: pre-wrap;
      word-wrap: break-word;
      max-height: 100%;
      overflow: auto;
    .highlighted-bg {
  position: relative;
  margin: 30px auto 0 auto;
  max-width: 900px;
  border-radius: 25px;
  overflow: hidden;
  box-shadow: 0 8px 25px rgba(214, 51, 132, 0.15);
  border: 4px solid #ff69b4;
  background: linear-gradient(
    120deg,
    #ffe0f7 0%,
    #ffb6e6 25%,
    #ff69b4 50%,
    #ffc0cb 75%,
    #ffe0f7 100%
  );
  background-size: 400% 400%;
  animation: highlightMove 6s linear infinite alternate;
  padding: 30px 0 20px 0;
}

@keyframes highlightMove {
  0% { background-position: 0% 50%; }
  100% { background-position: 100% 50%; }
}
    .close-json-btn {
      background: white;
      color: #d63384;
      border: none;
      padding: 8px 15px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: bold;
    }
    .close-json-btn:hover {
      background: #f0f0f0;
    }
    body, a, button {
  cursor: url('https://cur.cursors-4u.net/cursors/cur-9/cur818.cur'), auto;
}
    .json-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      z-index: 1999;
      display: none;
    }
  </style>
</head>
<!-- Add this inside your <head> or at the top of your HTML -->

<a href="https://www.cursors-4u.com/cursor/2011/02/18/cute-bow-tie-hearts-blinking-blue-and-pink-pointer.html" target="_blank" title="Cute Bow Tie Hearts Blinking Blue and Pink Pointer">
  <img src="https://cur.cursors-4u.net/cursor.png" border="0" alt="Cute Bow Tie Hearts Blinking Blue and Pink Pointer" style="position:absolute; top: 0px; right: 0px;" />
</a>
<body>
<div id="telegram-popup-overlay" style="display:block;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.45);z-index:9999;">
  <div style="background:linear-gradient(135deg,#ff69b4,#d63384);max-width:340px;margin:12vh auto 0 auto;padding:32px 24px 24px 24px;border-radius:22px;box-shadow:0 8px 32px #d6338440;text-align:center;position:relative;">
    <img src="https://telegram.org/img/t_logo.svg" alt="Telegram" style="width:48px;margin-bottom:10px;">
    <h2 style="color:#fff;margin:0 0 10px 0;font-size:1.4em;text-shadow:1px 1px 2px #d63384;">¿Quieres recibir alertas?</h2>
    <p style="color:#fff;margin-bottom:18px;font-weight:bold;text-shadow:1px 1px 2px #d63384;">Únete a nuestro canal de Telegram para enterarte de los cambios al instante.</p>
    <a href="https://t.me/TheBookOfMormonTicketsBot" target="_blank"
      style="display:inline-block;background:#fff;color:#d63384;font-weight:bold;border-radius:16px;padding:10px 24px;text-decoration:none;font-size:1.1em;box-shadow:0 2px 8px #d6338440;border:2px solid #ff69b4;transition:background 0.2s;">
      Unirme a Telegram
    </a>
    <br>
    <button onclick="document.getElementById('telegram-popup-overlay').style.display='none';"
      style="margin-top:18px;background:none;border:none;color:#fff;font-weight:bold;font-size:1em;cursor:pointer;text-shadow:1px 1px 2px #d63384;">
      No, gracias
    </button>
  </div>
</div>
<h1>✨ Ticket Monitor Dashboard ✨</h1>
<!-- Telegram Join Popup with matching table header colors -->


<div class="animated-bg"></div>
<div class="floating-sparkle s1">✨</div>
<div class="floating-sparkle s2">💖</div>
<div class="floating-sparkle s3">🌸</div>
<div class="floating-sparkle s4">💕</div>
<div class="floating-sparkle s5">✨</div>

<!-- Slideshow + Spotify widget alineados -->
<div style="display: flex; justify-content: center; align-items: center; gap: 40px; margin: 40px auto 30px auto; max-width: 1200px;">
  <!-- Slideshow grande y centrado -->
  <div style="flex: 2 1 0; min-width: 0; display: flex; justify-content: center;">
    <div class="slideshow-container" style="max-width: 700px; width: 100%; margin: 0 auto;">
      <div class="slide">
        <img src="https://paginasdigital.es/wp-content/uploads/2024/12/wicked-portada.jpg" alt="Wicked1">
      </div>
      <div class="slide">
        <img src="https://images.ctfassets.net/sjxdiqjbm079/3WMcDT3PaFgjIinkfvmh1L/cf88d0afc6280931ee110ac47ec573a8/01_LES_MIS_TOUR_02_24_0522_PJZEDIT_v002.jpg?w=708&h=531&fm=webp&fit=fill" alt="Los Miserables">
      </div>
      <div class="slide">
        <img src="https://www.princeofwalestheatre.co.uk/wp-content/uploads/2024/02/BOM-hi-res-Turn-it-off-Nov-2023-9135-hi-res.webp" alt="Book of Mormon">
      </div>
      <div class="slide">
        <img src="/static/AUDREY1.jpg" alt="Buscando a Audrey">
      </div>
      <div class="slide">
        <img src="/static/HOUDINI1.jpg" alt="Houdini">
      </div>
      <div class="slide">
        <img src="/static/WICKED1.jpg" alt="Wicked1">
      </div>
      <div class="slide">
        <img src="/static/LESMIS1.jpg" alt="Los Miserables1">
      </div>
      <div class="slide">
        <img src="/static/BOM1.jpg" alt="Book of Mormon1">
      </div>
      <div class="slide">
        <img src="/static/WICKED2.jpg" alt="Wicked2">
      </div>
      <div class="slide">
        <img src="/static/LESMIS2.jpg" alt="Los Miserables2">
      </div>
      <div class="slide">
        <img src="/static/BOM2.jpg" alt="Book of Mormon2">
      </div>
      <div class="slide">
        <img src="/static/WICKED3.jpg" alt="Wicked3">
      </div>
      <div class="slide">
        <img src="/static/LESMIS3.png" alt="Los Miserables3">
      </div>
      <div class="slide">
        <img src="/static/BOM3.jpg" alt="Book of Mormon3">
      </div>
      <div class="slide">
        <img src="/static/WICKED4.jpg" alt="Wicked4">
      </div>
      <div class="slide">
        <img src="/static/LESMIS4.jpg" alt="Los Miserables4">
      </div>
      <div class="slide">
        <img src="/static/BOM4.jpg" alt="Book of Mormon4">
      </div>
      <div class="slide">
        <img src="/static/WICKED5.jpg" alt="Wicked5">
      </div>
      <div class="slide">
        <img src="/static/LESMIS5.jpg" alt="Los Miserables5">
      </div>
      <div class="slide">
        <img src="/static/BOM5.jpg" alt="Book of Mormon5">
      </div>
      <div class="slide">
        <img src="/static/WICKED6.jpg" alt="Wicked6">
      </div>
      <div class="slide">
        <img src="/static/LESMIS6.jpg" alt="Los Miserables6">
      </div>
      <div class="slide">
        <img src="/static/BOM6.jpg" alt="Book of Mormon6">
      </div>
      <div class="slide">
        <img src="/static/WICKED7.jpg" alt="Wicked7">
      </div>
      <div class="slide">
        <img src="/static/LESMIS7.jpg" alt="Los Miserables7">
      </div>
      <div class="slide">
        <img src="/static/BOM7.jpg" alt="Book of Mormon7">
      </div>
    </div>
  </div>
  <!-- Widget Spotify alineado verticalmente -->
  <div style="flex: 0 0 340px; min-width: 300px; display: flex; align-items: center;">
    <iframe style="border-radius:12px; box-shadow:0 4px 16px #d6338440;" src="https://open.spotify.com/embed/playlist/7w9wB3KwgtClfngWeFLBQX?utm_source=generator&theme=0" width="340" height="452" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
  </div>
</div>

<div class="notification-overlay" id="notificationOverlay"></div>
<div class="notification-popup" id="notificationPopup">
  <h2>✨ New Changes Detected! ✨</h2>
  <p>💖 Fresh ticket updates are available! 💖</p>
  <div>
    <button class="popup-button" onclick="viewJsonFromPopup()">📄 View JSON Data</button>
    <button class="popup-button" onclick="closeNotification()">Close</button>
  </div>
</div>

<div class="json-overlay" id="jsonOverlay" onclick="closeJsonPopup()"></div>
<div class="json-popup" id="jsonPopup">
  <div class="json-popup-header">
    <h3>📄 JSON Changes Data</h3>
    <button class="close-json-btn" onclick="closeJsonPopup()">✕ Close</button>
  </div>
  <div class="json-popup-content">
    <div class="json-code" id="jsonContent">Loading...</div>
  </div>
</div>


<div class="last-checked" id="lastChecked">Last Checked: Loading...</div>



<table id="changesTable">
  <tr>
    <th>Show/Website</th>
    <th>Cambios</th>
    <th>URL</th>
    <th>Status</th>
    <th>Last Update</th>
  </tr>
  <td colspan="5" style="text-align: center;">Loading ticket data...</td>
</table>

<script>
  let slideIndex = 0;
  showSlides();

  function showSlides() {
    let slides = document.getElementsByClassName("slide");
    if (slides.length === 0) return;
    
    for (let i = 0; i < slides.length; i++) {
      slides[i].style.display = "none";
    }
    slideIndex++;
    if (slideIndex > slides.length) { slideIndex = 1; }
    slides[slideIndex-1].style.display = "block";
    setTimeout(showSlides, 3000);
  }
  window.addEventListener('DOMContentLoaded', function() {
  if (!localStorage.getItem('telegram_popup_shown')) {
    document.getElementById('telegram-popup-overlay').style.display = 'block';
    localStorage.setItem('telegram_popup_shown', 'yes');
  }
});
  function showNotification() {
    document.getElementById('notificationOverlay').style.display = 'block';
    document.getElementById('notificationPopup').style.display = 'block';
    
    // Play notification sound
    playNotificationSound();
  }
  
  function playNotificationSound() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      const playTone = (frequency, startTime, duration) => {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.setValueAtTime(frequency, startTime);
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0, startTime);
        gainNode.gain.linearRampToValueAtTime(0.1, startTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
        
        oscillator.start(startTime);
        oscillator.stop(startTime + duration);
      };
      
      const now = audioContext.currentTime;
      playTone(523.25, now, 0.2);        // C5
      playTone(659.25, now + 0.1, 0.2);  // E5
      playTone(783.99, now + 0.2, 0.3);  // G5
    } catch (e) {
      console.log('Audio not supported');
    }
  }

  function closeNotification() {
    document.getElementById('notificationOverlay').style.display = 'none';
    document.getElementById('notificationPopup').style.display = 'none';
  }

  function viewJsonFromPopup() {
    showJsonPopup();
    closeNotification();
  }
  
  async function showJsonPopup() {
    document.getElementById('jsonOverlay').style.display = 'block';
    document.getElementById('jsonPopup').style.display = 'block';
    document.getElementById('jsonContent').textContent = 'Loading JSON data...';
    
    try {
      const response = await fetch('/api/changes.json');
      const jsonData = await response.text();
      document.getElementById('jsonContent').textContent = jsonData;
    } catch (error) {
      document.getElementById('jsonContent').textContent = 'Error loading JSON data: ' + error.message;
    }
  }
  
  function closeJsonPopup() {
    document.getElementById('jsonOverlay').style.display = 'none';
    document.getElementById('jsonPopup').style.display = 'none';
  }

  async function updateTicketData() {
    try {
      const response = await fetch('/api/ticket-changes');
      const data = await response.json();
      
      document.getElementById('lastChecked').textContent = 
        'Last Checked: ' + new Date().toLocaleString();
      
      const table = document.getElementById('changesTable');
      table.innerHTML = `
        <tr>
          <th>Show/Website</th>
           <th>Cambios</th>
          <th>URL</th>
          <th>Status</th>
          <th>Last Update</th>
        </tr>
      `;
      
      let hasUpdates = false;
      data.forEach(item => {
        const row = table.insertRow();
        const changeCount = item.change_count || 0;
        const badgeClass = changeCount === 0 ? 'change-badge zero' : 'change-badge';
        
        row.innerHTML = `
          <td>${item.label}</td>
          <td><span class="${badgeClass}">${changeCount}</span></td>
          <td><a href="${item.url}" target="_blank" style="color: #d63384;">${item.url}</a></td>
          <td class="${item.status.includes('Actualizado') ? 'status-updated' : 'status-no-change'}">${item.status}</td>
          <td>${new Date(item.timestamp).toLocaleString()}</td>
        `;
        
        if (item.status.includes('Actualizado')) {
          hasUpdates = true;
          row.style.background = 'linear-gradient(135deg, #ffe4f1, #ffc0cb)';
        }
      });
      
      if (hasUpdates) {
        showNotification();
      }
      
    } catch (error) {
      console.error('Error fetching ticket data:', error);
      document.getElementById('lastChecked').textContent = 'Error loading data';
    }
  }

  // Initial load and periodic updates
  updateTicketData();
  setInterval(updateTicketData, 5000); // Check every 5 seconds
</script>

</body>
</html>
"""
@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/changes')
def changes_dummy():
    return "Not implemented", 200

@app.route('/api/changes.json')
def get_changes_json():
    global latest_changes
    updated_sites = [c for c in latest_changes if "Actualizado" in c.get("status", "")]
    now = datetime.now(UTC).isoformat()
    response_data = {
        "resumen": {
            "total_sitios_monitoreados": len(latest_changes),
            "sitios_actualizados": len(updated_sites),
            "ultimo_chequeo": now,
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        },
        "sitios_web_actualizados": updated_sites
    }
    response = app.response_class(
        response=json.dumps(response_data, indent=2, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route('/api/ticket-changes')
def get_ticket_changes():
    global latest_changes
    return jsonify(latest_changes)

@app.route('/api/check-changes')
def check_changes():
    try:
        has_new_changes = any(item.get('status', '').find('Actualizado') != -1 for item in latest_changes)
        return {"new_changes": has_new_changes}
    except:
        return {"new_changes": False}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)