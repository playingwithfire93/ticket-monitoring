from flask import Flask, jsonify, render_template_string
import os
from datetime import datetime, UTC

app = Flask(__name__)

@app.route("/")
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Ticket Monitor</title>
      <style>
        body {
          margin: 0;
          padding: 0;
          font-family: system-ui, sans-serif;
          background-color: #f9fafb;
          color: #111827;
        }
        header {
          background-color: #111827;
          color: #ffffff;
          padding: 1rem;
          text-align: center;
          font-size: 1.5rem;
          font-weight: bold;
        }
        .container {
          max-width: 800px;
          margin: 2rem auto;
          padding: 1rem;
        }
        .card {
          background-color: #ffffff;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 1rem;
          margin-bottom: 1rem;
          box-shadow: 0 2px 4px rgba(0,0,0,0.05);
          transition: background-color 0.3s ease;
        }
        .card:hover {
          background-color: #f3f4f6;
        }
        .card h3 {
          margin: 0 0 0.5rem;
          font-size: 1.1rem;
          color: #1f2937;
        }
        .card p {
          margin: 0.3rem 0;
          font-size: 0.95rem;
          color: #374151;
        }
        .card time {
          font-size: 0.85rem;
          color: #6b7280;
        }
      </style>
    </head>
    <body>
      <header>🎭 Ticket Monitor Dashboard</header>
      <div class="container" id="changesContainer">
        <p>Loading...</p>
      </div>
      <script>
        let previousData = [];

async function loadChanges() {
  const container = document.getElementById("changesContainer");
  try {
    const res = await fetch("/changes");
    if (!res.ok) throw new Error('Network response was not ok');
    const data = await res.json();

    container.innerHTML = "";

    data.forEach((change, index) => {
      const card = document.createElement("div");
      card.className = "card";

      card.innerHTML = `
        <h3><a href="${change.site}" target="_blank" rel="noopener noreferrer">${change.site}</a></h3>
        <p>Status: ${change.status}</p>
        <p>Summary: ${change.summary}</p>
        <time>Last checked: ${new Date(change.timestamp).toLocaleString()}</time>
      `;

      container.appendChild(card);

      // Check for a change from the previous fetch
      if (previousData.length && change.status !== previousData[index].status) {
        if (Notification.permission === "granted") {
          new Notification("🎭 Ticket Alert", {
            body: `Change detected on ${change.site}`,
            icon: "https://emojiapi.dev/api/v1/ticket/64.png"
          });
        }
      }
    });

    previousData = data;
  } catch (err) {
    container.innerHTML = "<p>⚠️ Could not load data. Check connection or server.</p>";
    console.error(err);
  }loadChanges();                       // 👈 Add this
  setInterval(loadChanges, 15000);
}

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
        changes.append({
            "site": url,
            "status": "unchanged",  # You can change this later via logic or data
            "summary": "No updates detected.",
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
