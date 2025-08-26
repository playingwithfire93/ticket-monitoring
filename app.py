import eventlet
eventlet.monkey_patch()

import hashlib
import json
from datetime import UTC, datetime
import requests
from bs4 import BeautifulSoup
from bs4.element import Comment
from flask import Flask, jsonify, render_template, render_template_string
from flask_socketio import SocketIO
import time
import os
from twilio.rest import Client
from dotenv import load_dotenv
import difflib
import traceback
from collections import defaultdict

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

def send_telegram_message(text, chat_id=None):
    """Send message to Telegram. If chat_id is provided, send to that specific chat."""
    print(f"DEBUG: send_telegram_message called with text: {text[:50]}...")
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")  # Main bot token
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")  # Default chat_id en .env
    
    print(f"DEBUG: Token: {token[:10]}...{token[-5:] if token else 'None'}")
    print(f"DEBUG: Chat ID: {chat_id}")
    
    if not token or not chat_id:
        print("ERROR: Telegram token or chat_id not set")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    print(f"DEBUG: Sending to URL: {url}")
    print(f"DEBUG: Payload: {payload}")
    
    try:
        r = requests.post(url, data=payload, timeout=5)
        print(f"Telegram response: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Telegram notification failed: {e}")

def send_to_admin_group(text):
    """Send message specifically to the admin Telegram bot"""
    print(f"DEBUG: send_to_admin_group called with text: {text[:50]}...")
    
    admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
    admin_chat_id = os.environ.get("ADMIN_TELEGRAM_CHAT_ID")
    
    print(f"DEBUG: Admin Token: {admin_token[:10]}...{admin_token[-5:] if admin_token else 'None'}")
    print(f"DEBUG: Admin Chat ID: {admin_chat_id}")
    
    if not admin_token or not admin_chat_id:
        print("ERROR: Admin Telegram bot token or chat ID not configured - skipping admin notification")
        return
    
    url = f"https://api.telegram.org/bot{admin_token}/sendMessage"
    payload = {"chat_id": admin_chat_id, "text": text, "parse_mode": "HTML"}
    
    print(f"DEBUG: Admin sending to URL: {url}")
    print(f"DEBUG: Admin payload: {payload}")
    
    try:
        r = requests.post(url, data=payload, timeout=5)
        print(f"Admin Telegram response: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Admin Telegram notification failed: {e}")

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
def get_simple_content(url):
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Only remove truly dynamic/irrelevant content
        for tag in soup(["script", "style", "noscript", "meta", "iframe", "link"]):
            tag.decompose()
            
        # Get clean text
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
        
        # Get current content using simplified method
        current_content = get_simple_content(url)
        
        # Get previous content
        last_content = previous_contents.get(url, "")
        
        # Determine status
        if not last_content:  # First check
            status = "Primer chequeo 👀"
            change_details = "Primera vez que se monitorea este sitio web"
            differences = "No hay contenido anterior para comparar"
            change_counts[url] = 0
        elif current_content != last_content and len(current_content) > 100:
            status = "¡Actualizado! 🎉"
            change_details = "Se detectaron cambios en el contenido del sitio web"
            change_counts[url] = change_counts.get(url, 0) + 1
            differences = find_differences(last_content, current_content)
            
            # Send notifications
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
        
        # Update previous content
        previous_contents[url] = current_content
        
        # Add to changes list
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

# Start background checker using SocketIO's method
socketio.start_background_task(background_checker)

