from google import genai

client = genai.Client(api_key="AIzaSyCPUX9qrPnojQylc9VsZRx94J5TjHzt828")

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Explain how AI works in a few words"
)

print(response.text)