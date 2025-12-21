import os
import json
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, jsonify, send_from_directory, request, Response
from flask_socketio import SocketIO
import requests
from models import db, Musical, MusicalLink, MusicalChange
from telegram import Bot
from telegram.ext import Application

# ==================== CONFIGURATION ====================
BASE = Path(__file__).parent

# File paths
STATIC_DIR = BASE / "static"
URLS_FILE = STATIC_DIR / "python" / "urls.json"
SUGGESTIONS_FILE = STATIC_DIR / "python" / "suggestions.json"
EVENTS_FILE = STATIC_DIR / "data" / "events.json"
EXCLUSIONS_FILE = STATIC_DIR / "data" / "exclusions.json"

UTC = timezone.utc

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHANNEL_URL = os.getenv("TELEGRAM_CHANNEL_URL", "https://t.me/TheBookOfMormonTicketsbot")
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")
DISCORD_SERVER_URL = os.getenv("DISCORD_SERVER_URL", "https://discord.gg/dGxUQ8mM")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# ==================== FLASK APP SETUP ====================
app = Flask(__name__,
           template_folder='templates',
           static_folder='static',
           static_url_path='/static')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE / 'musicals.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

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

async def send_telegram_notification_async(message_text):
    """Send notification via Telegram (async version for v20+)"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "reason": "telegram-not-configured"}
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_text)
        return {"ok": True}
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

def load_exclusions():
    """Load exclusions from JSON file"""
    try:
        if not EXCLUSIONS_FILE.exists():
            print(f"⚠️  Exclusions file not found: {EXCLUSIONS_FILE}")
            return {}
        
        with EXCLUSIONS_FILE.open('r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print("⚠️  Exclusions file is empty")
                return {}
            
            exclusions = json.loads(content)
            print(f"✅ Loaded exclusions for {len(exclusions)} musicals")
            return exclusions
            
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing exclusions.json: {e}")
        return {}
    except Exception as e:
        print(f"❌ Error loading exclusions: {e}")
        return {}

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

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/static/fotos/posters/<filename>')
def serve_poster(filename):
    """Serve poster images"""
    posters_dir = os.path.join(app.root_path, 'static', 'fotos', 'posters')
    return send_from_directory(posters_dir, filename)

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

@app.route("/api/calendar-events", methods=["GET"])
def api_calendar_events():
    """Get events formatted for FullCalendar, with custom exclusions"""
    from datetime import datetime, timedelta
    
    events = load_events()
    exclusions = load_exclusions()
    
    # Debug: verificar que los eventos tienen imagen y URL
    print(f"📊 Cargando {len(events)} eventos base")
    for evt in events[:3]:  # Mostrar primeros 3
        print(f"  - {evt.get('title')}: image={evt.get('image')}, url={evt.get('url')}")
    
    # Transform to FullCalendar format
    calendar_events = []
    
    for event in events:
        start_date = datetime.strptime(event.get('start'), '%Y-%m-%d')
        end_date = datetime.strptime(event.get('end'), '%Y-%m-%d')
        
        musical_name = event.get('musical', '').lower()
        musical_exclusions = exclusions.get(musical_name, {})
        
        # Get exclusion rules
        exclude_dates = set(musical_exclusions.get('exclude_dates', []))
        include_mondays = set(musical_exclusions.get('include_mondays', []))
        only_dates = musical_exclusions.get('only_dates', None)
        
        # Determine color class
        if 'wicked' in musical_name:
            class_name = 'event-wicked'
        elif 'book of mormon' in musical_name:
            class_name = 'event-book-mormon'
        elif 'misérables' in musical_name or 'miserables' in musical_name:
            class_name = 'event-les-miserables'
        elif 'rey león' in musical_name or 'rey leon' in musical_name:
            class_name = 'event-rey-leon'
        elif 'houdini' in musical_name:
            class_name = 'event-houdini'
        elif 'cabaret' in musical_name:
            class_name = 'event-cabaret'
        elif 'cenicienta' in musical_name:
            class_name = 'event-cenicienta'
        elif 'rent' in musical_name:
            class_name = 'event-rent'
        elif 'six' in musical_name:
            class_name = 'event-six'
        else:
            class_name = 'event-default'
        
        # Generate daily events
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            is_monday = current_date.weekday() == 0
            
            should_include = False
            
            # Check if musical has "only_dates" rule
            if only_dates is not None:
                should_include = date_str in only_dates
            else:
                # Normal logic: exclude Mondays unless specified
                if is_monday:
                    should_include = date_str in include_mondays
                else:
                    should_include = date_str not in exclude_dates
            
            if should_include:
                # IMPORTANTE: Incluir todos los campos del evento original
                calendar_event = {
                    'id': f"{event.get('id')}-{current_date.strftime('%Y%m%d')}",
                    'title': event.get('title', event.get('musical', 'Sin título')),
                    'start': date_str,
                    'allDay': True,
                    'className': class_name,
                    'extendedProps': {
                        'musical': event.get('musical', ''),
                        'location': event.get('location', ''),
                        'description': event.get('description', ''),
                        'image': event.get('image', ''),
                        'url': event.get('url', ''),
                        'type': event.get('type', '')
                    }
                }
                calendar_events.append(calendar_event)
            
            # Move to next day
            current_date += timedelta(days=1)
    
    print(f"✅ Generated {len(calendar_events)} calendar events")
    
    # Debug: verificar primer evento generado
    if calendar_events:
        sample = calendar_events[0]
        print(f"🔍 Primer evento: {sample['title']}")
        print(f"   - image: {sample['extendedProps'].get('image')}")
        print(f"   - url: {sample['extendedProps'].get('url')}")
    
    return jsonify(calendar_events)

# Definir colores para cada musical
MUSICAL_COLORS = {
    'wicked': '#2ecc71',                    # Verde
    'the book of mormon': '#e74c3c',        # Rojo
    'les misérables': '#3498db',            # Azul
    'el rey león': '#f39c12',               # Naranja/Amarillo
    'cabaret': '#34495e',                   # Gris oscuro
    'houdini': '#e67e22',                   # Naranja oscuro
    'cenicienta': '#ec407a',                # Rosa
    'oliver twist': '#78909c',              # Gris azulado
    'raffaella': '#ab47bc',                 # Morado
    'los pilares de la tierra': '#26a69a',  # Verde azulado
}

@app.route('/api/calendar-events')
def get_calendar_events():
    """Obtener eventos del calendario con colores específicos"""
    try:
        musicals = Musical.query.all()
        events = []
        
        for musical in musicals:
            musical_name = musical.name.lower()
            
            # Obtener color específico del musical
            color = MUSICAL_COLORS.get(musical_name, '#95a5a6')  # Gris por defecto
            
            # Obtener clase CSS para el musical
            css_class = 'event-' + musical_name.replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            
            for link in musical.links:
                event = {
                    'title': musical.name,
                    'start': link.date.isoformat() if link.date else datetime.now().isoformat(),
                    'backgroundColor': color,
                    'borderColor': color,
                    'textColor': '#ffffff',
                    'classNames': [css_class],  # ← Clase CSS para aplicar estilos
                    'extendedProps': {
                        'musical': musical.name,
                        'url': link.url,
                        'isAvailable': link.is_available,
                        'image': musical.images[0] if musical.images else None,
                        'description': f"{'✅ Disponible' if link.is_available else '❌ Agotado'}",
                        'location': 'Madrid'
                    }
                }
                events.append(event)
        
        return jsonify(events)
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify([]), 500

# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)