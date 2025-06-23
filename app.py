from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC
import requests
import hashlib
import json

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

        h3 {
          font-size: 1.2rem;
          margin: 0.5rem 0;
          color: #9d174d;
        }

        a {
          text-decoration: none;
          color: #7e22ce;
        }

        a:hover {
          text-decoration: underline;
        }

        p {
          margin: 0.25rem 0;
          font-size: 0.95rem;
        }

        time {
          display: block;
          margin-top: 0.5rem;
          font-size: 0.8rem;
          color: #6b7280;
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
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 1rem;
        }

        .card {
          background-color: #ffffff;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 1rem;
          margin-bottom: 1rem;
          box-shadow: 0 2px 4px rgba(0,0,0,0.05);
          transition: background-color 0.3s ease, box-shadow 0.3s ease;
          word-wrap: break-word;
          overflow-wrap: break-word;
        }

        .card:hover {
          border-color: #ec4899;
          box-shadow: 0 4px 16px rgba(236, 72, 153, 0.3);
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }

        .container {
          max-width: 800px;
          margin: 1rem auto 2rem auto;
          padding: 1rem;
        }

        @media (max-width: 500px) {
          h1 {
            font-size: 2rem;
          }

          .badge {
            margin-top: 0.5rem;
          }

          .grid {
            grid-template-columns: 1fr;
          }
        }
      </style>
    </head>
    <body>
      <h1>🎭 Ticket monitoring dashboard</h1>

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
              card.innerHTML = `
                <h3><a href="${change.site}" target="_blank" rel="noopener noreferrer">${change.label}</a></h3>
                <p>Status: ${change.status}</p>
                <p>Summary: ${change.summary}</p>
                <time>Last checked: ${new Date(change.timestamp).toLocaleString()}</time>
              `;
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
    {"label": "test", "url": "https://httpbin.org/get/"},
    {"label": "Wicked", "url": "https://wickedelmusical.com/"},
    {"label": "Wicked elenco", "url": "https://wickedelmusical.com/elenco"},
    {"label": "Wicked entradas", "url": "https://tickets.wickedelmusical.com/espectaculo/wicked-el-musical/W01"},
    {"label": "Houdini", "url": "https://www.houdinielmusical.com"},
    {"label": "Los Miserables", "url": "https://miserableselmusical.es/"},
    {"label": "Los Miserables elenco", "url": "https://miserableselmusical.es/elenco"},
    {"label": "Los Miserables entradas", "url": "https://tickets.miserableselmusical.es/espectaculo/los-miserables/M01"},
    {"label": "The Book of Mormon", "url": "https://thebookofmormonelmusical.es"},
    {"label": "Mormon elenco", "url": "https://thebookofmormonelmusical.es/elenco/"},
    {"label": "Mormon entradas", "url": "https://tickets.thebookofmormonelmusical.es/espectaculo/the-book-of-mormon-el-musical/BM01"},
    {"label": "Buscando a Audrey", "url": "https://buscandoaaudrey.com"}
]

@app.route("/changes")
def get_changes():
    changes = []
    for item in URLS:
        url = item["url"]
        label = item["label"]
        try:
            response = requests.get(url, timeout=10)
            content = response.text
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

            last_hash = previous_states.get(url)
            if last_hash != content_hash:
                previous_states[url] = content_hash
                changes.append({
                    "site": url,
                    "label": label,
                    "status": "changed",
                    "summary": "Page content updated.",
                    "timestamp": datetime.now(UTC).isoformat()
                })
            else:
                changes.append({
                    "site": url,
                    "label": label,
                    "status": "unchanged",
                    "summary": "No updates detected.",
                    "timestamp": datetime.now(UTC).isoformat()
                })

        except Exception as e:
            changes.append({
                "site": url,
                "label": label,
                "status": "error",
                "summary": f"Error fetching site: {e}",
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