def group_urls_by_musical(urls):
    groups = defaultdict(list)
    for item in urls:
        # Agrupa por la primera palabra del label (ejemplo: 'Wicked', 'Los Miserables', etc.)
        musical = item['label'].split()[0]
        groups[musical].append(item)
    return groups

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ticket Monitor Dashboard</title>
  <style>
    body {
      font-family: system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
      font-weight: 600;
      margin: 0;
      padding: 0;
      min-height: 100vh;
      overflow-x: hidden;
    }
    * {cursor: url(https://cur.cursors-4u.net/special/spe-3/spe302.ani), url(https://cur.cursors-4u.net/special/spe-3/spe302.png), auto !important;}
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
      font-weight: 900;
    }
    .slideshow-container {
      max-width: 1100px;
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
    .slide img {
      width: 100%;
      height: 520px;
      object-fit: contain;
      display: block;
      margin: 0 auto;
    }
    table {
      width: 98%;
      margin: 30px auto;
      border-collapse: collapse;
      table-layout: auto; /* Changed from 'fixed' to 'auto' to allow content-based sizing */
      background: linear-gradient(
        45deg,
        rgba(255, 182, 193, 0.9) 0%,   
        rgba(255, 240, 245, 0.95) 25%, 
        rgba(255, 228, 240, 0.95) 50%, 
        rgba(255, 192, 203, 0.9) 75%,  
        rgba(255, 218, 235, 0.95) 100% 
      );
      background-size: 400% 400%;
      animation: tableGradient 12s ease-in-out infinite alternate;
      border-radius: 25px;
      overflow: hidden;
      box-shadow: 
        0 15px 35px rgba(255, 105, 180, 0.4),
        0 5px 15px rgba(255, 182, 193, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.6);
      border: 4px solid transparent;
      background-clip: padding-box;
      position: relative;
    }
    table::before {
      content: '';
      position: absolute;
      top: -4px; left: -4px; right: -4px; bottom: -4px;
      background: linear-gradient(45deg,
        #ff69b4, #ff1493, #ff69b4, #ffc0cb,
        #ffb6e6, #ff69b4, #d63384, #ff69b4);
      background-size: 400% 400%;
      border-radius: 25px;
      z-index: -1;
      animation: sparklyBorder 8s linear infinite;
    }
    @keyframes sparklyBorder {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    @keyframes tableGradient {
      0% { background-position: 0% 50%; }
      100% { background-position: 100% 50%; }
    }
    th, td {
      padding: 15px;
      text-align: left;
      font-weight: 500;
    }
    th {
      background: linear-gradient(135deg,
        #ff69b4 0%,
        #ff1493 25%,
        #d63384 50%,
        #b83dba 75%,
        #8b2c5c 100%);
      color: #fff;
      font-weight: 900;
      text-shadow:
        2px 2px 4px rgba(0,0,0,0.3),
        0 0 10px rgba(255, 255, 255, 0.5);
      padding: 25px 20px;
      font-size: 1.15em;
      position: relative;
      text-align: center;
    }
    th::after {
      content: '✨';
      position: absolute;
      top: 5px;
      right: 10px;
      font-size: 0.8em;
      animation: sparkle 2s infinite;
      opacity: 0.8;
    }
    th:nth-child(1) {
      text-align: left;
      width: 180px;
      max-width: 180px;
    }
    th:nth-child(2) {
      text-align: center;
      width: 50px;
      max-width: none;
    }
    th:nth-child(3) {
      text-align: left;
      width: 350px;
      max-width: 350px;
    }
    th:nth-child(4) {
      text-align: center;
      width: 160px;
      max-width: 160px;
    }
    th:nth-child(5) {
      text-align: center;
      width: 140px;
      max-width: 140px;
    }
    th:nth-child(1)::before { content: "🎭 "; }
    th:nth-child(2)::before { content: "📊 "; }
    th:nth-child(3)::before { content: "🔗 "; }
    th:nth-child(4)::before { content: "📋 "; }
    th:nth-child(5)::before { content: "⏰ "; }
    td:nth-child(1) {
      text-align: left;
      font-weight: 800;
      color: #d63384;
      text-shadow: 1px 1px 2px rgba(255, 182, 193, 0.8);
      width: 180px;
      max-width: 180px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    td:nth-child(2) {
      text-align: center;
      width: auto; /* Let it size to content */
      min-width: 80px; /* Minimum width to match header */
      max-width: none; /* Remove max-width restriction */
      white-space: nowrap; /* Prevent wrapping */
    }
    
    td:nth-child(2) {
      text-align: center;
      width: auto;
      min-width: 80px;
      max-width: none;
      white-space: nowrap;
      vertical-align: middle; /* Add this for perfect vertical centering */
      display: table-cell; /* Ensure it behaves as table cell */
    }
    
    td:nth-child(4) {
      text-align: center;
      width: 160px;
      max-width: 160px;
      vertical-align: middle;
    }
    
    td:nth-child(5) {
      text-align: center;
      font-size: 0.9em;
      color: #b83dba;
      font-weight: 600;
      width: 140px;
      max-width: 140px;
    }
    tr:hover {
      background: linear-gradient(135deg, #ffe4f1, #fff0f5, #ffe4f1);
      transform: scale(1.01);
      transition: all 0.3s ease;
      box-shadow: 0 6px 20px rgba(214, 51, 132, 0.2);
    }
    td {
      padding: 20px 18px;
      color: #8b2c5c;
      font-weight: 600;
      font-size: 1em;
      vertical-align: middle;
      position: relative;
      background: rgba(255, 255, 255, 0.1);
      transition: all 0.3s ease;
    }
    tr:hover {
      background: linear-gradient(135deg,
        rgba(255, 182, 193, 0.3),
        rgba(255, 240, 245, 0.4),
        rgba(255, 218, 235, 0.3));
      transform: scale(1.02) translateY(-2px);
      transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      box-shadow:
        0 10px 30px rgba(255, 105, 180, 0.3),
        0 5px 15px rgba(255, 182, 193, 0.4);
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
      background: linear-gradient(135deg,
        #ff69b4 0%,
        #ff1493 50%,
        #d63384 100%);
      color: #fff;
      padding: 12px 20px;
      border-radius: 25px;
      font-weight: 800;
      box-shadow:
        0 6px 20px rgba(255, 105, 180, 0.5),
        inset 0 1px 0 rgba(255, 255, 255, 0.3);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-width: 130px;
      max-width: 130px;
      height: 45px;
      text-align: center;
      font-size: 0.95em;
      letter-spacing: 1px;
      text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
      position: relative;
      overflow: hidden;
    }
    .status-updated::before { content: "🎉"; }
    .status-updated::after {
      content: '';
      position: absolute;
      top: 0; left: -100%;
      width: 100%; height: 100%;
      background: linear-gradient(90deg,
        transparent,
        rgba(255, 255, 255, 0.4),
        transparent);
      animation: shimmer 2s infinite;
    }
    @keyframes shimmer {
      0% { left: -100%; }
      100% { left: 100%; }
    }
    .status-no-change {
      color: #8b2c5c;
      font-style: italic;
      padding: 12px 20px;
      background: linear-gradient(135deg,
        rgba(255, 240, 245, 0.8),
        rgba(255, 228, 240, 0.9));
      border-radius: 25px;
      border: 2px solid rgba(255, 182, 193, 0.6);
      min-width: 130px;
      max-width: 130px;
      height: 45px;
      text-align: center;
      font-weight: 800;
      font-size: 0.95em;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 3px 10px rgba(255, 182, 193, 0.3);
    }
    .last-checked {
      text-align: center;
      color: #d63384;
      font-weight: bold;
      margin: 30px 0;
      font-size: 1.2em;
      padding: 15px;
      background: linear-gradient(135deg, rgba(255, 105, 180, 0.1), rgba(255, 192, 203, 0.1));
      border-radius: 25px;
      border: 2px solid #ff69b4;
      max-width: 400px;
      margin: 30px auto;
    }
    .loading-row {
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: loading 1.5s infinite;
    }
    .change-badge {
      background: linear-gradient(135deg,
        #ff69b4 0%,     /* Hot pink */
        #ff1493 50%,    /* Deep pink */
        #d63384 100%);  /* Bootstrap pink */
      color: white;
      border-radius: 18px;
      padding: 8px 12px;
      font-size: 0.9em;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 40px;
      height: 36px;
      box-shadow:
        0 6px 20px rgba(255, 105, 180, 0.6),    /* Updated shadow color */
        inset 0 1px 0 rgba(255, 255, 255, 0.3);
      text-shadow: 1px 1px 2px rgba(0,0,0,0.4);
      transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      cursor: pointer;
      position: relative;
      overflow: hidden;
      white-space: nowrap;
    }
    
    .change-badge.zero {
      background: linear-gradient(135deg, #e9ecef, #dee2e6);
      color: #6c757d;
      cursor: default;
      min-width: 40px;
      height: 36px;
    }
    
    .change-badge:hover {
      transform: scale(1.1) rotate(2deg);
      box-shadow: 0 6px 20px rgba(255, 105, 180, 0.8);  /* Updated hover shadow */
    }
    
    .change-badge.zero:hover {
      transform: none;
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
      background: white;
      color: #333;
      padding: 20px;
      border-radius: 10px;
      font-family: system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
      font-size: 14px;
      line-height: 1.6;
      white-space: normal;
      word-wrap: break-word;
      max-height: 100%;
      overflow: auto;
      border: 1px solid #dee2e6;
    }
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
    @keyframes loading {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    .site-wicked::before { content: "🧙‍♀️ "; }
    .site-miserables::before { content: "⚖️ "; }
    .site-mormon::before { content: "📖🐸 "; }
    .site-audrey::before { content: "🔍 "; }
    .site-houdini::before { content: "🎩 "; }
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
    td a {
      color: #d63384;
      text-decoration: none;
      font-weight: 500;
      transition: all 0.3s ease;
      position: relative;
    }
    td a:hover {
      color: #8b2c5c;
      text-decoration: underline;
      text-decoration-color: #ff69b4;
      text-decoration-thickness: 2px;
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
<h1>✨ Ticket Monitor Dashboard ✨</h1>
<div class="animated-bg"></div>
<div class="floating-sparkle s1">✨</div>
<div class="floating-sparkle s2">💖</div>
<div class="floating-sparkle s3">🌸</div>
<div class="floating-sparkle s4">💕</div>
<div class="floating-sparkle s5">✨</div>
<div style="display: flex; justify-content: center; align-items: center; gap: 40px; margin: 40px auto 30px auto; max-width: 1200px;">
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
  <div style="flex: 0 0 340px; min-width: 300px; display: flex; align-items: center;">
    <iframe style="border-radius:12px; box-shadow:0 4px 16px #d6338440;" src="https://open.spotify.com/embed/playlist/7w9wB3KwgtClfngWeFLBQX?utm_source=generator&theme=0" width="340" height="452" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
  </div>
</div>
<div class="notification-overlay" id="notificationOverlay"></div>
<div class="notification-popup" id="notificationPopup">
  <h2>✨ New Changes Detected! ✨</h2>
  <p>💖 Fresh ticket updates are available! 💖</p>
  <div>
    <button class="popup-button" onclick="viewJsonFromPopup()">📄 Ver cambios 👀</button>
    <button class="popup-button" onclick="closeNotification()">Cerrar</button>
  </div>
</div>
<div class="json-overlay" id="jsonOverlay" onclick="closeJsonPopup()"></div>
<div class="json-popup" id="jsonPopup">
  <div class="json-popup-header">
    <h3>📊 Detalles del Cambio</h3>
    <button class="close-json-btn" onclick="closeJsonPopup()">✕ Cerrar</button>
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
<div style="max-width: 600px; margin: 40px auto; padding: 30px; background: rgba(255, 255, 255, 0.9); border-radius: 20px; box-shadow: 0 8px 25px rgba(214, 51, 132, 0.2); border: 2px solid #ff69b4;">
  <h2 style="color: #d63384; text-align: center; margin-bottom: 20px;">💡 ¿Tienes una sugerencia?</h2>
  <p style="text-align: center; color: #8b2c5c; margin-bottom: 25px;">¡Sugiere un nuevo sitio web para monitorear!</p>
  <form id="suggestionForm" style="display: flex; flex-direction: column; gap: 15px;">
    <input type="text" id="siteName" placeholder="Nombre del sitio (ej: Hamilton El Musical)"
           style="padding: 12px; border: 2px solid #ff69b4; border-radius: 10px; font-size: 16px;">
    <input type="url" id="siteUrl" placeholder="URL del sitio (ej: https://hamilton.com)"
           style="padding: 12px; border: 2px solid #ff69b4; border-radius: 10px; font-size: 16px;">
    <textarea id="reason" placeholder="¿Por qué deberíamos monitorear este sitio? (opcional)"
              style="padding: 12px; border: 2px solid #ff69b4; border-radius: 10px; font-size: 16px; min-height: 80px; resize: vertical;"></textarea>
    <button type="submit" style="background: linear-gradient(135deg, #ff69b4, #d63384); color: white; padding: 15px; border: none; border-radius: 15px; font-weight: bold; font-size: 16px; cursor: pointer; transition: transform 0.2s;">
      📤 Enviar Sugerencia
    </button>
  </form>
  <div id="suggestionResult" style="margin-top: 15px; text-align: center; font-weight: bold;"></div>
</div>
<script>
document.getElementById('suggestionForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  const siteName = document.getElementById('siteName').value;
  const siteUrl = document.getElementById('siteUrl').value;
  const reason = document.getElementById('reason').value;
  if (!siteName || !siteUrl) {
    document.getElementById('suggestionResult').innerHTML = '<span style="color: #d63384;">Por favor completa todos los campos obligatorios</span>';
    return;
  }
  try {
    const response = await fetch('/api/suggest-site', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ siteName, siteUrl, reason })
    });
    const result = await response.json();
    if (response.ok) {
      // Mostrar mensaje de éxito con animación
      document.getElementById('suggestionResult').innerHTML = `
        <div style="
          background: linear-gradient(45deg, #28a745, #20c997);
          color: white;
          padding: 15px;
          border-radius: 10px;
          box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
          animation: successPulse 2s ease-in-out;
          border: 2px solid #28a745;
        ">
          🎉 ¡Sugerencia enviada exitosamente!<br>
          📧 Te notificaremos cuando sea revisada<br>
          ⏰ Tiempo estimado: 24-48 horas
        </div>
        <style>
          @keyframes successPulse {
            0% { transform: scale(0.9); opacity: 0; }
            50% { transform: scale(1.05); opacity: 1; }
            100% { transform: scale(1); opacity: 1; }
          }
        </style>
      `;
      document.getElementById('suggestionForm').reset();
      
      // Limpiar el mensaje después de 5 segundos
      setTimeout(() => {
        document.getElementById('suggestionResult').innerHTML = '';
      }, 5000);
    } else {
      document.getElementById('suggestionResult').innerHTML = '<span style="color: #d63384;">❌ Error: ' + result.error + '</span>';
    }
  } catch (error) {
    document.getElementById('suggestionResult').innerHTML = '<span style="color: #d63384;">❌ Error al enviar la sugerencia</span>';
  }
});
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
    playTone(523.25, now, 0.2);
    playTone(659.25, now + 0.1, 0.2);
    playTone(783.99, now + 0.2, 0.3);
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
      <div style="font-family: system-ui, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333;">
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
      let siteClass = '';
      const labelLower = item.label.toLowerCase();
      if (labelLower.includes('wicked')) siteClass = 'site-wicked';
      else if (labelLower.includes('miserables')) siteClass = 'site-miserables';
      else if (labelLower.includes('mormon') || labelLower.includes('book')) siteClass = 'site-mormon';
      else if (labelLower.includes('audrey')) siteClass = 'site-audrey';
      else if (labelLower.includes('houdini')) siteClass = 'site-houdini';
      const changesBadge = changeCount > 0
        ? `<span class="${badgeClass}" onclick="showChangeDetails('${item.label}')" style="cursor: pointer;" title="Click to see changes">${changeCount}</span>`
        : `<span class="${badgeClass}">${changeCount}</span>`;
      row.innerHTML = `
        <td><span class="${siteClass}">${item.label}</span></td>
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
updateTicketData();
setInterval(updateTicketData, 5000);

@app.route('/')
def dashboard():
    grouped_urls = group_urls_by_musical(URLS)
    return render_template_string(HTML_TEMPLATE, grouped_urls=grouped_urls)

@app.route('/changes')
def changes_dummy():
    return "Not implemented", 200

import json
from datetime import datetime

# Add this new route
@app.route('/api/suggest-site', methods=['POST'])
def suggest_site():
    from flask import request
    try:
        print("DEBUG: suggest_site called")
        
        # Get JSON data
        data = request.get_json()
        if not data:
            print("ERROR: No JSON data received")
            return jsonify({"error": "No se recibieron datos"}), 400
        
        print(f"DEBUG: Received data: {data}")
        
        site_name = data.get('siteName', '').strip()
        site_url = data.get('siteUrl', '').strip()
        reason = data.get('reason', '').strip()
        
        print(f"DEBUG: Parsed - Name: {site_name}, URL: {site_url}, Reason: {reason}")
        
        if not site_name or not site_url:
            return jsonify({"error": "Nombre y URL son obligatorios"}), 400
        
        # Validate URL format
        if not site_url.startswith(('http://', 'https://')):
            return jsonify({"error": "URL debe empezar con http:// o https://"}), 400
        
        suggestion = {
            "siteName": site_name,
            "siteUrl": site_url,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
            "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        }
        
        print(f"DEBUG: Created suggestion: {suggestion}")
        
        # Save to file
        try:
            with open('suggestions.json', 'r') as f:
                suggestions = json.load(f)
        except FileNotFoundError:
            suggestions = []
        
        suggestions.append(suggestion)
        
        with open('suggestions.json', 'w') as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        
        print("DEBUG: Suggestion saved to file")
        
        # Send enhanced notification to admin bot
        try:
            admin_message = f"""
🚨 <b>¡NUEVA SUGERENCIA RECIBIDA!</b> 🚨

🆔 <b>Sugerencia #{ len(suggestions)}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 <b>Sitio:</b> {site_name}
🌐 <b>URL:</b> <a href="{site_url}">{site_url}</a>
💭 <b>Razón:</b> {reason or 'No especificada'}
⏰ <b>Recibida:</b> {suggestion['fecha_legible']}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 <b>ACCIONES DISPONIBLES:</b>

🌐 <a href="{site_url}">Ver sitio web sugerido</a>
📋 <a href="http://localhost:5000/admin/approval-panel">Panel de Aprobación</a>

⚡ <i>¡Revisar y aprobar lo antes posible!</i>
            """.strip()
            
            print("DEBUG: Sending enhanced notification to admin bot...")
            send_to_admin_group(admin_message)
            print("DEBUG: Enhanced admin notification sent")
            
        except Exception as notification_error:
            print(f"WARNING: Could not send admin notification: {notification_error}")
            # Don't fail the whole request if notification fails
        
        return jsonify({"success": True, "message": "Sugerencia enviada correctamente"})
        
    except Exception as e:
        print(f"ERROR in suggest_site: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error interno: {str(e)}"}), 500
      
@app.route('/admin/monitoring-list')
def monitoring_list():
    """Mostrar la lista actual de URLs que están siendo monitoreadas"""
    try:
        # Get current URLS from memory
        current_urls = URLS.copy();
        
        // Also load from urls.json
        try {
            with open('urls.json', 'r') as f:
                urls_data = json.load(f);
        } catch (FileNotFoundError) {
            urls_data = [];
        }
        
        html = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Lista de Monitoreo</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    background: linear-gradient(120deg, #ffb6e6 0%, #fecfef 50%, #ffb6e6 100%);
                    margin: 0;
                    padding: 20px;
                    min-height: 100vh;
                }
                .container {
                    max-width: 1000px;
                    margin: 0 auto;
                    background: rgba(255, 255, 255, 0.95);
                    border-radius: 20px;
                    padding: 30px;
                    box-shadow: 0 10px 30px rgba(214, 51, 132, 0.3);
                }
                h1 {
                    color: #d63384;
                    text-align: center;
                    margin-bottom: 30px;
                    font-size: 2.5em;
                    text-shadow: 2px 2px 4px rgba(214, 51, 132, 0.3);
                }
                .stats {
                    background: linear-gradient(135deg, #ff69b4, #d63384);
                    color: white;
                    padding: 20px;
                    border-radius: 15px;
                    text-align: center;
                    margin-bottom: 30px;
                }
                .section {
                    margin: 30px 0;
                    background: white;
                    border: 2px solid #ff69b4;
                    border-radius: 15px;
                    padding: 20px;
                    box-shadow: 0 5px 15px rgba(255, 105, 180, 0.2);
                }
                .section h2 {
                    color: #d63384;
                    border-bottom: 2px solid #ffe0f7;
                    padding-bottom: 10px;
                }
                .url-item {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 10px 0;
                }
                .url-link {
                    color: #ff69b4;
                    text-decoration: none;
                    font-weight: bold;
                }
                .url-link:hover { text-decoration: underline; }
                .musical-group {
                    border-left: 4px solid #ff69b4;
                    padding-left: 15px;
                    margin: 15px 0;
                }
                .navigation {
                    text-align: center;
                    margin-top: 40px;
                    padding-top: 30px;
                    border-top: 2px solid #ffe0f7;
                }
                .nav-buttons {
                    display: flex;
                    gap: 15px;
                    justify-content: center;
                    flex-wrap: wrap;
                }
                .nav-btn {
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 25px;
                    font-weight: bold;
                    color: white;
                    transition: transform 0.2s;
                }
                .nav-btn:hover { transform: translateY(-2px); }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔄 Lista de Monitoreo Activa</h1>
                
                <div class="stats">
                    <strong>📊 Total de URLs monitoreadas: ${current_urls.length}</strong><br>
                    <strong>🎭 Musicales en urls.json: ${urls_data.length}</strong>
                </div>
                
                <div class="section">
                    <h2>📋 URLs Activas en Memoria (URLS array)</h2>
        `;
        
        if (!current_urls.length) {
            html += "<p>No hay URLs configuradas en el array URLS.</p>";
        } else {
            current_urls.forEach((url_item, i) => {
                html += `
                <div class="url-item">
                    <strong>#{i+1}: ${url_item.get('label', 'Sin nombre')}</strong><br>
                    <a href="${url_item.get('url', '#')}" target="_blank" class="url-link">${url_item.get('url', 'Sin URL')}</a>
                </div>
                `;
            });
        }
        
        html += `
                </div>
                
                <div class="section">
                    <h2>📁 URLs en archivo urls.json</h2>
        `;
        
        if (!urls_data.length) {
            html += "<p>No hay datos en urls.json.</p>";
        } else {
            urls_data.forEach(musical => {
                const musical_name = musical.get('musical', 'Sin nombre');
                const urls = musical.get('urls', []);
                
                html += `
                <div class="musical-group">
                    <h3 style="color: #ff69b4;">${musical_name} (${urls.length} URLs)</h3>
                `;
                
                urls.forEach(url => {
                    html += `
                    <div class="url-item">
                        <a href="${url}" target="_blank" class="url-link">${url}</a>
                    </div>
                    `;
                });
                
                html += "</div>";
            });
        }
        
        html += `
                </div>
                
                <div class="navigation">
                    <div class="nav-buttons">
                        <a href="/" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);" class="nav-btn">🏠 Página Principal</a>
                        <a href="/admin/approval-panel" style="background: #ff69b4; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(255, 105, 180, 0.3);" class="nav-btn">📋 Panel de Aprobación</a>
                        <a href="/admin/suggestions" style="background: #6f42c1; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(111, 66, 193, 0.3);" class="nav-btn">📊 Ver Historial</a>
                        <a href="/admin/monitoring-list" style="background: #20c997; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(32, 201, 151, 0.3);" class="nav-btn">🔄 Ver Monitoreo</a>
                    </div>
                    <p style="color: #666; font-size: 0.9em; margin-top: 15px;">
                        ⚡ Esta página muestra las URLs que están siendo monitoreadas actualmente
                    </p>
                </div>
            </div>
        </body>
        </html>
        `;
        
        return html;
        
    } catch (Exception e) {
        return `
        <html><body style="font-family: system-ui; text-align: center; padding: 50px; background: #ffe6e6;">
            <h1 style="color: #dc3545;">❌ Error</h1>
            <p>Error al cargar la lista de monitoreo: ${e.message}</p>
            <a href="/" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">🏠 Página Principal</a>
        </body></html>
        `, 500;
}

@app.route('/debug/suggestions')
def debug_suggestions():
    """Debug endpoint to check suggestions file"""
    try:
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
        
        html = """
        <html><head><title>Debug Suggestions</title></head>
        <body style="font-family: monospace; padding: 20px; background: #f0f0f0;">
        <h1>🐛 Debug: Suggestions File</h1>
        """
        
        for i, suggestion in enumerate(suggestions):
            status = suggestion.get('status', 'Pendiente')
            html += f"""
            <div style="border: 1px solid #ccc; margin: 10px 0; padding: 15px; background: white;">
                <h3>Suggestion #{i}</h3>
                <p><strong>Name:</strong> {suggestion.get('siteName', 'N/A')}</p>
                <p><strong>URL:</strong> {suggestion.get('siteUrl', 'N/A')}</p>
                <p><strong>Status:</strong> {status}</p>
                <p><strong>Date:</strong> {suggestion.get('fecha_legible', 'N/A')}</p>
                <p><strong>Actions:</strong> 
                    <a href="/admin/approve/{i}" style="color: green;">Approve</a> | 
                    <a href="/admin/reject/{i}" style="color: red;">Reject</a>
                </p>
            </div>
            """
        
        html += `
        <p><strong>Total suggestions:</strong> ${suggestions.length}</p>
        <div style="text-align: center; margin: 30px;">
            <div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap;">
                <a href="/" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);">🏠 Página Principal</a>
                <a href="/admin/approval-panel" style="background: #ff69b4; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(255, 105, 180, 0.3);">📋 Panel de Aprobación</a>
                <a href="/admin/suggestions" style="background: #6f42c1; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(111, 66, 193, 0.3);">📊 Ver Historial</a>
            </div>
        </div>
        `;
        
        return html;
        
           
        
    } catch (Exception e) {
        return `<h1>Error: ${e.message}</h1>`, 500;
    }
}

@app.route('/admin/approval-panel')
def approval_panel():
    try {
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f);
    } catch (FileNotFoundError) {
        suggestions = [];
    }
    
    // Filter pending suggestions
    pending_suggestions = suggestions.filter(s => s.get('status', 'Pendiente') === 'Pendiente');
    
    html = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Panel de Aprobación de Sugerencias</title>
        <style>
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background: linear-gradient(120deg, #ffb6e6 0%, #fecfef 50%, #ffb6e6 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(214, 51, 132, 0.3);
            }
            h1 {
                color: #d63384;
                text-align: center;
                margin-bottom: 30px;
                font-size: 2.5em;
                text-shadow: 2px 2px 4px rgba(214, 51, 132, 0.3);
            }
            .suggestion-card {
                background: white;
                border: 2px solid #ff69b4;
                border-radius: 15px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 5px 15px rgba(255, 105, 180, 0.2);
                transition: transform 0.2s;
            }
            .suggestion-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(255, 105, 180, 0.3);
            }
            .suggestion-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #ffe0f7;
            }
            .suggestion-title {
                font-size: 1.5em;
                font-weight: bold;
                color: #d63384;
            }
            .suggestion-id {
                background: #ff69b4;
                color: white;
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 0.9em;
            }
            .suggestion-details {
                margin: 15px 0;
            }
            .suggestion-details p {
                margin: 8px 0;
                color: #666;
            }
            .suggestion-details strong {
                color: #d63384;
            }
            .action-buttons {
                display: flex;
                gap: 15px;
                margin-top: 20px;
            }
            .btn {
                padding: 12px 25px;
                border: none;
                border-radius: 25px;
                font-weight: bold;
                font-size: 1em;
                cursor: pointer;
                transition: all 0.3s;
                text-decoration: none;
                display: inline-block;
                text-align: center;
            }
            .btn-approve {
                background: linear-gradient(135deg, #28a745, #20c997);
                color: white;
                box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
            }
            .btn-approve:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(40, 167, 69, 0.4);
            }
            .btn-reject {
                background: linear-gradient(135deg, #dc3545, #e83e8c);
                color: white;
                box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);
            }
            .btn-reject:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(220, 53, 69, 0.4);
            }
            .no-suggestions {
                text-align: center;
                color: #666;
                font-size: 1.2em;
                margin: 50px 0;
            }
            .stats {
                background: linear-gradient(135deg, #ff69b4, #d63384);
                color: white;
                padding: 15px;
                border-radius: 15px;
                text-align: center;
                margin-bottom: 30px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✨ Panel de Aprobación ✨</h1>
            
            <div class="stats">
                <strong>📊 Sugerencias Pendientes: ${pending_suggestions.length}</strong>
            </div>
            
            ${pending_suggestions.length === 0 ? '<div class="no-suggestions">🎉 ¡No hay sugerencias pendientes!<br><small>Todas las sugerencias han sido procesadas.</small></div>' : ''}
            
            ${pending_suggestions.map((suggestion, i) => `
            <div class="suggestion-card">
                <div class="suggestion-header">
                    <div class="suggestion-title">${suggestion.siteName}</div>
                    <div class="suggestion-id">#${i}</div>
                </div>
                <div class="suggestion-details">
                    <p><strong>🔗 URL:</strong> <a href="${suggestion.siteUrl}" target="_blank" class="url-link">${suggestion.siteUrl}</a></p>
                    <p><strong>💭 Razón:</strong> ${suggestion.reason || 'No especificada'}</p>
                    <p><strong>📅 Fecha:</strong> ${suggestion.fecha_legible}</p>
                </div>
                <div class="action-buttons">
                    <a href="/admin/approve/${i}" class="btn btn-approve">✅ Aprobar</a>
                    <a href="/admin/reject/${i}" class="btn btn-reject">❌ Rechazar</a>
                </div>
            </div>
            `).join('')}
            
            <div style="text-align: center; margin-top: 40px; padding-top: 30px; border-top: 2px solid #ffe0f7;">
                <div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin-bottom: 20px;">
                    <a href="/" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);">🏠 Página Principal</a>
                    <a href="/admin/suggestions" style="background: #6f42c1; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(111, 66, 193, 0.3);">📊 Ver Historial</a>
                    <a href="/admin/notifications" style="background: #fd7e14; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(253, 126, 20, 0.3);">🔔 Notificaciones</a>
                    <a href="/admin/monitoring-list" style="background: #20c997; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold; box-shadow: 0 4px 15px rgba(32, 201, 151, 0.3);">🔄 Ver Monitoreo</a>
                </div>
                <p style="color: #666; font-size: 0.9em; margin-top: 15px;">
                    ⏱️ Esta página se actualiza automáticamente cada 30 segundos
                </p>
            </div>
        </div>
    </body>
    </html>
    `;
}

@app.route('/admin/suggestions')
def view_suggestions():
    try:
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
        return render_template('suggestions.html', suggestions=suggestions)
    except FileNotFoundError:
        return render_template('suggestions.html', suggestions=[])

@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook for button callbacks"""
    from flask import request
    try:
        data = request.get_json()
        
        # Check if this is a callback query (button press)
        if 'callback_query' in data:
            callback_query = data['callback_query']
            callback_data = callback_query['data']
            message_id = callback_query['message']['message_id']
            chat_id = callback_query['message']['chat']['id']
            
            # Parse callback data
            if callback_data.startsWith('approve_'):
                suggestion_id = int(callback_data.replace('approve_', ''))
                handle_approval(suggestion_id, true, message_id, chat_id)
            } else if (callback_data.startsWith('reject_')) {
                suggestion_id = int(callback_data.replace('reject_', ''))
                handle_approval(suggestion_id, false, message_id, chat_id)
            }
            
            return jsonify({"ok": true})
        
        return jsonify({"ok": true})
        
    } catch (Exception e) {
        print(`Webhook error: ${e}`)
        return jsonify({"error": str(e)}), 500
    }

function handle_approval(suggestion_id, approved, message_id, chat_id) {
    """Handle suggestion approval/rejection"""
    try {
        // Load suggestions
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
        
        if (suggestion_id >= suggestions.length) {
            console.log(`Invalid suggestion ID: ${suggestion_id}`);
            return;
        }
        
        suggestion = suggestions[suggestion_id];
        status = approved ? "Aprobada" : "Rechazada";
        suggestion['status'] = status;
        suggestion['approved_at'] = datetime.now(UTC).isoformat();
        
        // Save updated suggestions
        with open('suggestions.json', 'w') as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        
        // Update the admin message
        admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
        edit_url = `https://api.telegram.org/bot${admin_token}/editMessageText`;
        
        updated_text = `
🆕 <b>Sugerencia de Sitio Web - ${status}</b>

📝 <b>Nombre:</b> ${suggestion['siteName']}
🔗 <b>URL:</b> ${suggestion['siteUrl']}
💭 <b>Razón:</b> ${suggestion.get('reason', 'No especificada')}
📅 <b>Fecha:</b> ${suggestion['fecha_legible']}
✅ <b>Estado:</b> ${status}

<a href="${suggestion['siteUrl']}">Ver sitio sugerido</a>
        `.trim();
        
        edit_payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": updated_text,
            "parse_mode": "HTML"
        };
        
        requests.post(edit_url, data=edit_payload, timeout=5);
        
        // If approved, send notification to main bot
        if (approved) {
            main_message = `
🎉 <b>Nueva Web Aprobada para Monitoreo</b>

📝 <b>Sitio:</b> ${suggestion['siteName']}
🔗 <b>URL:</b> ${suggestion['siteUrl']}
💭 <b>Razón:</b> ${suggestion.get('reason', 'No especificada')}

¡Este sitio ha sido aprobado y será considerado para monitoreo!

<a href="${suggestion['siteUrl']}">Ver sitio</a>
            `.trim();
            
            // Send to main bot
            send_telegram_message(main_message);
            console.log("SUCCESS: Main bot notification sent");
        }
        
    } catch (Exception e) {
        console.log(`Error handling approval: ${e}`);
    }
}

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
    try {
        has_new_changes = any(item.get('status', '').find('Actualizado') != -1 for item in latest_changes)
        return {"new_changes": has_new_changes}
    } catch {
        return {"new_changes": False}
    }

