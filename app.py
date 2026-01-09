import os
import json
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, jsonify, send_from_directory, request, Response
from flask_socketio import SocketIO
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import hashlib
import difflib
import asyncio
import threading
import time
from models import db, Musical, MusicalLink, MusicalChange
from telegram import Bot
from telegram.ext import Application
import smtplib
import ssl
import random
import string
import re

# ==================== CONFIGURATION ====================
BASE = Path(__file__).parent

# File paths
STATIC_DIR = BASE / "static"
URLS_FILE = STATIC_DIR / "python" / "urls.json"
SUGGESTIONS_FILE = STATIC_DIR / "python" / "suggestions.json"
EVENTS_FILE = STATIC_DIR / "data" / "events.json"
SNAPSHOTS_FILE = STATIC_DIR / "data" / "snapshots.json"
EXCLUSIONS_FILE = STATIC_DIR / "data" / "exclusions.json"

# In-memory cache for resolved photo paths (key: requested lower-path -> actual relative path)
PHOTO_PATH_CACHE = {}

UTC = timezone.utc

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHANNEL_URL = os.getenv("TELEGRAM_CHANNEL_URL", "https://t.me/TheBookOfMormonTicketsbot")
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")
DISCORD_SERVER_URL = os.getenv("DISCORD_SERVER_URL", "https://discord.gg/dGxUQ8mM")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise RuntimeError(
        "SECURITY: ADMIN_PASSWORD environment variable is not set. "
        "Set a strong ADMIN_PASSWORD before starting the application."
    )
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')

# Configuration flags (safe defaults)
TELEGRAM_CONFIGURED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
DISCORD_CONFIGURED = bool(DISCORD_WEBHOOK_ALERTS or DISCORD_WEBHOOK_SUGGESTIONS)
SMTP_CONFIGURED = bool(SMTP_SERVER and SMTP_USERNAME and SMTP_PASSWORD and SENDER_EMAIL)
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
DATABASE_CONFIGURED = bool(DATABASE_URL)

if not TELEGRAM_CONFIGURED:
    print('⚠️  TELEGRAM not configured: notifications via Telegram will be disabled')
if not DISCORD_CONFIGURED:
    print('⚠️  DISCORD webhooks not configured: suggestion/alert webhooks will be disabled')
if not SMTP_CONFIGURED:
    print('⚠️  SMTP not configured: confirmation emails will be skipped')

# ==================== FLASK APP SETUP ====================
app = Flask(__name__,
           template_folder='templates',
           static_folder='static',
           static_url_path='/static')

db_url = os.getenv('DATABASE_URL', '').strip()
# Remove surrounding quotes if present (common issue with env vars)
db_url = db_url.strip('"').strip("'")

# Debug logging
print("=" * 60)
print("🔍 DATABASE CONFIGURATION")
print("=" * 60)
print(f"DATABASE_URL exists: {bool(db_url)}")
if db_url:
    # Mask password for logging
    safe_url = db_url
    if '@' in safe_url:
        parts = safe_url.split('@')
        if ':' in parts[0]:
            user_pass = parts[0].split(':')
            safe_url = f"{user_pass[0]}:****@{parts[1]}"
    print(f"DATABASE_URL (masked): {safe_url}")
    print(f"DB starts with 'postgres://': {db_url.startswith('postgres://')}")
    print(f"DB starts with 'postgresql://': {db_url.startswith('postgresql://')}")

if db_url:
    # Fix for Render/Heroku: postgres:// -> postgresql://
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        print("✅ Converted postgres:// to postgresql://")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    print("✅ Using PostgreSQL database")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE / 'musicals.db')
    print("⚠️  DATABASE_URL not found, using SQLite fallback")

