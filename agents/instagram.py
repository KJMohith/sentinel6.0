import os

class InstagramAgent:
    def process(self, input_path):
        # Ensure outputs folder exists
        os.makedirs("outputs", exist_ok=True)

        # Get filename
        filename = os.path.basename(input_path)
        output_path = os.path.join("outputs", f"insta_{filename}")

        # ✅ FFmpeg command (safe version WITHOUT text first)
        cmd = f'ffmpeg -y -i "{input_path}" -vf scale=1080:1920 -t 15 "{output_path}"'

        print("\n🚀 Running FFmpeg command:")
        print(cmd)

        # Run command
        result = os.system(cmd)

        # Check if success
        if result != 0:
            print("❌ FFmpeg failed")
            return None

        print("✅ Video processed successfully!")
        return output_path


# ✅ TEST CODE
if __name__ == "__main__":
    # 🔁 CHANGE THIS if your video is outside agents folder
    input_video = "test.mp4"  
    # OR use:
    # input_video = "../test.mp4"

    print("📁 Current working directory:", os.getcwd())

    # Check file exists
    if not os.path.exists(input_video):
        print("❌ File not found:", input_video)
        exit()

    agent = InstagramAgent()
    output = agent.process(input_video)

    if output:
        print("\n🎉 Output saved at:")
        print(output)