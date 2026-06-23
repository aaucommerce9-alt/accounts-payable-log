"""
Manual OAuth2 flow — no PKCE, works in headless environments.
Step 1: run this to get the URL, visit it, copy the code.
Step 2: set CODE below and run again to save token.json.
"""
import json, os, sys, webbrowser
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from swiftcart import config

with open(config.GMAIL_CREDENTIALS_FILE) as f:
    creds_data = json.load(f)["installed"]

CLIENT_ID     = creds_data["client_id"]
CLIENT_SECRET = creds_data["client_secret"]
REDIRECT_URI  = "urn:ietf:wg:oauth:2.0:oob"
SCOPE         = " ".join(config.GMAIL_SCOPES)

# ── Step 1: print auth URL ────────────────────────────────────────────────────
from urllib.parse import urlencode
params = urlencode({
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": SCOPE,
    "access_type": "offline",
    "prompt": "consent",
})
auth_url = f"https://accounts.google.com/o/oauth2/auth?{params}"

CODE = ""   # ← paste code here for Step 2

if not CODE:
    print("\n" + "=" * 60)
    print("STEP 1 — Open this URL in your browser:")
    print(auth_url)
    print("=" * 60)
    print("\nThen paste the code into CODE= above and run again.")
    sys.exit(0)

# ── Step 2: exchange code for tokens ─────────────────────────────────────────
resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": CODE,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
})
resp.raise_for_status()
token_data = resp.json()

# Save in google-auth compatible format
token_json = {
    "token": token_data.get("access_token"),
    "refresh_token": token_data.get("refresh_token"),
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scopes": config.GMAIL_SCOPES,
    "expiry": None,
}
with open(config.GMAIL_TOKEN_FILE, "w") as f:
    json.dump(token_json, f, indent=2)

print(f"\n✓ token.json saved. Scopes: {token_data.get('scope')}")
