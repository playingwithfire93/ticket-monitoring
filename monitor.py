import requests
from datetime import datetime

URLS = [
    "https://wickedelmusical.com/",
    "https://miserableselmusical.es"
]

results = []

def check_sites():
    global results
    new_results = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for url in URLS:
        try:
            res = requests.get(url, timeout=10)
            if "date_info" in res.text:
                new_results.append(f"[{now}] {url} OK ✅")
            else:
                new_results.append(f"[{now}] {url} ❌ CHANGE or missing")
        except Exception as e:
            new_results.append(f"[{now}] {url} ❌ ERROR: {e}")

    results[:] = new_results
