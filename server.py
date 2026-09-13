"""
server.py - MCP-Style Server (FastAPI + Uvicorn)

The entry point and orchestrator for the MCP server. Exposes two POST
endpoints for Google Docs and Gmail tool operations, each gated behind
a human-in-the-loop terminal approval prompt.

Endpoints:
  POST /append_to_doc       - Append text to a Google Doc
  POST /create_email_draft  - Create a Gmail draft email
  POST /upload_to_drive     - Upload a file (the weekly PDF) to Google Drive

Run:
  python server.py
  - Uvicorn starts on http://127.0.0.1:8000
"""

import json
import os
import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from docs_tool import append_to_doc
from drive_tool import upload_to_drive
from gmail_tool import create_email_draft


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MCP-Style Server",
    description="Google Docs & Gmail integration via MCP tool endpoints",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------


class AppendToDocRequest(BaseModel):
    """Request schema for the /append_to_doc endpoint."""
    doc_id: Optional[str] = ""
    title: Optional[str] = "Untitled Document"
    content: str


class CreateEmailDraftRequest(BaseModel):
    """Request schema for the /create_email_draft endpoint."""
    to: str
    subject: str
    body: str
    body_html: Optional[str] = None


class UploadToDriveRequest(BaseModel):
    """Request schema for the /upload_to_drive endpoint."""
    filename: str
    content_b64: str
    mime_type: Optional[str] = "application/pdf"
    folder_id: Optional[str] = ""


# ---------------------------------------------------------------------------
# Human-in-the-Loop Approval
# ---------------------------------------------------------------------------


# Strings longer than this are summarised rather than printed in full, so a
# base64 PDF payload cannot flood the approval prompt.
MAX_DISPLAY_CHARS = 400


def _redact_for_display(payload: dict) -> dict:
    """Return a copy of *payload* with oversized string values summarised.

    The approval prompt exists to be read by a human. A base64-encoded PDF is
    hundreds of kilobytes of noise, so long values are replaced with their
    length and a short prefix.
    """
    redacted = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > MAX_DISPLAY_CHARS:
            redacted[key] = (
                f"<{len(value)} chars> {value[:80]}..."
            )
        else:
            redacted[key] = value
    return redacted


def request_approval(action_name: str, payload: dict) -> bool:
    """
    Print the action and payload to the terminal and ask the operator
    to approve or reject the action.

    Args:
        action_name: The name of the tool action (e.g., "append_to_doc").
        payload:     The request payload as a dict.

    Returns:
        True if the operator approves (types 'y'), False otherwise.
    """
    print("\n" + "=" * 60)
    print(f"  ACTION: {action_name}")
    print("=" * 60)
    print(json.dumps(_redact_for_display(payload), indent=2))
    print("=" * 60)

    # In headless/deployed environments (e.g., Railway), auto-approve if configured
    auto_approve = os.getenv("AUTO_APPROVE", "false").lower() == "true"
    if auto_approve:
        print("[server] AUTO_APPROVE is enabled - action approved automatically.")
        return True

    try:
        response = input("Approve? (y/n): ").strip().lower()
    except EOFError:
        # If stdin is not available (e.g., running in background), reject
        print("[server] stdin not available - action rejected.")
        return False

    return response == "y"


# ---------------------------------------------------------------------------
# Global Exception Handler
# ---------------------------------------------------------------------------


@app.exception_handler(HttpError)
async def google_api_error_handler(request, exc: HttpError):
    """Handle Google API HttpError and return a 502 Bad Gateway response."""
    return JSONResponse(
        status_code=502,
        content={
            "status": "error",
            "message": f"Google API error: {exc.reason}",
            "details": str(exc),
        },
    )


@app.exception_handler(FileNotFoundError)
async def auth_error_handler(request, exc: FileNotFoundError):
    """Handle missing credentials file and return a 401 Unauthorized response."""
    return JSONResponse(
        status_code=401,
        content={
            "status": "error",
            "message": "Authentication error: credentials file not found.",
            "details": str(exc),
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request, exc: Exception):
    """Catch-all handler for unhandled exceptions - returns 500."""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error.",
            "details": str(exc),
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/append_to_doc")
def endpoint_append_to_doc(req: AppendToDocRequest):
    """
    Append text content to a Google Doc.

    Workflow:
      1. Print the action name and payload to the terminal.
      2. Prompt the operator for approval (y/n).
      3. If approved -> call docs_tool.append_to_doc().
      4. If rejected -> return 403 Forbidden.
    """
    payload = req.model_dump()

    if not request_approval("append_to_doc", payload):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "rejected",
                "message": "Action not approved by operator.",
            },
        )

    result = append_to_doc(doc_id=req.doc_id, content=req.content, title=req.title)

    return {
        "status": result["status"],
        "message": result["message"],
        "doc_id": result["doc_id"],
        "doc_url": result.get("doc_url"),
    }


@app.post("/create_email_draft")
def endpoint_create_email_draft(req: CreateEmailDraftRequest):
    """
    Create a draft email in Gmail.

    Workflow:
      1. Print the action name and payload to the terminal.
      2. Prompt the operator for approval (y/n).
      3. If approved -> call gmail_tool.create_email_draft().
      4. If rejected -> return 403 Forbidden.
    """
    payload = req.model_dump()

    if not request_approval("create_email_draft", payload):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "rejected",
                "message": "Action not approved by operator.",
            },
        )

    result = create_email_draft(to=req.to, subject=req.subject, body=req.body, body_html=req.body_html)

    return {
        "status": result["status"],
        "message": result["message"],
        "draft_id": result["draft_id"],
    }


@app.post("/upload_to_drive")
def endpoint_upload_to_drive(req: UploadToDriveRequest):
    """
    Upload a file to Google Drive and return a shareable link.

    Used by the review-pulse pipeline to publish the detailed weekly PDF,
    whose URL is then linked from the summary email.

    Workflow:
      1. Print the action name and payload to the terminal (the base64
         body is summarised, not dumped).
      2. Prompt the operator for approval (y/n).
      3. If approved -> call drive_tool.upload_to_drive().
      4. If rejected -> return 403 Forbidden.
    """
    payload = req.model_dump()

    if not request_approval("upload_to_drive", payload):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "rejected",
                "message": "Action not approved by operator.",
            },
        )

    try:
        result = upload_to_drive(
            filename=req.filename,
            content_b64=req.content_b64,
            mime_type=req.mime_type,
            folder_id=req.folder_id,
        )
    except ValueError as exc:
        # Malformed base64 or empty payload is a client error, not a 500.
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": str(exc)},
        )

    return {
        "status": result["status"],
        "message": result["message"],
        "file_id": result["file_id"],
        "file_url": result["file_url"],
        "shared": result["shared"],
        "folder_id": result["folder_id"],
    }


# ---------------------------------------------------------------------------
# Main - Run with Uvicorn
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"[server] Starting MCP-Style Server on http://{host}:{port}")
    print("[server] Press Ctrl+C to stop.\n")
    uvicorn.run(app, host=host, port=port)
