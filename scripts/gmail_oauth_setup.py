#!/usr/bin/env python3
"""
gmail_oauth_setup.py — Run THIS ONCE locally on your friend's machine (or yours).

This script opens a browser, asks leonidaseldarov@gmail.com to grant access,
then prints the refresh token to store in GCP Secret Manager.

Usage:
    python scripts/gmail_oauth_setup.py

Requirements:
    pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.oauth2.credentials

# Scopes: read-only Gmail access
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
]

PROJECT_ID = "project-b7155ed8-61c1-491f-a36"


def main():
    print("=" * 60)
    print("Gazzetta di Kyiv — Gmail OAuth Setup")
    print("=" * 60)
    print()
    print("This will open a browser window.")
    print("Sign in as: leonidaseldarov@gmail.com")
    print("Click 'Allow' to grant newsletter read access.")
    print()

    # Look for client_secret.json in the project root
    client_secret_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "client_secret.json"
    )

    if not os.path.exists(client_secret_path):
        print("ERROR: client_secret.json not found at project root.")
        print()
        print("To get it:")
        print("  1. Go to: https://console.cloud.google.com/apis/credentials")
        print(f"  2. Project: {PROJECT_ID}")
        print("  3. Create > OAuth client ID > Desktop app")
        print("  4. Download JSON → save as client_secret.json in project root")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(
        port=0,
        authorization_prompt_message="Open this link to authorize the harvester: {url}",
        success_message="Success! The token has been generated. You can close this tab now."
    )

    # Build the token data
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    print()
    print("=" * 60)
    print("SUCCESS! OAuth token obtained.")
    print("=" * 60)
    print()
    print("Now store these in GCP Secret Manager by running:")
    print()
    print(
        f"  echo '{json.dumps(token_data)}' | gcloud secrets create gmail-newsletter-token \\"
    )
    print(f"    --project={PROJECT_ID} \\")
    print(f"    --data-file=-")
    print()
    print("Or update if it already exists:")
    print()
    print(
        f"  echo '{json.dumps(token_data)}' | gcloud secrets versions add gmail-newsletter-token \\"
    )
    print(f"    --project={PROJECT_ID} \\")
    print(f"    --data-file=-")
    print()

    # Also save locally for testing
    local_token_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), ".gmail_token.json"
    )
    with open(local_token_path, "w") as f:
        json.dump(token_data, f, indent=2)
    os.chmod(local_token_path, 0o600)
    print(f"Token also saved locally to: {local_token_path} (chmod 600)")
    print("NOTE: .gmail_token.json is in .gitignore — never commit it.")


if __name__ == "__main__":
    main()
