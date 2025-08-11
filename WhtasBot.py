import os
import requests
from flask import Flask, request, jsonify
import mimetypes

VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
MY_WHATSAPP = os.environ["MY_WHATSAPP"]
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

app = Flask(__name__)

def upload_media(file_path):
    print(f"DEBUG: WHATSAPP_TOKEN length = {len(WHATSAPP_TOKEN)}")
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/media"
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    files = {
        'file': (os.path.basename(file_path), open(file_path, 'rb'), mime_type)
    }
    data = {"messaging_product": "whatsapp"}
    resp = requests.post(url, headers=headers, files=files, data=data)
    print("DEBUG: Upload response:", resp.text)
    resp.raise_for_status()
    return resp.json()["id"]

def send_media(media_id):
    """Send media by ID to MY_WHATSAPP."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": MY_WHATSAPP,
        "type": "image",
        "image": {"id": media_id}
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

@app.route("/send-image", methods=["POST"])
def send_image():
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    tmp_path = os.path.join("/tmp", file.filename)
    file.save(tmp_path)

    try:
        media_id = upload_media(tmp_path)
        result = send_media(media_id)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
