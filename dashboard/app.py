"""CONUS dashboard: Flask entry point.

Run:  flask --app app run --debug      (or: python app.py)
"""
import time

from flask import Flask, abort, jsonify, render_template, request

from conus.airports import AIRPORTS
from conus.fleet import AIRLINES, Fleet

app = Flask(__name__)
fleet = Fleet(seed=42, count=70, motion=True)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/airports")
def api_airports():
    return jsonify(AIRPORTS)


@app.get("/api/airlines")
def api_airlines():
    return jsonify(AIRLINES)


@app.get("/api/aircraft")
def api_aircraft():
    return jsonify({"ts": time.time(), "motion": fleet.motion, "aircraft": fleet.snapshot()})


@app.get("/api/aircraft/<ac_id>")
def api_aircraft_one(ac_id):
    a = fleet.get(ac_id)
    if a is None:
        abort(404)
    return jsonify(a)


@app.post("/api/motion")
def api_motion():
    body = request.get_json(silent=True) or {}
    return jsonify({"motion": fleet.set_motion(body.get("enabled", True))})


@app.post("/api/chat")
def api_chat():
    body = request.get_json(silent=True) or {}
    q = str(body.get("q", ""))[:500]
    selected = body.get("selected") if isinstance(body.get("selected"), dict) else None
    return jsonify(fleet.answer(q, selected))


if __name__ == "__main__":
    app.run(debug=True, port=8080)
