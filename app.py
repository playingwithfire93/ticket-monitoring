import os
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
import json
import requests
from models import db, Musical, MusicalLink, MusicalChange

# ==================== CONFIGURATION ====================
BASE = Path(__file__).parent

# File paths
STATIC_DIR = BASE / "static"
URLS_FILE = STATIC_DIR / "python" / "urls.json"
SUGGESTIONS_FILE = STATIC_DIR / "python" / "suggestions.json"
EVENTS_FILE = BASE / "events.json"

UTC = timezone.utc

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHANNEL_URL = os.getenv("TELEGRAM_CHANNEL_URL", "https://t.me/TheBookOfMormonTicketsbot")
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")
DISCORD_SERVER_URL = os.getenv("DISCORD_SERVER_URL", "https://discord.gg/YHCs5T79")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# ==================== FLASK APP SETUP ====================
app = Flask(__name__,
           template_folder='templates',
           static_folder='static',
           static_url_path='/static')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE / 'musicals.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Log configuration
print("=" * 60)
print("🔍 FILE STRUCTURE CHECK")
print("=" * 60)
print(f"📁 BASE: {BASE}")
print(f"📁 Templates: {app.template_folder}")
print(f"📁 Static: {app.static_folder}")
print(f"✅ Templates exist: {os.path.exists(BASE / 'templates')}")
print(f"✅ Static exist: {os.path.exists(BASE / 'static')}")
print(f"✅ CSS exists: {os.path.exists(BASE / 'static' / 'css' / 'style.css')}")
print(f"✅ JS exists: {os.path.exists(BASE / 'static' / 'js' / 'main.js')}")
print("=" * 60)

# ==================== HELPER FUNCTIONS (BEFORE ROUTES) ====================
def require_auth(f):
    """Decorator for admin authentication"""
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

