import eventlet
eventlet.monkey_patch()

import hashlib
import json
import time
import os
import difflib
import requests
from datetime import UTC, datetime
from bs4 import BeautifulSoup
from bs4.element import Comment
from flask import Flask, jsonify, render_template_string, request
from flask_socketio import SocketIO
from twilio.rest import Client
from dotenv import load_dotenv

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
    content_sid='HXb5b62575e6e4ff6129ad7c8efe1f983e',  # replace with your approved template content_sid
    content_variables=json.dumps({
      "1": label,
      "2": url
    }),
    to=f'whatsapp:{to}'
  )
  return message.sid

def send_telegram_message(text):
  token = os.environ.get("TELEGRAM_BOT_TOKEN")
  chat_id = os.environ.get("TELEGRAM_CHAT_ID")
  if not token or not chat_id:
    print("Telegram token or chat_id not set")
    return
  url = f"https://api.telegram.org/bot{token}/sendMessage"
  payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
  try:
    r = requests.post(url, data=payload, timeout=5)
    print("Telegram response:", r.status_code, r.text)
  except Exception as e:
    print("Telegram notification failed:", e)

URLS = [
  {"label": "ddf", "url": "https://httpbin.org/get"},
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

def get_simple_content(url):
  try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "iframe", "link"]):
      tag.decompose()
    content_text = soup.get_text(separator=" ", strip=True)
    normalized_text = " ".join(content_text.split())
    return normalized_text
  except Exception as e:
    print(f"Error fetching {url}: {str(e)}")
    return f"ERROR: {str(e)}"

def scrape_all_sites():
  global previous_contents, change_counts
  changes_list = []
  now = datetime.now(UTC).isoformat()
  for item in URLS:
    label = item["label"]
    url = item["url"]
    current_content = get_simple_content(url)
    last_content = previous_contents.get(url, "")
    if not last_content:
      status = "Primer chequeo 👀"
      change_details = "Primera vez que se monitorea este sitio web"
      differences = "No hay contenido anterior para comparar"
      change_counts[url] = 0
    elif current_content != last_content and len(current_content) > 100:
      status = "¡Actualizado! 🎉"
      change_details = "Se detectaron cambios en el contenido del sitio web"
      change_counts[url] = change_counts.get(url, 0) + 1
      differences = find_differences(last_content, current_content)
      try:
        send_whatsapp_message(label, url, '+34602502302')
        send_telegram_message(f"🎟 <b>{label}</b> ha cambiado!\n🔗 <a href='{url}'>{url}</a>")
      except Exception as e:
        print("Notification failed:", e)
    else:
      status = "Sin cambios ✨"
      change_details = "El contenido permanece igual desde la última verificación"
      differences = "Sin diferencias detectadas"
      if url not in change_counts:
        change_counts[url] = 0
    previous_contents[url] = current_content
    changes_list.append({
      "label": label,
      "url": url,
      "status": status,
      "timestamp": now,
      "hash_actual": hashlib.md5(current_content.encode("utf-8")).hexdigest(),
      "hash_anterior": hashlib.md5(last_content.encode("utf-8")).hexdigest() if last_content else None,
      "detalles_cambio": change_details,
      "contenido_completo": current_content,
      "contenido_anterior": last_content,
      "diferencias_detectadas": differences,
      "longitud_contenido": len(current_content),
      "change_count": change_counts[url],
      "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
    })
  print("latest_changes updated:", len(changes_list), "sites")
  return changes_list

def background_checker():
  global latest_changes
  while True:
    try:
      latest_changes = scrape_all_sites()
    except Exception as e:
      print("Error in background_checker:", e)
    time.sleep(30)

@app.route('/')
def dashboard():
  return render_template_string(HTML_TEMPLATE)

socketio.start_background_task(background_checker)

