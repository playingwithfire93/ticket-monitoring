"""
Configuración centralizada de la aplicación Ticket Monitor
"""
import os
from pathlib import Path

# ==================== PATHS ====================
BASE_DIR = Path(__file__).parent
URLS_FILE = BASE_DIR / "urls.json"
SUGGESTIONS_FILE = BASE_DIR / "suggestions.json"
EVENTS_FILE = BASE_DIR / "events.json"
DATABASE_FILE = BASE_DIR / "musicals.db"

# ==================== FLASK CONFIG ====================
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# ==================== DATABASE CONFIG ====================
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_FILE}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ==================== EXTERNAL SERVICES ====================
# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Discord
DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")

# ==================== ADMIN ====================
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# ==================== MONITORING ====================
POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL', '300'))  # 5 minutos
REQUEST_TIMEOUT = 5  # segundos

# ==================== COMMUNITY LINKS ====================
# Enlaces públicos para invitar usuarios
TELEGRAM_CHANNEL_URL = os.getenv("TELEGRAM_CHANNEL_URL", "https://t.me/TheBookOfMormonTicketsbot")
DISCORD_SERVER_URL = os.getenv("DISCORD_SERVER_URL", "https://discord.gg/b54EwTxx")

# ==================== HELPERS ====================
def is_telegram_configured():
    """Check if Telegram is properly configured"""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

def is_discord_alerts_configured():
    """Check if Discord alerts are configured"""
    return bool(DISCORD_WEBHOOK_ALERTS)

def is_discord_suggestions_configured():
    """Check if Discord suggestions are configured"""
    return bool(DISCORD_WEBHOOK_SUGGESTIONS)

def log_configuration():
    """Log configuration status on startup"""
    print("=" * 70)
    print("🔧 CONFIGURATION STATUS")
    print("=" * 70)
    print(f"✅ Telegram:             {is_telegram_configured()}")
    print(f"✅ Discord Alerts:       {is_discord_alerts_configured()}")
    print(f"✅ Discord Suggestions:  {is_discord_suggestions_configured()}")
    print(f"⏱️  Poll Interval:        {POLL_INTERVAL_SECONDS}s")
    print(f"🗄️  Database:             {DATABASE_FILE}")
    print("=" * 70)