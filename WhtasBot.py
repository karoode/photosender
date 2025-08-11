import os, json
from flask import Flask, request, jsonify
import requests

# -----------------------------
# Environment Variables
# -----------------------------
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

# -----------------------------
# Flask App
# -----------------------------
app = Flask(__name__)

# -----------------------------
# Send Text Message
# -----------------------------
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

# -----------------------------
# Upload Image and Send
# -----------------------------
def upload_image(file_path):
    """Uploads an image to WhatsApp and returns the media ID."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }
    files = {
        "file": open(file_path, "rb"),
        "type": (None, "image/jpeg"),
        "messaging_product": (None, "whatsapp")
    }
    r = requests.post(url, headers=headers, files=files)
    r.raise_for_status()
    media_id = r.json().get("id")
    print(f"✅ Uploaded image. Media ID: {media_id}")
    return media_id

def send_image(to, file_path, caption=None):
    """Uploads an image and sends it to a WhatsApp user."""
    media_id = upload_image(file_path)
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "id": media_id
        }
    }
    if caption:
        payload["image"]["caption"] = caption
    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    print(f"✅ Image sent to {to}")
    return r.json()

# -----------------------------
# Webhook Verification
# -----------------------------
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# -----------------------------
# Incoming Messages
# -----------------------------
@app.route("/webhook", methods=["POST"])
def inbound():
    data = request.get_json(silent=True, force=True) or {}

    print("=== Incoming Webhook Data ===")
    print(json.dumps(data, indent=2))
    print("=============================")

    try:
        changes = data.get("entry", [])[0].get("changes", [])[0]
        value = changes.get("value", {})

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

# -----------------------------
# Run Flask or Send Image from Terminal
# -----------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        # Example: python app.py path/to/image.jpg
        send_image("9647804084822", sys.argv[1], caption="Here’s your image 📷")
    else:
        app.run(host="0.0.0.0", port=8000)
