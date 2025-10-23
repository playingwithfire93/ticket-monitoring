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

# Cambiar rutas
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
URLS_FILE = BASE_DIR / "static" / "python" / "urls.json"
SUGGESTIONS_FILE = BASE_DIR / "static" / "python" / "suggestions.json"

EVENTS_FILE = BASE / "events.json"
UTC = timezone.utc

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# ==================== FLASK APP SETUP ====================
# Configurar paths - los templates están en static/html/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'static', 'html')  # ✅ Correcto
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Debug: mostrar estructura de archivos
print("=" * 60)
print("🔍 DEBUGGING FILE STRUCTURE")
print("=" * 60)
print(f"📁 __file__: {__file__}")
print(f"📁 BASE: {BASE}")
print(f"📁 BASE_DIR: {BASE_DIR}")
print(f"📁 TEMPLATE_DIR: {TEMPLATE_DIR}")
print(f"📁 STATIC_DIR: {STATIC_DIR}")

# Verificar si los directorios existen
print(f"\n✅ Templates dir exists: {os.path.exists(TEMPLATE_DIR)}")
print(f"✅ Static dir exists: {os.path.exists(STATIC_DIR)}")

# Listar archivos en TEMPLATE_DIR si existe
if os.path.exists(TEMPLATE_DIR):
    print(f"\n📄 Files in TEMPLATE_DIR:")
    for root, dirs, files in os.walk(TEMPLATE_DIR):
        level = root.replace(TEMPLATE_DIR, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f'{subindent}{file}')
else:
    print(f"\n❌ TEMPLATE_DIR does not exist!")

print("=" * 60)

app = Flask(__name__,
           static_folder='static',
           static_url_path='/static')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE / 'musicals.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Log configuration status
print(f"\n📱 Configuration Status:")
print(f"✅ Telegram configured: {bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)}")
print(f"✅ Discord Alerts configured: {bool(DISCORD_WEBHOOK_ALERTS)}")
print(f"✅ Discord Suggestions configured: {bool(DISCORD_WEBHOOK_SUGGESTIONS)}")
print(f"✅ Template folder set to: {app.template_folder}")
print(f"✅ Static folder set to: {app.static_folder}")

# Create database tables
with app.app_context():
    try:
        db.create_all()
        app.logger.info("Database initialized")
        
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        if inspector.has_table('musicals'):
            columns = [col['name'] for col in inspector.get_columns('musicals')]
            
            if 'updated_at' not in columns:
                app.logger.warning("Database schema outdated, recreating tables...")
                db.drop_all()
                db.create_all()
                app.logger.info("Database recreated successfully")
        else:
            app.logger.info("Creating database tables for the first time...")
            db.create_all()
            
    except Exception as e:
        app.logger.error(f"Database initialization error: {e}")

# ==================== AUTHENTICATION ====================
def require_auth(f):
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
    try:
        with URLS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def group_urls_by_musical(urls_list):
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
    try:
        with EVENTS_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

