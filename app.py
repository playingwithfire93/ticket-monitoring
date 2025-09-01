# ...existing code...
import json
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import requests

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


if __name__ == "__main__":
    # Development friendly: auto-reload and run socketio
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
# ...existing code...