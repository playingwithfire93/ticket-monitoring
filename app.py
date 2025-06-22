from flask import Flask, jsonify, render_template
import json

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status")
def status():
    with open("data.json") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/changes")
def changes():
    with open("data.json") as f:
        data = json.load(f)
    return jsonify(data["changes"])

if __name__ == "__main__":
    app.run(debug=True)
