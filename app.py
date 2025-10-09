from datetime import datetime, timezone
from pathlib import Path
import json
import os
import requests
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
from functools import wraps

BASE = Path(__file__).parent
URLS_FILE = BASE / "urls.json"
SUGGESTIONS_FILE = BASE / "suggestions.json"
EVENTS_FILE = BASE / "events.json"
UTC = timezone.utc

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Admin authentication decorator
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
    """Return dict {musical_name: [url,...]}"""
    grouped = {}
    for item in urls_list:
        name = item.get("musical") or item.get("name") or "Sin nombre"
        grouped.setdefault(name, []).extend(item.get("urls", []) or [])
    return grouped


def save_suggestion(suggestion):
    try:
        if SUGGESTIONS_FILE.exists():
            with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
                suggestions = json.load(f)
        else:
            suggestions = []
    except Exception:
        suggestions = []
    suggestions.append(suggestion)
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)


@app.route("/")
def index():
    musicals = load_urls()
    grouped = group_urls_by_musical(musicals)
    return render_template("index.html", musicals=musicals, grouped_urls=grouped)

@app.route("/api/monitored-urls")
def api_monitored_urls():
    """Return raw list for debugging/JS consumption."""
    return jsonify(load_urls())


@app.route("/api/monitored-status")
def api_monitored_status():
    """
    Optionally perform a simple GET for each url and return status.
    This is synchronous and intended for manual use / small lists.
    """
    results = []
    for item in load_urls():
        musical = item.get("musical", "")
        for url in item.get("urls", []):
            try:
                r = requests.get(url, timeout=8)
                status = f"{r.status_code}"
            except Exception as e:
                status = f"err: {str(e)}"
            results.append({
                "musical": musical,
                "url": url,
                "status": status,
                "checked_at": datetime.now(UTC).isoformat()
            })
    return jsonify(results)


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


