# combined_server.py
import os
import mimetypes
import cv2
import numpy as np
import requests
from io import BytesIO
from flask import Flask, request, jsonify, send_file
from gfpgan import GFPGANer

# --- WhatsApp Env Variables ---
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")
TEMPLATE_NAME = os.getenv("TEMPLATE_NAME", "send_photo")

# --- Init Flask ---
app = Flask(__name__)
UPLOAD_FOLDER = "/tmp/whatsapp_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Init GFPGAN ---
model_path = 'GFPGANv1.4.pth'
gfpganer = GFPGANer(
    model_path=model_path,
    upscale=1,
    arch='clean',
    channel_multiplier=2,
    bg_upsampler=None
)

# --- WhatsApp Helpers ---
def upload_media(file_path):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/media"
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    files = {'file': (os.path.basename(file_path), open(file_path, 'rb'), mime_type)}
    data = {"messaging_product": "whatsapp"}
    resp = requests.post(url, headers=headers, files=files, data=data)
    print("Upload response:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()["id"]

def send_template_with_media_id(to_number, media_id, name_param):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": "en"},
            "components": [
                {"type": "header", "parameters": [{"type": "image", "image": {"id": media_id}}]},
                {"type": "body", "parameters": [{"type": "text", "text": name_param}]}
            ]
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    print("Send response:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()

# --- Routes ---
@app.route("/enhance", methods=["POST"])
def enhance_image():
    if "image" not in request.files:
        return "No image uploaded", 400

    file = request.files["image"]
    file_bytes = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        return "Invalid image", 400

    try:
        _, _, restored_img = gfpganer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
        _, buffer = cv2.imencode('.jpg', restored_img)
        return send_file(BytesIO(buffer), mimetype="image/jpeg")
    except Exception as e:
        return str(e), 500

@app.route("/send-image", methods=["POST"])
def send_image():
    if "file" not in request.files or "to" not in request.form or "name" not in request.form:
        return jsonify(error="Missing file, to, or name"), 400

    phone_number = request.form["to"].strip()
    user_name = request.form["name"].strip()
    file = request.files["file"]

    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(save_path)

    try:
        media_id = upload_media(save_path)
        result = send_template_with_media_id(phone_number, media_id, user_name)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
