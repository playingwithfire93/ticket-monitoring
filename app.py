
import hashlib
import json
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup
from bs4.element import Comment
from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)

# Track previous states for change detection
previous_states = {}
previous_contents = {}

# Track change counts for each website
change_counts = {}

# Track if there are new changes for notification
new_changes_detected = True

# Real ticket monitoring URLs
URLS = [
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

        # Remove tags that usually include changing content
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
            tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove common dynamic elements by class/id
        dynamic_selectors = [
            ".date_info", ".timestamp", "#ad", ".ads", ".cookie-banner", "#cookies", ".tracker"
        ]
        for selector in dynamic_selectors:
            for tag in soup.select(selector):
                tag.decompose()

        # Normalize whitespace and strip
        content_text = soup.get_text(separator=" ", strip=True)
        normalized_text = " ".join(content_text.split())

        return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"

def extract_normalized_date_info(url):
    """Get normalized text content from .date_info element."""
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

import difflib


def find_differences(old_text, new_text):
    """Generate a diff showing changes between old and new content."""
    diff = difflib.unified_diff(
        old_text.splitlines(), 
        new_text.splitlines(), 
        fromfile='anterior', 
        tofile='actual', 
        lineterm=""
    )
    return "\n".join(diff)

def broadcast_change(url, data):
    socketio.emit('update', {'url': url, 'data': data})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Ticket Monitor Dashboard</title>
    <style>
        body {
            font-family: 'Georgia', serif;
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fecfef 100%);
            margin: 0;
            padding: 0;
            min-height: 100vh;
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
            max-width: 800px;
            margin: 20px auto;
            position: relative;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(214, 51, 132, 0.3);
            border: 3px solid #ff69b4;
        }
        .slide {
            display: none;
            width: 100%;
        }
        .slide img {
            width: 100%;
            height: 400px;
            object-fit: cover;
            display: block;
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
            background: linear-gradient(135deg, #ff6b6b, #ff8e53);
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
    /* Custom cursor */
    body {
        cursor: url('data:image/x-icon;base64,AAACAAEAICAQAAAAAADoAgAAFgAAACgAAAAgAAAAQAAAAAEABAAAAAAAAAIAAAAAAAAAAAAAEAAAAAAAAAAAAAAAq0wyALKw9wCFgugA////AHi6dQAGjwEABQUFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGZmZmZmZmAAAAAAAAAAAGZVVVVVVVVWYAAAAAAAAAZVVVVVVVVVVVYAAAAAAABlVVVVVVVVVVVVYAAAAAAAZVVVVVVVVVVVVWAAAAAAAGVVVVVVVVVVVVVgAAAAAAZVVVVVVVVVVVVVVgAAAAAGVVVVVVU1VVVVVVYAAAAABlVVVVVTI1VVVVVWAAAAAAZVVVVVMiI1VVVVVgAAAAAGVVVVVTIiNVVVVVYAAAAABlVVVVUyIjVVVVVWAAAAAAZVVVVVMiI1VVVVVgAAAAAGVVVVVTMzNVVVVVYAAAAAAGVXdVVVVVVVd1VgAAAAAABlcXdVVVVVVxd1YAAAAAAAZXdHVVVVVVd0dWAAAAAAAAZXdVZmZmZVd1YAAAAAAAAGVVVgAAAAZVVWAAAAAGAAAGZmAAAAAAZmYAAAAABmAAAAAAAAAAAAAAAAAAAAZmAAAAAAAAAAAAAAAAAAAGZmAAAAAAAAAAAAAAAAAAD/////////////////////////////////////////////////AAf//AAB//gAAP/wAAB/8AAAf/AAAH/gAAA/4AAAP+AAAD/gAAA/4AAAP+AAAD/gAAA/4AAAP/AAAH/wAAB/8AAAf/gAAP/4H8D/fD/h/z////8f////D////w=='), auto;
    }
        }
    </style>
</head>
<body>

<h1>✨ Panel de Monitoreo de Entradas ✨</h1>

<div class="sparkle" style="top: 10%; left: 10%;">💖</div>
<div class="sparkle" style="top: 20%; right: 15%;">✨</div>
<div class="sparkle" style="top: 70%; left: 5%;">🌸</div>
<div class="sparkle" style="bottom: 10%; right: 10%;">💕</div>

<div class="notification-overlay" id="notificationOverlay"></div>
<div class="notification-popup" id="notificationPopup">
    <h2>✨ ¡Nuevos cambios detectados! ✨</h2>
    <p>💖 ¡Hay actualizaciones frescas de entradas! 💖</p>
    <div>
        <button class="popup-button" onclick="viewJsonFromPopup()">📄 Ver datos JSON</button>
        <button class="popup-button" onclick="closeNotification()">Cerrar</button>
    </div>
</div>

<div class="json-overlay" id="jsonOverlay" onclick="closeJsonPopup()"></div>
<div class="json-popup" id="jsonPopup">
    <div class="json-popup-header">
        <h3>📄 Datos de cambios (JSON)</h3>
        <button class="close-json-btn" onclick="closeJsonPopup()">✕ Cerrar</button>
    </div>
    <div class="json-popup-content">
        <div class="json-code" id="jsonContent">Cargando...</div>
    </div>
</div>

<div class="slideshow-container" id="slideshow"></div>

<div class="last-checked" id="lastChecked">Última revisión: Cargando...</div>

<table id="changesTable">
    <tr>
        <th>Obra/Sitio web</th>
        <th>Cambios</th>
        <th>URL</th>
        <th>Estado</th>
        <th>Última actualización</th>
    </tr>
    <tr>
        <td colspan="5" style="text-align: center;">Cargando datos de entradas...</td>
    </tr>
</table>

<script>
    let slideIndex = 0;
    showSlides();

    function showSlides() {
        let slides = document.getElementsByClassName("slide");
        for (let i = 0; i < slides.length; i++) {
            slides[i].style.display = "none";
        }
        slideIndex++;
        if (slideIndex > slides.length) { slideIndex = 1; }
        slides[slideIndex-1].style.display = "block";
        setTimeout(showSlides, 3000);
    }

    function showNotification() {
        document.getElementById('notificationOverlay').style.display = 'block';
        document.getElementById('notificationPopup').style.display = 'block';
        
        // Play notification sound
        playNotificationSound();
    }
    
    function playNotificationSound() {
        // Create audio context for a pleasant notification sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        // Create a pleasant notification melody
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
        
        // Play a pleasant notification melody (C-E-G chord progression)
        const now = audioContext.currentTime;
        playTone(523.25, now, 0.2);        // C5
        playTone(659.25, now + 0.1, 0.2);  // E5
        playTone(783.99, now + 0.2, 0.3);  // G5
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
        document.getElementById('jsonContent').textContent = 'Cargando datos JSON...';
        
        try {
            const response = await fetch('/api/changes.json');
            const jsonData = await response.text();
            document.getElementById('jsonContent').textContent = jsonData;
        } catch (error) {
            document.getElementById('jsonContent').textContent = 'Error cargando datos JSON: ' + error.message;
        }
    }
    
    function closeJsonPopup() {
        document.getElementById('jsonOverlay').style.display = 'none';
        document.getElementById('jsonPopup').style.display = 'none';
    }
    const images = {{ images|tojson }};
    const slideshow = document.getElementById('slideshow');
    images.forEach(src => {
        const div = document.createElement('div');
        div.className = 'slide';
        const img = document.createElement('img');
        img.src = src;
        img.alt = '';
        div.appendChild(img);
        slideshow.appendChild(div);
    });

    let slideIndex = 0;
    showSlides();

    function showSlides() {
        let slides = document.getElementsByClassName("slide");
        for (let i = 0; i < slides.length; i++) {
            slides[i].style.display = "none";
        }
        slideIndex++;
        if (slideIndex > slides.length) { slideIndex = 1; }
        slides[slideIndex-1].style.display = "block";
        setTimeout(showSlides, 3000);
    }
    async function updateTicketData() {
        try {
            const response = await fetch('/api/ticket-changes');
            const data = await response.json();
            
            document.getElementById('lastChecked').textContent = 
                'Última revisión: ' + new Date().toLocaleString();
            
            const table = document.getElementById('changesTable');
            table.innerHTML = `
                <tr>
                    <th>Obra/Sitio web</th>
                    <th>Cambios</th>
                    <th>URL</th>
                    <th>Estado</th>
                    <th>Última actualización</th>
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
            console.error('Error al obtener los datos de entradas:', error);
            document.getElementById('lastChecked').textContent = 'Error cargando datos';
        }
    }


    // Carga inicial y actualizaciones periódicas
    updateTicketData();
    setInterval(updateTicketData, 5000); // Revisar cada 5 segundos
</script>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/changes.json')
def get_changes_json():
    """Get detailed changes data as JSON"""
    global previous_states
    changes_list = []
    now = datetime.now(UTC).isoformat()

    for item in URLS:
        label = item["label"]
        url = item["url"]

        # Get current full content
        current_content = ""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Remove scripts, styles, etc. but keep the full text
            for tag in soup(["script", "style", "noscript", "meta", "iframe", "link", "svg"]):
                tag.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            current_content = soup.get_text(separator=" ", strip=True)
        except Exception as e:
            current_content = f"Error al obtener contenido: {str(e)}"

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
        elif last_state != state:
            status = "¡Actualizado! 🎉"
            change_details = "Se detectaron cambios en el contenido del sitio web"
            if last_content and current_content != last_content:
                differences = find_differences(last_content, current_content)
            else:
                differences = "Contenido modificado pero no se pudieron detectar diferencias específicas"
        else:
            status = "Sin cambios ✨"
            change_details = "El contenido permanece igual desde la última verificación"
            differences = "Sin diferencias detectadas"

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
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        })

    # Filter only updated websites
    updated_sites = [c for c in changes_list if "Actualizado" in c["status"]]
    
    # Create response with proper formatting
    response_data = {
        "resumen": {
            "total_sitios_monitoreados": len(changes_list),
            "sitios_actualizados": len(updated_sites),
            "ultimo_chequeo": now,
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        },
        "sitios_web_actualizados": updated_sites
    }
    
    # Return pretty-printed JSON
    response = app.response_class(
        response=json.dumps(response_data, indent=2, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )
    return response
import threading
import time

latest_changes = []

def scrape_all_sites():
    global previous_states, previous_contents, change_counts
    changes_list = []
    now = datetime.now(UTC).isoformat()
    for item in URLS:
        label = item["label"]
        url = item["url"]

        # Obtener el contenido actual completo
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

        # Obtener el hash del estado actual
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
        else:
            status = "Sin cambios ✨"
            change_details = "El contenido permanece igual desde la última verificación"
            differences = "Sin diferencias detectadas"
            if url not in change_counts:
                change_counts[url] = 0

        # Actualizar los estados y contenidos después de comparar
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
    return changes_list

def background_checker():
    global latest_changes
    while True:
        latest_changes = scrape_all_sites()
        time.sleep(300)  # cada 5 minutos

threading.Thread(target=background_checker, daemon=True).start()

@app.route('/api/ticket-changes')
def get_ticket_changes():
    return jsonify(latest_changes)
  
@app.route('/api/check-changes')
def check_changes():
    """Check if there are any new changes"""
    try:
        response = requests.get('http://localhost:5000/api/ticket-changes', timeout=5)
        data = response.json()
        has_new_changes = any(item['status'].includes('Actualizado') for item in data)
        return {"new_changes": has_new_changes}
    except:
        return {"new_changes": False}

import os
import random

def get_static_images():
    static_folder = os.path.join(app.root_path, 'static')
    # Only include common image extensions
    exts = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.gif', '.avif')
    files = [f for f in os.listdir(static_folder) if f.lower().endswith(exts)]
    # Shuffle the list for random order
    random.shuffle(files)
    # Return as URLs for the static folder
    return [f"/static/{f}" for f in files]

@app.route('/')
def dashboard():
    images = get_static_images()
    return render_template_string(HTML_TEMPLATE, images=images)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
