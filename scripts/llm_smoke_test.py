"""Check that the chat model endpoint answers a tool-calling request.

    python3 scripts/llm_smoke_test.py            # uses LLM_BASE_URL, default http://localhost:8081/v1

Standard library only, so it runs on any host. Exits non-zero unless the reply
contains a tool call to get_airport_status with an airport argument.
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("LLM_BASE_URL", "http://localhost:8081/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "gpt-oss-20b")

request = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "You answer questions about US airports using the provided tools."},
        {"role": "user", "content": "Is there a ground stop at Denver right now?"},
    ],
    "tools": [{
        "type": "function",
        "function": {
            "name": "get_airport_status",
            "description": "Current FAA delay programs, ground stops and weather for one airport.",
            "parameters": {
                "type": "object",
                "properties": {"airport": {"type": "string", "description": "IATA or ICAO code, e.g. DEN"}},
                "required": ["airport"],
            },
        },
    }],
}

req = urllib.request.Request(f"{BASE}/chat/completions", data=json.dumps(request).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.monotonic()
with urllib.request.urlopen(req, timeout=300) as r:
    body = json.load(r)
elapsed = time.monotonic() - t0

msg = body["choices"][0]["message"]
calls = msg.get("tool_calls") or []
usage = body.get("usage", {})
print(f"{elapsed:.1f}s, {usage.get('completion_tokens', '?')} completion tokens")
for c in calls:
    print("tool call:", c["function"]["name"], c["function"]["arguments"])
ok = any(c["function"]["name"] == "get_airport_status" and "airport" in json.loads(c["function"]["arguments"])
         for c in calls)
if not ok:
    print("FAIL: no get_airport_status tool call; message was:", json.dumps(msg)[:500])
sys.exit(0 if ok else 1)
