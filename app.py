from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC
import requests

app = Flask(__name__)
previous_states = {}
@app.route("/")
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>🎟️ Ticket Monitor Dashboard</title>
      <style>
        body {
          margin: 0;
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
          background: linear-gradient(135deg, #ffe4e6, #fbcfe8);
          color: #444;
          min-height: 100vh;
          padding: 2rem;
        }

        h1 {
          text-align: center;
          font-size: 3rem;
          color: #ec4899;
          margin-bottom: 2rem;
          animation: fadeIn 1s ease-in-out;
        }

        .dashboard {
          background: white;
          border: 1px solid #f9a8d4;
          border-radius: 16px;
          box-shadow: 0 4px 20px rgba(249, 168, 212, 0.2);
          padding: 1.5rem;
          max-width: 1200px;
          margin: 0 auto;
        }

        .header {
          display: flex;
          justify-content: space-between;
          flex-wrap: wrap;
          margin-bottom: 1rem;
        }

        .last-checked {
          font-size: 0.9rem;
          font-style: italic;
          color: #ec4899;
        }

        .badge {
          background: #ec4899;
          color: white;
          padding: 0.25rem 0.75rem;
          border-radius: 999px;
          font-size: 0.8rem;
          animation: pulse 1.5s infinite;
        }

        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 1rem;
        }

        .card {
  background-color: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  transition: background-color 0.3s ease;

  /* Previene desbordamientos de texto */
  word-wrap: break-word;
  overflow-wrap: break-word;
}


        .card:hover {
          border-color: #ec4899;
          box-shadow: 0 4px 16px rgba(236, 72, 153, 0.3);
        }

        .card span:first-child {
          font-size: 1.5rem;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes pulse {
          0%, 100 { opacity: 1; }
          50% { opacity: 0.6; }
        }
      </style>
    </head>
    <body>
      <h1>🎭 HOLAAAA</h1>

      <div class="dashboard">
        <div class="header">
          <p id="lastChecked" class="last-checked">Last Checked: ...</p>
          <span class="badge">🔄 Auto-refreshing</span>
        </div>

        <div id="changesList" class="grid">
          <div class="card"><span>⏳</span><span>Loading updates...</span></div>
        </div>
      </div>

      <script>
        async function update() {
          const res = await fetch("/changes");
          const data = await res.json();
          document.getElementById("lastChecked").textContent =
            "Last Checked: " + new Date().toLocaleString("es-ES");

          const list = document.getElementById("changesList");
          list.innerHTML = "";

          if (data.length === 0) {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = "<span>✅</span><span>No new changes detected.</span>";
            list.appendChild(card);
          } else {
            data.forEach(change => {
              const card = document.createElement("div");
              card.className = "card";
              card.innerHTML = `<span>🎫</span><span>${change.site}: ${change.summary}</span>`;
              list.appendChild(card);
            });
          }
        }

        update();
        setInterval(update, 10000);
      </script>
    </body>
    </html>
    """)


URLS = [
    "https://httpbin.org/get",
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
from datetime import datetime
@app.route("/changes")
def get_changes():
    changes = []
    for url in URLS:
        try:
            response = requests.get(url, timeout=10)
            content = response.text if response.ok else None
        except Exception as e:
            content = None

        status = "unchanged"
        summary = "No updates detected."

        if content is None:
            summary = "Failed to fetch site."
        else:
            previous = previous_states.get(url)
            if previous is None:
                summary = "First check, no previous data."
            elif previous != content:
                status = "changed"
                summary = "Content updated!"
            previous_states[url] = content

        changes.append({
            "site": url,
            "status": status,
            "summary": summary,
            "timestamp": datetime.now(UTC).isoformat()
        })
    return jsonify(changes)


@app.route("/urls")
def urls():
    with open("urls.json") as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
