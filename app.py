import os
import requests
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")

app = FastAPI()

# Scopes needed for posting and identifying the user
# 'openid', 'profile', 'email' -> For login/identity
# 'w_member_social' -> CRITICAL: This allows posting
SCOPES = "openid profile email w_member_social"


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