"""CONUS dashboard: Flask entry point. Reads the ingest database; never calls external APIs.

Run:  docker compose up -d        (or locally: flask --app app run --debug --port 8080)
"""
import time

import psycopg
from flask import Flask, abort, jsonify, render_template, request

from conus import chat, store
from conus.airports import AIRPORTS

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/airports")
def api_airports():
    return jsonify(AIRPORTS)


@app.get("/api/airlines")
def api_airlines():
    return jsonify(store.airlines())


@app.get("/api/aircraft")
def api_aircraft():
    """Snapshot of aircraft heard from recently. ETag = latest poll id, so unchanged polls cost a 304."""
    poll = store.latest_poll()
    etag = f'"poll-{poll["id"]}"' if poll else None
    if etag and request.headers.get("If-None-Match") == etag:
        return "", 304, {"ETag": etag}
    body = {"ts": time.time(), "poll_ts": poll["ts"] if poll else None, "aircraft": store.snapshot()}
    resp = jsonify(body)
    if etag:
        resp.headers["ETag"] = etag
    return resp


@app.get("/api/aircraft/<ident>")
def api_aircraft_one(ident):
    a = store.aircraft(ident)
    if a is None:
        abort(404)
    return jsonify(a)


@app.get("/api/health")
def api_health():
    try:
        poll = store.latest_poll()
    except psycopg.Error as e:  # report, don't raise: this endpoint exists to describe failures
        return jsonify({"db_ok": False, "error": type(e).__name__}), 503
    return jsonify({
        "db_ok": True,
        "last_poll_age_s": round(time.time() - poll["ts"]) if poll else None,
        "last_poll_kept": poll["kept"] if poll else None,
        "credits_remaining": poll["credits_remaining"] if poll else None,
    })


@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True) or {}
    q = str(body.get("q", ""))[:500]
    selected = body.get("selected") if isinstance(body.get("selected"), dict) else None
    return jsonify(chat.answer(q, selected))


if __name__ == "__main__":
    app.run(debug=True, port=8080)
