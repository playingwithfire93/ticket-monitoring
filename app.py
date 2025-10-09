from datetime import datetime, timezone
from pathlib import Path
import json
import os
import requests
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, Musical, MusicalLink, MusicalChange

# ==================== CONFIGURATION ====================
BASE = Path(__file__).parent
URLS_FILE = BASE / "urls.json"
SUGGESTIONS_FILE = BASE / "suggestions.json"
EVENTS_FILE = BASE / "events.json"
UTC = timezone.utc

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# ==================== FLASK APP SETUP ====================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE / 'musicals.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Create database tables
with app.app_context():
    db.create_all()
    app.logger.info("Database initialized")

# ==================== AUTHENTICATION ====================
def require_auth(f):
    """Decorator to require HTTP Basic Auth for admin routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response(
                'Acceso denegado. Introduce la contraseña de administrador.\n',
                401,
                {'WWW-Authenticate': 'Basic realm="Admin Area"'}
            )
        return f(*args, **kwargs)
    return decorated

# ==================== DATA HELPERS ====================
def load_urls():
    """Load raw list from urls.json (returns list of {musical, urls})."""
    try:
        with URLS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def group_urls_by_musical(urls_list):
    """Return list of dicts with musical names and their URLs."""
    grouped = []
    seen = set()
    for item in urls_list:
        name = item.get("musical") or item.get("name") or "Sin nombre"
        if name not in seen:
            seen.add(name)
            grouped.append({
                'name': name,
                'urls': item.get("urls", [])
            })
    return grouped

def load_events():
    """Load events from events.json."""
    try:
        with EVENTS_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

# ==================== NOTIFICATION SYSTEM ====================
def send_telegram_notification(message_text):
    """Send plain-text notification to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.warning("Telegram not configured")
        return {"ok": False, "reason": "telegram-not-configured"}
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message_text}
        r = requests.post(url, json=payload, timeout=6)
        data = r.json() if r.ok else {"status": r.status_code}
        
        if r.ok:
            app.logger.info("Telegram notification sent")
        else:
            app.logger.error(f"Telegram error: {data}")
        
        return {"ok": r.ok, "resp": data}
    except Exception as e:
        app.logger.exception("send_telegram_notification failed")
        return {"ok": False, "error": str(e)}

def send_discord_webhook(message_text, webhook_type="alert"):
    """Send notification to Discord via webhook."""
    webhook_url = DISCORD_WEBHOOK_SUGGESTIONS if webhook_type == "suggestion" else DISCORD_WEBHOOK_ALERTS
    
    if not webhook_url:
        app.logger.warning(f"Discord webhook ({webhook_type}) not configured")
        return {"ok": False, "reason": f"discord-{webhook_type}-not-configured"}
    
    try:
        r = requests.post(webhook_url, json={"content": message_text}, timeout=6)
        
        if r.ok:
            app.logger.info(f"Discord notification sent ({webhook_type})")
        else:
            app.logger.error(f"Discord error ({webhook_type}): {r.status_code}")
        
        return {"ok": r.ok, "status": r.status_code}
    except Exception as e:
        app.logger.exception(f"send_discord_webhook failed ({webhook_type})")
        return {"ok": False, "error": str(e)}

def notify_all_channels(message_text, channel_type="alert"):
    """Send notification to ALL configured channels (Telegram + Discord)."""
    results = {}
    
    results["telegram"] = send_telegram_notification(message_text)
    results["discord"] = send_discord_webhook(message_text, webhook_type=channel_type)
    
    success_count = sum(1 for r in results.values() if r.get("ok"))
    results["success_count"] = success_count
    results["total_channels"] = 2
    
    return results

# ==================== MONITORING SYSTEM ====================
def check_all_urls(send_notifications=False):
    """Check all monitored URLs for availability."""
    musicals = load_urls()
    results = {"checked": 0, "errors": []}
    
    for item in musicals:
        name = item.get("musical") or item.get("name") or "Unknown"
        urls = item.get("urls") or []
        
        for url in urls:
            results["checked"] += 1
            
            try:
                r = requests.head(url, timeout=5, allow_redirects=True)
                
                if r.status_code >= 400:
                    results["errors"].append({"musical": name, "url": url, "status": r.status_code})
                    
                    if send_notifications:
                        alert = f"⚠️ Error monitorizando {name}\n\nURL: {url}\nEstado: {r.status_code}"
                        notify_all_channels(alert, channel_type="alert")
                
            except Exception as e:
                results["errors"].append({"musical": name, "url": url, "error": str(e)})
                
                if send_notifications:
                    alert = f"❌ Error accediendo a {name}\n\nURL: {url}\nError: {str(e)[:200]}"
                    notify_all_channels(alert, channel_type="alert")
    
    return results

