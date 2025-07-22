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

socketio.start_background_task(background_checker)

# HTML_TEMPLATE omitted for brevity, keep your original HTML_TEMPLATE here

@app.route('/')
def dashboard():
  return render_template_string(HTML_TEMPLATE)

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
