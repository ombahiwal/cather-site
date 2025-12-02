# backend/app.py
import json
import logging
import os
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from PIL import Image

from decision_tree import classify_label
from gemini_client import send_to_gemini


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger(__name__)
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

BASE_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage"))
IMAGE_DIR = STORAGE_ROOT / "images"
HISTORY_FILE = STORAGE_ROOT / "history.json"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _load_history():
    if HISTORY_FILE.exists():
        try:
            with HISTORY_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            LOGGER.warning("History file corrupt, resetting.")
    return []


def _write_history(entries):
    with HISTORY_FILE.open("w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)


def _append_history(entry):
    history = _load_history()
    history.insert(0, entry)
    # keep latest 100 entries
    _write_history(history[:100])

app = Flask(__name__, static_folder="../frontend", static_url_path="/")

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    request_id = str(uuid.uuid4())
    LOGGER.info("[%s] Analyze request received", request_id)

    if 'image' not in request.files:
        LOGGER.warning("[%s] No image in request", request_id)
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    if not file.filename:
        LOGGER.warning("[%s] Empty filename", request_id)
        return jsonify({"error": "Filename missing"}), 400

    if file.mimetype not in ALLOWED_CONTENT_TYPES:
        LOGGER.warning("[%s] Unsupported mime type: %s", request_id, file.mimetype)
        return jsonify({"error": "Unsupported image format"}), 400

    filename = file.filename

    raw_bytes = b""
    try:
        raw_bytes = file.read()
        if not raw_bytes:
            raise ValueError("Empty file payload")

        img = Image.open(BytesIO(raw_bytes))
        img.thumbnail((1024, 1024))
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        img_bytes = buffer.getvalue()
    except Exception as exc:
        LOGGER.warning("[%s] Failed to preprocess image: %s", request_id, exc)
        img_bytes = raw_bytes

    try:
        gemini_result = send_to_gemini(img_bytes, filename)
        classification = classify_label(gemini_result)
    except Exception as exc:
        LOGGER.exception("[%s] Analysis failed", request_id)
        return jsonify({"error": "Analysis failed", "details": str(exc)}), 500

    stored_filename = f"{request_id}.jpg"
    try:
        target_bytes = raw_bytes or img_bytes
        with (IMAGE_DIR / stored_filename).open("wb") as fh:
            fh.write(target_bytes)
    except Exception as exc:
        LOGGER.warning("[%s] Failed to persist image: %s", request_id, exc)

    history_entry = {
        "id": request_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "image_url": f"/history/image/{stored_filename}",
        "image_filename": stored_filename,
        "original_filename": filename,
        "classification": classification,
        "gemini": gemini_result,
    }
    try:
        _append_history(history_entry)
    except Exception as exc:
        LOGGER.warning("[%s] Failed to persist history entry: %s", request_id, exc)

    response = {
        "request_id": request_id,
        "gemini": gemini_result,
        "classification": classification,
        "history_entry": history_entry,
    }
    LOGGER.info("[%s] Analysis complete with label %s", request_id, classification["label"])
    return jsonify(response), 200


@app.route("/history", methods=["GET"])
def history():
    return jsonify(_load_history())


@app.route("/history/image/<path:filename>")
def history_image(filename):
    return send_from_directory(str(IMAGE_DIR), filename)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