@app.route('/test-notification')
def test_notification():
    """Simple test to trigger notifications"""
    try {
        console.log("TEST: Starting notification test...");
        
        // Test environment variables first
        main_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if (!main_token || !admin_token || !chat_id) {
            return `
            <html><body style="padding: 20px;">
                <h1>❌ Configuration Error</h1>
                <p>Main token: ${main_token ? '✅' : '❌'}</p>
                <p>Admin token: ${admin_token ? '✅' : '❌'}</p>
                <p>Chat ID: ${chat_id ? '✅' : '❌'}</p>
            </body></html>
            `;
        }
        
        // Test main bot
        console.log("TEST: Testing main bot...");
        send_telegram_message("Test desde app.py - Bot Principal funcionando!");
        
        // Test admin bot
        console.log("TEST: Testing admin bot...");
        send_to_admin_group("Test desde app.py - Bot Admin funcionando!");
        
        return `
        <html>
        <body style="font-family: monospace; padding: 20px; background: #f0f0f0;">
            <h1>🧪 Test de Notificaciones Enviado</h1>
            <p>Check your Telegram and the console/terminal for debug messages.</p>
            <a href="/" style="background: #ff69b4; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">← Back to Dashboard</a>
        </body>
        </html>
        `;
        
    } catch (Exception e) {
        console.log(`ERROR in test_notification: ${e}`);
        return `
        <html><body style="padding: 20px;">
            <h1>❌ Error</h1>
            <p>${e.message}</p>
            <pre>${e.stack}</pre>
        </body></html>
        `;
    }
}