@app.route("/api/suggest-site", methods=["POST"])
def suggest_site():
    data = request.get_json(silent=True) or {}
    site_name = (data.get("siteName") or data.get("site_name") or "").strip()
    site_url = (data.get("siteUrl") or data.get("site_url") or "").strip()
    reason = (data.get("reason") or "").strip()
    if not site_name or not site_url:
        return jsonify({"error": "Nombre y URL obligatorios"}), 400
    if not site_url.startswith(("http://", "https://")):
        return jsonify({"error": "URL debe empezar con http:// o https://"}), 400

    suggestion = {
        "siteName": site_name,
        "siteUrl": site_url,
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    save_suggestion(suggestion)

    # optional: emit event for admin UI via socketio
    try:
        socketio.emit("new_suggestion", suggestion, namespace="/admin")
    except Exception:
        pass

    return jsonify({"success": True})


# small helper to reload urls file via HTTP (admin)
@app.route("/admin/reload-urls", methods=["POST"])
@require_auth
def reload_urls():
    # simply attempt to load; return basic result
    loaded = load_urls()
    return jsonify({"loaded": len(loaded)})


# Simple Telegram sender helper (uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env)
TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')

_last_sent = {'ts': 0, 'msg': None}
_MIN_INTERVAL = 3.0  # seconds between identical messages

def send_telegram_message(text):
    if not TG_TOKEN or not TG_CHAT:
        app.logger.warning('Telegram not configured: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing')
        return {'ok': False, 'reason': 'not-configured'}

    now = time.time()
    if now - _last_sent['ts'] < _MIN_INTERVAL and _last_sent['msg'] == text:
        app.logger.info('Telegram rate limit: skipping duplicate message')
        return {'ok': False, 'reason': 'rate-limited'}

    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    payload = {'chat_id': TG_CHAT, 'text': text, 'parse_mode': 'HTML'}
    try:
        r = requests.post(url, json=payload, timeout=8)
        try:
            data = r.json()
        except Exception:
            data = {'raw_text': r.text}
        app.logger.info('Telegram send: status=%s resp=%s', r.status_code, data)
        if not r.ok or not data.get('ok', False):
            return {'ok': False, 'status_code': r.status_code, 'resp': data}
        _last_sent['ts'] = now
        _last_sent['msg'] = text
        return data
    except Exception as e:
        app.logger.exception('Exception when sending Telegram message')
        return {'ok': False, 'reason': str(e)}

@app.route('/admin/test-telegram', methods=['POST'])
@require_auth
def admin_test_telegram():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    # accept either TELEGRAM_CHAT or TELEGRAM_CHAT_ID (Render shows TELEGRAM_CHAT_ID)
    chat = os.getenv('TELEGRAM_CHAT') or os.getenv('TELEGRAM_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID'.upper())
    if not token or not chat:
        return jsonify({
            'ok': False,
            'error': 'Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT (or TELEGRAM_CHAT_ID) env vars',
            'found_token': bool(token),
            'found_chat': bool(chat)
        }), 400

    body = request.get_json(silent=True) or {}
    text = body.get('text', 'Test desde Ticket Monitor ✅')

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
        res = requests.post(url, json={'chat_id': chat, 'text': text}, timeout=10)
        res.raise_for_status()
        return jsonify({'ok': True, 'result': res.json()})
    except requests.RequestException as e:
        # include response body/status if available
        resp = getattr(e, 'response', None)
        return jsonify({
            'ok': False,
            'error': str(e),
            'status_code': resp.status_code if resp is not None else None,
            'response_text': resp.text if resp is not None else None
        }), 500

# Monitor state (persist last seen content hashes + body)
MONITOR_STATE_FILE = BASE / "monitor_state.json"
try:
    if MONITOR_STATE_FILE.exists():
        with MONITOR_STATE_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        # support legacy format where values were plain hash strings
        _prev_hashes = {}
        if isinstance(raw, dict):
            for url, val in raw.items():
                if isinstance(val, str):
                    _prev_hashes[url] = {"hash": val, "body": ""}
                elif isinstance(val, dict) and "hash" in val:
                    # keep existing structure
                    _prev_hashes[url] = {"hash": val.get("hash"), "body": val.get("body", "")}
    else:
        _prev_hashes = {}
except Exception:
    _prev_hashes = {}

def _save_state():
    try:
        # persist mapping url -> {hash, body}
        with MONITOR_STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(_prev_hashes, f, ensure_ascii=False, indent=2)
    except Exception:
        app.logger.exception("Could not save monitor state")

def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

# Try to reuse BoMtickets helpers (non-mandatory)
try:
    import BoMtickets as bm
except Exception:
    bm = None

# JSON-style Telegram alert (image optional) — match BoMtickets format
def send_telegram_json_alert(url, changes_text, timestamp=None, image_path=None):
    """
    Send a Telegram notification that mirrors the JSON-format used in BoMtickets.
    Sends image (if provided) via sendPhoto, then a pretty-printed JSON message
    inside a Markdown code block.
    """
    if not TG_TOKEN or not TG_CHAT:
        app.logger.warning('Telegram not configured for JSON alert')
        return {'ok': False, 'reason': 'not-configured'}

    # 1) try to send image first (ignore failures)
    if image_path:
        try:
            photo_url = f'https://api.telegram.org/bot{TG_TOKEN}/sendPhoto'
            if os.path.exists(image_path):
                with open(image_path, 'rb') as imgf:
                    files = {'photo': imgf}
                    data = {'chat_id': TG_CHAT}
                    requests.post(photo_url, data=data, files=files, timeout=15)
        except Exception:
            app.logger.debug('send_telegram_json_alert: sending photo failed', exc_info=True)

    # 2) prepare JSON payload and send as pretty-printed code block
    payload = {
        "type": "ticket_alert",
        "url": url,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "changes_truncated": (changes_text or "")[:3900],
        "changes_full_length": len(changes_text or "")
    }
    msg = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"

    send_url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        r = requests.post(send_url, json={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'Markdown'}, timeout=8)
        try:
            return r.json()
        except Exception:
            return {'ok': r.ok, 'status_code': r.status_code, 'text': r.text}
    except Exception as e:
        app.logger.exception('send_telegram_json_alert failed')
        return {'ok': False, 'reason': str(e)}

def send_telegram_pretty_alert(url, changes, timestamp=None, image_path=None):
    """
    Send a Telegram alert that matches the attached screenshot:
      - Send photo (if available)
      - Send a nicely formatted HTML message:
          🎭 <b>Ticket Alert!</b>
          🌐 URL: <a href="...">...</a>
          ⏱ Cambio detectado: ...
          📄 Cambios:
          <pre>...diff...</pre>
    Truncates the changes to fit Telegram limits and marks truncation.
    """
    if not TG_TOKEN or not TG_CHAT:
        app.logger.warning('Telegram not configured: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing')
        return {'ok': False, 'reason': 'not-configured'}

    ts = timestamp or datetime.now(UTC).isoformat()
    # Telegram message max ~4096 chars; reserve some room for other text
    MAX_PAYLOAD = 3800
    changes = changes or ""
    truncated = changes if len(changes) <= MAX_PAYLOAD else changes[:MAX_PAYLOAD] + "\n\n...[truncated]"

    # Escape for HTML, but keep pre block to preserve diff formatting
    escaped_url = _html.escape(url or "")
    escaped_changes = _html.escape(truncated)

    # Build message in HTML
    html_msg = (
        "🎭 <b>Ticket Alert!</b>\n"
        f"🌐 URL: <a href=\"{escaped_url}\">{escaped_url}</a>\n"
        f"⏱ Cambio detectado: {_html.escape(ts)}\n"
        "📄 Cambios:\n"
        f"<pre>{escaped_changes}</pre>"
    )

    # 1) Send image first (ignore failures)
    if image_path:
        try:
            if os.path.exists(image_path):
                photo_url = f'https://api.telegram.org/bot{TG_TOKEN}/sendPhoto'
                with open(image_path, 'rb') as ph:
                    files = {'photo': ph}
                    data = {'chat_id': TG_CHAT}
                    # Don't rely on caption (could be truncated); send message separately
                    requests.post(photo_url, data=data, files=files, timeout=12)
        except Exception:
            app.logger.debug('send_telegram_pretty_alert: sending photo failed', exc_info=True)

    # 2) Send formatted message (HTML)
    send_url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        r = requests.post(send_url, json={'chat_id': TG_CHAT, 'text': html_msg, 'parse_mode': 'HTML'}, timeout=10)
        try:
            data = r.json()
        except Exception:
            data = {'status_code': r.status_code, 'text': r.text}
        app.logger.info('Telegram pretty send: status=%s', r.status_code)
        return {'ok': r.ok, 'resp': data}
    except Exception as e:
        app.logger.exception('send_telegram_pretty_alert failed')
        return {'ok': False, 'reason': str(e)}

def check_all_urls(send_notifications=True):
    """Fetch all monitored URLs, detect content changes and notify."""
    app.logger.debug("Running check_all_urls")
    changes = []
    for item in load_urls():
        musical = item.get("musical") or item.get("name") or "Sin nombre"
        for url in item.get("urls", []) or []:
            try:
                r = requests.get(url, timeout=10)
                body = r.text or ""
                h = _hash_text(body)
            except Exception as e:
                app.logger.warning("Error fetching %s: %s", url, e)
                body = ""
                h = None

            prev_entry = _prev_hashes.get(url)
            prev_hash = prev_entry.get("hash") if prev_entry else None

            if h is None:
                continue

            if prev_entry is None:
                # first time: store hash + body
                _prev_hashes[url] = {"hash": h, "body": body}
                continue

            if prev_hash != h:
                # compute diff between previous body and current body
                prev_body = prev_entry.get("body", "") or ""
                diff_lines = list(difflib.unified_diff(
                    prev_body.splitlines(), body.splitlines(),
                    fromfile='before', tofile='after', lineterm=''
                ))
                changes_text = "\n".join(diff_lines).strip()
                if not changes_text:
                    # fallback if diff generator produced nothing
                    changes_text = "Contenido cambiado (no se pudo generar diff)."

                # update stored state
                _prev_hashes[url] = {"hash": h, "body": body}

                change = {
                    "musical": musical,
                    "url": url,
                    "when": datetime.now(UTC).isoformat()
                }
                changes.append(change)
                try:
                    socketio.emit("monitor_change", change, namespace="/")
                except Exception:
                    app.logger.exception("socketio emit failed")

                if send_notifications:
                    # try to get image asset from BoMtickets module (if available)
                    image_path = None
                    try:
                        if bm and hasattr(bm, 'get_alert_assets'):
                            sp, ip = bm.get_alert_assets(url)
                            image_path = ip if ip and os.path.exists(ip) else None
                    except Exception:
                        image_path = None

                    # fallback: choose a random matching image from static/
                    if not image_path:
                        try:
                            image_path = get_random_musical_image(musical)
                            if image_path and not os.path.exists(image_path):
                                image_path = None
                        except Exception:
                            image_path = None

                    # send Telegram pretty alert with the diff text
                    try:
                        send_telegram_pretty_alert(url, changes_text, timestamp=change["when"], image_path=image_path)
                    except Exception:
                        app.logger.exception("Failed to send Telegram pretty alert")

                    # send same payload to Discord alerts webhook if configured
                    try:
                        send_discord_json_alert(url, changes_text, timestamp=change["when"])
                    except Exception:
                        app.logger.exception("Discord notify failed")

    if changes:
        _save_state()
    return {"checked": True, "changes": len(changes), "details": changes}

# admin endpoint to force a check now (useful for testing)
@app.route("/admin/check-now", methods=["POST"])
@require_auth
def admin_check_now():
    res = check_all_urls(send_notifications=True)
    return jsonify(res)

# background scheduler to run periodic checks
POLL_INTERVAL_SECONDS = 30  # was 5, increase to 30 (or 60) to avoid overlapping job runs
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: check_all_urls(send_notifications=True), "interval", seconds=POLL_INTERVAL_SECONDS, id="monitor_job")
scheduler.start()

