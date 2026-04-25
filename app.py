import os
import sys
import json
import queue
import threading
import traceback
from flask import (
    Flask, render_template, request,
    jsonify, send_from_directory, Response, stream_with_context
)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.join(BASE_DIR, "agents")

# This is the folder the agents expect the raw video to live in.
# YouTube agent reads OUTPUT_DIR from its own BASE_DIR (project root).
# Instagram agent computes its own base_dir from __file__.
# X agent has hardcoded Windows paths we'll patch at runtime.
UPLOADS_DIR         = os.path.join(BASE_DIR, "uploads")
OUTPUTS_YOUTUBE_DIR = os.path.join(BASE_DIR, "outputs_youtube")
OUTPUTS_INSTAGRAM_DIR = os.path.join(BASE_DIR, "outputs_instagram")
OUTPUTS_X_DIR       = os.path.join(BASE_DIR, "outputs_x")

for d in [UPLOADS_DIR, OUTPUTS_YOUTUBE_DIR, OUTPUTS_INSTAGRAM_DIR, OUTPUTS_X_DIR]:
    os.makedirs(d, exist_ok=True)

# Add agents folder to path so we can import the agents
sys.path.insert(0, AGENTS_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SERVE OUTPUT FILES
# All three agents save files using absolute paths inside their output dirs.
# We expose those dirs as static routes so the browser can play/download them.
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/outputs_youtube/<path:filename>")
def serve_youtube_output(filename):
    return send_from_directory(OUTPUTS_YOUTUBE_DIR, filename)

@app.route("/outputs_instagram/<path:filename>")
def serve_instagram_output(filename):
    return send_from_directory(OUTPUTS_INSTAGRAM_DIR, filename)

@app.route("/outputs_x/<path:filename>")
def serve_x_output(filename):
    return send_from_directory(OUTPUTS_X_DIR, filename)

# ─────────────────────────────────────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

# ─────────────────────────────────────────────────────────────────────────────
# RUN X AGENT
#
# x.py uses module-level global variables for ALL file paths (hardcoded Windows
# paths). The functions smart_trim(), format_video(), render() all READ those
# globals directly (e.g. START, MID, END, FORMATTED, OUTPUT_VIDEO, OUTPUT_TEXT).
# We must patch the module's globals BEFORE calling any function.
# We do NOT touch x.py itself.
# ─────────────────────────────────────────────────────────────────────────────

def run_x_agent(video_path, event_queue):
    import x as x_mod

    # Patch every path the x agent uses to point at our local outputs_x dir
    x_mod.INPUT_VIDEO  = video_path
    x_mod.OUTPUT_VIDEO = os.path.join(OUTPUTS_X_DIR, "final_video.mp4")
    x_mod.OUTPUT_TEXT  = os.path.join(OUTPUTS_X_DIR, "description.txt")
    x_mod.START        = os.path.join(OUTPUTS_X_DIR, "start.mp4")
    x_mod.MID          = os.path.join(OUTPUTS_X_DIR, "mid.mp4")
    x_mod.END          = os.path.join(OUTPUTS_X_DIR, "end.mp4")
    x_mod.FORMATTED    = os.path.join(OUTPUTS_X_DIR, "formatted.mp4")

    event_queue.put({"agent": "x", "status": "running", "msg": "🎙️ Transcribing video for X…"})
    transcript = x_mod.transcribe_video(video_path)

    event_queue.put({"agent": "x", "status": "running", "msg": "✂️ Smart trimming for X…"})
    clip_path = x_mod.smart_trim(video_path)

    event_queue.put({"agent": "x", "status": "running", "msg": "📐 Formatting to square…"})
    formatted = x_mod.format_video(clip_path)

    event_queue.put({"agent": "x", "status": "running", "msg": "🧠 Classifying content…"})
    category = x_mod.classify(transcript)

    event_queue.put({"agent": "x", "status": "running", "msg": "📝 Writing caption from transcript…"})
    description = x_mod.generate_description(category, transcript)

    event_queue.put({"agent": "x", "status": "running", "msg": "🎯 Generating overlay…"})
    overlay = x_mod.generate_overlay(category, transcript)

    event_queue.put({"agent": "x", "status": "running", "msg": "🎬 Rendering final clip…"})
    x_mod.render(formatted, overlay)

    # Write description text file
    with open(x_mod.OUTPUT_TEXT, "w", encoding="utf-8") as f:
        f.write(description)

    output_video_path = x_mod.OUTPUT_VIDEO
    return {
        "video_url":    "/outputs_x/" + os.path.basename(output_video_path),
        "video_exists":  os.path.exists(output_video_path),
        "description":   description,
        "overlay":       overlay,
        "category":      category,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RUN YOUTUBE AGENT
#
# youtube.py defines OUTPUT_DIR at module level from its own BASE_DIR.
# Since youtube.py lives in agents/ and BASE_DIR = dirname(dirname(__file__)),
# OUTPUT_DIR correctly resolves to project_root/outputs_youtube — which is
# exactly OUTPUTS_YOUTUBE_DIR. We just call process_youtube(video_path).
# It returns: { shorts, full, subtitled, community_post } — all absolute paths.
# ─────────────────────────────────────────────────────────────────────────────

def run_youtube_agent(video_path, event_queue):
    from youtube import process_youtube

    event_queue.put({"agent": "youtube", "status": "running", "msg": "🎬 Splitting video into segments…"})
    result = process_youtube(video_path)
    # result keys: shorts, full, subtitled, community_post, hindi_dubbed

    shorts_path       = result["shorts"]
    subtitled_path    = result["subtitled"]
    hindi_dubbed_path = result["hindi_dubbed"]
    community         = result["community_post"]

    return {
        "shorts_url":         "/outputs_youtube/" + os.path.basename(shorts_path),
        "subtitled_url":      "/outputs_youtube/" + os.path.basename(subtitled_path),
        "hindi_dubbed_url":   "/outputs_youtube/" + os.path.basename(hindi_dubbed_path),
        "shorts_exists":         os.path.exists(shorts_path),
        "subtitled_exists":      os.path.exists(subtitled_path),
        "hindi_dubbed_exists":   os.path.exists(hindi_dubbed_path),
        "community_post":     community,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RUN INSTAGRAM AGENT
#
# InstagramAgent.process(input_path) computes its own base_dir from __file__
# (which lives in agents/), goes up one level → project root, and saves to
# project_root/outputs_instagram/insta_<filename>. Returns absolute path.
# ─────────────────────────────────────────────────────────────────────────────

def run_instagram_agent(video_path, event_queue):
    from instagram import InstagramAgent

    event_queue.put({"agent": "instagram", "status": "running", "msg": "📊 Detecting best motion segment…"})
    agent = InstagramAgent()

    event_queue.put({"agent": "instagram", "status": "running", "msg": "🤖 Generating AI hook text…"})
    output_path = agent.process(video_path)
    # output_path is the absolute path to insta_<filename>.mp4

    return {
        "reel_url":    "/outputs_instagram/" + os.path.basename(output_path),
        "reel_exists":  os.path.exists(output_path),
    }


# ─────────────────────────────────────────────────────────────────────────────
# /upload  — receives the video, saves to uploads/, streams SSE progress
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"error": "No video file in request"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Save the uploaded file into uploads/
    save_path = os.path.join(UPLOADS_DIR, file.filename)
    file.save(save_path)

    # Queue for agent threads to push events into
    event_queue = queue.Queue()

    def run_all_agents():
        results = {}
        errors  = {}

        # ── YouTube ────────────────────────────────────────────────────────
        try:
            yt = run_youtube_agent(save_path, event_queue)
            results["youtube"] = yt
            event_queue.put({"agent": "youtube", "status": "done",
                             "msg": "✅ YouTube done"})
        except Exception:
            tb = traceback.format_exc()
            errors["youtube"] = tb
            event_queue.put({"agent": "youtube", "status": "error",
                             "msg": "❌ YouTube failed", "error": tb})

        # ── Instagram ──────────────────────────────────────────────────────
        try:
            ig = run_instagram_agent(save_path, event_queue)
            results["instagram"] = ig
            event_queue.put({"agent": "instagram", "status": "done",
                             "msg": "✅ Instagram done"})
        except Exception:
            tb = traceback.format_exc()
            errors["instagram"] = tb
            event_queue.put({"agent": "instagram", "status": "error",
                             "msg": "❌ Instagram failed", "error": tb})

        # ── X ──────────────────────────────────────────────────────────────
        try:
            xd = run_x_agent(save_path, event_queue)
            results["x"] = xd
            event_queue.put({"agent": "x", "status": "done",
                             "msg": "✅ X done"})
        except Exception:
            tb = traceback.format_exc()
            errors["x"] = tb
            event_queue.put({"agent": "x", "status": "error",
                             "msg": "❌ X failed", "error": tb})

        # ── Final event ────────────────────────────────────────────────────
        event_queue.put({
            "agent": "complete",
            "status": "done",
            "results": results,
            "errors":  errors,
        })

    thread = threading.Thread(target=run_all_agents, daemon=True)
    thread.start()

    # Stream SSE events back to browser
    def generate():
        while True:
            try:
                event = event_queue.get(timeout=600)  # 10 min max
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("agent") == "complete":
                    break
            except queue.Empty:
                # Keep connection alive
                yield "data: {\"agent\":\"ping\"}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n🚀 Sentinel 6.0 starting...")
    print(f"   Uploads  → {UPLOADS_DIR}")
    print(f"   YouTube  → {OUTPUTS_YOUTUBE_DIR}")
    print(f"   Instagram→ {OUTPUTS_INSTAGRAM_DIR}")
    print(f"   X        → {OUTPUTS_X_DIR}\n")
    app.run(debug=True, port=5000, threaded=True)