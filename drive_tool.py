"""
drive_tool.py - Google Drive Tool

Provides a single-purpose function to upload a binary file (typically the
weekly pulse PDF) to Google Drive via the Drive API (v3) and return a
shareable link.

The file content arrives base64-encoded because it travels as JSON over the
REST endpoint; this module decodes it and streams it to Drive as a resumable
upload.
"""

import base64
import io

from googleapiclient.http import MediaIoBaseUpload

from auth import build_service


# When True, every uploaded file gets an "anyone with the link can view"
# permission so that email recipients can open it without requesting access.
# Set to False to keep uploads private to the authenticated account.
LINK_SHARING_ENABLED = True


def upload_to_drive(
    filename: str,
    content_b64: str,
    mime_type: str = "application/pdf",
    folder_id: str = "",
) -> dict:
    """
    Upload a base64-encoded file to Google Drive and return a shareable link.

    Internal flow:
      1. Build an authenticated Google Drive service.
      2. Decode the base64 payload into raw bytes.
      3. Upload via files().create() with a resumable media upload.
      4. If link sharing is enabled, grant "anyone with the link" reader access.
      5. Return the file ID and viewable URL.

    Args:
        filename:    Destination filename in Drive, e.g. "pulse_2026-09-07.pdf".
        content_b64: The file contents, base64-encoded.
        mime_type:   MIME type of the file. Defaults to "application/pdf".
        folder_id:   Optional Drive folder ID to upload into. When empty the
                     file lands in the account's Drive root.

    Returns:
        A dict containing:
          - status: "success" or "error"
          - message: Human-readable result description
          - file_id: The Drive file ID
          - file_url: The shareable webViewLink
          - shared: Whether link sharing was applied

    Raises:
        ValueError: If content_b64 is empty or not valid base64.
        googleapiclient.errors.HttpError: If the Drive API call fails.
    """
    if not content_b64:
        raise ValueError("content_b64 is empty - nothing to upload.")

    try:
        file_bytes = base64.b64decode(content_b64, validate=True)
    except (base64.binascii.Error, ValueError) as exc:
        raise ValueError(f"content_b64 is not valid base64: {exc}") from exc

    if not file_bytes:
        raise ValueError("Decoded file content is empty - nothing to upload.")

    service = build_service("drive", "v3")

    file_metadata = {"name": filename}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype=mime_type,
        resumable=True,
    )

    uploaded = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
        )
        .execute()
    )

    file_id = uploaded.get("id")
    print(f"[drive] Uploaded '{filename}' ({len(file_bytes)} bytes) as {file_id}")

    # Grant link access so email recipients can open the file directly.
    shared = False
    if LINK_SHARING_ENABLED:
        service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
        ).execute()
        shared = True
        print(f"[drive] Link sharing enabled for {file_id}")

    return {
        "status": "success",
        "message": "File uploaded to Drive.",
        "file_id": file_id,
        "file_url": uploaded.get(
            "webViewLink", f"https://drive.google.com/file/d/{file_id}/view"
        ),
        "shared": shared,
        "api_response": uploaded,
    }