# ==================== TEMPLATE FILTERS ====================
@app.template_filter('format_date')
def format_date(date_str):
    """Convert ISO date to human-readable format."""
    if not date_str:
        return ''
    
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = date_str
        
        now = datetime.now(timezone.utc)
        diff = now - dt.replace(tzinfo=timezone.utc)
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'Ahora'
        elif seconds < 3600:
            return f'Hace {int(seconds/60)}m'
        elif seconds < 86400:
            return f'Hace {int(seconds/3600)}h'
        elif seconds < 604800:
            return f'Hace {int(seconds/86400)}d'
        else:
            return dt.strftime('%d %b')
    except Exception:
        return ''

# ==================== PUBLIC ROUTES ====================
@app.route("/")
def index():
    musicals = load_urls()
    grouped = group_urls_by_musical(musicals)
    
    # Enrich with database info
    for item in grouped:
        name = item.get('name', '')
        musical = Musical.query.filter_by(name=name).first()
        if musical:
            item['last_updated'] = musical.updated_at.isoformat() if musical.updated_at else None
            item['total_links'] = len(musical.links)
            item['musical_id'] = musical.id
            last_change = MusicalChange.query.filter_by(musical_id=musical.id).order_by(MusicalChange.changed_at.desc()).first()
            if last_change:
                item['last_change_type'] = last_change.change_type
                item['last_change_date'] = last_change.changed_at.isoformat()
        else:
            item['last_updated'] = None
            item['total_links'] = len(item.get('urls', []))
            item['musical_id'] = None
    
    return render_template("index.html", grouped_urls=grouped)

@app.route("/calendar")
def calendar_page():
    grouped = group_urls_by_musical(load_urls())
    return render_template("calendar.html", grouped_urls=grouped)

@app.route("/shows")
def shows_page():
    events = load_events()
    grouped = {}
    for ev in events:
        key = (ev.get('musical') or ev.get('title') or 'Sin título').strip()
        g = grouped.setdefault(key, {
            'title': key, 'id': key, 'dates': [],
            'image': ev.get('image') or '/static/BOM1.jpg',
            'short': ev.get('short') or '',
            'url': ev.get('url') or '#',
            'location': ev.get('location') or ''
        })
        g['dates'].append(ev.get('start'))
    
    shows = []
    for v in grouped.values():
        dates = sorted([d for d in v['dates'] if d])
        v['range'] = dates[0] + (f' → {dates[-1]}' if len(dates) > 1 else '') if dates else ''
        shows.append(v)
    
    return render_template('shows.html', shows=shows)

@app.route("/health")
def health():
    return jsonify({"ok": True, "time": datetime.now(UTC).isoformat()})

# ==================== API ROUTES ====================
@app.route("/api/events")
def api_events():
    try:
        return jsonify(load_events())
    except Exception:
        app.logger.exception("api_events failed")
        return jsonify([]), 500

@app.route("/api/monitored-urls")
def api_monitored_urls():
    return jsonify(load_urls())

