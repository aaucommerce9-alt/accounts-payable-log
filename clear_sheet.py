#!/usr/bin/env python3
"""One-time script: clears all data rows from the tracking sheet, keeps header."""
import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
svc = build("sheets", "v4", credentials=creds)
sheet = svc.spreadsheets()

# Clear everything from row 2 down, keep header in row 1
sheet.values().clear(
    spreadsheetId=SHEET_ID,
    range="Sheet1!A2:Z",
).execute()

print("All data rows cleared. Header row preserved.")
