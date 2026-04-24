from google import genai

client = genai.Client(api_key="AIzaSyA4RqMmg8O0gjbMplVuaeJNr4BKJj8Szbc")

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Explain how AI works in a few words"
)

print(response.text)