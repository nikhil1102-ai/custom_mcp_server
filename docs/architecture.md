# Architecture — MCP-Style Server (Google Docs & Gmail Integration)

> **Version:** 1.0  
> **Last Updated:** 2026-09-12  
> **Source:** [problemStatement.md](file:///d:/nextleap/MCP_server/docs/problemStatement.md)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture Diagram](#2-high-level-architecture-diagram)
3. [Project Structure](#3-project-structure)
4. [Component Design](#4-component-design)
   - 4.1 [server.py — API Gateway](#41-serverpy--api-gateway)
   - 4.2 [auth.py — Authentication Module](#42-authpy--authentication-module)
   - 4.3 [docs_tool.py — Google Docs Tool](#43-docs_toolpy--google-docs-tool)
   - 4.4 [gmail_tool.py — Gmail Tool](#44-gmail_toolpy--gmail-tool)
5. [Data Flow](#5-data-flow)
   - 5.1 [Append to Google Doc](#51-append-to-google-doc)
   - 5.2 [Create Gmail Draft](#52-create-gmail-draft)
6. [API Contracts](#6-api-contracts)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Security Considerations](#8-security-considerations)
9. [Dependency Map](#9-dependency-map)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Error Handling Strategy](#11-error-handling-strategy)
12. [Future Extensibility](#12-future-extensibility)

---

## 1. System Overview

The **MCP-Style Server** is a lightweight Python service that acts as a bridge between an external caller (e.g., an LLM agent, CLI tool, or front-end application) and Google Workspace APIs. It exposes a set of **tool endpoints** following the Model Context Protocol (MCP) pattern — each endpoint maps to a discrete, human-approvable action on a Google service.

### Key Design Principles

| Principle | Description |
|---|---|
| **Human-in-the-Loop** | Every tool action is printed to the terminal and requires explicit `y/n` approval before execution. |
| **Single Responsibility** | Each module owns exactly one concern: routing, auth, Docs interaction, or Gmail interaction. |
| **Stateless API** | The FastAPI server itself holds no session state; authentication tokens are persisted to disk. |
| **Minimal Surface Area** | Only two tool endpoints are exposed, reducing attack surface and cognitive load. |

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Client                          │
│              (LLM Agent / CLI / Frontend App)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP POST requests
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      server.py (FastAPI + Uvicorn)              │
│  ┌────────────────────┐       ┌──────────────────────────┐     │
│  │ POST /append_to_doc│       │ POST /create_email_draft │     │
│  └────────┬───────────┘       └─────────┬────────────────┘     │
│           │                             │                       │
│           │    ┌────────────────────┐    │                       │
│           │    │  Human Approval    │    │                       │
│           │    │  (Terminal y/n)    │    │                       │
│           │    └────────┬───────────┘    │                       │
│           │             │ approved       │                       │
│           ▼             ▼               ▼                       │
│  ┌─────────────┐  ┌──────────┐  ┌──────────────┐              │
│  │ docs_tool.py│  │ auth.py  │  │ gmail_tool.py│              │
│  └──────┬──────┘  └────┬─────┘  └──────┬───────┘              │
└─────────┼──────────────┼───────────────┼───────────────────────┘
          │              │               │
          ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Google Cloud Platform                        │
│  ┌──────────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │  Google Docs API  │  │  OAuth 2.0    │  │  Gmail API     │  │
│  └──────────────────┘  └───────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
google-mcp-server/
│
├── server.py              → FastAPI application with tool endpoints & approval logic
├── auth.py                → Google OAuth 2.0 authentication & token management
├── docs_tool.py           → Google Docs tool: append content to a document
├── gmail_tool.py          → Gmail tool: create a draft email
├── requirements.txt       → Python dependencies
├── README.md              → Setup and usage instructions
│
├── credentials.json       → 🔒 Google Cloud OAuth client credentials (NOT committed)
├── token.json             → 🔒 Auto-generated OAuth refresh token (NOT committed)
│
└── docs/
    ├── problemStatement.md  → Original problem specification
    └── architecture.md      → This document
```

### File Responsibility Matrix

| File | Responsibility | Depends On |
|---|---|---|
| `server.py` | HTTP routing, request validation, human approval flow | `auth.py`, `docs_tool.py`, `gmail_tool.py` |
| `auth.py` | OAuth 2.0 credential loading, token refresh, service building | `credentials.json`, `token.json` |
| `docs_tool.py` | Append text content to a Google Doc via API | `auth.py` |
| `gmail_tool.py` | Create a Gmail draft email via API | `auth.py` |

---

## 4. Component Design

### 4.1 `server.py` — API Gateway

**Role:** The entry point and orchestrator. Receives HTTP requests, validates payloads, solicits human approval, and delegates to the appropriate tool module.

```
┌──────────────────────────────────────────────────────────┐
│                       server.py                          │
│                                                          │
│  ┌──────────────────┐    ┌────────────────────────────┐ │
│  │  FastAPI App      │    │  Human Approval Middleware │ │
│  │  Instance         │    │  (Terminal I/O)            │ │
│  └────────┬─────────┘    └─────────────┬──────────────┘ │
│           │                            │                 │
│  ┌────────▼─────────┐    ┌─────────────▼──────────────┐ │
│  │  POST Endpoints   │    │  Request/Response Models   │ │
│  │  /append_to_doc   │    │  (Pydantic schemas)        │ │
│  │  /create_email_   │    │                            │ │
│  │       draft       │    │                            │ │
│  └──────────────────┘    └────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

#### Responsibilities

1. **Define FastAPI application** with Uvicorn as the ASGI server.
2. **Expose two POST endpoints:**
   - `POST /append_to_doc` — accepts `{ doc_id: str, content: str }`
   - `POST /create_email_draft` — accepts `{ to: str, subject: str, body: str }`
3. **Human-in-the-loop approval:**
   - Print the action name and full payload to the terminal.
   - Prompt `"Approve? (y/n)"` and block until the operator responds.
   - If `y` → proceed to tool execution.
   - If `n` → return a `403 Forbidden` or appropriate rejection response.
4. **Return structured JSON responses** with success/failure status and relevant metadata.

#### Pydantic Request Models

```python
class AppendToDocRequest(BaseModel):
    doc_id: str
    content: str

class CreateEmailDraftRequest(BaseModel):
    to: str
    subject: str
    body: str
```

---

### 4.2 `auth.py` — Authentication Module

**Role:** Manages the entire OAuth 2.0 lifecycle — from initial browser-based consent to silent token refresh.

```
┌───────────────────────────────────────────────────────────┐
│                        auth.py                            │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              get_credentials()                       │ │
│  │                                                      │ │
│  │  1. Check if token.json exists                       │ │
│  │     ├─ YES → Load token                              │ │
│  │     │        ├─ Valid?    → Return credentials        │ │
│  │     │        └─ Expired? → Refresh & save            │ │
│  │     └─ NO  → Run OAuth browser flow                  │ │
│  │              → Save new token to token.json           │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │        build_service(api, version)                   │ │
│  │                                                      │ │
│  │  Returns a googleapiclient.discovery Resource        │ │
│  │  object for the given API (docs v1 / gmail v1)       │ │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

#### OAuth Scopes

| Scope | Purpose |
|---|---|
| `https://www.googleapis.com/auth/documents` | Read/write access to Google Docs |
| `https://www.googleapis.com/auth/gmail.compose` | Create and manage Gmail drafts |

#### Token Lifecycle

```
First Run:
  credentials.json → OAuth browser flow → token.json (created)

Subsequent Runs:
  token.json exists?
  ├── YES & valid       → Use directly
  ├── YES & expired     → Refresh via refresh_token → Update token.json
  └── NO                → Re-run OAuth browser flow
```

---

### 4.3 `docs_tool.py` — Google Docs Tool

**Role:** Encapsulates all interaction with the Google Docs API.

#### Function Signature

```python
def append_to_doc(doc_id: str, content: str) -> dict:
    """
    Appends the given text content to the end of the specified Google Doc.

    Args:
        doc_id:  The unique identifier of the Google Doc.
        content: The text string to append.

    Returns:
        A dict containing the API response or status metadata.
    """
```

#### Internal Flow

```
append_to_doc(doc_id, content)
    │
    ├── 1. Obtain authenticated credentials via auth.get_credentials()
    ├── 2. Build Google Docs service via auth.build_service("docs", "v1")
    ├── 3. Retrieve current document to find end-of-body index
    ├── 4. Construct batchUpdate request with InsertTextRequest:
    │       {
    │         "insertText": {
    │           "location": { "index": <end_of_body_index> },
    │           "text": content
    │         }
    │       }
    └── 5. Execute batchUpdate and return response
```

---

### 4.4 `gmail_tool.py` — Gmail Tool

**Role:** Encapsulates all interaction with the Gmail API.

#### Function Signature

```python
def create_email_draft(to: str, subject: str, body: str) -> dict:
    """
    Creates a draft email in the authenticated user's Gmail account.

    Args:
        to:      Recipient email address.
        subject: Email subject line.
        body:    Email body text.

    Returns:
        A dict containing the draft ID and metadata.
    """
```

#### Internal Flow

```
create_email_draft(to, subject, body)
    │
    ├── 1. Obtain authenticated credentials via auth.get_credentials()
    ├── 2. Build Gmail service via auth.build_service("gmail", "v1")
    ├── 3. Construct MIME message:
    │       From: authenticated user
    │       To: <to>
    │       Subject: <subject>
    │       Body: <body>
    ├── 4. Base64url-encode the MIME message
    ├── 5. Call gmail.users().drafts().create(userId="me", body={"message": {"raw": encoded}})
    └── 6. Return draft ID and metadata
```

---

## 5. Data Flow

### 5.1 Append to Google Doc

```
Client                    server.py               Terminal          docs_tool.py         Google Docs API
  │                          │                       │                   │                     │
  │  POST /append_to_doc     │                       │                   │                     │
  │  { doc_id, content }     │                       │                   │                     │
  │─────────────────────────►│                       │                   │                     │
  │                          │  Print action+payload │                   │                     │
  │                          │──────────────────────►│                   │                     │
  │                          │                       │  "Approve? (y/n)" │                     │
  │                          │                       │◄──────────────────│                     │
  │                          │  User types "y"       │                   │                     │
  │                          │◄──────────────────────│                   │                     │
  │                          │                       │                   │                     │
  │                          │  append_to_doc()      │                   │                     │
  │                          │──────────────────────────────────────────►│                     │
  │                          │                       │                   │  batchUpdate        │
  │                          │                       │                   │────────────────────►│
  │                          │                       │                   │  200 OK             │
  │                          │                       │                   │◄────────────────────│
  │                          │  { status: "success"} │                   │                     │
  │◄─────────────────────────│                       │                   │                     │
  │                          │                       │                   │                     │
```

### 5.2 Create Gmail Draft

```
Client                    server.py               Terminal          gmail_tool.py        Gmail API
  │                          │                       │                   │                   │
  │  POST /create_email_draft│                       │                   │                   │
  │  { to, subject, body }   │                       │                   │                   │
  │─────────────────────────►│                       │                   │                   │
  │                          │  Print action+payload │                   │                   │
  │                          │──────────────────────►│                   │                   │
  │                          │                       │  "Approve? (y/n)" │                   │
  │                          │                       │◄──────────────────│                   │
  │                          │  User types "y"       │                   │                   │
  │                          │◄──────────────────────│                   │                   │
  │                          │                       │                   │                   │
  │                          │  create_email_draft() │                   │                   │
  │                          │──────────────────────────────────────────►│                   │
  │                          │                       │                   │  drafts.create    │
  │                          │                       │                   │──────────────────►│
  │                          │                       │                   │  201 Created      │
  │                          │                       │                   │◄──────────────────│
  │                          │  { status: "success", draft_id: "..." }  │                   │
  │◄─────────────────────────│                       │                   │                   │
  │                          │                       │                   │                   │
```

---

## 6. API Contracts

### `POST /append_to_doc`

| Field | Details |
|---|---|
| **URL** | `/append_to_doc` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "doc_id": "1aBcDeFgHiJkLmNoPqRsTuVwXyZ",
  "content": "Hello, this text will be appended."
}
```

**Success Response (200):**

```json
{
  "status": "success",
  "message": "Content appended to document.",
  "doc_id": "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
}
```

**Rejection Response (403):**

```json
{
  "status": "rejected",
  "message": "Action not approved by operator."
}
```

---

### `POST /create_email_draft`

| Field | Details |
|---|---|
| **URL** | `/create_email_draft` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |

**Request Body:**

```json
{
  "to": "recipient@example.com",
  "subject": "Meeting Agenda",
  "body": "Hi, here is the agenda for tomorrow's meeting..."
}
```

**Success Response (200):**

```json
{
  "status": "success",
  "message": "Draft created successfully.",
  "draft_id": "r1234567890"
}
```

**Rejection Response (403):**

```json
{
  "status": "rejected",
  "message": "Action not approved by operator."
}
```

---

## 7. Authentication & Authorization

### OAuth 2.0 Flow

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Server   │     │ Browser  │     │ Google OAuth  │     │ Google APIs  │
│ (auth.py) │     │          │     │  Consent      │     │              │
└─────┬─────┘     └─────┬────┘     └──────┬───────┘     └──────┬───────┘
      │                 │                  │                    │
      │  Open consent   │                  │                    │
      │  URL            │                  │                    │
      │────────────────►│                  │                    │
      │                 │  User grants     │                    │
      │                 │  consent         │                    │
      │                 │─────────────────►│                    │
      │                 │                  │                    │
      │  Authorization  │  Redirect w/     │                    │
      │  code received  │  auth code       │                    │
      │◄────────────────│◄─────────────────│                    │
      │                 │                  │                    │
      │  Exchange code for tokens          │                    │
      │───────────────────────────────────►│                    │
      │  Access + Refresh tokens           │                    │
      │◄───────────────────────────────────│                    │
      │                 │                  │                    │
      │  Save to token.json               │                    │
      │                 │                  │                    │
      │  API call with access token        │                    │
      │────────────────────────────────────────────────────────►│
      │  API response                      │                    │
      │◄────────────────────────────────────────────────────────│
```

### Credential Files

| File | Purpose | Committed to VCS? |
|---|---|---|
| `credentials.json` | OAuth client ID and secret from Google Cloud Console | ❌ No — sensitive |
| `token.json` | Access and refresh tokens after user consent | ❌ No — auto-generated |

---

## 8. Security Considerations

| Concern | Mitigation |
|---|---|
| **Credential Exposure** | `credentials.json` and `token.json` are excluded from version control via `.gitignore`. |
| **Unauthorized Actions** | Human-in-the-loop approval ensures no action executes without explicit operator consent. |
| **Scope Minimization** | Only `documents` and `gmail.compose` scopes are requested — no read access to email inbox. |
| **Token Storage** | Tokens are stored locally on disk; consider encrypted storage for production deployments. |
| **Input Validation** | Pydantic models enforce type and presence validation on all incoming payloads. |
| **Network Exposure** | Default Uvicorn binding should be `127.0.0.1` (localhost only) to prevent external access. |
| **HTTPS** | For any non-local deployment, a reverse proxy (e.g., Nginx) with TLS termination is required. |

---

## 9. Dependency Map

```
┌──────────────────────────────────────────────────────────┐
│                    requirements.txt                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  fastapi              → Web framework for API endpoints  │
│  uvicorn              → ASGI server to run FastAPI       │
│  pydantic             → Request/response model validation│
│                                                          │
│  google-auth          → Google authentication library    │
│  google-auth-oauthlib → OAuth 2.0 flow helpers           │
│  google-auth-httplib2 → HTTP transport for Google auth   │
│  google-api-python-   → Google API client library        │
│    client             │                                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Module Dependency Graph

```
server.py
    ├── auth.py
    │     ├── google.oauth2.credentials
    │     ├── google_auth_oauthlib.flow
    │     └── googleapiclient.discovery
    │
    ├── docs_tool.py
    │     └── auth.py → get_credentials() / build_service()
    │
    └── gmail_tool.py
          └── auth.py → get_credentials() / build_service()
```

---

## 10. Deployment Architecture

### Local Development (Default)

```
┌──────────────────────────────────────────┐
│           Developer Machine              │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Uvicorn (127.0.0.1:8000)       │   │
│  │  └── FastAPI (server.py)        │   │
│  │       ├── docs_tool.py          │   │
│  │       ├── gmail_tool.py         │   │
│  │       └── auth.py               │   │
│  └──────────────────────────────────┘   │
│                                          │
│  Terminal ← Human approval prompts       │
│                                          │
└──────────────────────────────────────────┘
```

### Production Deployment (Future)

```
┌─────────────────────────────────────────────────────────────┐
│                      Cloud VM / Container                   │
│                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────┐   │
│  │  Nginx       │    │  Gunicorn + Uvicorn Workers     │   │
│  │  (TLS/HTTPS) │───►│  └── FastAPI (server.py)        │   │
│  │  Reverse     │    │       ├── docs_tool.py          │   │
│  │  Proxy       │    │       ├── gmail_tool.py         │   │
│  └─────────────┘    │       └── auth.py               │   │
│                      └──────────────────────────────────┘   │
│                                                             │
│  Secrets Manager ← credentials.json, token.json             │
│  (e.g., GCP Secret Manager, HashiCorp Vault)                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. Error Handling Strategy

### Error Categories & Responses

| Category | HTTP Status | Example | Handling |
|---|---|---|---|
| **Validation Error** | `422` | Missing `doc_id` in request | FastAPI auto-validates via Pydantic |
| **Approval Rejected** | `403` | Operator types `n` | Return rejection response immediately |
| **Auth Failure** | `401` | Expired token, missing `credentials.json` | Attempt refresh; if failed, return auth error |
| **Google API Error** | `502` | Docs/Gmail API returns error | Catch `HttpError`, log details, return error response |
| **Internal Error** | `500` | Unhandled exception | Global exception handler returns generic error |

### Exception Flow

```
Request → Pydantic Validation
            │
            ├── FAIL → 422 Unprocessable Entity
            │
            └── PASS → Human Approval
                         │
                         ├── REJECTED → 403 Forbidden
                         │
                         └── APPROVED → Tool Execution
                                         │
                                         ├── Auth Error    → 401 Unauthorized
                                         ├── Google API Err → 502 Bad Gateway
                                         ├── Unknown Error  → 500 Internal Server Error
                                         └── Success        → 200 OK
```

---

## 12. Future Extensibility

The MCP pattern is inherently extensible. New tools can be added by following this pattern:

### Adding a New Tool

1. **Create `new_tool.py`** with a single-purpose function.
2. **Add a new POST endpoint** in `server.py` with a Pydantic request model.
3. **Add any required OAuth scopes** to `auth.py`.
4. **The human approval flow is inherited** automatically via the server's middleware pattern.

### Potential Future Tools

| Tool | Endpoint | Google API |
|---|---|---|
| Read Document | `GET /read_doc` | Docs API |
| Send Email | `POST /send_email` | Gmail API |
| Create Document | `POST /create_doc` | Docs API |
| List Drafts | `GET /list_drafts` | Gmail API |
| Calendar Event | `POST /create_event` | Calendar API |
| Drive Upload | `POST /upload_file` | Drive API |

### Scaling Considerations

- **Remove terminal approval** for automated pipelines; replace with token-based or policy-based approval.
- **Add request queuing** (e.g., Redis/Celery) for high-throughput scenarios.
- **Implement rate limiting** to respect Google API quotas.
- **Add observability** (structured logging, OpenTelemetry tracing) for production monitoring.

---

> **Note:** This architecture is designed for the initial MVP as specified in the [problem statement](file:///d:/nextleap/MCP_server/docs/problemStatement.md). Production deployments should address the security and scaling considerations outlined above.