@app.route('/setup-webhook')
def setup_webhook():
    """Setup Telegram webhook for the admin bot"""
    admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
    if not admin_token:
        return jsonify({"error": "Admin bot token not configured"}), 400
    
    # You'll need to replace this with your actual domain/ngrok URL
    webhook_url = "https://your-domain.com/telegram-webhook"  # Change this!
    
    setup_url = f"https://api.telegram.org/bot{admin_token}/setWebhook"
    payload = {"url": webhook_url}
    
    try {
        r = requests.post(setup_url, data=payload, timeout=5);
        return jsonify({"status": r.status_code, "response": r.json()});
    } catch (Exception e) {
        return jsonify({"error": str(e)}), 500;
    }
}

@app.route('/admin/notifications')
def admin_notifications():
    """Página especial para recibir notificaciones en tiempo real"""
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>🔔 Panel de Notificaciones Admin</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            h1 {
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }
            .notification {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                padding: 20px;
                border-radius: 15px;
                margin: 15px 0;
                animation: slideIn 0.5s ease-out;
                display: none;
                border: 2px solid #a855f7;
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
            }
            .notification.show {
                display: block;
            }
            .status {
                text-align: center;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 8px;
                margin: 20px 0;
            }
            @keyframes slideIn {
                from { transform: translateX(-100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
            }
            .pulse {
                animation: pulse 1s ease-in-out;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔔 Panel de Notificaciones Admin</h1>
            <div class="status" id="status">
                ✅ Esperando nuevas sugerencias...
            </div>
            <div id="notifications"></div>
        </div>

        <script>
            let lastCheck = 0;
            let notificationSound = null;

            // Crear sonido de notificación
            function createNotificationSound() {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
                oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);
                oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.2);
                
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
                
                oscillator.start();
                oscillator.stop(audioContext.currentTime + 0.3);
            }

            // Verificar nuevas sugerencias
            async function checkForNewSuggestions() {
                try {
                    const response = await fetch('/get-latest-suggestions');
                    const data = await response.json();
                    
                    // Verificar si hay nuevas sugerencias
                    if (data.suggestions.length > 0) {
                        data.suggestions.forEach(suggestion => {
                            if (!suggestion.notified) {
                                // Nueva sugerencia detectada!
                                showDetailedNotification(suggestion);
                                createNotificationSound();
                                
                                // Notificación del navegador si está permitida
                                if (Notification.permission === 'granted') {
                                    new Notification('🆕 Nueva Sugerencia!', {
                                        body: `Sitio: ${suggestion.siteName}`,
                                        icon: '🔔'
                                    });
                                }
                            }
                        });
                    }
                    
                    document.getElementById('status').innerHTML = 
                        `✅ Última verificación: ${new Date().toLocaleTimeString()}<br>
                         📊 Total sugerencias: ${data.total}<br>
                         🆕 Pendientes: ${data.suggestions.length}`;
                } catch (error) {
                    console.error('Error checking suggestions:', error);
                    document.getElementById('status').innerHTML = 
                        `❌ Error de conexión: ${new Date().toLocaleTimeString()}`;
                }
            }

            // Verificar nuevas sugerencias al cargar
            window.addEventListener('load', () => {
                checkForNewSuggestions();
                setInterval(checkForNewSuggestions, 5000);
            });
        </script>
    </body>
    </html>
    """

@app.route('/get-all-suggestions')
def get_all_suggestions():
    """API para obtener todas las sugerencias con límite opcional"""
    from flask import request
    try {
        limit = request.args.get('limit', type=int)
        
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
        
        if (limit) {
            suggestions = suggestions.slice(-limit);  // Últimas N sugerencias
        }
        
        return jsonify({
            "total": suggestions.length,
            "suggestions": suggestions
        })
    } catch (FileNotFoundError) {
        return jsonify({"total": 0, "suggestions": []})
    }

@app.route('/get-latest-suggestions')
def get_latest_suggestions():
    """API para obtener las últimas sugerencias con detalles completos"""
    try {
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
        
        // Obtener las últimas 3 sugerencias para mostrar
        latest_suggestions = suggestions.slice(-3);
        
        // Marcar como nuevas las que fueron agregadas en los últimos 5 minutos
        now = datetime.now(UTC);
        recent_suggestions = [];
        
        latest_suggestions.forEach(suggestion => {
            suggestion_time = datetime.fromisoformat(suggestion['timestamp'].replace('Z', '+00:00'));
            time_diff = (now - suggestion_time).total_seconds();
            
            // Si la sugerencia es de los últimos 10 minutos, marcarla como nueva
            if (time_diff < 600) {  // 10 minutos
                suggestion['notified'] = false;
                recent_suggestions.push(suggestion);
            }
        });
        
        return jsonify({
            "total": suggestions.length,
            "suggestions": recent_suggestions
        })
    } catch (FileNotFoundError) {
        return jsonify({"total": 0, "suggestions": []})
    }

@app.route('/get-suggestions-count')
def get_suggestions_count():
    """API para obtener el número total de sugerencias (mantener compatibilidad)"""
    try {
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
        return jsonify({"count": suggestions.length})
    } catch (FileNotFoundError) {
        return jsonify({"count": 0})
    }

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)