import os, json
from flask import Flask, request, jsonify
import requests

VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

app = Flask(__name__)

def send_text(to, text):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        print("Send error:", r.status_code, r.text)
    return r.json() if r.content else {}

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def inbound():
    data = request.get_json(silent=True, force=True) or {}

    # 🔹 Log the entire request for debugging
    print("=== Incoming Webhook Data ===")
    print(json.dumps(data, indent=2))
    print("=============================")

    try:
        changes = data.get("entry", [])[0].get("changes", [])[0]
        value = changes.get("value", {})

        # 🔹 Make sure message belongs to THIS bot
        incoming_phone_id = value.get("metadata", {}).get("phone_number_id")
        if incoming_phone_id != PHONE_NUMBER_ID:
            print(f"Ignored message for phone_number_id {incoming_phone_id}")
            return jsonify(status="ignored"), 200

        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            from_wa = msg.get("from")
            t = msg.get("text", {}).get("body", "") if msg.get("type") == "text" else ""
            if from_wa:
                if t.strip().lower() == "hello":
                    send_text(from_wa, "Welcome 👋")
                else:
                    send_text(from_wa, "I’m alive. Send 'hello'.")
    except Exception as e:
        print("Parse error:", e, json.dumps(data))
    return jsonify(status="ok"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
