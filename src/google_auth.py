"""
Google Auth — Personal Ops Agent
Handles OAuth2 authentication for Google Calendar and Gmail APIs.
All scopes are read-only. Tokens are stored locally and gitignored.
"""

import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

CREDENTIALS_DIR = Path(__file__).parent.parent / "config" / "credentials"
CLIENT_SECRET = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

# Read-only scopes only — never write to Calendar or Gmail
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_credentials(include_gmail=False):
    """
    Get valid OAuth credentials, running the browser auth flow if needed.
    Returns google.oauth2.credentials.Credentials object.
    """
    scopes = CALENDAR_SCOPES + (GMAIL_SCOPES if include_gmail else [])
    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), scopes)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not CLIENT_SECRET.exists():
                print(f"Error: {CLIENT_SECRET} not found.")
                print("Download your OAuth credentials from Google Cloud Console")
                print("and place them at: config/credentials/client_secret.json")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET), scopes
            )
            creds = flow.run_local_server(port=0)

        # Save token for next run
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def get_calendar_service():
    """Get an authenticated Google Calendar API service."""
    creds = get_credentials(include_gmail=False)
    return build("calendar", "v3", credentials=creds)


def get_gmail_service():
    """Get an authenticated Gmail API service."""
    creds = get_credentials(include_gmail=True)
    return build("gmail", "v1", credentials=creds)


def verify_calendar():
    """Verify Calendar connection by listing next 5 events."""
    try:
        service = get_calendar_service()
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=5,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = result.get("items", [])
        print(f"✓ Calendar connected — {len(events)} upcoming events found")
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(f"  • {start}: {event.get('summary', '(no title)')}")
        return True
    except Exception as e:
        print(f"✗ Calendar connection failed: {e}")
        return False


def verify_gmail():
    """Verify Gmail connection by listing 5 recent email subjects."""
    try:
        service = get_gmail_service()
        result = service.users().messages().list(userId="me", maxResults=5).execute()
        messages = result.get("messages", [])
        print(f"✓ Gmail connected — {len(messages)} recent messages found")
        for msg in messages:
            detail = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From"],
                )
                .execute()
            )
            headers = {
                h["name"]: h["value"]
                for h in detail.get("payload", {}).get("headers", [])
            }
            print(f"  • {headers.get('Subject', '(no subject)')}")
        return True
    except Exception as e:
        print(f"✗ Gmail connection failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Google OAuth for Personal Ops Agent"
    )
    parser.add_argument(
        "--add-gmail", action="store_true", help="Add Gmail scope to existing auth"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify API connections"
    )
    parser.add_argument(
        "--gmail", action="store_true", help="Include Gmail in verification"
    )
    args = parser.parse_args()

    if args.verify:
        print("\n--- Verifying Google Connections ---\n")
        verify_calendar()
        if args.gmail:
            print()
            verify_gmail()
    elif args.add_gmail:
        print("\n--- Adding Gmail Scope ---\n")
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
            print("Removed existing token — re-authenticating with Calendar + Gmail...")
        creds = get_credentials(include_gmail=True)
        print("✓ Gmail scope added successfully")
        print("\nVerifying...")
        verify_gmail()
    else:
        print("\n--- Google OAuth Setup ---\n")
        print("Authenticating with Calendar read-only access...")
        creds = get_credentials(include_gmail=False)
        print("✓ Authentication successful!")
        print(f"Token saved to: {TOKEN_PATH}")
        print("\nVerifying connection...")
        verify_calendar()
        print("\nTo add Gmail access later, run:")
        print("  python -m src.google_auth --add-gmail")
