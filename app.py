from flask import Flask, jsonify, render_template_string

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
        async function loadChanges() {
          const container = document.getElementById("changesContainer");
          try {
            const res = await fetch("/changes");
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();

            container.innerHTML = "";

            data.forEach(change => {
              const card = document.createElement("div");
              card.className = "card";

              card.innerHTML = `
                <h3>${change.site}</h3>
                <p>Status: ${change.status}</p>
                <p>Summary: ${change.summary}</p>
                <time>Last checked: ${new Date(change.timestamp).toLocaleString()}</time>
              `;

              container.appendChild(card);
            });
          } catch (err) {
            container.innerHTML = "<p>⚠️ Could not load data. Check connection or server.</p>";
            console.error(err);
          }
        }

        loadChanges(); // Initial load
        setInterval(loadChanges, 15000); // Refresh every 15 seconds
      </script>
    </body>
    </html>
    """)

@app.route("/changes")
def get_changes():
    # Dummy data - replace with your real monitoring data
    return jsonify([
        {
            "site": "https://wickedelmusical.es",
            "status": "changed",
            "summary": "New tickets available for July.",
            "timestamp": "2025-06-22T18:43:00Z"
        },
        {
            "site": "https://lesmiserables.es",
            "status": "unchanged",
            "summary": "No updates detected.",
            "timestamp": "2025-06-22T18:40:00Z"
        }
    ])

if __name__ == "__main__":
    app.run(debug=True)