print("=" * 60)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Validate SQLAlchemy URL to avoid parse errors on startup (Render deploys)
try:
    from sqlalchemy.engine.url import make_url
    candidate = app.config.get('SQLALCHEMY_DATABASE_URI')
    if candidate and isinstance(candidate, str) and candidate.startswith(('postgres://', 'postgresql://', 'mysql://')):
        try:
            make_url(candidate)
        except Exception as e:
            print(f"⚠️  Invalid DATABASE_URL detected: {e}")
            print("⚠️  Falling back to local SQLite for startup. Fix DATABASE_URL in environment.")
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE / 'musicals.db')
            try:
                os.environ.pop('DATABASE_URL', None)
            except Exception:
                pass
except Exception:
    # If sqlalchemy not available at this point, let init handle it
    pass

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")
Compress(app)

# Rate limiting: sensible defaults and key by remote address
# Allow configuring a persistent storage backend via `RATELIMIT_STORAGE_URL` (e.g. redis://...)
ratelimit_storage = os.getenv('RATELIMIT_STORAGE_URL') or os.getenv('REDIS_URL') or os.getenv('RATELIMIT_STORAGE')
# Emit rate limit headers so clients can see remaining quota
app.config['RATELIMIT_HEADERS_ENABLED'] = True

if ratelimit_storage:
    try:
        print(f"🔒 Using rate-limit storage backend: {ratelimit_storage}")
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=["200 per day", "50 per hour"],
            storage_uri=ratelimit_storage
        )
    except Exception as e:
        # If storage backend fails to initialize, fall back to in-memory but log the issue
        app.logger.warning(f"Could not initialize rate-limit storage '{ratelimit_storage}': {e}. Falling back to in-memory storage.")
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=["200 per day", "50 per hour"]
        )
else:
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"]
    )


# WSGI middleware to enforce security headers on ALL responses (includes static and socket responses)
class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def custom_start(status, headers, exc_info=None):
            try:
                # Prevent duplicate headers by using a dict-style set
                hdrs = {k.lower(): v for k, v in headers}
            except Exception:
                hdrs = {}

            # HSTS only when served over HTTPS (we cannot detect scheme reliably here, set conservatively)
            hdrs.setdefault('strict-transport-security', 'max-age=63072000; includeSubDomains; preload')
            hdrs.setdefault('x-content-type-options', 'nosniff')
            hdrs.setdefault('x-frame-options', 'DENY')
            hdrs.setdefault('referrer-policy', 'no-referrer-when-downgrade')
            hdrs.setdefault('x-xss-protection', '0')
            hdrs.setdefault('permissions-policy', "geolocation=(), microphone=()")

            # Minimal CSP — adjust later for external vendors
            hdrs.setdefault('content-security-policy', "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:;")

            # Convert back to list preserving original header order roughly
            new_headers = [(k, v) for k, v in headers if k.lower() not in hdrs]
            for k, v in hdrs.items():
                new_headers.append((k, v))

            return start_response(status, new_headers, exc_info)

        return self.app(environ, custom_start)


# Wrap the WSGI app so headers are always applied
app.wsgi_app = SecurityHeadersMiddleware(app.wsgi_app)

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
    if not TELEGRAM_CONFIGURED:
        app.logger.info('Telegram not configured; skipping telegram notification')
        return {"ok": False, "reason": "telegram-not-configured"}
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        app.logger.debug('Sending Telegram message via python-telegram-bot')
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message_text)
        app.logger.info('Telegram message sent (async)')
        return {"ok": True}
    except Exception as e:
        app.logger.warning(f"Async Telegram send failed: {e}; falling back to HTTP API")
        # Fallback to simple HTTP API call (synchronous) to avoid asyncio issues in some runtimes
        try:
            return _send_telegram_http(message_text)
        except Exception as ex:
            app.logger.error(f"Telegram fallback also failed: {ex}")
            return {"ok": False, "error": f"async_err:{e}; fallback_err:{ex}"}