# ==================== NOTIFICATION SYSTEM ====================
def send_telegram_notification(message_text):
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
    webhook_url = DISCORD_WEBHOOK_SUGGESTIONS if webhook_type == "suggestion" else DISCORD_WEBHOOK_ALERTS
    
    if not webhook_url:
        app.logger.warning(f"Discord webhook ({webhook_type}) not configured")
        return {"ok": False, "reason": f"discord-{webhook_type}-not-configured"}
    
    try:
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            app.logger.error(f"Invalid Discord webhook URL format ({webhook_type})")
            return {"ok": False, "reason": "invalid-webhook-url"}
        
        content = message_text[:2000] if len(message_text) > 2000 else message_text
        
        payload = {
            "content": content,
            "username": "Ticket Monitor",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3176/3176366.png"
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TicketMonitorBot/1.0"
        }
        
        app.logger.info(f"Sending Discord notification ({webhook_type})...")
        
        r = requests.post(webhook_url, json=payload, headers=headers, timeout=15)
        
        if r.status_code in [200, 204]:
            app.logger.info(f"✅ Discord notification sent successfully ({webhook_type})")
            return {"ok": True, "status": r.status_code}
        elif r.status_code == 429:
            retry_after = r.json().get("retry_after", 0) if r.text else 0
            app.logger.warning(f"Discord rate limit ({webhook_type}), retry after {retry_after}s")
            return {"ok": False, "status": 429, "error": f"rate_limit:{retry_after}s"}
        elif r.status_code == 404:
            app.logger.error(f"Discord webhook not found ({webhook_type})")
            return {"ok": False, "status": 404, "error": "webhook_not_found"}
        else:
            error_msg = r.text[:200] if r.text else f"HTTP {r.status_code}"
            app.logger.error(f"Discord error ({webhook_type}): {error_msg}")
            return {"ok": False, "status": r.status_code, "error": error_msg}
        
    except requests.exceptions.Timeout:
        app.logger.error(f"Discord webhook timeout ({webhook_type})")
        return {"ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError as e:
        app.logger.error(f"Discord connection error ({webhook_type}): {e}")
        return {"ok": False, "error": "connection_error"}
    except Exception as e:
        app.logger.exception(f"send_discord_webhook failed ({webhook_type})")
        return {"ok": False, "error": str(e)}

def notify_all_channels(message_text, channel_type="alert"):
    results = {}
    
    results["telegram"] = send_telegram_notification(message_text)
    results["discord"] = send_discord_webhook(message_text, webhook_type=channel_type)
    
    success_count = sum(1 for r in results.values() if r.get("ok"))
    results["success_count"] = success_count
    results["total_channels"] = 2
    
    return results

# ==================== MONITORING ====================
def check_url(url):
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        return {"ok": r.status_code < 400, "status": r.status_code}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "connection_error"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_all_urls():
    musicals = load_urls()
    results = {"checked": 0, "errors": []}
    
    for item in musicals:
        name = item.get("musical") or item.get("name") or "Unknown"
        urls = item.get("urls") or []
        
        for url in urls:
            results["checked"] += 1
            check = check_url(url)
            
            if not check["ok"]:
                error_data = {"musical": name, "url": url, **check}
                results["errors"].append(error_data)
                
                if "status" in check:
                    msg = f"⚠️ Error monitorizando {name}\n\nURL: {url}\nEstado: {check['status']}"
                else:
                    msg = f"❌ Error accediendo a {name}\n\nURL: {url}\nError: {check.get('error', 'Unknown')}"
                
                notify_all_channels(msg, channel_type="alert")
    
    app.logger.info(f"Checked {results['checked']} URLs, {len(results['errors'])} errors")
    return results

# ==================== ROUTES ====================
@app.route("/")
def index():
    """Página principal con el dashboard"""
    with app.app_context():
        musicals = Musical.query.all()
        
        # Prepare data for each musical
        for musical in musicals:
            musical.links = MusicalLink.query.filter_by(musical_id=musical.id).all()
            musical.active_links = sum(1 for link in musical.links if link.is_available)
            musical.sold_out_links = len(musical.links) - musical.active_links
        
        return render_template(
            'index.html',
            musicals=musicals
        )

@app.route("/calendar")
def calendar():
    grouped = group_urls_by_musical(load_urls())
    return render_template("calendar.html", grouped_urls=grouped)

@app.route("/shows")
def shows():
    """Lista solo los musicales que estás monitoreando (en la base de datos)"""
    try:
        musicals = Musical.query.all()
        
        for musical in musicals:
            musical.links = MusicalLink.query.filter_by(musical_id=musical.id).all()
            musical.active_links = sum(1 for link in musical.links if link.is_available)
            musical.sold_out_links = len(musical.links) - musical.active_links
            
            last_change = MusicalChange.query.filter_by(
                musical_id=musical.id
            ).order_by(MusicalChange.changed_at.desc()).first()
            
            if last_change:
                musical.last_change_type = last_change.change_type
                musical.last_change_date = last_change.changed_at
        
        musicals = sorted(musicals, key=lambda x: x.updated_at or datetime.min, reverse=True)
        
        return render_template("shows.html", musicals=musicals)
    except Exception as e:
        app.logger.error(f"Error in /shows route: {e}")
        return render_template("shows.html", musicals=[])

# ==================== API ROUTES ====================
@app.route("/api/events")
def api_events():
    try:
        return jsonify(load_events())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/monitored-urls")
def api_monitored_urls():
    return jsonify(load_urls())

@app.route("/api/suggest-site", methods=["POST"])
def suggest_site():
    data = request.get_json(silent=True) or {}
    
    suggestion = {
        "siteName": data.get("siteName", ""),
        "siteUrl": data.get("siteUrl", ""),
        "reason": data.get("reason", ""),
        "timestamp": datetime.now(UTC).isoformat()
    }
    
    if not suggestion["siteName"] or not suggestion["siteUrl"]:
        return jsonify({"error": "siteName and siteUrl required"}), 400
    
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        suggestions = []
    
    suggestions.append(suggestion)
    
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    message = f"""🎭 Nueva sugerencia de musical

**{suggestion['siteName']}**
🔗 {suggestion['siteUrl']}

Razón: {suggestion['reason'] or 'No especificada'}

📅 {suggestion['timestamp']}"""
    
    notify_results = notify_all_channels(message, channel_type="suggestion")
    
    return jsonify({
        "ok": True,
        "suggestion": suggestion,
        "notifications": notify_results
    }), 201

# ==================== ADMIN ROUTES ====================
@app.route("/admin")
@require_auth
def admin_panel():
    return render_template("admin/panel.html")

@app.route("/admin/suggestions")
@require_auth
def admin_suggestions():
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        suggestions = []
    return render_template("admin/suggestions.html", suggestions=suggestions)

@app.route("/admin/monitoring-list")
@require_auth
def admin_monitoring_list():
    musicals = load_urls()
    grouped = group_urls_by_musical(musicals)
    return render_template("admin/monitoring_list.html", musicals=musicals, grouped=grouped)

@app.route("/admin/musicals")
@require_auth
def admin_musicals():
    musicals = Musical.query.all()
    return jsonify([m.to_dict() for m in musicals])

@app.route("/admin/check-now", methods=["POST"])
@require_auth
def admin_check_now():
    results = check_all_urls()
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
    
    return jsonify({
        "message": f"Test sent ({channel_type})",
        "results": results
    })

@app.route("/admin/suggestions/<int:idx>/approve", methods=["POST"])
@require_auth
def approve_suggestion(idx):
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        suggestions = []
    
    if idx >= len(suggestions):
        return jsonify({"error": "suggestion not found"}), 404
    
    sug = suggestions.pop(idx)
    name = (sug.get("siteName") or sug.get("musical") or "Sin nombre").strip()
    url = (sug.get("siteUrl") or sug.get("url") or "").strip()
    notes = sug.get("reason") or sug.get("message") or ""
    
    if not name or not url:
        return jsonify({"error": "invalid suggestion"}), 400
    
    musical = Musical.query.filter_by(name=name).first()
    
    if not musical:
        musical = Musical(name=name, description=notes)
        db.session.add(musical)
        db.session.flush()
        
        change = MusicalChange(
            musical_id=musical.id,
            change_type='created',
            description=f"Musical '{name}' creado desde sugerencia",
            changed_by='admin',
            extra_data=json.dumps({'source': 'suggestion'})
        )
        db.session.add(change)
    
    existing = MusicalLink.query.filter_by(musical_id=musical.id, url=url).first()
    if not existing:
        link = MusicalLink(musical_id=musical.id, url=url, notes=notes, status='active')
        db.session.add(link)
        
        change = MusicalChange(
            musical_id=musical.id,
            change_type='link_added',
            description=f"Enlace añadido: {url[:50]}...",
            changed_by='admin',
            extra_data=json.dumps({'url': url})
        )
        db.session.add(change)
        musical.updated_at = datetime.now(UTC)
    
    db.session.commit()
    
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
        suggestions = []
    
    if idx >= len(suggestions):
        return jsonify({"error": "suggestion not found"}), 404
    
    rejected = suggestions.pop(idx)
    
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    return jsonify({"ok": True, "rejected": rejected})

@app.route("/health")
def health():
    return jsonify({"ok": True, "time": datetime.now(UTC).isoformat()})

# ==================== SCHEDULER ====================
scheduler = BackgroundScheduler()
scheduler.add_job(check_all_urls, "interval", seconds=int(os.getenv('POLL_INTERVAL', '300')), id="monitor_job")
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