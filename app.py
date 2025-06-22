from flask import Flask, render_template, jsonify
from monitor import check_sites, results
import threading
import time

app = Flask(__name__)

def background_task():
    while True:
        check_sites()
        time.sleep(60)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status")
def status():
    return jsonify(results)

if __name__ == "__main__":
    threading.Thread(target=background_task, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
