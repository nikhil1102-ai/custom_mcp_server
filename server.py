"""
server.py — MCP-Style Server (FastAPI + Uvicorn)

The entry point and orchestrator for the MCP server. Exposes two POST
endpoints for Google Docs and Gmail tool operations, each gated behind
a human-in-the-loop terminal approval prompt.

Endpoints:
  POST /append_to_doc       — Append text to a Google Doc
  POST /create_email_draft  — Create a Gmail draft email

Run:
  python server.py
  → Uvicorn starts on http://127.0.0.1:8000
"""

import json
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from docs_tool import append_to_doc
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
    doc_id: str
    content: str


class CreateEmailDraftRequest(BaseModel):
    """Request schema for the /create_email_draft endpoint."""
    to: str
    subject: str
    body: str


# ---------------------------------------------------------------------------
# Human-in-the-Loop Approval
# ---------------------------------------------------------------------------


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
    print(json.dumps(payload, indent=2))
    print("=" * 60)

    try:
        response = input("Approve? (y/n): ").strip().lower()
    except EOFError:
        # If stdin is not available (e.g., running in background), reject
        print("[server] stdin not available — action rejected.")
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
    """Catch-all handler for unhandled exceptions — returns 500."""
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
      3. If approved → call docs_tool.append_to_doc().
      4. If rejected → return 403 Forbidden.
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

    result = append_to_doc(doc_id=req.doc_id, content=req.content)

    return {
        "status": result["status"],
        "message": result["message"],
        "doc_id": result["doc_id"],
    }


@app.post("/create_email_draft")
def endpoint_create_email_draft(req: CreateEmailDraftRequest):
    """
    Create a draft email in Gmail.

    Workflow:
      1. Print the action name and payload to the terminal.
      2. Prompt the operator for approval (y/n).
      3. If approved → call gmail_tool.create_email_draft().
      4. If rejected → return 403 Forbidden.
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

    result = create_email_draft(to=req.to, subject=req.subject, body=req.body)

    return {
        "status": result["status"],
        "message": result["message"],
        "draft_id": result["draft_id"],
    }


# ---------------------------------------------------------------------------
# Main — Run with Uvicorn
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("[server] Starting MCP-Style Server on http://127.0.0.1:8000")
    print("[server] Press Ctrl+C to stop.\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
