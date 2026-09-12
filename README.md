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
├── Procfile           → Railway deployment config
├── README.md          → This file
├── .gitignore         → Git ignore rules
└── docs/
    ├── problemStatement.md
    └── architecture.md
```

---

## Deploy to Railway

### Prerequisites

- A [Railway](https://railway.app/) account (free tier available)
- The project pushed to GitHub (see Setup above)
- Google OAuth `token.json` generated locally (run the server once locally first)

### Step 1: Create a New Project on Railway

1. Go to [railway.app](https://railway.app/) and log in.
2. Click **"New Project"** → **"Deploy from GitHub Repo"**.
3. Select your repository: `nikhil1102-ai/custom_mcp_server`.
4. Railway will auto-detect the `Procfile` and configure the start command.

### Step 2: Configure Environment Variables

In your Railway project dashboard, go to **Variables** and add:

| Variable | Value | Description |
|---|---|---|
| `AUTO_APPROVE` | `true` | Auto-approve actions (no terminal in cloud) |
| `HOST` | `0.0.0.0` | Bind to all interfaces (required by Railway) |
| `GOOGLE_TOKEN_JSON` | *(contents of token.json)* | OAuth token for Google APIs (see Step 3) |

> **Note:** Railway automatically sets the `PORT` variable — you do **not** need to add it manually.

### Step 3: Set Up Google OAuth Token

Since Railway has no browser for the OAuth consent flow, you must generate `token.json` locally first:

1. **Run the server locally** once:
   ```bash
   python server.py
   ```
2. **Make any API call** (e.g., append to doc) — this triggers the OAuth browser flow.
3. **Complete the consent** in your browser — `token.json` is created.
4. **Copy the token contents:**
   ```bash
   # Windows (PowerShell)
   Get-Content token.json

   # macOS/Linux
   cat token.json
   ```
5. **Paste the entire JSON** into the `GOOGLE_TOKEN_JSON` Railway variable.

> **Alternative:** You can also upload `token.json` and `credentials.json` as Railway volume mounts if your plan supports it.

### Step 4: Handle Credentials in Production

For Railway, the `credentials.json` and `token.json` files need to be provided via environment variables since they can't be committed to git. Update `auth.py` to read from env vars by adding this pattern (optional enhancement):

```python
import json
import os

# If GOOGLE_TOKEN_JSON env var is set, write it to token.json on startup
token_env = os.getenv("GOOGLE_TOKEN_JSON")
if token_env and not os.path.exists("token.json"):
    with open("token.json", "w") as f:
        f.write(token_env)
```

### Step 5: Deploy

1. **Push your code** to GitHub:
   ```bash
   git add .
   git commit -m "Add Railway deployment support"
   git push origin main
   ```
2. Railway will **auto-deploy** from the `main` branch.
3. Once deployed, Railway provides a **public URL** like:
   ```
   https://your-app-name.up.railway.app
   ```

### Step 6: Test the Deployed API

```bash
# Replace with your Railway URL
curl -X POST https://your-app-name.up.railway.app/append_to_doc \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "YOUR_DOC_ID", "content": "Hello from Railway!"}'

curl -X POST https://your-app-name.up.railway.app/create_email_draft \
  -H "Content-Type: application/json" \
  -d '{"to": "test@example.com", "subject": "Test", "body": "Deployed!"}'
```

### Railway Environment Summary

| Setting | Value |
|---|---|
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` (from Procfile) |
| **Build Command** | `pip install -r requirements.txt` (auto-detected) |
| **Port** | Auto-assigned by Railway via `$PORT` |
| **Health Check** | `GET /docs` (FastAPI Swagger UI) |

---

## Security Notes

- `credentials.json` and `token.json` are excluded from version control via `.gitignore`.
- The server binds to `127.0.0.1` (localhost) by default — it is **not** exposed to the network.
- On Railway, set `AUTO_APPROVE=true` since there is no terminal for manual approval.
- Only `documents` and `gmail.compose` OAuth scopes are requested.
- For production, consider adding API key authentication to protect your endpoints.
