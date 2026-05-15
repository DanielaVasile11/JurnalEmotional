import google.generativeai as genai

# Pune cheia ta între ghilimele:
GOOGLE_API_KEY = "AIzaSyDalF_jcxX9qMVvCzL0jM0k5eZzeBmjhmM"
genai.configure(api_key=GOOGLE_API_KEY)

print("Caut modelele disponibile pentru această cheie...\n")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
    print("\nCăutare finalizată!")
except Exception as e:
    print(f"Eroare la conectare: {e}")