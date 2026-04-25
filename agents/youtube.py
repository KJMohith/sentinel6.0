import os
import subprocess
import whisper
import time
import json
import asyncio
import edge_tts
from google import genai

# =====================================================
# CONFIG
# =====================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs_youtube")   # keep repo's folder name
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Gemini Client
client = genai.Client(api_key="AIzaSyBhiGZAj98tE6dgaXOc5rcd_IvW-JmgxnE")


# =====================================================
# GEMINI SAFE RETRY
# =====================================================
def gemini_request_with_retry(prompt, retries=3, delay=3):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )
            return response.text.strip()

        except Exception as e:
            print(f"⚠️ Gemini Error Attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                wait = delay * (attempt + 1)
                print(f"⏳ Waiting {wait} sec...")
                time.sleep(wait)

    return None


# =====================================================
# GET VIDEO DURATION  (new version — uses ffprobe json)
# =====================================================
def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


# =====================================================
# 1. SPLIT VIDEO  (new version — duration-aware clips)
# =====================================================
def split_video(input_path):
    duration = get_video_duration(input_path)

    start_len     = min(10, duration)
    middle_start  = max(0, duration / 2 - 5)
    end_start     = max(0, duration - 10)

    parts = {
        "start":  os.path.join(OUTPUT_DIR, "start.mp4"),
        "middle": os.path.join(OUTPUT_DIR, "middle.mp4"),
        "end":    os.path.join(OUTPUT_DIR, "end.mp4"),
    }

    clips = {
        "start":  ("0",              str(start_len)),
        "middle": (str(middle_start), "10"),
        "end":    (str(end_start),    "10"),
    }

    for name in parts:
        ss, t = clips[name]
        subprocess.run([
            "ffmpeg", "-y",
            "-i", input_path,
            "-ss", ss,
            "-t", t,
            "-c:v", "libx264",
            "-c:a", "aac",
            parts[name]
        ])

    return parts


# =====================================================
# 2. WHISPER TEXT
# =====================================================
def get_text(video_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    return result["text"]


# =====================================================
# 3. AI SELECT SEGMENT
# =====================================================
def choose_best_segment(texts):
    prompt = f"""
    Which part is most engaging for a YouTube Short?

    START:
    {texts['start']}

    MIDDLE:
    {texts['middle']}

    END:
    {texts['end']}

    Reply ONLY: start OR middle OR end
    """

    result = gemini_request_with_retry(prompt)

    if result:
        result = result.lower()
        if "start" in result:
            return "start"
        elif "middle" in result:
            return "middle"
        elif "end" in result:
            return "end"

    print("⚠️ Using fallback: middle")
    return "middle"


# =====================================================
# 4. CREATE SHORTS
# =====================================================
def create_shorts(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=1080:1920,setsar=1",
        "-c:v", "libx264", "-c:a", "aac",
        output_path
    ])
    return output_path


# =====================================================
# 5. CREATE FULL VIDEO
# =====================================================
def create_full_video(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=1280:-2",
        "-c:v", "libx264", "-c:a", "aac",
        output_path
    ])
    return output_path


# =====================================================
# TIME FORMAT
# =====================================================
def format_time(seconds):
    hrs  = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02}:{mins:02}:{secs:06.3f}".replace(".", ",")


# =====================================================
# 6. GENERATE SYNCED SUBTITLES
# =====================================================
def generate_subtitles(video_path, srt_path):
    model  = whisper.load_model("base")
    result = model.transcribe(video_path)

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"]):
            start = format_time(seg["start"])
            end   = format_time(seg["end"])
            text  = seg["text"].strip()

            f.write(f"{i+1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")

    return srt_path


# =====================================================
# 7. ADD SUBTITLES
# =====================================================
def add_subtitles(video_path, srt_path, output_path):
    srt_file = os.path.basename(srt_path)
    cwd      = os.path.dirname(srt_path)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={srt_file}",
        "-c:a", "copy",
        output_path
    ], cwd=cwd)

    return output_path