def _send_telegram_http(message_text):
    """Synchronous HTTP fallback to Telegram sendMessage API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "reason": "telegram-not-configured"}
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message_text}
    try:
        r = requests.post(api, json=payload, timeout=8)
        try:
            data = r.json()
        except Exception:
            data = {"ok": False, "status_code": r.status_code, "text": r.text}
        if r.ok and data.get('ok'):
            app.logger.info('Telegram message sent (http fallback)')
            return {"ok": True, "result": data.get('result')}
        else:
            app.logger.error(f"Telegram API error: {data}")
            return {"ok": False, "error": data}
    except Exception as e:
        app.logger.error(f"HTTP Telegram request failed: {e}")
        raise

def send_discord_webhook(message_text, webhook_type="alert"):
    """Send notification via Discord webhook"""
    webhook_url = DISCORD_WEBHOOK_SUGGESTIONS if webhook_type == "suggestion" else DISCORD_WEBHOOK_ALERTS
    if not DISCORD_CONFIGURED or not webhook_url:
        app.logger.info('Discord webhook not configured; skipping discord notification')
        return {"ok": False, "reason": "discord-not-configured"}
    
    try:
        payload = {"content": message_text}
        r = requests.post(webhook_url, json=payload, timeout=6)
        return {"ok": r.ok}
    except Exception as e:
        app.logger.error(f"Discord error: {e}")
        return {"ok": False, "error": str(e)}


def _generate_discount_code(prefix='TM', length=6):
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}-{suffix}"


def _is_email(val):
    if not val: return False
    return bool(re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", val))


def send_confirmation_email(recipient_email, discount_code):
    """Send a simple confirmation email with discount code using SMTP.

    Requires environment variables: SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SENDER_EMAIL
    """
    if not (SMTP_SERVER and SMTP_USERNAME and SMTP_PASSWORD and SENDER_EMAIL):
        app.logger.warning('SMTP not configured; skipping confirmation email')
        return {'ok': False, 'reason': 'smtp-not-configured'}

    subject = 'Gracias por tu sugerencia — aquí tienes tu código de descuento'
    body = f"Hola!\n\nGracias por enviar una sugerencia. Aquí tienes tu código de descuento:\n\n{discount_code}\n\n¡Gracias!"
    message = f"From: {SENDER_EMAIL}\r\nTo: {recipient_email}\r\nSubject: {subject}\r\n\r\n{body}"

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls(context=context)
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, [recipient_email], message.encode('utf-8'))
        return {'ok': True}
    except Exception as e:
        app.logger.error(f"Error sending confirmation email: {e}")
        return {'ok': False, 'error': str(e)}

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
                # Process any entries that are flagged as suggestion-only:
                try:
                    def _process_suggestion_only_entries():
                        if not isinstance(data, list):
                            return
                        changed = False
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            if item.get('suggestion_only') and not item.get('sent_to_suggestions'):
                                # Build a friendly message
                                name = item.get('musical') or item.get('name') or item.get('siteName') or 'Suggestion'
                                urls = item.get('urls') or item.get('url') or []
                                if isinstance(urls, str):
                                    urls = [urls]
                                url = urls[0] if urls else ''
                                message = f"📨 Nueva sugerencia (importada): {name}\n{url}"
                                try:
                                    send_discord_webhook(message, webhook_type='suggestion')
                                    app.logger.info(f"Sent suggestion-only entry to Discord: {name} {url}")
                                except Exception as e:
                                    app.logger.warning(f"Failed sending suggestion-only entry to Discord: {e}")
                                item['sent_to_suggestions'] = True
                                changed = True
                        if changed:
                            try:
                                with URLS_FILE.open('w', encoding='utf-8') as wf:
                                    json.dump(data, wf, indent=2, ensure_ascii=False)
                                app.logger.info('Updated urls.json after processing suggestion-only entries')
                            except Exception as e:
                                app.logger.warning(f'Could not write urls.json: {e}')

                    _process_suggestion_only_entries()
                except Exception as e:
                    app.logger.warning(f"Error processing suggestion-only entries: {e}")
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


    # Security & caching headers for all responses
    @app.after_request
    def set_security_headers(response):
        try:
            # HSTS only when served over HTTPS
            if request.scheme == 'https':
                response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'

            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'
            response.headers['X-XSS-Protection'] = '0'

            # Minimal CSP — adjust for external vendors as needed
            csp = "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:;"
            response.headers['Content-Security-Policy'] = csp

            # Permissions policy (formerly feature-policy)
            response.headers['Permissions-Policy'] = "geolocation=(), microphone=()"

            # Cache policy: long cache for static assets, conservative for dynamic
            if request.path.startswith('/static/'):
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            else:
                # Default for API/dynamic responses
                response.headers.setdefault('Cache-Control', 'no-cache, no-store, must-revalidate')
        except Exception:
            pass
        return response

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


# Robust fotos handler: tries exact path first, then common case variants,
# then performs a case-insensitive filesystem scan (cached) and finally
# serves a placeholder if nothing is found. This helps on case-sensitive
# deployments where local filenames may differ in casing.
@app.route('/static/fotos/<path:relpath>')
def serve_foto(relpath):
    fotos_root = os.path.join(app.root_path, 'static', 'fotos')
    # Normalize relpath to forward slashes
    relpath_norm = relpath.replace('\\', '/')

    # Exact match first
    exact_path = os.path.join(fotos_root, relpath_norm)
    if os.path.exists(exact_path):
        app.logger.debug(f"Serving exact photo: {relpath_norm}")
        return send_from_directory(fotos_root, relpath_norm)

    key = relpath_norm.lower()
    # Cached resolution
    cached = PHOTO_PATH_CACHE.get(key)
    if cached:
        candidate = os.path.join(fotos_root, cached)
        if os.path.exists(candidate):
            app.logger.debug(f"Serving cached photo for {relpath_norm} -> {cached}")
            return send_from_directory(fotos_root, cached)
        else:
            PHOTO_PATH_CACHE.pop(key, None)

    # Try common folder/filename casing permutations
    parts = relpath_norm.split('/', 1)
    candidates = []
    if len(parts) == 2:
        folder, fname = parts
        candidates.extend([
            f"{folder}/{fname}",
            f"{folder.lower()}/{fname}",
            f"{folder.title()}/{fname}",
            f"{folder.upper()}/{fname}",
            f"{folder}/{fname.lower()}",
            f"{folder}/{fname.upper()}"
        ])
    else:
        candidates.extend([relpath_norm, relpath_norm.lower(), relpath_norm.upper()])

    for cand in candidates:
        cand_path = os.path.join(fotos_root, cand)
        if os.path.exists(cand_path):
            PHOTO_PATH_CACHE[key] = cand.replace('\\', '/')
            app.logger.debug(f"Resolved photo {relpath_norm} -> {cand}")
            return send_from_directory(fotos_root, cand)

    # Last resort: do a case-insensitive scan (expensive the first time)
    try:
        requested_lower = relpath_norm.lower()
        for root, dirs, files in os.walk(fotos_root):
            rel_root = os.path.relpath(root, fotos_root)
            for f in files:
                candidate_rel = os.path.join(rel_root, f) if rel_root != '.' else f
                candidate_rel_norm = candidate_rel.replace('\\', '/')
                if candidate_rel_norm.lower() == requested_lower:
                    PHOTO_PATH_CACHE[key] = candidate_rel_norm
                    app.logger.debug(f"Scanned and found photo {relpath_norm} -> {candidate_rel_norm}")
                    return send_from_directory(fotos_root, candidate_rel_norm)
    except Exception as e:
        app.logger.warning(f"Photo resolution scan failed: {e}")

    # If still not found, try to serve a placeholder if available
    placeholder = os.path.join(app.root_path, 'static', 'posters', 'placeholder.png')
    if os.path.exists(placeholder):
        app.logger.debug(f"Photo not found, serving placeholder for {relpath_norm}")
        return send_from_directory(os.path.join(app.root_path, 'static', 'posters'), 'placeholder.png')

    app.logger.debug(f"Photo not found: {relpath_norm}")
    return Response('Not found', status=404)


# Serve favicon (redirect to SVG placeholder)
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.svg', mimetype='image/svg+xml')
    except Exception:
        return Response(status=404)

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
                if hasattr(link, 'last_checked') and link.last_checked:
                    link_dict['last_checked'] = link.last_checked.isoformat()
                if hasattr(link, 'created_at') and link.created_at:
                    link_dict['created_at'] = link.created_at.isoformat()
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
@limiter.limit("10 per hour")
def api_suggest_site():
    """Endpoint para recibir sugerencias de musicales"""
    data = request.get_json(silent=True) or {}
    
    site_name = data.get("siteName", "").strip()
    site_url = data.get("siteUrl", "").strip()
    reason = data.get("reason", "No especificada").strip()
    contact = data.get("contact", "").strip()
    
    if not site_name or not site_url or not contact:
        return jsonify({"ok": False, "error": "siteName, siteUrl and contact are required"}), 400
    
    suggestion = {
        "siteName": site_name,
        "siteUrl": site_url,
        "reason": reason,
        "contact": contact,
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
        
        # Generate discount code for sender and attempt confirmation email
        discount_code = _generate_discount_code()
        suggestion['discount_code'] = discount_code

        # Send notifications to admins
        message = f"""🌟 Nueva sugerencia de musical

    **{suggestion['siteName']}**
    {suggestion['siteUrl']}

    Razón: {suggestion['reason']}
    Contacto: {suggestion.get('contact','-')}
    """
        send_discord_webhook(message, webhook_type="suggestion")

        # If contact looks like an email, send confirmation with discount code
        if contact and _is_email(contact):
            send_confirmation_email(contact, discount_code)

        return jsonify({"ok": True, "message": "Suggestion saved"})
    
    except Exception as e:
        app.logger.error(f"Error saving suggestion: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/check-now", methods=["POST"])
@require_auth
@limiter.limit("5 per hour")
def api_check_now():
    """Trigger manual check"""
    try:
        # Reuse the run-check logic via helper to keep behaviour consistent
        res = run_check_and_alert()
        return jsonify({"ok": True, "results": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _load_snapshots():
    try:
        if SNAPSHOTS_FILE.exists():
            with SNAPSHOTS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                # Normalize legacy format (url -> hash) to new format (url -> {hash, body})
                normalized = {}
                for k, v in (data.items() if isinstance(data, dict) else []):
                    if isinstance(v, dict):
                        normalized[k] = v
                    else:
                        normalized[k] = {'hash': v, 'body': None, 'last_checked': None}
                return normalized
    except Exception:
        pass
    return {}


def _save_snapshots(snap):
    try:
        SNAPSHOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SNAPSHOTS_FILE.open('w', encoding='utf-8') as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def run_check_and_alert():
    """Check monitored URLs, detect body-hash changes and send Telegram alerts.

    Returns a dict with per-URL status and whether a notification was sent.
    """
    results = []
    snapshots = _load_snapshots()

    # Build list of URLs to check from DB if possible, else from urls.json
    urls_to_check = []
    try:
        with app.app_context():
            musicals = Musical.query.all()
            if musicals:
                for m in musicals:
                    links = MusicalLink.query.filter_by(musical_id=m.id).all()
                    for ln in links:
                        urls_to_check.append({'musical': m.name, 'url': ln.url, 'source': 'db'})
    except Exception:
        pass
    # Also merge URLs from static/python/urls.json (avoid duplicates)
    if URLS_FILE.exists():
        try:
            with URLS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                existing_urls = {entry.get('url') for entry in urls_to_check if entry.get('url')}
                for item in data:
                    name = item.get('musical') or item.get('name') or item.get('siteName') or 'unknown'
                    urls = item.get('urls') or item.get('url') or []
                    if isinstance(urls, str):
                        urls = [urls]
                    for u in urls:
                        if u and u not in existing_urls:
                            urls_to_check.append({'musical': name, 'url': u, 'source': 'file'})
                            existing_urls.add(u)
        except Exception as e:
            app.logger.warning(f"Error reading {URLS_FILE}: {e}")

    # Log which URLs we will check (useful for Render logs)
    if not urls_to_check:
        app.logger.info("No monitored URLs found to check.")
    else:
        try:
            total = len(urls_to_check)
            # prepare a short preview of the first 20 entries
            preview_items = []
            for e in urls_to_check[:20]:
                m = e.get('musical') or 'unknown'
                u = e.get('url') or ''
                preview_items.append(f"{m}->{u}")
            preview_text = ", ".join(preview_items)
            more_text = f", ... (+{total-20} more)" if total > 20 else ""
            app.logger.info(f"Running check on {total} URLs. Preview: {preview_text}{more_text}")
        except Exception:
            app.logger.info("Running check on URLs (unable to build preview)")

    for entry in urls_to_check:
        url = entry.get('url')
        musical = entry.get('musical')
        try:
            r = requests.get(url, timeout=8)
            body = r.text or ''
            h = hashlib.sha256(body.encode('utf-8')).hexdigest()

            prev_entry = snapshots.get(url)
            prev_hash = None
            prev_body = None
            if isinstance(prev_entry, dict):
                prev_hash = prev_entry.get('hash')
                prev_body = prev_entry.get('body')
            elif isinstance(prev_entry, str):
                prev_hash = prev_entry

            changed = (prev_hash is not None and prev_hash != h)
            notified = False
            diff_snippet = None

            if changed:
                # try to compute a unified diff if we have previous body
                if prev_body is not None:
                    prev_lines = prev_body.splitlines()
                    curr_lines = body.splitlines()
                    diff_lines = list(difflib.unified_diff(prev_lines, curr_lines, fromfile='before', tofile='after', lineterm=''))
                    if diff_lines:
                        diff_text = '\n'.join(diff_lines)
                        # truncate to a safe size for messages and logs
                        max_chars = 1200
                        diff_snippet = diff_text if len(diff_text) <= max_chars else diff_text[:max_chars] + '\n... (truncated)'
                # send Telegram notification (sync via asyncio.run)
                msg = f"🔔 Cambio detectado en {musical}: {url}"
                if diff_snippet:
                    msg = msg + "\n\nDiff (truncated):\n" + diff_snippet

                try:
                    asyncio.run(send_telegram_notification_async(msg))
                    notified = True
                except Exception:
                    notified = False

                # Persist change to DB if possible
                try:
                    with app.app_context():
                        # Prefer to find a MusicalLink by URL
                        link = MusicalLink.query.filter_by(url=url).first()
                        if link:
                            old_val = (prev_body or '')[:20000]
                            new_val = (body or '')[:20000]
                            change = MusicalChange(
                                musical_id=link.musical_id,
                                change_type='page_diff',
                                url=url,
                                status_code=(r.status_code if 'r' in locals() and hasattr(r, 'status_code') else None),
                                notified=bool(notified),
                                diff_snippet=(diff_snippet or None),
                                old_value=old_val,
                                new_value=new_val,
                                created_at=datetime.now(UTC)
                            )
                            db.session.add(change)
                            # update last_checked on link
                            try:
                                link.last_checked = datetime.now(UTC)
                            except Exception:
                                pass
                            # Update musical's updated_at timestamp
                            try:
                                musical_obj = Musical.query.get(link.musical_id)
                                if musical_obj:
                                    musical_obj.updated_at = datetime.now(UTC)
                            except Exception:
                                pass
                            db.session.commit()
                            app.logger.info(f"Saved change to DB for musical_id={link.musical_id} url={url}")
                        else:
                            # Try to match by musical name
                            musical_obj = Musical.query.filter_by(name=musical).first()
                            if musical_obj:
                                old_val = (prev_body or '')[:20000]
                                new_val = (body or '')[:20000]
                                change = MusicalChange(
                                    musical_id=musical_obj.id,
                                    change_type='page_diff',
                                    url=url,
                                    status_code=(r.status_code if 'r' in locals() and hasattr(r, 'status_code') else None),
                                    notified=bool(notified),
                                    diff_snippet=(diff_snippet or None),
                                    old_value=old_val,
                                    new_value=new_val,
                                    created_at=datetime.now(UTC)
                                )
                                db.session.add(change)
                                # Update musical's updated_at timestamp
                                musical_obj.updated_at = datetime.now(UTC)
                                db.session.commit()
                                app.logger.info(f"Saved change to DB for musical (by name) id={musical_obj.id} url={url}")
                except Exception as e:
                    app.logger.warning(f"Could not persist change to DB for {url}: {e}")

            # store limited body to avoid unbounded snapshots sizes
            store_body = body if len(body) <= 20000 else body[:20000]
            snapshots[url] = {'hash': h, 'body': store_body, 'last_checked': datetime.now(UTC).isoformat()}

            results.append({'musical': musical, 'url': url, 'status_code': r.status_code, 'changed': changed, 'notified': notified, 'diff_snippet': diff_snippet})
        except Exception as e:
            results.append({'musical': musical, 'url': url, 'error': str(e), 'changed': False, 'notified': False})

    _save_snapshots(snapshots)
    return results

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


@app.route("/api/changes", methods=["GET"])
def api_get_changes():
    """Return recent MusicalChange rows for inspection.

    Query params:
      - limit (int): number of rows to return (default 20)
    """
    try:
        limit = int(request.args.get('limit', 20))
    except Exception:
        limit = 20

    with app.app_context():
        rows = MusicalChange.query.order_by(MusicalChange.created_at.desc()).limit(limit).all()
        out = []
        for r in rows:
            musical = None
            try:
                musical = Musical.query.get(r.musical_id)
            except Exception:
                musical = None
            out.append({
                'id': r.id,
                'musical_id': r.musical_id,
                'musical': musical.name if musical else None,
                'change_type': r.change_type,
                'url': getattr(r, 'url', None),
                'status_code': getattr(r, 'status_code', None),
                'notified': bool(getattr(r, 'notified', False)),
                'diff_snippet': (getattr(r, 'diff_snippet', None) or '')[:2000],
                'old_value': (r.old_value or '')[:2000],
                'new_value': (r.new_value or '')[:2000],
                'created_at': r.created_at.isoformat() if r.created_at else None
            })
        return jsonify(out)

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
        # Accept optional start/end query params (ISO date strings)
        start_q = request.args.get('start')
        end_q = request.args.get('end')
        from datetime import datetime
        start_dt = None
        end_dt = None
        if start_q:
            try:
                start_dt = datetime.fromisoformat(start_q)
            except Exception:
                start_dt = None
        if end_q:
            try:
                end_dt = datetime.fromisoformat(end_q)
            except Exception:
                end_dt = None

        events_out = []

        # Prefer events.json source if present
        if EVENTS_FILE.exists():
            raw = load_events()
            from datetime import datetime, timedelta
            for ev in raw:
                try:
                    ev_start = datetime.strptime(ev.get('start'), '%Y-%m-%d')
                    ev_end = datetime.strptime(ev.get('end'), '%Y-%m-%d')
                except Exception:
                    continue

                # expand daily occurrences
                cur = ev_start
                while cur <= ev_end:
                    # range filter
                    if start_dt and cur.date() < (start_dt.date() if hasattr(start_dt,'date') else start_dt):
                        cur = cur + timedelta(days=1)
                        continue
                    if end_dt and cur.date() > (end_dt.date() if hasattr(end_dt,'date') else end_dt):
                        break

                    date_str = cur.strftime('%Y-%m-%d')
                    events_out.append({
                        'id': f"{ev.get('id','e')}-{date_str}",
                        'title': ev.get('title') or ev.get('musical') or 'Evento',
                        'start': date_str,
                        'allDay': True,
                        'extendedProps': {
                            'musical': ev.get('musical'),
                            'location': ev.get('location'),
                            'description': ev.get('description'),
                            'image': ev.get('image'),
                            'url': ev.get('url'),
                            'type': ev.get('type')
                        }
                    })
                    cur = cur + timedelta(days=1)

            return jsonify(events_out)

        # Fallback: build from DB musicals (limited, requires link dates)
        musicals = Musical.query.all()
        for musical in musicals:
            musical_name = musical.name.lower()
            color = MUSICAL_COLORS.get(musical_name, '#95a5a6')
            css_class = 'event-' + musical_name.replace(' ', '-')
            for link in musical.links:
                # Attempt to use last_checked/created_at if no explicit date
                dt = None
                if hasattr(link, 'date') and getattr(link, 'date'):
                    dt = getattr(link, 'date')
                elif getattr(link, 'last_checked', None):
                    dt = getattr(link, 'last_checked')
                elif getattr(link, 'created_at', None):
                    dt = getattr(link, 'created_at')
                if not dt:
                    continue
                if start_dt and dt.date() < (start_dt.date() if hasattr(start_dt,'date') else start_dt):
                    continue
                if end_dt and dt.date() > (end_dt.date() if hasattr(end_dt,'date') else end_dt):
                    continue
                events_out.append({
                    'title': musical.name,
                    'start': dt.isoformat(),
                    'backgroundColor': color,
                    'borderColor': color,
                    'textColor': '#ffffff',
                    'classNames': [css_class],
                    'extendedProps': {
                        'musical': musical.name,
                        'url': link.url,
                        'isAvailable': link.is_available,
                        'image': (musical.images[0] if musical.images else None),
                        'description': f"{'✅ Disponible' if link.is_available else '❌ Agotado'}",
                        'location': 'N/A'
                    }
                })

        return jsonify(events_out)
    except Exception as e:
        print(f"❌ Error generating calendar events: {e}")
        return jsonify([]), 500


# Admin test endpoint for notifications (Telegram + Discord)
@app.route('/admin/test-telegram', methods=['GET', 'POST'])
@require_auth
def admin_test_telegram():
    """Endpoint to trigger a test notification to Telegram and Discord.

    Accepts optional JSON body {"message": "..."} for custom message.
    Returns a JSON object with the results for each provider.
    """
    try:
        payload = request.get_json(silent=True) or {}
        message = payload.get('message') if isinstance(payload, dict) else None
        if not message:
            message = f"Test notification from BOM Monitor — {datetime.now(UTC).isoformat()}"

        results = {}

        # Telegram (async helper)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                import asyncio
                tg_res = asyncio.run(send_telegram_notification_async(message))
                results['telegram'] = tg_res
            except Exception as e:
                results['telegram'] = {'ok': False, 'error': str(e)}
        else:
            results['telegram'] = {'ok': False, 'reason': 'telegram-not-configured'}

        # Discord (sync)
        try:
            dc_res = send_discord_webhook(message, webhook_type='alert')
            results['discord'] = dc_res
        except Exception as e:
            results['discord'] = {'ok': False, 'error': str(e)}

        # Emit via Socket.IO for UI feedback if needed
        try:
            socketio.emit('telegram_test', results)
        except Exception:
            pass

        return jsonify({'ok': True, 'results': results})
    except Exception as e:
        app.logger.error(f"Error in admin_test_telegram: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


# Simple health endpoint for Render and uptime checks
@app.route('/health', methods=['GET'])
def health_check():
    try:
        return jsonify({
            'ok': True,
            'time': datetime.now(UTC).isoformat(),
            'port_env': int(os.getenv('PORT', 0)),
            'monitor_interval': int(os.getenv('MONITOR_INTERVAL', '5'))
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    # Start background monitor thread if requested
    try:
        monitor_interval = int(os.getenv('MONITOR_INTERVAL', '5'))
    except Exception:
        monitor_interval = 5

    def _start_background_monitor():
        def _loop():
            app.logger.info(f"Background monitor started (interval={monitor_interval}s)")
            while True:
                try:
                    run_check_and_alert()
                except Exception as e:
                    app.logger.error(f"Background check error: {e}")
                time.sleep(monitor_interval)
        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    # Background monitor is opt-in. Set START_MONITOR=1 to enable background checks.
    if os.getenv('START_MONITOR', '0') == '1':
        app.logger.info('START_MONITOR=1 detected; starting background monitor')
        _start_background_monitor()
    else:
        app.logger.info('Background monitor disabled by default. Set START_MONITOR=1 to enable.')
    socketio.run(app, debug=False, host='0.0.0.0', port=port)