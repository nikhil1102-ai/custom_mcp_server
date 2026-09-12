# MCP-Style Server — Google Docs & Gmail Integration

A lightweight Python server that exposes Google Docs and Gmail operations as **MCP-style tool endpoints** via FastAPI. Every action requires explicit **human approval** in the terminal before execution.

---

## Features

- **Append to Google Doc** — Append text content to any Google Doc you have access to.
- **Create Gmail Draft** — Create a draft email in your Gmail account.
- **Human-in-the-Loop** — Every action is printed to the terminal and requires `y/n` approval.
- **OAuth 2.0** — Secure authentication via Google's OAuth 2.0 flow.

---

## Prerequisites

- **Python 3.9+**
- **Google Cloud Project** with the following APIs enabled:
  - Google Docs API
  - Gmail API
- **OAuth 2.0 Client Credentials** (`credentials.json`) downloaded from the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd MCP_server
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your credentials

Place your Google OAuth client secrets file in the project root. The server is pre-configured to look for the credentials file by its downloaded name. If you renamed it, update the `CREDENTIALS_FILE` path in `auth.py`.

### 5. Run the server

```bash
python server.py
```

On the **first run**, a browser window will open asking you to sign in and grant permissions. After approval, a `token.json` file is created and subsequent runs will not require browser login.

---

## Usage

### Append to a Google Doc

```bash
curl -X POST http://127.0.0.1:8000/append_to_doc \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "YOUR_DOC_ID", "content": "Hello from MCP server!"}'
```

Check the **terminal running the server** — you'll see:

```
============================================================
  ACTION: append_to_doc
============================================================
{
  "doc_id": "YOUR_DOC_ID",
  "content": "Hello from MCP server!"
}
============================================================
Approve? (y/n):
```

Type `y` to approve and execute, or `n` to reject.

### Create a Gmail Draft

```bash
curl -X POST http://127.0.0.1:8000/create_email_draft \
  -H "Content-Type: application/json" \
  -d '{"to": "recipient@example.com", "subject": "Test", "body": "Hello!"}'
```

---

## API Reference

### `POST /append_to_doc`

| Field   | Type   | Description                        |
|---------|--------|------------------------------------|
| doc_id  | string | Google Doc ID (from the URL)       |
| content | string | Text content to append             |

**Response (200):**
```json
{ "status": "success", "message": "Content appended to document.", "doc_id": "..." }
```

### `POST /create_email_draft`

| Field   | Type   | Description                        |
|---------|--------|------------------------------------|
| to      | string | Recipient email address            |
| subject | string | Email subject line                 |
| body    | string | Email body text                    |

**Response (200):**
```json
{ "status": "success", "message": "Draft created successfully.", "draft_id": "..." }
```

### Error Responses

| Status | Meaning                    |
|--------|----------------------------|
| 403    | Action rejected by operator|
| 401    | Authentication error       |
| 422    | Invalid request payload    |
| 502    | Google API error           |
| 500    | Internal server error      |

---

## Project Structure

```
MCP_server/
├── server.py          → FastAPI app with tool endpoints
├── auth.py            → Google OAuth 2.0 authentication
├── docs_tool.py       → Google Docs tool (append content)
├── gmail_tool.py      → Gmail tool (create draft)
├── requirements.txt   → Python dependencies
├── README.md          → This file
├── .gitignore         → Git ignore rules
└── docs/
    ├── problemStatement.md
    └── architecture.md
```

---

## Security Notes

- `credentials.json` and `token.json` are excluded from version control via `.gitignore`.
- The server binds to `127.0.0.1` (localhost) by default — it is **not** exposed to the network.
- Only `documents` and `gmail.compose` OAuth scopes are requested.
