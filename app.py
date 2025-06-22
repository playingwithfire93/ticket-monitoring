from flask import Flask, jsonify, render_template_string
import os

app = Flask(__name__)

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
    async function loadChanges() {
      const container = document.getElementById("changesContainer");
      try {
        const res = await fetch("/changes");
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();

        container.innerHTML = "";

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
        });
      } catch (err) {
        container.innerHTML = '<p class="col-span-full text-center text-red-600 font-semibold">⚠️ Could not load data. Check connection or server.</p>';
        console.error(err);
      }
    }

    loadChanges(); // Initial load
    setInterval(loadChanges, 15000); // Refresh every 15 seconds
  </script>

</body>
</html>
""")

URLS = [
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
            "timestamp": datetime.utcnow().isoformat() + "Z"
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
