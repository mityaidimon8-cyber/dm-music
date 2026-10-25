from pathlib import Path
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder=None)
BASE_DIR = Path(__file__).resolve().parent

@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
