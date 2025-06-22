from flask import Flask, jsonify, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import json
from pytz import utc
import os
from datetime import datetime, timezone

app = Flask(__name__)

# Global storage
previous_states = {}
latest_changes = []

# Telegram Configuration
TELEGRAM_TOKEN = '7763897628:AAEQVDEOBfHmWHbyfeF_Cx99KrJW2ILlaw0'
CHAT_ID = '553863319'


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram bot token or chat ID not set.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Exception sending Telegram message: {e}")
        return False

def fetch_page_content(url):
    try:
        response = requests.get(url, timeout=10)
        return response.text if response.ok else None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

URLS = [
    "https://httpbin.org/get/",
    "https://wickedelmusical.com/",
    "https://wickedelmusical.com/elenco",
    "https://tickets.wickedelmusical.com/espectaculo/wicked-el-musical/W01",
    "https://www.houdinielmusical.com",
    "https://miserableselmusical.es/",
    "https://miserableselmusical.es/elenco",
    "https://tickets.miserableselmusical.es/espectaculo/los-miserables/M01",
    "https://thebookofmormonelmusical.es",
    "https://thebookofmormonelmusical.es/elenco/",
    "https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01",
    "https://buscandoaaudrey.com"
]

def check_sites():
    global previous_states, latest_changes
    print(f"Running scheduled check at {datetime.now().isoformat()}")

    changes = []
    for url in URLS:
        current_content = fetch_page_content(url)
        status = "unchanged"
        summary = "No updates detected."

        if current_content is None:
            summary = "Failed to fetch site."
        else:
            prev_content = previous_states.get(url)
            if prev_content is None:
                previous_states[url] = current_content
                summary = "First check, no previous data."
            elif current_content != prev_content:
                status = "changed"
                summary = "New tickets or changes detected!"
                send_telegram_message(f"🎟️ Update detected for {url}: {summary}")
                previous_states[url] = current_content

        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds') + "Z"

        changes.append({
            "site": url,
            "status": status,
            "summary": summary,
            "timestamp": timestamp
        })

    latest_changes = changes

@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>🎭 Ticket Monitor Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-r from-purple-300 via-pink-300 to-red-300 min-h-screen flex flex-col">

  <header class="bg-gradient-to-r from-purple-700 via-pink-700 to-red-700 text-white text-center py-6 shadow-lg font-extrabold text-3xl tracking-wide">
    🎭 Ticket Monitor Dashboard
  </header>

  <main class="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <div id="changesContainer" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
      <p class="col-span-full text-center text-gray-700 text-lg animate-pulse">Loading...</p>
    </div>
  </main>

  <footer class="text-center text-white py-4 bg-purple-800 font-semibold">
    &copy; 2025 Ticket Monitor. Stay fabulous. 💅
  </footer>

  <script>
    if ("Notification" in window && Notification.permission !== "granted") {
      Notification.requestPermission();
    }

    const alertSound = new Audio("/static/door-bell-sound-99933.mp3");

    async function loadChanges() {
      const container = document.getElementById("changesContainer");
      try {
        const res = await fetch("/changes");
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();

        container.innerHTML = "";

        if (data.length === 0) {
          container.innerHTML = '<p class="col-span-full text-center text-gray-600 italic">No recent changes available yet. Please check back soon.</p>';
          return;
        }

        data.forEach(change => {
          const card = document.createElement("div");
          card.className = "bg-white bg-opacity-80 backdrop-blur-md rounded-xl p-5 shadow-lg hover:shadow-2xl transition-shadow duration-300 flex flex-col";

          card.innerHTML = `
            <h3 class="text-purple-900 font-bold text-lg mb-2 truncate">
              <a href="${change.site}" target="_blank" rel="noopener noreferrer" class="hover:text-pink-600 transition-colors duration-200 underline decoration-pink-400">${change.site}</a>
            </h3>
            <p class="text-sm text-gray-700 mb-1"><strong>Status:</strong> <span class="text-green-600 font-semibold">${change.status}</span></p>
            <p class="text-sm text-gray-600 mb-3">${change.summary}</p>
            <time class="mt-auto text-xs text-gray-500 italic">Last checked: ${new Date(change.timestamp).toLocaleString()}</time>
          `;

          container.appendChild(card);

          if (change.status === "changed") {
            if (Notification.permission === "granted") {
              new Notification("Ticket Monitor Update", {
                body: `${change.site} — ${change.summary}`,
                icon: "/static/icon.png",
              });
            }

            alertSound.play().catch(e => console.log("Sound play failed:", e));

            document.title = "🔔 Ticket Update!";

            if ("vibrate" in navigator) {
              navigator.vibrate(1000);
            }
          }
        });
      } catch (err) {
        container.innerHTML = '<p class="col-span-full text-center text-red-600 font-semibold">⚠️ Could not load data. Check connection or server.</p>';
        console.error(err);
      }
    }

    loadChanges();
    setInterval(loadChanges, 15000);
  </script>
</body>
</html>
""")

@app.route("/changes")
def get_changes():
    return jsonify(latest_changes)

@app.route("/urls")
def urls():
    try:
        with open("urls.json") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Could not load URL list: {e}"}), 500

# Start monitoring
scheduler = BackgroundScheduler(timezone=utc)
scheduler.add_job(func=check_sites, trigger="interval", seconds=60)
scheduler.start()

# Initial run so the UI has data on startup
check_sites()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
