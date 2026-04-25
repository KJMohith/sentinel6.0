import os
import subprocess
import time
import random
import whisper
from google import genai

# ================= CONFIG =================
API_KEY = "AIzaSyBtDmZ3UYBUZQwOlYjgdHXPNGQJvD4wT9o"

INPUT_VIDEO = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\uploads\\test.mp4"
OUTPUT_VIDEO = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs\\final_video.mp4"
OUTPUT_TEXT = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs\\description.txt"

START = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs\\start.mp4"
MID = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs\\mid.mp4"
END = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs\\end.mp4"
FORMATTED = "C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs\\formatted.mp4"

os.makedirs("C:\\Users\\someo\\Desktop\\ksit\\sentinel6.0\\outputs", exist_ok=True)

# ================= GEMINI =================
client = genai.Client(api_key=API_KEY)

# Cache last good outputs (prevents demo failures)
last_good = {
    "category": None,
    "description": None,
    "overlay": None
}

# ================= AI CALL =================
def ask_ai(prompt, retries=3):
    for attempt in range(retries):
        try:
            res = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )

            if res.text:
                return res.text.strip()

        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} failed:", e)

            if "503" in str(e) or "UNAVAILABLE" in str(e):
                wait = (attempt + 1) * 2 + random.uniform(0, 1)
                print(f"⏳ Retrying in {round(wait,1)} sec...")
                time.sleep(wait)
                continue

            break

    print("❌ Final failure, using fallback/cache")
    return None

# ================= VIDEO =================
def get_duration(video):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    return float(out.stdout.strip())

def clip(video, start, dur, out):
    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-ss", str(start),
        "-t", str(dur),
        "-c:v", "libx264",
        "-c:a", "aac",
        out
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ================= TRANSCRIBE =================
def transcribe_video(video):
    """Extract speech from video using Whisper. Returns plain text or empty string."""
    try:
        print("🎙️ Transcribing video with Whisper...")
        model = whisper.load_model("base")
        result = model.transcribe(video)
        text = result.get("text", "").strip()
        print(f"📝 Transcript ({len(text)} chars): {text[:120]}{'...' if len(text) > 120 else ''}")
        return text
    except Exception as e:
        print(f"⚠️ Transcription failed: {e}")
        return ""

# ================= SMART TRIM =================
def smart_trim(video):
    d = get_duration(video)

    clip(video, 0, 10, START)
    clip(video, max(d/2 - 5, 0), 10, MID)
    clip(video, max(d - 10, 0), 10, END)

    choice = ask_ai("""
    For viral short videos, which part is most engaging?

    start
    middle
    end

    Answer ONLY one word.
    """)

    if choice:
        choice = choice.lower()
        if "start" in choice:
            return START
        elif "end" in choice:
            return END

    return MID

# ================= CLASSIFY =================
def classify(transcript=""):
    transcript_section = f"\nVideo transcript:\n{transcript[:1000]}\n" if transcript.strip() else ""

    result = ask_ai(f"""
    Classify this video into ONE category based on its content.
    {transcript_section}
    Categories:
    funny
    emotional
    informative
    shocking
    satisfying
    motivational
    neutral
    casual
    vlogging

    Output ONLY the single category word.
    """)

    if result:
        last_good["category"] = result.lower().split()[0]
        return last_good["category"]

    return last_good["category"] or "engaging"

# ================= DESCRIPTION =================
def generate_description(category, transcript=""):
    transcript_section = (
        f"\nHere is what was said or shown in the video:\n\"\"\"\n{transcript[:1500]}\n\"\"\"\n"
        if transcript.strip()
        else ""
    )

    text = ask_ai(f"""
    Write a 3–4 line post for X (Twitter) about this specific video.
    {transcript_section}
    Video category: {category}

    STRICT RULES:
    - Write ONLY about what actually happens in this video
    - First person tone, as if you filmed or experienced it
    - Include 1–2 relevant emojis
    - Sound natural and human, not like a bot
    - Spark curiosity or emotion based on the real content
    - No hashtags
    - Do NOT make up content that isn't in the transcript
    """)

    if text:
        last_good["description"] = text
        return text

    return last_good["description"] or (
        "I didn’t expect this at all 😅\n"
        "but the way it plays out is actually interesting.\n"
        "Definitely one of those clips you watch twice."
    )

# ================= OVERLAY =================
def generate_overlay(category, transcript=""):
    transcript_hint = f"\nVideo is about: {transcript[:300]}" if transcript.strip() else ""

    text = ask_ai(f"""
    Create a viral overlay text for this video.
    {transcript_hint}
    Category: {category}

    STRICT:
    - Max 4 words
    - MUST include one emoji
    - Very catchy, scroll-stopping, relevant to the actual content
    - No explanation

    Examples:
    funny → this got me 😂
    shocking → wait what 😳

    Output ONLY the overlay text.
    """)

    if text:
        last_good["overlay"] = text
        return text

    return last_good["overlay"] or "watch this 👀"

# ================= FORMAT =================
def format_video(video):
    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-vf",
        "scale=1080:1080:force_original_aspect_ratio=decrease,"
        "pad=1080:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-c:a", "aac",
        FORMATTED
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return FORMATTED

# ================= RENDER =================
def render(video, text):
    safe = text.replace(":", "").replace("'", "")

    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-vf",
        f"drawtext=fontfile='C\\:/Windows/Fonts/seguiemj.ttf':"
        f"text='{safe}':fontcolor=white:fontsize=52:"
        f"x=(w-text_w)/2:y=60",
        "-c:v", "libx264",
        "-c:a", "aac",
        OUTPUT_VIDEO
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ================= PIPELINE =================
def run():
    if not os.path.exists(INPUT_VIDEO):
        print("❌ Missing video:", INPUT_VIDEO)
        return

    print("🚀 Running AI X Bot...\n")

    print("🎙️ Transcribing video...")
    transcript = transcribe_video(INPUT_VIDEO)

    print("✂️ Selecting best clip...")
    clip_path = smart_trim(INPUT_VIDEO)

    print("📐 Formatting video...")
    formatted = format_video(clip_path)

    print("🧠 Classifying content...")
    category = classify(transcript)
    print("Category:", category)

    print("📝 Generating description...")
    description = generate_description(category, transcript)

    print("🎯 Generating overlay...")
    overlay = generate_overlay(category, transcript)

    print("🎬 Rendering final video...")
    render(formatted, overlay)

    with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
        f.write(description)

    print("\n✅ DONE")
    print("📹 Video:", OUTPUT_VIDEO)
    print("📝 Text:", OUTPUT_TEXT)
    print("🎯 Overlay:", overlay)

# ================= RUN =================
if __name__ == "__main__":
    run()