def load_events():
    """Load events from JSON file"""
    try:
        with EVENTS_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def send_telegram_notification(message_text):
    """Send notification via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "reason": "telegram-not-configured"}
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message_text}
        r = requests.post(url, json=payload, timeout=6)
        return {"ok": r.ok}
    except Exception as e:
        app.logger.error(f"Telegram error: {e}")
        return {"ok": False, "error": str(e)}

def send_discord_webhook(message_text, webhook_type="alert"):
    """Send notification via Discord webhook"""
    webhook_url = DISCORD_WEBHOOK_SUGGESTIONS if webhook_type == "suggestion" else DISCORD_WEBHOOK_ALERTS
    
    if not webhook_url:
        return {"ok": False, "reason": "discord-not-configured"}
    
    try:
        payload = {"content": message_text}
        r = requests.post(webhook_url, json=payload, timeout=6)
        return {"ok": r.ok}
    except Exception as e:
        app.logger.error(f"Discord error: {e}")
        return {"ok": False, "error": str(e)}

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
        
        # Auto-migrate from urls.json if database is empty
        musical_count = Musical.query.count()
        if musical_count == 0 and URLS_FILE.exists():
            app.logger.info("Database is empty, attempting to load from urls.json...")
            try:
                with URLS_FILE.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                
                app.logger.info(f"Found {len(data)} musicals in urls.json")
                
                # Handle list format
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            musical_name = item.get('musical') or item.get('name') or item.get('siteName')
                            urls = item.get('urls') or item.get('url') or []
                            
                            if isinstance(urls, str):
                                urls = [urls]
                            
                            if musical_name and urls:
                                musical = Musical(
                                    name=musical_name,
                                    description=f"Musical: {musical_name}",
                                    created_at=datetime.now(timezone.utc),
                                    updated_at=datetime.now(timezone.utc)
                                )
                                db.session.add(musical)
                                db.session.flush()
                                
                                for url in urls:
                                    if isinstance(url, str):
                                        link = MusicalLink(
                                            musical_id=musical.id,
                                            url=url,
                                            created_at=datetime.now(timezone.utc),
                                            last_checked=datetime.now(timezone.utc)
                                        )
                                        db.session.add(link)
                                
                                db.session.commit()
                
                app.logger.info(f"✅ Successfully loaded musicals from urls.json")
            except Exception as e:
                app.logger.error(f"Error loading urls.json: {e}")
                db.session.rollback()
            
    except Exception as e:
        app.logger.error(f"Database initialization error: {e}")

# ==================== ROUTES ====================
@app.route("/")
def index():
    """Página principal con el dashboard"""
    with app.app_context():
        musicals = Musical.query.all()
        
        # Prepare data for each musical
        for musical in musicals:
            musical.links = MusicalLink.query.filter_by(musical_id=musical.id).all()
            # Check if is_available attribute exists
            if musical.links and hasattr(musical.links[0], 'is_available'):
                musical.active_links = sum(1 for link in musical.links if link.is_available)
                musical.sold_out_links = len(musical.links) - musical.active_links
            else:
                musical.active_links = len(musical.links)
                musical.sold_out_links = 0
        
        return render_template(
            'index.html',
            musicals=musicals,
            telegram_url=TELEGRAM_CHANNEL_URL,
            discord_url=DISCORD_SERVER_URL
        )

@app.route("/shows")
def shows():
    """Página de cartelera de musicales"""
    with app.app_context():
        musicals = Musical.query.all()
        for musical in musicals:
            musical.links = MusicalLink.query.filter_by(musical_id=musical.id).all()
        return render_template('shows.html', musicals=musicals)

@app.route("/calendar")
def calendar():
    """Página de calendario de eventos"""
    events = load_events()
    return render_template('calendar.html', events=events)

@app.route("/admin")
@require_auth
def admin():
    """Panel de administración"""
    with app.app_context():
        musicals = Musical.query.all()
        for musical in musicals:
            musical.links = MusicalLink.query.filter_by(musical_id=musical.id).all()
        return render_template('admin.html', musicals=musicals)

# ==================== API ENDPOINTS ====================
@app.route("/api/musicals", methods=["GET"])
def api_get_musicals():
    """Get all musicals with their links"""
    with app.app_context():
        musicals = Musical.query.all()
        result = []
        for musical in musicals:
            links = MusicalLink.query.filter_by(musical_id=musical.id).all()
            
            # Build links data
            links_data = []
            for link in links:
                link_dict = {'url': link.url}
                if hasattr(link, 'is_available'):
                    link_dict['is_available'] = link.is_available
                else:
                    link_dict['is_available'] = True
                links_data.append(link_dict)
            
            musical_dict = {
                'id': musical.id,
                'name': musical.name,
                'links': links_data
            }
            
            # Add optional fields if they exist
            if hasattr(musical, 'description'):
                musical_dict['description'] = musical.description
            if hasattr(musical, 'is_available'):
                musical_dict['is_available'] = musical.is_available
            if hasattr(musical, 'updated_at') and musical.updated_at:
                musical_dict['updated_at'] = musical.updated_at.isoformat()
                
            result.append(musical_dict)
        
        return jsonify(result)

@app.route("/api/suggest-site", methods=["POST"])
def api_suggest_site():
    """Endpoint para recibir sugerencias de musicales"""
    data = request.get_json(silent=True) or {}
    
    site_name = data.get("siteName", "").strip()
    site_url = data.get("siteUrl", "").strip()
    reason = data.get("reason", "No especificada").strip()
    
    if not site_name or not site_url:
        return jsonify({"ok": False, "error": "siteName and siteUrl are required"}), 400
    
    suggestion = {
        "siteName": site_name,
        "siteUrl": site_url,
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat()
    }
    
    # Save to file
    try:
        suggestions = []
        if SUGGESTIONS_FILE.exists():
            with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
                suggestions = json.load(f)
        
        suggestions.append(suggestion)
        
        # Ensure directory exists
        SUGGESTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        
        # Send notifications
        message = f"""🌟 Nueva sugerencia de musical

**{suggestion['siteName']}**
{suggestion['siteUrl']}

Razón: {suggestion['reason']}
"""
        
        send_telegram_notification(message)
        send_discord_webhook(message, webhook_type="suggestion")
        
        return jsonify({"ok": True, "message": "Suggestion saved"})
    
    except Exception as e:
        app.logger.error(f"Error saving suggestion: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/check-now", methods=["POST"])
@require_auth
def api_check_now():
    """Trigger manual check"""
    try:
        # Tu lógica de verificación aquí
        return jsonify({"ok": True, "message": "Check initiated"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)