#!/usr/bin/env python3
"""
Test script for the approval system
This script simulates the approval workflow without needing webhooks.
"""

import os
import json
import requests
from datetime import datetime, UTC
from dotenv import load_dotenv

load_dotenv()

def send_test_suggestion():
    """Send a test suggestion to see the approval buttons"""
    admin_token = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
    admin_chat_id = os.environ.get("ADMIN_TELEGRAM_CHAT_ID")
    
    if not admin_token or not admin_chat_id:
        print("Admin bot not configured")
        return
    
    # Create test suggestion
    suggestion = {
        "siteName": "Hamilton El Musical",
        "siteUrl": "https://hamilton.com",
        "reason": "Musical muy popular que necesita monitoreo",
        "timestamp": datetime.now(UTC).isoformat(),
        "fecha_legible": datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
    }
    
    # Load existing suggestions or create new list
    try:
        with open('suggestions.json', 'r') as f:
            suggestions = json.load(f)
    except FileNotFoundError:
        suggestions = []
    
    suggestions.append(suggestion)
    
    with open('suggestions.json', 'w') as f:
        json.dump(suggestions, f, indent=2, ensure_ascii=False)
    
    # Send with approval buttons
    text = f"""
🆕 <b>Nueva Sugerencia de Sitio Web</b>

📝 <b>Nombre:</b> {suggestion['siteName']}
🔗 <b>URL:</b> {suggestion['siteUrl']}
💭 <b>Razón:</b> {suggestion['reason']}
📅 <b>Fecha:</b> {suggestion['fecha_legible']}

<a href="{suggestion['siteUrl']}">Ver sitio sugerido</a>
    """.strip()
    
    url = f"https://api.telegram.org/bot{admin_token}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Aprobar", "callback_data": f"approve_{len(suggestions) - 1}"},
                {"text": "❌ Rechazar", "callback_data": f"reject_{len(suggestions) - 1}"}
            ]
        ]
    }
    
    payload = {
        "chat_id": admin_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(keyboard)
    }
    
    try:
        r = requests.post(url, data=payload, timeout=5)
        print("Test suggestion sent:", r.status_code)
        if r.status_code == 200:
            print("✅ Check your Telegram! You should see a message with Approve/Reject buttons")
            print("📋 Suggestion ID:", len(suggestions) - 1)
        else:
            print("Error:", r.text)
    except Exception as e:
        print("Error sending test:", e)

def send_approval_notification():
    """Send test approval notification to main bot"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Main bot not configured")
        return
    
    main_message = """
🎉 <b>Nueva Web Aprobada para Monitoreo</b>

📝 <b>Sitio:</b> Hamilton El Musical
🔗 <b>URL:</b> https://hamilton.com
💭 <b>Razón:</b> Musical muy popular que necesita monitoreo

¡Este sitio ha sido aprobado y será considerado para monitoreo!

<a href="https://hamilton.com">Ver sitio</a>
    """.strip()
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": main_message, "parse_mode": "HTML"}
    
    try:
        r = requests.post(url, data=payload, timeout=5)
        print("Approval notification sent to main bot:", r.status_code)
        if r.status_code == 200:
            print("✅ Check your main Telegram bot! You should see the approval notification")
        else:
            print("Error:", r.text)
    except Exception as e:
        print("Error sending approval notification:", e)

if __name__ == "__main__":
    print("🧪 Testing Approval System")
    print("=" * 50)
    
    print("\n1. Sending test suggestion with approval buttons...")
    send_test_suggestion()
    
    input("\n👆 Check your admin bot and press any button, then press Enter to continue...")
    
    print("\n2. Sending test approval notification to main bot...")
    send_approval_notification()
    
    print("\n✅ Test complete!")
    print("\nNext steps:")
    print("1. The suggestion form on your website will now send messages with buttons")
    print("2. When you click 'Aprobar', it will send a notification to the main bot")
    print("3. For the buttons to work automatically, you need to set up webhooks")
