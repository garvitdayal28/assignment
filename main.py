"""Flask API. No templates, no static files, no UI -- the React app in
frontend/ owns everything the guest sees; this process owns the logic.

  python main.py          -> API on http://127.0.0.1:5000
  python main.py --cli    -> same agent in the terminal, no HTTP

Endpoints:
  GET  /api/hotel   inventory summary + LLM status, for the dashboard header
  POST /chat        {message, session_id} -> reply + structured turn
  POST /reset       {session_id} -> drops that conversation

Conversation state lives in a plain dict in this process. The dashboard mints
a fresh session id on every page load, so a browser refresh starts a new
conversation and the old one is dropped. Nothing is persisted.
"""

import sys
import uuid
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

import agent
import llm
from inventory import Inventory
from state import BookingState

# Resolved against this file, not the working directory, so the API can be
# started from anywhere.
INVENTORY_PATH = str(Path(__file__).resolve().parent / "inventory.json")
MAX_SESSIONS = 200

inv = Inventory.load(INVENTORY_PATH)
sessions: dict[str, BookingState] = {}

app = Flask(__name__)
# The Vite dev server proxies /chat, /reset and /api to this process, so
# same-origin is the normal case. CORS is here so a separately hosted build of
# the dashboard also works.
CORS(app, origins=[r"http://localhost:*", r"http://127.0.0.1:*", r"https://hotel-booking-conversation-agent.vercel.app/*"])


def get_state(session_id: str) -> BookingState:
    if session_id not in sessions:
        if len(sessions) >= MAX_SESSIONS:
            sessions.pop(next(iter(sessions)))
        sessions[session_id] = BookingState()
    return sessions[session_id]


@app.get("/")
def root():
    return jsonify({
        "service": "hotel booking agent api",
        "ui": "run `npm run dev` in frontend/ and open http://localhost:5173",
        "endpoints": ["GET /api/hotel", "POST /chat", "POST /reset"],
    })


@app.get("/api/hotel")
def hotel():
    return jsonify({
        "hotel_name": inv.hotel_name,
        "currency": inv.currency,
        "check_in_time": inv.check_in_time,
        "check_out_time": inv.check_out_time,
        "rooms": [room.__dict__ for room in inv.rooms],
        "policies": inv.policies,
        "llm": llm.llm_status(),
        "model": llm.MODEL,
    })


@app.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    session_id = payload.get("session_id") or uuid.uuid4().hex
    if not message:
        return jsonify({"error": "message is required"}), 400

    result = agent.handle_turn(message, get_state(session_id), inv)
    result["session_id"] = session_id
    return jsonify(result)


@app.post("/reset")
def reset():
    payload = request.get_json(silent=True) or {}
    sessions.pop(payload.get("session_id", ""), None)
    return jsonify({"ok": True})


def run_cli() -> None:
    state = BookingState()
    print(f"{inv.hotel_name} booking agent  |  LLM: {llm.llm_status()}")
    print("Type 'reset' to start over, 'quit' to exit.\n")
    while True:
        try:
            message = input("guest > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        if message.lower() in {"quit", "exit"}:
            break
        if message.lower() == "reset":
            state = BookingState()
            print("(state cleared)\n")
            continue
        result = agent.handle_turn(message, state, inv, today=date.today())
        print(f"\nbot   > {result['reply']}\n")
        print(f"json  > status={result['status']} state={result['state']}\n")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        print(f"{inv.hotel_name} | LLM: {llm.llm_status()}")
        print("API on http://127.0.0.1:5000  ·  dashboard: npm run dev in frontend/")
        app.run(port=5000, debug=False)
