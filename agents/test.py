from google import genai

client = genai.Client(api_key="AIzaSyB8Iv8S6GoRziCa_ZyW-UZ83iA0YbDWzmU")

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Explain how AI works in a few words"
)

print(response.text)