# >>> Removed duplicate imports and duplicate /api/monitored-urls route that caused Flask AssertionError.
# The api_monitored_urls route is already defined above; keeping only the first definition.

import os, requests
from flask import request, jsonify

# Replace existing /suggest handler (SendGrid) with this Gmail/SMTP version
@app.route('/suggest', methods=['POST'])
def suggest_smtp():
    """
    Unified /suggest handler:
      - Try Slack webhook (if configured)
      - Then Discord suggestions webhook (if configured)
      - If none succeeded, fall back to SMTP using env vars
    """
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    sender = (data.get('email') or '').strip() or os.getenv('SUGGEST_SMTP_USER') or f'no-reply@{os.getenv("HOSTNAME","local")}'
    message_body = (data.get('message') or '').strip()
    musical = (data.get('musical') or '').strip()
    url = (data.get('url') or '').strip()

    if not message_body:
        return jsonify({'ok': False, 'error': 'message required'}), 400

    remote = request.remote_addr
    timestamp = datetime.now(UTC).isoformat()
    payload_text = (
        f"*Nueva sugerencia* · {timestamp}\n"
        f"Nombre: {name or '—'}\n"
        f"Email: {sender or '—'}\n"
        f"Musical: {musical or '—'}\n"
        f"Link: {url or '—'}\n\n"
        f"Mensaje:\n{message_body}\n\n"
        f"_IP: {remote}_"
    )

    sent_via = []

    # Try Discord suggestions webhook
    try:
        if DISCORD_WEBHOOK_SUGGESTIONS:
            resd = send_discord_suggestion(payload_text)
            if resd.get("ok"):
                sent_via.append("discord")
    except Exception:
        app.logger.exception("Discord notify failed")

    # If either handled it, persist + emit and return success
    if sent_via:
        save_suggestion({"name": name, "email": sender, "musical": musical, "url": url, "message": message_body, "timestamp": timestamp})
        try:
            socketio.emit("new_suggestion", {"name": name, "musical": musical, "url": url, "message": message_body}, namespace="/admin")
        except Exception:
            pass
        return jsonify({"ok": True, "via": sent_via})

    # Fallback to SMTP if no webhook handled it
    to_email = os.getenv('SUGGEST_TO_EMAIL')
    smtp_host = os.getenv('SUGGEST_SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SUGGEST_SMTP_PORT', '587'))
    smtp_user = os.getenv('SUGGEST_SMTP_USER')
    smtp_pass = os.getenv('SUGGEST_SMTP_PASS')

    if not to_email or not smtp_host or not smtp_user or not smtp_pass:
        return jsonify({'ok': False, 'error': 'SMTP not configured and no webhooks configured'}), 500

    msg = EmailMessage()
    msg['Subject'] = 'Sugerencia desde Ticket Monitor'
    msg['From'] = f'{name or "Usuario"} <{smtp_user}>'
    msg['To'] = to_email
    msg.set_content(f'Nombre: {name}\nEmail: {sender}\nMusical: {musical}\nLink: {url}\n\nMensaje:\n{message_body}\n\nOrigen: {remote}\nTimestamp: {timestamp}')

    try:
        if smtp_port == 465:
            smtp = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)
        smtp.quit()
        save_suggestion({"name": name, "email": sender, "musical": musical, "url": url, "message": message_body, "timestamp": timestamp})
        try:
            socketio.emit("new_suggestion", {"name": name, "musical": musical, "url": url, "message": message_body}, namespace="/admin")
        except Exception:
            pass
        return jsonify({'ok': True, 'via': 'smtp'})
    except Exception as e:
        app.logger.exception('Failed to send suggestion via SMTP')
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    """Simple health check for uptime monitors."""
    return jsonify({"ok": True, "time": datetime.now(UTC).isoformat()}), 200

