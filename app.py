import os
import uuid
import requests
import urllib.parse
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Response
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
# Load environment variables
load_dotenv()

GENAI_KEY = os.getenv("GEMINI_API_KEY")
if GENAI_KEY:
    genai.configure(api_key=GENAI_KEY)


CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")

app = FastAPI()

# Scopes needed for posting and identifying the user
# 'openid', 'profile', 'email' -> For login/identity
# 'w_member_social' -> CRITICAL: This allows posting
SCOPES = "openid profile email w_member_social"

os.makedirs("images", exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "LinkedIn Automator is running. Go to /login to authenticate."}


@app.get("/login")
def login():
    """
    Step 1: Redirect user to LinkedIn to authorize the app.
    """
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    # Create the full LinkedIn authorization URL
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urllib.parse.urlencode(params)}"
    return RedirectResponse(auth_url)


@app.get("/callback")
def callback(code: str = None, error: str = None):
    """
    Step 2: LinkedIn redirects back here with a 'code'.
    We exchange this code for an Access Token.
    """
    if error:
        return {"error": error}
    if not code:
        return {"error": "No code received"}

    # Exchange authorization code for access token
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(token_url, data=payload)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=response.json())

    data = response.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in")

    # In a real app, save this token to a database.
    # For now, we print it to the screen so you can grab it.
    return {
        "status": "Success",
        "access_token": access_token,
        "expires_in_seconds": expires_in,
        "message": "Copy the access_token. You will need it for the next step!"
    }


@app.get("/get_user_info")
def get_user_info(access_token: str):
    """
    Step 3 (FIXED): Use the 'userinfo' endpoint which works with 'openid' scope.
    """
    # CORRECT endpoint for openid/profile scopes
    api_url = "https://api.linkedin.com/v2/userinfo"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=response.json())

    user_data = response.json()

    # In the OIDC standard, 'sub' (Subject) is your unique Member ID
    user_id = user_data.get("sub")

    # Construct the full URN format required for posting
    author_urn = f"urn:li:person:{user_id}"

    return {
        "status": "Success",
        "user_id": user_id,
        "author_urn": author_urn,  # <--- SAVE THIS!
        "full_name": user_data.get("name"),
        "email": user_data.get("email"),
        "raw_response": user_data  # Showing full data just in case
    }




@app.post("/generate-image")
async def generate_image(prompt: str = Form(...)):
    try:
        # 1. Initialize the model
        model = genai.GenerativeModel('gemini-2.0-flash-image-generation')
        # 2. Generate content
        response = model.generate_content(prompt)
        print(response)
        if response.parts:
            for part in response.parts:
                if part.inline_data:
                    # Extract raw image bytes and mime type
                    image_data = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"

                    # 3. Determine file extension and unique name
                    ext = "png" if "png" in mime_type else "jpg"
                    filename = f"images/img_{uuid.uuid4()}.{ext}"

                    # 4. Save to local disk
                    with open(filename, "wb") as f:
                        f.write(image_data)
                    print(f"Image saved locally to: {filename}")

                    # 5. Return image to the browser
                    return Response(content=image_data, media_type=mime_type)

        raise HTTPException(status_code=500, detail="No image data found in response.")

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/post_image")
async def post_image(
        access_token: str = Form(...),
        author_urn: str = Form(...),
        caption: str = Form(...),
        file: UploadFile = File(...)
):
    """
    Automates the 3-step flow to post an Image to LinkedIn.
    """

    # --- STEP 1: Register the Upload ---
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"

    register_json = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent"
                }
            ]
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    reg_response = requests.post(register_url, headers=headers, json=register_json)

    if reg_response.status_code != 200:
        return {"error": "Step 1 Failed (Register)", "details": reg_response.json()}

    reg_data = reg_response.json()

    # Extract the upload URL and the Asset ID (URN)
    upload_url = reg_data['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest'][
        'uploadUrl']
    asset_urn = reg_data['value']['asset']

    print(f"Step 1 Success. Asset URN: {asset_urn}")

    # --- STEP 2: Upload the Binary Image Data ---
    # We read the file bytes from the FastAPI upload
    file_content = await file.read()

    # Note: We do NOT send the Authorization header here.
    # The upload_url already contains a secure token.
    upload_response = requests.put(upload_url, data=file_content)

    if upload_response.status_code not in [200, 201]:
        return {"error": "Step 2 Failed (Upload)", "details": upload_response.text}

    print("Step 2 Success. Image uploaded.")

    # --- STEP 3: Create the UGC Post ---
    post_url = "https://api.linkedin.com/v2/ugcPosts"

    post_json = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": caption
                },
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "description": {
                            "text": "Image uploaded via API"
                        },
                        "media": asset_urn,
                        "title": {
                            "text": "My Automated Post"
                        }
                    }
                ]
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    final_response = requests.post(post_url, headers=headers, json=post_json)

    if final_response.status_code != 201:
        return {"error": "Step 3 Failed (Creation)", "details": final_response.json()}

    return {
        "status": "Post Published Successfully!",
        "post_id": final_response.json().get("id"),
        "link": f"https://www.linkedin.com/feed/update/{final_response.json().get('id')}"
    }