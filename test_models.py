import google.generativeai as genai

GENAI_API_KEY = "AIzaSyDUJU8w51LuCV1SaTltkruW7xjT17P2sJ4"
genai.configure(api_key=GENAI_API_KEY)

print("Available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")