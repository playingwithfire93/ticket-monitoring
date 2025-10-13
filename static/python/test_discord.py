"""Test Discord webhooks directamente"""
import os
import requests

DISCORD_WEBHOOK_ALERTS = os.getenv("DISCORD_WEBHOOK_ALERTS")
DISCORD_WEBHOOK_SUGGESTIONS = os.getenv("DISCORD_WEBHOOK_SUGGESTIONS")

def test_webhook(webhook_url, name):
    if not webhook_url:
        print(f"❌ {name}: No configurado")
        return
    
    print(f"🔍 Probando {name}...")
    print(f"   URL: {webhook_url[:50]}...")
    
    payload = {
        "content": f"🧪 Test de {name}\n\nSi ves este mensaje, el webhook funciona.",
        "username": "Test Bot"
    }
    
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        
        if r.status_code in [200, 204]:
            print(f"   ✅ Éxito (código {r.status_code})")
        else:
            print(f"   ❌ Error {r.status_code}")
            print(f"   Respuesta: {r.text[:200]}")
    except Exception as e:
        print(f"   ❌ Excepción: {e}")

if __name__ == "__main__":
    print("="*60)
    print("TEST DE WEBHOOKS DE DISCORD")
    print("="*60 + "\n")
    
    test_webhook(DISCORD_WEBHOOK_ALERTS, "Discord Alerts")
    print()
    test_webhook(DISCORD_WEBHOOK_SUGGESTIONS, "Discord Suggestions")
    print("\n" + "="*60)