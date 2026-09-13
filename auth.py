"""
auth.py — Google OAuth 2.0 Authentication Module

Manages the entire OAuth 2.0 lifecycle:
  - Loading credentials from the client secrets file
  - Persisting/refreshing tokens via token.json
  - Building authenticated Google API service objects

Scopes:
  - https://www.googleapis.com/auth/documents     (Google Docs read/write)
  - https://www.googleapis.com/auth/gmail.compose (Gmail draft creation)
  - https://www.googleapis.com/auth/drive.file    (upload/manage app-created files)

NOTE: changing SCOPES invalidates an existing token.json. Delete it and re-run
the consent flow locally, then copy the new token into GOOGLE_TOKEN_JSON on the
deployment. A stale token produces 403 "insufficient authentication scopes".
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# OAuth scopes required by the MCP server tools
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.compose",
    # drive.file grants access only to files this app creates - not the
    # user's whole Drive - which is the least privilege needed to upload
    # the report and share it by link.
    "https://www.googleapis.com/auth/drive.file",
]

# Path to the OAuth client secrets file downloaded from Google Cloud Console.
# Update this if your file has a different name or location.
CREDENTIALS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "credentials.json",
)

# Path where the access/refresh token will be persisted after first login.
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")


# ---------------------------------------------------------------------------
# Production bootstrap — write credential files from environment variables
# (used on Railway / other headless deployments where files are gitignored)
# ---------------------------------------------------------------------------

_creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
if _creds_env and not os.path.exists(CREDENTIALS_FILE):
    with open(CREDENTIALS_FILE, "w") as _f:
        _f.write(_creds_env)
    print(f"[auth] Wrote credentials.json from GOOGLE_CREDENTIALS_JSON env var.")

_token_env = os.getenv("GOOGLE_TOKEN_JSON")
if _token_env and not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as _f:
        _f.write(_token_env)
    print(f"[auth] Wrote token.json from GOOGLE_TOKEN_JSON env var.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_credentials() -> Credentials:
    """
    Obtain valid Google OAuth 2.0 credentials.

    Token lifecycle:
      1. If token.json exists and is valid → return immediately.
      2. If token.json exists but is expired → refresh using the refresh token.
      3. If token.json does not exist → launch the OAuth browser flow for
         the user to grant consent, then persist the new token.

    Returns:
        google.oauth2.credentials.Credentials — authenticated credentials.

    Raises:
        FileNotFoundError: If the client secrets file (credentials.json) is missing.
        Exception: If the OAuth flow fails or tokens cannot be refreshed.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Client secrets file not found at: {CREDENTIALS_FILE}\n"
            "Download it from the Google Cloud Console and place it in the project root."
        )

    creds = None

    # Step 1: Try loading existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Step 2: Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[auth] Refreshing expired access token...")
            creds.refresh(Request())
        else:
            print("[auth] No valid token found. Launching OAuth consent flow...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Persist the token for future runs
        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"[auth] Token saved to {TOKEN_FILE}")

    return creds


def build_service(api: str, version: str):
    """
    Build and return an authenticated Google API service resource.

    Args:
        api:     The API name (e.g., "docs", "gmail").
        version: The API version (e.g., "v1").

    Returns:
        googleapiclient.discovery.Resource — the service object for making
        API calls.

    Example:
        docs_service = build_service("docs", "v1")
        gmail_service = build_service("gmail", "v1")
    """
    creds = get_credentials()
    service = build(api, version, credentials=creds)
    print(f"[auth] Built {api} {version} service.")
    return service
