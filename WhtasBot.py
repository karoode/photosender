import os, json
from flask import Flask, request, jsonify
import requests

VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

app = Flask(__name__)

# -----------------------------
# Upload image to WhatsApp
# -----------------------------
def upload_image(file_path):
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
    return r.json().get("id")

# -----------------------------
# Send image message
# -----------------------------
def send_image(to, file_path, caption=None):
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
    return r.json()

# -----------------------------
# POST endpoint to send image
# -----------------------------
@app.route("/send_image", methods=["POST"])
def send_image_api():
    """
    POST JSON:
    {
      "to": "9647804084822",
      "file_path": "myphoto.jpg",
      "caption": "Hello!"
    }
    """
    data = request.get_json()
    to = data.get("to")
    file_path = data.get("file_path")
    caption = data.get("caption")
    if not to or not file_path:
        return jsonify({"error": "Missing 'to' or 'file_path'"}), 400
    try:
        result = send_image(to, file_path, caption)
        return jsonify({"status": "sent", "response": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------
# Webhook verification
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
# Webhook receiver
# -----------------------------
@app.route("/webhook", methods=["POST"])
def inbound():
    data = request.get_json(silent=True, force=True) or {}
    print("=== Incoming Webhook Data ===")
    print(json.dumps(data, indent=2))
    print("=============================")
    return jsonify(status="ok"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
