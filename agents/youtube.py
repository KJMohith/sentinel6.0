import os
import subprocess
import whisper
import time
from google import genai

# -----------------------------
# CONFIG
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs_youtube")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Gemini Client
client = genai.Client(api_key="YOUR_API_KEY")


# -----------------------------
# RETRY FUNCTION
# -----------------------------
def gemini_request_with_retry(prompt, retries=3, delay=3):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )
            return response.text

        except Exception as e:
            print(f"⚠️ Gemini error (attempt {attempt+1}):", e)

            if attempt < retries - 1:
                wait_time = delay * (attempt + 1)
                print(f"⏳ Waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("❌ All retries failed")

    return None


# -----------------------------
# 1. SPLIT VIDEO
# -----------------------------
def split_video(input_path):
    parts = {
        "start": os.path.join(OUTPUT_DIR, "start.mp4"),
        "middle": os.path.join(OUTPUT_DIR, "middle.mp4"),
        "end": os.path.join(OUTPUT_DIR, "end.mp4"),
    }

    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-t", "20", parts["start"]])
    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-ss", "20", "-t", "20", parts["middle"]])
    subprocess.run(["ffmpeg", "-y", "-sseof", "-20", "-i", input_path, parts["end"]])

    return parts


# -----------------------------
# 2. WHISPER TEXT
# -----------------------------
def get_text(video_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    return result["text"]


# -----------------------------
# 3. AI SELECT SEGMENT
# -----------------------------
def choose_best_segment(texts):
    prompt = f"""
    Which part is most engaging for a YouTube short?

    START: {texts['start']}
    MIDDLE: {texts['middle']}
    END: {texts['end']}

    Reply only one word: start or middle or end
    """

    result = gemini_request_with_retry(prompt)

    if result:
        result = result.strip().lower()
        if result in ["start", "middle", "end"]:
            print("🤖 AI selected:", result)
            return result

    print("⚠️ Using fallback")
    return "middle"


# -----------------------------
# 4. CREATE SHORTS
# -----------------------------
def create_shorts(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=1080:1920,setsar=1",
        "-c:v", "libx264", "-c:a", "aac",
        output_path
    ])
    return output_path


# -----------------------------
# 5. CREATE FULL VIDEO (FIXED)
# -----------------------------
def create_full_video(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=1280:-2",
        "-c:v", "libx264", "-c:a", "aac",
        output_path
    ])
    return output_path


# -----------------------------
# TIME FORMAT
# -----------------------------
def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02}:{mins:02}:{secs:06.3f}".replace(".", ",")


# -----------------------------
# 6. GENERATE SYNCED SUBTITLES
# -----------------------------
def generate_subtitles(video_path, srt_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)

    # optional AI enhancement
    prompt = f"""
    Clean this transcript:
    - Add punctuation
    - Improve readability

    TEXT:
    {result['text']}
    """

    ai_text = gemini_request_with_retry(prompt)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"]):
            start = format_time(seg["start"])
            end = format_time(seg["end"])

            text = seg["text"].strip()

            f.write(f"{i+1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")

    return srt_path


# -----------------------------
# 7. ADD SUBTITLES
# -----------------------------
def add_subtitles(video_path, srt_path, output_path):
    srt_dir = os.path.dirname(srt_path)
    srt_file = os.path.basename(srt_path)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={srt_file}",
        "-c:a", "copy",
        output_path
    ], cwd=srt_dir)

    return output_path


# -----------------------------
# 8. COMMUNITY POST
# -----------------------------
def generate_community_post(text):
    prompt = f"""
    Generate a short engaging YouTube community post:

    {text}
    """

    result = gemini_request_with_retry(prompt)

    if result:
        return result

    return "🔥 Watch this amazing moment!"


# -----------------------------
# MAIN PIPELINE
# -----------------------------
def process_youtube(video_path):
    filename = os.path.basename(video_path).split(".")[0]

    print("\n🎬 Splitting video...")
    parts = split_video(video_path)

    print("🧠 Extracting text...")
    texts = {k: get_text(v) for k, v in parts.items()}

    print("🤖 Selecting best segment...")
    best = choose_best_segment(texts)
    selected_video = parts[best]

    shorts = os.path.join(OUTPUT_DIR, f"{filename}_shorts.mp4")
    full = os.path.join(OUTPUT_DIR, f"{filename}_full.mp4")
    srt = os.path.join(OUTPUT_DIR, f"{filename}.srt")
    subtitled = os.path.join(OUTPUT_DIR, f"{filename}_subtitled.mp4")

    print("📱 Creating Shorts...")
    create_shorts(selected_video, shorts)

    print("🎥 Creating Full Video...")
    create_full_video(video_path, full)

    print("📝 Generating Subtitles...")
    full_text = get_text(video_path)
    generate_subtitles(video_path, srt)

    print("🎬 Adding subtitles...")
    add_subtitles(full, srt, subtitled)

    print("💬 Generating Community Post...")
    community = generate_community_post(full_text)

    return {
        "shorts": shorts,
        "full": full,
        "subtitled": subtitled,
        "community_post": community
    }


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    test_video = r"C\:\Users\Hemanth\Desktop\ksit\sentinel6.0\uploads\test.mp4"

    result = process_youtube(test_video)

    print("\n✅ DONE")
    for k, v in result.items():
        print(f"{k}: {v}")