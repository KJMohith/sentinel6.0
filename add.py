import os
import uuid
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from agents.instagram import InstagramAgent
from agents.x import process_x
from agents.youtube import process_youtube

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}

app = Flask(__name__, template_folder="templates", static_folder="static")


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _to_public_path(path: str) -> str:
    abs_path = Path(path).resolve()
    return f"/download/{abs_path.parent.name}/{abs_path.name}"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/upload")
def upload():
    if "video" not in request.files:
        return jsonify({"success": False, "error": "No video file found in request."}), 400

    file = request.files["video"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"success": False, "error": "Unsupported file type."}), 400

    safe_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    upload_path = UPLOAD_DIR / unique_name
    file.save(upload_path)

    try:
        instagram_output = InstagramAgent().process(str(upload_path))
        x_output = process_x(str(upload_path))
        youtube_outputs = process_youtube(str(upload_path))

        outputs = {
            "instagram": _to_public_path(instagram_output),
            "x": _to_public_path(x_output),
            "youtube": _to_public_path(youtube_outputs["shorts"]),
        }

        return jsonify({"success": True, "outputs": outputs})

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.get("/download/<folder>/<filename>")
def download(folder: str, filename: str):
    target_dir = BASE_DIR / folder
    if not target_dir.exists():
        return jsonify({"success": False, "error": "File folder does not exist."}), 404
    return send_from_directory(target_dir, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
