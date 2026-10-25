import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import Flask, jsonify, redirect, request, session, send_from_directory

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("VK_DB_PATH", "/tmp/dm_muzic_vk.sqlite3")
VK_API_VERSION = "5.199"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS vk_tokens (
        sid TEXT PRIMARY KEY, access_token TEXT NOT NULL, user_id TEXT,
        expires_at INTEGER, updated_at INTEGER NOT NULL
    )""")
    return conn


def setting(name):
    return (os.environ.get(name) or "").strip()


def vk_api(method, token, params=None):
    values = {"v": VK_API_VERSION, "access_token": token}
    values.update(params or {})
    url = "https://api.vk.com/method/" + method + "?" + urlencode(values)
    req = Request(url, headers={"User-Agent": "DM-Muzic/1.0"})
    try:
        with urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Не удалось связаться с VK API") from exc
    if "error" in payload:
        err = payload["error"]
        raise RuntimeError(err.get("error_msg", "VK API вернул ошибку"))
    return payload.get("response")


def current_token():
    sid = session.get("vk_sid")
    if not sid:
        return None
    with db() as conn:
        row = conn.execute("SELECT access_token FROM vk_tokens WHERE sid=?", (sid,)).fetchone()
        return row["access_token"] if row else None


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/vk.js")
def vk_script():
    return send_from_directory(BASE_DIR, "vk.js", mimetype="application/javascript")


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.get("/api/vk/status")
def vk_status():
    token = current_token()
    if not token:
        return jsonify({"connected": False})
    try:
        users = vk_api("users.get", token, {"fields": "first_name,last_name"})
        user = users[0] if users else {}
        return jsonify({"connected": True, "name": " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))})
    except RuntimeError:
        return jsonify({"connected": False})


@app.get("/api/vk/login")
def vk_login():
    client_id = setting("VK_CLIENT_ID")
    redirect_uri = setting("VK_REDIRECT_URI")
    if not client_id or not redirect_uri:
        return jsonify({"error": "Сначала добавь VK_CLIENT_ID и VK_REDIRECT_URI в Environment на Render."}), 503
    state = secrets.token_urlsafe(24)
    session["vk_oauth_state"] = state
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "audio",
        "state": state,
        "v": VK_API_VERSION,
    }
    return redirect("https://oauth.vk.com/authorize?" + urlencode(params))


@app.get("/api/vk/callback")
def vk_callback():
    if request.args.get("error"):
        return redirect("/?vk_error=" + request.args.get("error", "access_denied"))
    state = request.args.get("state", "")
    expected = session.pop("vk_oauth_state", "")
    if not state or not expected or not secrets.compare_digest(state, expected):
        return redirect("/?vk_error=invalid_state")
    code = request.args.get("code")
    client_id = setting("VK_CLIENT_ID")
    client_secret = setting("VK_CLIENT_SECRET")
    redirect_uri = setting("VK_REDIRECT_URI")
    if not code or not client_id or not client_secret or not redirect_uri:
        return redirect("/?vk_error=missing_config")
    params = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    })
    try:
        req = Request("https://oauth.vk.com/access_token?" + params, headers={"User-Agent": "DM-Muzic/1.0"})
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        token = data.get("access_token")
        if not token:
            return redirect("/?vk_error=oauth_failed")
        sid = session.get("vk_sid") or secrets.token_urlsafe(32)
        session["vk_sid"] = sid
        with db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO vk_tokens(sid,access_token,user_id,expires_at,updated_at) VALUES(?,?,?,?,?)",
                (sid, token, str(data.get("user_id", "")), int(time.time()) + int(data.get("expires_in", 0)), int(time.time()))
            )
        return redirect("/?vk_connected=1")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return redirect("/?vk_error=oauth_failed")


@app.post("/api/vk/logout")
def vk_logout():
    sid = session.pop("vk_sid", None)
    session.pop("vk_oauth_state", None)
    if sid:
        with db() as conn:
            conn.execute("DELETE FROM vk_tokens WHERE sid=?", (sid,))
    return jsonify({"ok": True})


@app.get("/api/vk/search")
def vk_search():
    token = current_token()
    q = (request.args.get("q") or "").strip()
    if not token:
        return jsonify({"error": "Сначала подключи аккаунт ВК."}), 401
    if not q:
        return jsonify({"items": []})
    try:
        result = vk_api("audio.search", token, {"q": q, "count": 20, "sort": 2, "auto_complete": 1})
        items = result.get("items", []) if isinstance(result, dict) else (result or [])
        return jsonify({"items": [{
            "id": item.get("id"), "owner_id": item.get("owner_id"),
            "title": item.get("title", "Без названия"),
            "artist": item.get("artist", item.get("performer", "Неизвестный исполнитель")),
            "duration": item.get("duration", 0), "url": item.get("url", ""),
            "vk_url": "https://vk.com/audio{}_{}".format(item.get("owner_id", ""), item.get("id", ""))
        } for item in items]})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502


@app.get("/api/vk/my-audio")
def vk_my_audio():
    token = current_token()
    if not token:
        return jsonify({"error": "Сначала подключи аккаунт ВК."}), 401
    try:
        result = vk_api("audio.get", token, {"count": 100, "offset": 0})
        items = result.get("items", []) if isinstance(result, dict) else (result or [])
        return jsonify({"items": [{
            "id": item.get("id"), "owner_id": item.get("owner_id"),
            "title": item.get("title", "Без названия"),
            "artist": item.get("artist", item.get("performer", "Неизвестный исполнитель")),
            "duration": item.get("duration", 0), "url": item.get("url", ""),
            "vk_url": "https://vk.com/audio{}_{}".format(item.get("owner_id", ""), item.get("id", ""))
        } for item in items]})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
