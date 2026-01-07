import google.generativeai as genai
from dotenv import load_dotenv
import os
from PIL import Image
import base64
from io import BytesIO

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-image-generation"
)

prompt = "A futuristic humanoid robot teaching students in a classroom, ultra realistic"

response = model.generate_content(prompt)

# Extract image
for part in response.candidates[0].content.parts:
    if "inline_data" in part:
        image_data = base64.b64decode(part.inline_data.data)
        image = Image.open(BytesIO(image_data))
        image.save("nano_banana_output.png")
