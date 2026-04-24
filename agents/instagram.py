import os
import cv2
import numpy as np
from google import genai

class InstagramAgent:

    # 🔥 1. SMART TRIM (motion-based)
    def detect_best_segment(self, video_path, clip_length=15):
        cap = cv2.VideoCapture(video_path)

        prev = None
        motion_scores = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev is not None:
                diff = cv2.absdiff(prev, gray)
                score = np.sum(diff)
                motion_scores.append(score)

            prev = gray

        cap.release()

        if len(motion_scores) < 10:
            return 0

        motion_scores = np.array(motion_scores)
        smoothed = np.convolve(
            motion_scores,
            np.ones(10) / 10,
            mode='valid'
        )

        best_frame = int(np.argmax(smoothed))

        fps = 25
        start_time = max(0, (best_frame // fps) - clip_length // 2)

        print("📊 Best frame:", best_frame)
        print("🎯 Start time:", start_time)

        return start_time


    # 🤖 2. GENERATE HOOK (Gemini - FIXED)
    def generate_hook(self):
        try:
            client = genai.Client(
                api_key="AIzaSyCPUX9qrPnojQylc9VsZRx94J5TjHzt828"
            )

            prompt = """
            Give ONE viral Instagram reel hook:
            - Max 5 words
            - Very catchy
            - No explanation
            """

            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )

            text = response.text.strip().upper()

            # sanitize for ffmpeg
            text = text.replace(":", "").replace("'", "").replace("\n", "").replace('"', '')

            # limit to 5 words
            text = " ".join(text.split()[:5])

            print("🤖 Hook:", text)

            return text if text else "WATCH THIS!"

        except Exception as e:
            print("❌ Gemini ERROR:", e)
            return "WATCH THIS!"


    # 🎬 3. PROCESS VIDEO
    def process(self, input_path):
        os.makedirs("outputs", exist_ok=True)

        filename = os.path.basename(input_path)
        output_path = os.path.join("outputs", f"insta_{filename}")

        # 🔥 AI trim
        start_time = self.detect_best_segment(input_path)

        # 🤖 AI hook
        hook = self.generate_hook()

        print("🎯 Start time:", start_time)
        print("🤖 Hook:", hook)

        # 🎥 FFmpeg command
        cmd = f'ffmpeg -y -ss {start_time} -i "{input_path}" -t 15 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawtext=text=\'{hook}\':x=(w-text_w)/2:y=100:fontsize=60:fontcolor=white:box=1:boxcolor=black@0.5" "{output_path}"'

        print("\n🚀 Running FFmpeg:")
        print(cmd)

        os.system(cmd)

        return output_path


# 🧪 TEST
if __name__ == "__main__":
    input_video = "test.mp4"

    if not os.path.exists(input_video):
        print("❌ File not found:", input_video)
        exit()

    agent = InstagramAgent()
    output = agent.process(input_video)

    print("\n🎉 Output saved at:", output)