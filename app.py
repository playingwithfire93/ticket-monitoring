
import os
import json
import traceback
import requests
from datetime import datetime, timezone
from flask import Flask, render_template, render_template_string, jsonify, request

URLS = []
def group_urls_by_musical(urls):
  return {}
HTML_TEMPLATE = ""
UTC = timezone.utc
def send_to_admin_group(message):
  print(f"Admin notification: {message}")
def send_telegram_message(message):
  print(f"Telegram message: {message}")
class SocketIO:
  def run(self, app, host, port, debug):
    print(f"Running app on {host}:{port} debug={debug}")
socketio = SocketIO()

app = Flask(__name__)

def scrape_all_sites():
  """Scrape all URLs from urls.json and return their status and timestamp."""
  results = []
  try:
    with open('urls.json', 'r', encoding='utf-8') as f:
      musicals = json.load(f)
    for musical in musicals:
      for url in musical.get('urls', []):
        try:
          response = requests.get(url, timeout=10)
          status = f"Actualizado ({response.status_code})"
        except Exception as e:
          status = f"Error: {e}"
        results.append({
          'musical': musical.get('musical', ''),
          'url': url,
          'status': status,
          'timestamp': datetime.now().isoformat()
        })
  except Exception as e:
    print(f"Error in scrape_all_sites: {e}")
  return results

# ...existing code...
@app.route('/changes')
def changes_dummy():
  return "Not implemented", 200

@app.route('/api/suggest-site', methods=['POST'])
def suggest_site():
  print("DEBUG: suggest_site called")
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
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
  except FileNotFoundError:
    suggestions = []
  suggestions.append(suggestion)
  with open('suggestions.json', 'w') as f:
    json.dump(suggestions, f, indent=2, ensure_ascii=False)
  print("DEBUG: Suggestion saved to file")
  try:
    admin_message = (
      "&#128680; <b>¡NUEVA SUGERENCIA RECIBIDA!</b> &#128680;<br>"
      f"<b>Sugerencia # {len(suggestions)}</b><br>"
      "<hr>"
      f"<b>Sitio:</b> {site_name}<br>"
      f"<b>URL:</b> <a href='{site_url}'>{site_url}</a><br>"
      f"<b>Razón:</b> {reason or 'No especificada'}<br>"
      f"<b>Recibida:</b> {suggestion['fecha_legible']}<br>"
      "<hr>"
      "<b>ACCIONES DISPONIBLES:</b><br>"
      f"<a href='{site_url}'>Ver sitio web sugerido</a><br>"
      "<a href='http://localhost:5000/admin/approval-panel'>Panel de Aprobación</a><br>"
      "<i>¡Revisar y aprobar lo antes posible!</i>"
    )
    print("DEBUG: Sending enhanced notification to admin bot...")
    send_to_admin_group(admin_message)
    print("DEBUG: Enhanced admin notification sent")
  except Exception as notification_error:
    print(f"WARNING: Could not send admin notification: {notification_error}")
  return jsonify({"success": True, "message": "Sugerencia enviada correctamente"})

@app.route('/admin/monitoring-list')
def monitoring_list():
  try:
    current_urls = URLS.copy()
    try:
      with open('urls.json', 'r') as f:
        urls_data = json.load(f)
    except FileNotFoundError:
      urls_data = []
    return render_template(
      'monitoring_list.html',
      current_urls=current_urls,
      urls_data=urls_data
    )
  except Exception as e:
    print(f"ERROR in monitoring_list: {e}")
    return render_template('monitoring_list.html', current_urls=[], urls_data=[])

@app.route('/admin/approval-panel')
def approval_panel():
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
  except FileNotFoundError:
    suggestions = []
  pending_suggestions = [s for s in suggestions if s.get('status', 'Pendiente') == 'Pendiente']
  return render_template('approval_panel.html', pending_suggestions=pending_suggestions)

@app.route('/admin/suggestions')
def view_suggestions():
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
    return render_template('suggestions.html', suggestions=suggestions)
  except FileNotFoundError:
    return render_template('suggestions.html', suggestions=[])

@app.route('/api/ticket-changes')
def get_ticket_changes():
  global latest_changes
  return jsonify(latest_changes)

@app.route('/api/check-changes')
def check_changes():
  try:
    has_new_changes = any(item.get('status', '').find('Actualizado') != -1 for item in latest_changes)
    return {"new_changes": has_new_changes}
  except Exception:
    return {"new_changes": False}

@app.route('/test-notification')
def test_notification():
  main_token = os.environ.get("TELEGRAM_BOT_TOKEN")
  admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
  chat_id = os.environ.get("TELEGRAM_CHAT_ID")
  if not main_token or not admin_token or not chat_id:
    return render_template('error.html', main_token=main_token, admin_token=admin_token, chat_id=chat_id)
  send_telegram_message("Test desde app.py - Bot Principal funcionando!")
  send_to_admin_group("Test desde app.py - Bot Admin funcionando!")
  return render_template('notification_test.html')

@app.route('/setup-webhook')
def setup_webhook():
  admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
  if not admin_token:
    return jsonify({"error": "Admin bot token not configured"}), 400
  webhook_url = "https://your-domain.com/telegram-webhook"  # Change this!
  setup_url = f"https://api.telegram.org/bot{admin_token}/setWebhook"
  payload = {"url": webhook_url}
  try:
    r = requests.post(setup_url, data=payload, timeout=5)
    return jsonify({"status": r.status_code, "response": r.json()})
  except Exception as e:
    return jsonify({"error": str(e)}), 500

@app.route('/admin/notifications')
def admin_notifications():
  return render_template("admin_notifications.html")

@app.route('/get-all-suggestions')
def get_all_suggestions():
  limit = request.args.get('limit', type=int)
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
    if limit:
      suggestions = suggestions[-limit:]
    return jsonify({
      "total": len(suggestions),
      "suggestions": suggestions
    })
  except FileNotFoundError:
    return jsonify({"total": 0, "suggestions": []})

@app.route('/get-latest-suggestions')
def get_latest_suggestions():
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
    latest_suggestions = suggestions[-3:]
    now = datetime.now(UTC)
    recent_suggestions = []
    for suggestion in latest_suggestions:
      suggestion_time = datetime.fromisoformat(suggestion['timestamp'].replace('Z', '+00:00'))
      time_diff = (now - suggestion_time).total_seconds()
      if time_diff < 600:
        suggestion['notified'] = False
        recent_suggestions.append(suggestion)
    return jsonify({
      "total": len(suggestions),
      "suggestions": recent_suggestions
    })
  except FileNotFoundError:
    return jsonify({"total": 0, "suggestions": []})

@app.route('/get-suggestions-count')
def get_suggestions_count():
  try:
    with open('suggestions.json', 'r') as f:
      suggestions = json.load(f)
    return jsonify({"count": len(suggestions)})
  except FileNotFoundError:
    return jsonify({"count": 0})

if __name__ == '__main__':
  socketio.run(app, host='0.0.0.0', port=5000, debug=False)