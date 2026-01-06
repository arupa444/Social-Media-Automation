import google.generativeai as genai
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
import os
import base64

# Load .env variables
load_dotenv()

GENAI_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GENAI_KEY)

# Create model
model = genai.GenerativeModel("gemini-2.0-flash-image-generation")

# Generate image
response = model.generate_content(
    "Create a picture of a futuristic banana with neon lights in a cyberpunk city."
)

# Extract & display image
for candidate in response.candidates:
    for part in candidate.content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            image_bytes = base64.b64decode(part.inline_data.data)
            image = Image.open(BytesIO(image_bytes))
            image.show()
