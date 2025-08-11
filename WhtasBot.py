import os
import requests
import mimetypes
from flask import Flask, request, jsonify

# Environment variables (set these in Render dashboard or locally)
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

# Folder to store images
UPLOAD_FOLDER = "/tmp/whatsapp_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Memory for tracking user states
user_states = {}  # {wa_id: {"stage": "start"|"await_phone"|"done"}}

app = Flask(__name__)

# ------------------- WhatsApp API helpers -------------------

def send_whatsapp(payload):
    """Send a WhatsApp message using the API."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json=payload)
    print("Send response:", resp.text)
    resp.raise_for_status()
    return resp.json()

def send_text(to, text):
    return send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    })

def send_buttons(to, text, buttons):
    return send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [{"type": "reply", "reply": {"id": b[0], "title": b[1]}} for b in buttons]
            }
        }
    })

def upload_media(file_path):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/media"
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    files = {
        'file': (os.path.basename(file_path), open(file_path, 'rb'), mime_type)
    }
    data = {"messaging_product": "whatsapp"}
    resp = requests.post(url, headers=headers, files=files, data=data)
    print("Upload response:", resp.text)
    resp.raise_for_status()
    return resp.json()["id"]

def send_media(media_id, to_number):
    return send_whatsapp({
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {"id": media_id}
    })

# ------------------- Webhook verification -------------------

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# ------------------- Webhook events -------------------

@app.route("/webhook", methods=["POST"])
def inbound():
    data = request.get_json(silent=True, force=True)
    print("Incoming Webhook:", data)

    try:
        changes = data["entry"][0]["changes"][0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        # Ignore if not for our phone number
        if value.get("metadata", {}).get("phone_number_id") != PHONE_NUMBER_ID:
            return jsonify(status="ignored"), 200

        if messages:
            msg = messages[0]
            wa_id = msg.get("from")
            msg_type = msg.get("type")

            # If first time user
            if wa_id not in user_states:
                user_states[wa_id] = {"stage": "start"}
                send_buttons(
                    wa_id,
                    "Welcome to Aljazari Photo Bot, press Start to continue.",
                    [("start_btn", "Start")]
                )
                return jsonify(status="ok"), 200

            stage = user_states[wa_id]["stage"]

            # Handle button clicks
            if msg_type == "interactive":
                btn_id = msg["interactive"]["button_reply"]["id"]

                if btn_id == "start_btn":
                    user_states[wa_id]["stage"] = "await_receive"
                    send_buttons(
                        wa_id,
                        "Select your service below:",
                        [("receive_btn", "Receive Image")]
                    )

                elif btn_id == "receive_btn":
                    user_states[wa_id]["stage"] = "await_phone"
                    send_text(wa_id, "Please send your phone number to receive your image.")

            # Handle phone number text
            elif msg_type == "text" and stage == "await_phone":
                phone_number = msg["text"]["body"].strip()
                img_path = os.path.join(UPLOAD_FOLDER, f"{phone_number}.png")
                if os.path.exists(img_path):
                    media_id = upload_media(img_path)
                    send_media(media_id, wa_id)
                    user_states[wa_id]["stage"] = "done"
                else:
                    send_text(wa_id, "No image found for this number. Please try again later.")

    except Exception as e:
        print("Error:", e)

    return jsonify(status="ok"), 200

# ------------------- Image upload endpoint -------------------

@app.route("/send-image", methods=["POST"])
def send_image():
    if "file" not in request.files or "to" not in request.form:
        return jsonify(error="Missing file or 'to' parameter (phone number to save as name)"), 400

    phone_number = request.form["to"].strip()
    file = request.files["file"]

    save_path = os.path.join(UPLOAD_FOLDER, f"{phone_number}.png")
    file.save(save_path)

    return jsonify(message=f"Image saved for {phone_number}"), 200

# ------------------- Run server -------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
