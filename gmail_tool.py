"""
gmail_tool.py - Gmail Tool

Provides a single-purpose function to create a draft email in the
authenticated user's Gmail account via the Gmail API (v1).
Supports sending rich HTML email using multipart/alternative.
"""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from auth import build_service


def create_email_draft(to: str, subject: str, body: str, body_html: str = None) -> dict:
    """
    Create a draft email in the authenticated user's Gmail account.

    Internal flow:
      1. Build an authenticated Gmail service.
      2. Construct a MIME text/multipart message with the given recipient, subject, and body.
      3. Base64url-encode the MIME message.
      4. Call drafts().create() on the Gmail API.
      5. Return the draft ID and metadata.

    Args:
        to:        Recipient email address.
        subject:   Email subject line.
        body:      Email body text (plain text fallback).
        body_html: Optional rich HTML body.

    Returns:
        A dict containing:
          - status: "success" or "error"
          - message: Human-readable result description
          - draft_id: The ID of the created draft
          - api_response: Raw API response (on success)

    Raises:
        googleapiclient.errors.HttpError: If the Gmail API call fails.
    """
    service = build_service("gmail", "v1")

    # Construct the MIME message
    if body_html:
        mime_message = MIMEMultipart('alternative')
        mime_message["to"] = to
        mime_message["subject"] = subject

        # Attach plain text first, then HTML (so clients prefer HTML if available)
        part1 = MIMEText(body, 'plain')
        part2 = MIMEText(body_html, 'html')

        mime_message.attach(part1)
        mime_message.attach(part2)
    else:
        mime_message = MIMEText(body, 'plain')
        mime_message["to"] = to
        mime_message["subject"] = subject

    # Base64url-encode the message (Gmail API requirement)
    encoded_message = base64.urlsafe_b64encode(
        mime_message.as_bytes()
    ).decode("utf-8")

    # Create the draft
    draft_body = {
        "message": {
            "raw": encoded_message,
        }
    }

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body=draft_body)
        .execute()
    )

    draft_id = draft.get("id", "unknown")

    return {
        "status": "success",
        "message": "Draft created successfully.",
        "draft_id": draft_id,
        "api_response": draft,
    }
