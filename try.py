from google import genai
from google.genai import types  # Import types to access HttpOptions
from PIL import Image
from io import BytesIO
import base64
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Client with HttpOptions for timeout
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=120000)  # Timeout in milliseconds (120s = 120,000ms)
)

prompt = "A simple illustration of a small robot sitting on a desk"

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash-image-generation", # Ensure this model ID is correct/available to you
        contents=prompt
    )

    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                img_bytes = base64.b64decode(part.inline_data.data)
                img = Image.open(BytesIO(img_bytes)).convert("RGB")
                img.save("nano_banana.png")
                print("Image saved successfully as nano_banana.png")
    else:
        print("No content generated.")

except Exception as e:
    print(f"An error occurred: {e}")