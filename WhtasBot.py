import os
import requests
import mimetypes
from flask import Flask, request, jsonify

# Environment variables
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")
TEMPLATE_NAME = os.getenv("TEMPLATE_NAME", "send_photo")  # must match approved template name

UPLOAD_FOLDER = "/tmp/whatsapp_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

# ---------------- WhatsApp API Helpers ---------------- #

def send_whatsapp(payload):
    """Send a WhatsApp message using the API."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    r = requests.post(url, headers=headers, json=payload)
    print("Send response:", r.status_code, r.text)
    r.raise_for_status()
    return r.json()

def send_template_with_image(to_number, image_url, name_param):
    """Send approved template with image header to the user."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {"type": "image", "image": {"link": image_url}}
                    ]
                },
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": name_param}
                    ]
                }
            ]
        }
    }
    return send_whatsapp(payload)

# ---------------- Endpoints ---------------- #

@app.route("/send-image", methods=["POST"])
def send_image():
    """
    Uploads image from client, saves it, generates public URL, and sends it instantly via template.
    Requires:
        file: image file
        to: recipient WhatsApp number (in international format without +)
        name: name for {{1}} placeholder in template
    """
    if "file" not in request.files or "to" not in request.form or "name" not in request.form:
        return jsonify(error="Missing required fields: file, to, name"), 400

    phone_number = request.form["to"].strip()
    user_name = request.form["name"].strip()
    file = request.files["file"]

    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(save_path)

    # Public URL to file (adjust if not using Render)
    public_url = f"https://{request.host}/static/{file.filename}"

    # Ensure static hosting works
    os.makedirs(os.path.join(app.root_path, "static"), exist_ok=True)
    file.save(os.path.join(app.root_path, "static", file.filename))

    try:
        result = send_template_with_image(phone_number, public_url, user_name)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/webhook", methods=["GET"])
def verify():
    """Webhook verification"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# ---------------- Main ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