# Add this HTML_TEMPLATE before the routes
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎭 Ticket Monitor Dashboard</title>
    <style>
        body {
            font-family: 'Georgia', serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #ff9a9e, #fecfef, #fecfef, #ff9a9e);
            min-height: 100vh;
            color: #2c2c2c;
        }
        
        .container {
            max-width: 95%;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 15px 35px rgba(214, 51, 132, 0.3);
            border: 3px solid #ff69b4;
        }
        
        h1 {
            text-align: center;
            color: #d63384;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(214, 51, 132, 0.3);
        }
        
        .subtitle {
            text-align: center;
            color: #8b2c5c;
            font-size: 1.2em;
            margin-bottom: 30px;
            font-style: italic;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #ff69b4, #d63384);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            min-width: 150px;
            margin: 10px;
            box-shadow: 0 8px 25px rgba(214, 51, 132, 0.4);
            transform: translateY(0);
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-card h3 {
            margin: 0 0 10px 0;
            font-size: 2em;
        }
        
        .stat-card p {
            margin: 0;
            font-size: 1.1em;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 30px 0;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(214, 51, 132, 0.2);
        }
        
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #ffb6c1;
        }
        
        th {
            background: linear-gradient(135deg, #ff69b4, #d63384);
            color: white;
            font-weight: bold;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }
        
        tr:hover {
            background-color: #ffe4f1;
            transform: scale(1.01);
            transition: all 0.3s ease;
        }
        
        .status-updated {
            color: #d63384;
            font-weight: bold;
            background: linear-gradient(135deg, #d4edda, #c3e6cb);
            padding: 5px 10px;
            border-radius: 20px;
            display: inline-block;
        }
        
        .status-no-change {
            color: #6c757d;
            font-style: italic;
        }
        
        .change-badge {
            background: linear-gradient(135deg, #ff69b4, #d63384);
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
            transition: transform 0.2s ease;
        }
        
        .change-badge:hover {
            transform: scale(1.1);
        }
        
        .change-badge.zero {
            background: #ddd;
            color: #666;
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #8b2c5c;
            font-style: italic;
        }
        
        .notification-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            z-index: 1000;
        }
        
        .notification-popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: linear-gradient(135deg, #ff69b4, #d63384);
            color: white;
            padding: 30px;
            border-radius: 20px;
            text-align: center;
            display: none;
            z-index: 1001;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
            border: 3px solid #ff1493;
        }
        
        .close-btn {
            background: rgba(255, 255, 255, 0.2);
            border: 2px solid white;
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            margin-top: 15px;
            transition: all 0.3s ease;
        }
        
        .close-btn:hover {
            background: white;
            color: #d63384;
        }
        
        .json-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: none;
            z-index: 2000;
        }
        
        .json-popup {
            position: fixed;
            top: 5%;
            left: 5%;
            width: 90%;
            height: 90%;
            background: white;
            border-radius: 15px;
            display: none;
            z-index: 2001;
            overflow: hidden;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        }
        
        .json-popup-header {
            background: linear-gradient(135deg, #ff69b4, #d63384);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .json-popup-header h3 {
            margin: 0;
            font-size: 1.5em;
        }
        
        .close-json-btn {
            background: rgba(255, 255, 255, 0.2);
            border: 2px solid white;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        
        .close-json-btn:hover {
            background: white;
            color: #d63384;
        }
        
        .json-code {
            background: white;
            color: #333;
            padding: 20px;
            border-radius: 10px;
            font-family: 'Georgia', serif;
            font-size: 14px;
            line-height: 1.6;
            white-space: normal;
            word-wrap: break-word;
            max-height: 100%;
            overflow: auto;
            border: 1px solid #dee2e6;
        }
        
        .slideshow-container {
            position: relative;
            max-width: 100%;
            margin: 20px auto;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(214, 51, 132, 0.3);
        }
        
        .slide {
            display: none;
            width: 100%;
            height: 200px;
            background: linear-gradient(135deg, #ff69b4, #d63384);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5em;
            font-weight: bold;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        
        .slide.active {
            display: flex;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎭 Ticket Monitor Dashboard</h1>
        <p class="subtitle">Monitoring Broadway & West End Shows in Real-Time</p>
        
        <!-- Slideshow -->
        <div class="slideshow-container">
            <div class="slide active">🎟️ Stay Updated with Live Ticket Monitoring</div>
            <div class="slide">🎭 Never Miss Out on Your Favorite Shows</div>
            <div class="slide">⚡ Real-Time Notifications for Changes</div>
            <div class="slide">🎵 Wicked • Les Mis • Book of Mormon & More!</div>
        </div>
        
        <!-- Stats Cards -->
        <div class="stats">
            <div class="stat-card">
                <h3 id="totalSites">-</h3>
                <p>Sites Monitored</p>
            </div>
            <div class="stat-card">
                <h3 id="activeSites">-</h3>
                <p>Active Changes</p>
            </div>
            <div class="stat-card">
                <h3 id="lastChecked">-</h3>
                <p>Last Updated</p>
            </div>
        </div>
        
        <!-- Changes Table -->
        <table id="changesTable">
            <tr>
                <th>Show/Website</th>
                <th>Cambios</th>
                <th>URL</th>
                <th>Status</th>
                <th>Last Update</th>
            </tr>
        </table>
        
        <div class="footer">
            <p>🎵 Powered by Broadway Magic ✨ | Last check: <span id="footerTime">Loading...</span></p>
        </div>
    </div>
    
    <!-- Notification Overlay -->
    <div id="notificationOverlay" class="notification-overlay" onclick="closeNotification()"></div>
    <div id="notificationPopup" class="notification-popup">
        <h2>🚨 NEW CHANGES DETECTED!</h2>
        <p>Some monitored sites have been updated!</p>
        <p>Check the table above for details.</p>
        <button class="close-btn" onclick="closeNotification()">Awesome! 🎉</button>
    </div>
    
    <!-- JSON Details Overlay -->
    <div id="jsonOverlay" class="json-overlay" onclick="closeJsonPopup()"></div>
    <div id="jsonPopup" class="json-popup">
        <div class="json-popup-header">
            <h3>📊 Detalles del Cambio</h3>
            <button class="close-json-btn" onclick="closeJsonPopup()">✕ Cerrar</button>
        </div>
        <div id="jsonContent" class="json-code"></div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        
        // Slideshow functionality
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        
        function showSlide(n) {
            slides[currentSlide].classList.remove('active');
            currentSlide = (n + slides.length) % slides.length;
            slides[currentSlide].classList.add('active');
        }
        
        function nextSlide() {
            showSlide(currentSlide + 1);
        }
        
        setInterval(nextSlide, 3000);
        
        function playNotificationSound() {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            oscillator.frequency.setValueAtTime(1000, audioContext.currentTime + 0.1);
            oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.2);
            
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
        }
        
        function showNotification() {
            document.getElementById('notificationOverlay').style.display = 'block';
            document.getElementById('notificationPopup').style.display = 'block';
            playNotificationSound();
        }
        
        function closeNotification() {
            document.getElementById('notificationOverlay').style.display = 'none';
            document.getElementById('notificationPopup').style.display = 'none';
        }
        
        function closeJsonPopup() {
            document.getElementById('jsonOverlay').style.display = 'none';
            document.getElementById('jsonPopup').style.display = 'none';
        }
        
        async function showChangeDetails(label) {
            try {
                const response = await fetch('/api/ticket-changes');
                const data = await response.json();
                
                const item = data.find(d => d.label === label);
                if (!item) {
                    alert('No se encontraron datos de cambios para ' + label);
                    return;
                }
                
                const friendlyContent = `
                    <div style="font-family: Georgia, serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #d63384; border-bottom: 2px solid #ff69b4; padding-bottom: 10px;">
                            📋 Cambios en: ${item.label}
                        </h2>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 15px 0;">
                            <h3 style="color: #d63384; margin-top: 0;">🌐 Página</h3>
                            <p><strong>Sitio:</strong> ${item.label}</p>
                            <p><strong>Enlace:</strong> <a href="${item.url}" target="_blank" style="color: #d63384;">${item.url}</a></p>
                            <p><strong>Última revisión:</strong> ${item.fecha_legible}</p>
                        </div>

                        <div style="background: #fff3cd; padding: 20px; border-radius: 10px; margin: 15px 0;">
                            <h3 style="color: #856404; margin-top: 0;">📝 ¿Qué ha cambiado?</h3>
                            <p style="font-size: 16px; line-height: 1.8;">
                                ${item.status.includes('Actualizado') ? 
                                    '✅ <strong>¡La página se ha actualizado!</strong><br>Esto significa que hay nuevas noticias, entradas disponibles, cambios de precios, nuevas fechas, o información actualizada.' : 
                                    '😊 <strong>No hay cambios</strong><br>La página sigue igual que la última vez que la revisamos.'
                                }
                            </p>
                        </div>

                        ${item.change_count > 0 ? `
                        <div style="background: #d1ecf1; padding: 20px; border-radius: 10px; margin: 15px 0;">
                            <h3 style="color: #0c5460; margin-top: 0;">🔢 Historial</h3>
                            <p>Esta página ha cambiado <strong>${item.change_count} ${item.change_count === 1 ? 'vez' : 'veces'}</strong> desde que la monitoreamos.</p>
                        </div>
                        ` : ''}

                        <div style="background: #e2e3e5; padding: 20px; border-radius: 10px; margin: 15px 0;">
                            <h3 style="color: #383d41; margin-top: 0;">💡 ¿Qué hacer ahora?</h3>
                            ${item.status.includes('Actualizado') ? 
                                '<p>🎯 <strong>¡Visita la página ahora!</strong></p><p>Puede haber:</p><ul><li>🎟️ Nuevas entradas disponibles</li><li>💰 Cambios en los precios</li><li>📅 Nuevas fechas de funciones</li><li>👥 Cambios en el elenco</li><li>📢 Noticias importantes</li></ul>' :
                                '<p>😌 <strong>Todo tranquilo por ahora</strong></p><p>Te avisaremos en cuanto haya novedades.</p>'
                            }
                        </div>

                        <div style="text-align: center; margin-top: 25px;">
                            <a href="${item.url}" target="_blank" 
                               style="background: linear-gradient(135deg, #ff69b4, #d63384); color: white; padding: 15px 30px; border-radius: 25px; text-decoration: none; font-weight: bold; box-shadow: 0 4px 15px rgba(214, 51, 132, 0.3); font-size: 16px;">
                                🔗 Ver ${item.label}
                            </a>
                        </div>
                    </div>
                `;
                
                document.getElementById('jsonOverlay').style.display = 'block';
                document.getElementById('jsonPopup').style.display = 'block';
                document.getElementById('jsonContent').innerHTML = friendlyContent;
                
            } catch (error) {
                alert('Error cargando los detalles: ' + error.message);
            }
        }
        
        async function updateTicketData() {
            try {
                const response = await fetch('/api/ticket-changes');
                const data = await response.json();
                
                document.getElementById('totalSites').textContent = data.length;
                document.getElementById('activeSites').textContent = 
                    data.filter(item => item.status.includes('Actualizado')).length;
                document.getElementById('lastChecked').textContent = 
                    'Last Checked: ' + new Date().toLocaleString();
                document.getElementById('footerTime').textContent = 
                    new Date().toLocaleString();

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
                    
                    const changesBadge = changeCount > 0 
                        ? `<span class="${badgeClass}" onclick="showChangeDetails('${item.label}')" style="cursor: pointer;" title="Click to see changes">${changeCount}</span>`
                        : `<span class="${badgeClass}">${changeCount}</span>`;

                    row.innerHTML = `
                        <td>${item.label}</td>
                        <td>${changesBadge}</td>
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
        
        // Update every 30 seconds
        setInterval(updateTicketData, 30000);
        
        // Initial load
        updateTicketData();
        
        // Socket.IO listeners
        socket.on('update', function(data) {
            console.log('Received update:', data);
            updateTicketData();
        });
    </script>
</body>
</html>
"""



# HTML_TEMPLATE omitted for brevity, keep your original HTML_TEMPLATE here



@app.route('/changes')
def changes_dummy():
  return "Not implemented", 200

@app.route('/api/suggest-site', methods=['POST'])
def suggest_site():
  try:
    data = request.get_json()
    site_name = data.get('siteName', '').strip()
    site_url = data.get('siteUrl', '').strip()
    reason = data.get('reason', '').strip()
    if not site_name or not site_url:
      return jsonify({"error": "Nombre y URL son obligatorios"}), 400
    if not site_url.startswith(('http://', 'https://')):
      return jsonify({"error": "URL debe empezar con http:// o https://"}), 400
    suggestion = {
      "siteName": site_name,
      "siteUrl": site_url,
      "reason": reason,
      "timestamp": datetime.now(UTC).isoformat(),
      "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
    }
    try:
      with open('suggestions.json', 'r') as f:
        suggestions = json.load(f)
    except FileNotFoundError:
      suggestions = []
    suggestions.append(suggestion)
    with open('suggestions.json', 'w') as f:
      json.dump(suggestions, f, indent=2, ensure_ascii=False)
    admin_message = f"""
🆕 <b>Nueva Sugerencia de Sitio Web</b>

📝 <b>Nombre:</b> {site_name}
🔗 <b>URL:</b> {site_url}
💭 <b>Razón:</b> {reason or 'No especificada'}
📅 <b>Fecha:</b> {suggestion['fecha_legible']}

<a href="{site_url}">Ver sitio sugerido</a>
    """.strip()
    send_telegram_message(admin_message)
    return jsonify({"success": True, "message": "Sugerencia enviada correctamente"})
  except Exception as e:
    print(f"Error in suggest_site: {e}")
    return jsonify({"error": "Error interno del servidor"}), 500

@app.route('/admin/suggestions')
def view_suggestions():
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
    html = """
    <html><head><title>Sugerencias de Sitios</title></head><body>
    <h1>Sugerencias Recibidas</h1>
    """
    for suggestion in reversed(suggestions):
      html += f"""
      <div style="border: 1px solid #ccc; margin: 10px; padding: 15px; border-radius: 5px;">
        <h3>{suggestion['siteName']}</h3>
        <p><strong>URL:</strong> <a href="{suggestion['siteUrl']}" target="_blank">{suggestion['siteUrl']}</a></p>
        <p><strong>Razón:</strong> {suggestion['reason'] or 'No especificada'}</p>
        <p><strong>Fecha:</strong> {suggestion['fecha_legible']}</p>
      </div>
      """
    html += "</body></html>"
    return html
  except FileNotFoundError:
    return "<h1>No hay sugerencias aún</h1>"

@app.route('/api/changes.json')
def get_changes_json():
    global latest_changes
    updated_sites = [c for c in latest_changes if "Actualizado" in c.get("status", "")]
    
    # SIMPLE JSON - only what users care about
    simple_data = {
        "resumen": {
            "total_sitios": len(latest_changes),
            "con_cambios": len(updated_sites),
            "ultima_revision": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S")
        },
        "sitios_con_cambios": []
    }
    
    for site in updated_sites:
        simple_data["sitios_con_cambios"].append({
            "nombre": site["label"],
            "enlace": site["url"],
            "que_paso": "La página se actualizó - puede haber nuevas entradas, precios, fechas o información",
            "cuando": site["fecha_legible"],
            "veces_cambiado": site["change_count"]
        })
    
    response = app.response_class(
        response=json.dumps(simple_data, indent=2, ensure_ascii=False),
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