def send_email_via_smtp(subject: str, body: str, to_addrs: list):
    """
    Minimal SMTP sender using env vars:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SENDER_EMAIL
    """
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    sender = os.environ.get("SENDER_EMAIL", user)
    if not host or not user or not pwd:
        app.logger.warning("SMTP not configured (SMTP_HOST/SMTP_USER/SMTP_PASS missing)")
        return {"ok": False, "error": "smtp-not-configured"}

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls(context=context)
            s.login(user, pwd)
            s.send_message(msg)
        return {"ok": True}
    except Exception as e:
        app.logger.exception("send_email_via_smtp failed")
        return {"ok": False, "error": str(e)}

DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS") or os.getenv("DISCORD_WEBHOOK_URL")
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")

def send_discord_suggestion(payload_text: str) -> dict:
    """
    Send a plain-text suggestion to the suggestions webhook (DISCORD_WEBHOOK_SUGGESTIONS).
    """
    if not DISCORD_WEBHOOK_SUGGESTIONS:
        return {"ok": False, "reason": "discord-suggestions-not-configured"}
    try:
        r = requests.post(DISCORD_WEBHOOK_SUGGESTIONS, json={"content": payload_text}, timeout=6)
        try:
            data = r.json()
        except Exception:
            data = {"status_code": r.status_code, "text": r.text}
        return {"ok": r.ok, "resp": data}
    except Exception as e:
        app.logger.exception("send_discord_suggestion failed")
        return {"ok": False, "error": str(e)}

def send_discord_json_alert(url, changes_text, timestamp=None):
    """
    Send the JSON-style alert payload to the alerts webhook (DISCORD_WEBHOOK_ALERTS).
    Posts a pretty-printed JSON code block similar to Telegram.
    """
    if not DISCORD_WEBHOOK_ALERTS:
        app.logger.debug("Discord alerts webhook not configured (DISCORD_WEBHOOK_ALERTS missing)")
        return {"ok": False, "reason": "not-configured"}

    payload = {
        "type": "ticket_alert",
        "url": url,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "changes_truncated": (changes_text or "")[:3900],
        "changes_full_length": len(changes_text or "")
    }
    text = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
    try:
        r = requests.post(DISCORD_WEBHOOK_ALERTS, json={"content": text}, timeout=8)
        try:
            data = r.json()
        except Exception:
            data = {"status_code": r.status_code, "text": r.text}
        app.logger.info("Discord alert send: status=%s resp=%s", r.status_code, data)
        return {"ok": r.ok, "resp": data}
    except Exception as e:
        app.logger.exception("send_discord_json_alert failed")
        return {"ok": False, "reason": str(e)}

def load_events():
    try:
        with EVENTS_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

@app.route('/shows')
def shows_page():
    events = load_events()
    # agrupa por musical y genera mini-datos para la vista
    grouped = {}
    for ev in events:
        key = (ev.get('musical') or ev.get('title') or 'Sin título').strip()
        g = grouped.setdefault(key, {
            'title': key,
            'id': key,
            'dates': [],
            'image': ev.get('image') or '/static/BOM1.jpg',
            'short': ev.get('short') or '',
            'url': ev.get('url') or '#',
            'location': ev.get('location') or ''
        })
        g['dates'].append(ev.get('start'))
    shows = []
    for k,v in grouped.items():
        dates = sorted([d for d in v['dates'] if d])
        if dates:
            v['range'] = dates[0] + ((' → ' + dates[-1]) if len(dates) > 1 else '')
        else:
            v['range'] = ''
        shows.append(v)
    return render_template('shows.html', shows=shows)

@app.route("/calendar")
def calendar_page():
    """
    Página del calendario (cliente carga /api/events).
    grouped_urls se pasa por compatibilidad si la plantilla la usa.
    """
    grouped = group_urls_by_musical(load_urls())
    return render_template("calendar.html", grouped_urls=grouped)


@app.route("/api/events", methods=["GET"])
def api_events():
    """
    Devuelve la lista de eventos (events.json) en JSON.
    """
    try:
        events = load_events()
        return jsonify(events)
    except Exception:
        app.logger.exception("api_events failed")
        return jsonify([]), 500

# >>> Re-add the app runner at EOF so it runs after all routes are defined
if __name__ == "__main__":
    # Development friendly: auto-reload and run socketio
    try:
        socketio.run(app, host="0.0.0.0", port=5000, debug=True)
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass

@app.route("/admin/suggestions/<int:idx>/approve", methods=["POST"])
@require_auth
def approve_suggestion(idx):
    """Aprobar sugerencia: moverla a urls.json y eliminarla de suggestions.json"""
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        return jsonify({"error": "no suggestions file"}), 404
    
    if idx >= len(suggestions):
        return jsonify({"error": "suggestion not found"}), 404
    
    sug = suggestions.pop(idx)
    
    # Añadir a urls.json
    urls = load_urls()
    name = sug.get("siteName") or sug.get("musical") or "Sin nombre"
    url = sug.get("siteUrl") or sug.get("url") or ""
    
    # Buscar si ya existe el musical
    found = False
    for item in urls:
        if (item.get("musical") or item.get("name")) == name:
            if url not in item.get("urls", []):
                item.setdefault("urls", []).append(url)
            found = True
            break
    
    if not found:
        urls.append({"musical": name, "urls": [url]})
    
    # Guardar urls.json actualizado
    with URLS_FILE.open("w", encoding="utf-8") as f:
        json.dump(urls, f, indent=2, ensure_ascii=False)
    
    # Guardar suggestions.json sin la sugerencia aprobada
    with SUGGESTIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    return jsonify({"ok": True, "approved": sug})


@app.route("/admin/suggestions/<int:idx>/reject", methods=["POST"])
@require_auth
def reject_suggestion(idx):
    """Rechazar sugerencia: solo eliminarla de suggestions.json"""
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