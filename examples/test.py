import json
import requests

BASE_URL = "http://127.0.0.1:8000/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

# 1) initialize
init_payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "clientInfo": {"name": "python", "version": "1.0"},
        "capabilities": {},
    },
}
init_resp = requests.post(BASE_URL, headers=HEADERS, json=init_payload)
init_resp.raise_for_status()
content_type = (init_resp.headers.get("Content-Type") or "").lower()
raw_text = init_resp.text.strip()
if not raw_text:
    raise RuntimeError("Empty initialize response. Is the server running?")

if "text/event-stream" in content_type:
    # Streamable HTTP returns SSE; grab the first data line.
    data_lines = [line for line in raw_text.splitlines() if line.startswith("data:")]
    if not data_lines:
        raise RuntimeError(f"No SSE data lines. Raw response: {raw_text}")
    init_data = json.loads(data_lines[0].replace("data:", "", 1).strip())
else:
    init_data = init_resp.json()

print(json.dumps(init_data, indent=2))

# session id may be in header or body, try both
session_id = init_resp.headers.get("MCP-Session-Id") or init_data.get("result", {}).get("sessionId")
print(f"Session ID: {session_id}")
if not session_id:
    raise RuntimeError(f"Missing session id. init response: {init_data}")

# 2) call web_search
call_payload = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "get_content",
        "arguments": {"url": "https://stackoverflow.com/questions/11828270/how-to-exit-the-vim-editor"},
    },
}
call_headers = {**HEADERS, "MCP-Session-Id": session_id}
call_resp = requests.post(BASE_URL, headers=call_headers, json=call_payload)
call_resp.raise_for_status()
call_content_type = (call_resp.headers.get("Content-Type") or "").lower()
call_raw_text = call_resp.text.strip()
if not call_raw_text:
    raise RuntimeError("Empty tools/call response. Is the server running?")

if "text/event-stream" in call_content_type:
    call_data_lines = [line for line in call_raw_text.splitlines() if line.startswith("data:")]
    if not call_data_lines:
        raise RuntimeError(f"No SSE data lines. Raw response: {call_raw_text}")
    call_data = json.loads(call_data_lines[0].replace("data:", "", 1).strip())
else:
    call_data = call_resp.json()

print(json.dumps(call_data, indent=2))