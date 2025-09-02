import json
import os
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

BASE = Path(__file__).parent
URLS_FILE = BASE / "urls.json"
SUGGESTIONS_FILE = BASE / "suggestions.json"
UTC = timezone.utc

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


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


@app.route("/admin/monitoring-list")
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


@app.route("/admin/suggestions")
def admin_suggestions():
    try:
        with SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            suggestions = json.load(f)
    except Exception:
        suggestions = []
    return render_template("suggestions.html", suggestions=suggestions)


# small helper to reload urls file via HTTP (admin)
@app.route("/admin/reload-urls", methods=["POST"])
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
def admin_test_telegram():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat  = os.getenv('TELEGRAM_CHAT')  # acepta '@username' o chat_id numérico
    if not token or not chat:
        return jsonify({'ok': False, 'error': 'Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT env vars'}), 400

    body = request.get_json(silent=True) or {}
    text = body.get('text', 'Test desde Ticket Monitor ✅')

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
      res = requests.post(url, json={'chat_id': chat, 'text': text}, timeout=10)
      res.raise_for_status()
      return jsonify({'ok': True, 'result': res.json()})
    except Exception as e:
      return jsonify({'ok': False, 'error': str(e), 'status_code': getattr(e, "response", None) and e.response.status_code}), 500


if __name__ == "__main__":
    # Development friendly: auto-reload and run socketio
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)