@app.route("/api/suggest-site", methods=["POST"])
def api_suggest_site():
    """Public endpoint: save suggestion and notify all channels."""
    data = request.get_json(silent=True) or {}
    
    suggestion = {
        "siteName": data.get("siteName", ""),
        "siteUrl": data.get("siteUrl", ""),
        "reason": data.get("reason", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if not suggestion["siteName"] or not suggestion["siteUrl"]:
        return jsonify({"error": "siteName and siteUrl required"}), 400
    
    # Save to file
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        suggestions = []
    
    suggestions.append(suggestion)
    
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    app.logger.info(f"New suggestion: {suggestion['siteName']}")
    
    # Notify
    message = f"""🎭 Nueva sugerencia de musical

**{suggestion['siteName']}**
🔗 {suggestion['siteUrl']}

Razón: {suggestion['reason'] or 'No especificada'}

📅 {suggestion['timestamp']}"""
    
    notify_results = notify_all_channels(message, channel_type="suggestion")
    
    return jsonify({"ok": True, "suggestion": suggestion, "notifications": notify_results}), 201

# ==================== ADMIN ROUTES ====================
@app.route("/admin")
@require_auth
def admin_panel():
    """Admin panel with test notifications button."""
    return render_template("admin_panel.html")

@app.route("/admin/suggestions")
@require_auth
def admin_suggestions():
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        suggestions = []
    return render_template("suggestions.html", suggestions=suggestions)

@app.route("/admin/monitoring-list")
@require_auth
def monitoring_list():
    musicals = load_urls()
    grouped = group_urls_by_musical(musicals)
    return render_template("monitoring_list.html", musicals=musicals, grouped=grouped)

@app.route("/admin/musicals")
@require_auth
def admin_musicals():
    musicals = Musical.query.all()
    return jsonify([m.to_dict() for m in musicals])

@app.route("/admin/check-now", methods=["POST"])
@require_auth
def admin_check_now():
    results = check_all_urls(send_notifications=True)
    return jsonify(results)

@app.route("/admin/test-notifications", methods=["POST"])
@require_auth
def admin_test_notifications():
    data = request.get_json(silent=True) or {}
    channel_type = data.get("type", "alert")
    
    if channel_type == "suggestion":
        test_message = "🧪 Test de SUGERENCIAS desde Ticket Monitor\n\nSi ves este mensaje, funciona."
    else:
        test_message = "🧪 Test de ALERTAS desde Ticket Monitor\n\nSi ves este mensaje, funciona."
    
    results = notify_all_channels(test_message, channel_type=channel_type)
    
    return jsonify({"message": f"Test sent ({channel_type})", "results": results})

@app.route("/admin/suggestions/<int:idx>/approve", methods=["POST"])
@require_auth
def approve_suggestion(idx):
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        return jsonify({"error": "no suggestions file"}), 404
    
    if idx >= len(suggestions):
        return jsonify({"error": "suggestion not found"}), 404
    
    sug = suggestions.pop(idx)
    name = (sug.get("siteName") or sug.get("musical") or "Sin nombre").strip()
    url = (sug.get("siteUrl") or sug.get("url") or "").strip()
    notes = sug.get("reason") or sug.get("message") or ""
    
    if not name or not url:
        return jsonify({"error": "invalid suggestion"}), 400
    
    # Create or update musical in DB
    musical = Musical.query.filter_by(name=name).first()
    is_new = not musical
    
    if not musical:
        musical = Musical(name=name, description=notes)
        db.session.add(musical)
        db.session.flush()
        
        change = MusicalChange(
            musical_id=musical.id, change_type='created',
            description=f"Musical '{name}' creado desde sugerencia",
            changed_by='admin', extra_data=json.dumps({'source': 'suggestion'})  # ← CAMBIAR metadata a extra_data
        )
        db.session.add(change)
    
    # Add link if not exists
    existing = MusicalLink.query.filter_by(musical_id=musical.id, url=url).first()
    if not existing:
        link = MusicalLink(musical_id=musical.id, url=url, notes=notes, status='active')
        db.session.add(link)
        
        change = MusicalChange(
            musical_id=musical.id, change_type='link_added',
            description=f"Enlace añadido: {url[:50]}...",
            changed_by='admin', extra_data=json.dumps({'url': url})  # ← CAMBIAR metadata a extra_data
        )
        db.session.add(change)
        musical.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    # Update urls.json for compatibility
    urls = load_urls()
    found = False
    for item in urls:
        if (item.get("musical") or item.get("name")) == name:
            if url not in item.get("urls", []):
                item.setdefault("urls", []).append(url)
            found = True
            break
    
    if not found:
        urls.append({"musical": name, "urls": [url]})
    
    with URLS_FILE.open("w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2, ensure_ascii=False)
    
    # Remove suggestion
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    return jsonify({"ok": True, "approved": sug, "musical": musical.to_dict()})

@app.route("/admin/suggestions/<int:idx>/reject", methods=["POST"])
@require_auth
def reject_suggestion(idx):
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        return jsonify({"error": "no suggestions file"}), 404
    
    if idx >= len(suggestions):
        return jsonify({"error": "suggestion not found"}), 404
    
    rejected = suggestions.pop(idx)
    
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    return jsonify({"ok": True, "rejected": rejected})

# ==================== BACKGROUND SCHEDULER ====================
POLL_INTERVAL_SECONDS = 300  # 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(
    lambda: check_all_urls(send_notifications=True),
    "interval",
    seconds=POLL_INTERVAL_SECONDS,
    id="monitor_job"
)
scheduler.start()

# ==================== APP RUNNER ====================
if __name__ == "__main__":
    try:
        socketio.run(app, host="0.0.0.0", port=5000, debug=True)
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass