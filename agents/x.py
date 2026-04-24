import os
import random
import subprocess
import time
from google import genai

API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY) if API_KEY else None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs_x")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def ask_ai(prompt, retries=3):
    if client is None:
        return None

    for attempt in range(retries):
        try:
            res = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
            )
            if res.text:
                return res.text.strip()
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep((attempt + 1) * 2 + random.uniform(0, 1))
                continue
            break
    return None


def get_duration(video):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def clip(video, start, dur, out):
    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-ss", str(start),
        "-t", str(dur),
        "-c:v", "libx264",
        "-c:a", "aac",
        out,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def smart_trim(video, output_prefix):
    d = get_duration(video)
    start_clip = os.path.join(OUTPUT_DIR, f"{output_prefix}_start.mp4")
    mid_clip = os.path.join(OUTPUT_DIR, f"{output_prefix}_mid.mp4")
    end_clip = os.path.join(OUTPUT_DIR, f"{output_prefix}_end.mp4")

    clip(video, 0, 10, start_clip)
    clip(video, max(d / 2 - 5, 0), 10, mid_clip)
    clip(video, max(d - 10, 0), 10, end_clip)

    choice = ask_ai(
        """
        For viral short videos, which part is most engaging?
        start
        middle
        end
        Answer ONLY one word.
        """
    )

    if choice:
        selection = choice.lower()
        if "start" in selection:
            return start_clip
        if "end" in selection:
            return end_clip

    return mid_clip


def generate_overlay():
    text = ask_ai(
        """
        Create a viral overlay text.
        STRICT:
        - Max 4 words
        - MUST include emoji
        - Very catchy and scroll-stopping
        - No explanation
        Output ONLY the text.
        """
    )
    return text or "watch this 👀"


def format_video(video, output_prefix):
    formatted = os.path.join(OUTPUT_DIR, f"{output_prefix}_formatted.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-vf",
        "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-c:a", "aac",
        formatted,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return formatted


def render(video, text, output_path):
    safe = text.replace(":", "").replace("'", "")
    cmd = [
        "ffmpeg", "-y",
        "-i", video,
        "-vf",
        f"drawtext=text='{safe}':fontcolor=white:fontsize=52:x=(w-text_w)/2:y=60",
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def process_x(input_video):
    filename = os.path.splitext(os.path.basename(input_video))[0]
    output_prefix = f"x_{filename}"
    final_video = os.path.join(OUTPUT_DIR, f"{output_prefix}.mp4")

    picked_clip = smart_trim(input_video, output_prefix)
    formatted_clip = format_video(picked_clip, output_prefix)
    overlay = generate_overlay()
    render(formatted_clip, overlay, final_video)

    return final_video


if __name__ == "__main__":
    sample = os.path.join(BASE_DIR, "uploads", "test.mp4")
    if os.path.exists(sample):
        print(process_x(sample))