# =====================================================
# 8. COMMUNITY POST
# =====================================================
def generate_community_post(text):
    prompt = f"""
    Generate one short engaging YouTube community post:

    {text}
    """
    result = gemini_request_with_retry(prompt)
    return result if result else "🔥 Watch our latest video now!"


# =====================================================
# 9. TRANSLATE TEXT  (new — Gemini translation)
# =====================================================
def translate_text(text, language="Hindi"):
    prompt = f"""
    Translate this text into natural spoken {language}.
    Return ONLY the translated text, nothing else.

    TEXT:
    {text}
    """
    result = gemini_request_with_retry(prompt)
    return result if result else text


# =====================================================
# 10. EDGE TTS — Male Hindi Neural Voice  (new)
# =====================================================
async def edge_generate(text, output_mp3):
    communicate = edge_tts.Communicate(
        text=text,
        voice="hi-IN-MadhurNeural"
    )
    await communicate.save(output_mp3)


def create_tts_audio(text, output_mp3):
    asyncio.run(edge_generate(text, output_mp3))
    return output_mp3


# =====================================================
# 11. DUBBED VIDEO — replace audio track  (new)
# =====================================================
def create_dubbed_video(video_path, audio_path, output_path):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-shortest",
        output_path
    ])
    return output_path


# =====================================================
# 12. TRANSLATE + DUB PIPELINE  (new)
# =====================================================
def translate_and_dub(video_path, filename):
    print("🌍 Translating transcript to Hindi...")
    text       = get_text(video_path)
    translated = translate_text(text, "Hindi")

    mp3_path = os.path.join(OUTPUT_DIR, f"{filename}_hindi.mp3")
    dubbed   = os.path.join(OUTPUT_DIR, f"{filename}_hindi_dubbed.mp4")

    print("🎙️ Generating Male Hindi Neural Voice (edge-tts)...")
    create_tts_audio(translated, mp3_path)

    print("🎬 Creating Hindi dubbed video...")
    create_dubbed_video(video_path, mp3_path, dubbed)

    return dubbed


# =====================================================
# MAIN PIPELINE
# =====================================================
def process_youtube(video_path):
    filename = os.path.basename(video_path).split(".")[0]

    print("\n🎬 Splitting video...")
    parts = split_video(video_path)

    print("🧠 Extracting text from segments...")
    texts = {k: get_text(v) for k, v in parts.items()}

    print("🤖 Selecting best segment...")
    best           = choose_best_segment(texts)
    selected_video = parts[best]

    shorts    = os.path.join(OUTPUT_DIR, f"{filename}_shorts.mp4")
    full      = os.path.join(OUTPUT_DIR, f"{filename}_full.mp4")
    srt       = os.path.join(OUTPUT_DIR, f"{filename}.srt")
    subtitled = os.path.join(OUTPUT_DIR, f"{filename}_subtitled.mp4")

    print("📱 Creating Shorts...")
    create_shorts(selected_video, shorts)

    print("🎥 Creating Full Video...")
    create_full_video(video_path, full)

    print("📝 Generating Subtitles...")
    full_text = get_text(video_path)
    generate_subtitles(video_path, srt)

    print("🎬 Adding Subtitles...")
    add_subtitles(full, srt, subtitled)

    print("💬 Creating Community Post...")
    community = generate_community_post(full_text)

    print("🌍 Creating Hindi Dubbed Video...")
    dubbed = translate_and_dub(video_path, filename)

    return {
        "shorts":        shorts,
        "full":          full,
        "subtitled":     subtitled,
        "community_post": community,
        "hindi_dubbed":  dubbed
    }


# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    test_video = r"C:\Users\kusha\sentinel6.0\uploads\test.mp4"

    result = process_youtube(test_video)

    print("\n✅ DONE")
    for k, v in result.items():
        print(f"{k}: {v}")