# Quick start: run locally, expose with ngrok, connect the Voice AI app

You get a public HTTPS URL for the MCP server running on your laptop, so the Voice AI web application can call your tools. The commands are for macOS/Linux; on Windows, use WSL or Git Bash.

**1. Prerequisites.** Install [Python 3.12+](https://www.python.org/downloads/), [uv](https://docs.astral.sh/uv/getting-started/installation/) and git. Create a **free [ngrok](https://dashboard.ngrok.com/signup) account of your own**; don't share accounts with teammates, because the free limits are per account. ngrok requires you to be 18 or older.

**2. Install ngrok and log in** (macOS: `brew install ngrok`; other systems: [ngrok.com/download](https://ngrok.com/download)). Copy your authtoken from [dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken):
```bash
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

**3. Clone and install:**
```bash
git clone <REPO_URL> mcp-server && cd mcp-server
uv sync
```

**4. Start ngrok** in a **second terminal** and leave it running:
```bash
ngrok http 8000
```
Copy the `Forwarding` URL, e.g. `https://your-name.ngrok-free.app`. This is your free dev domain, and it stays the same every time you start ngrok.

**5. Create `.env`** in the first terminal. Replace the URL with yours; all settings are documented in `.env.example`.
```bash
cat > .env <<EOF
MCP_TRANSPORT=http
MCP_AUTH_MODE=bearer
MCP_AUTH_TOKEN=$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')
MCP_PUBLIC_URL=https://your-name.ngrok-free.app
EOF
```

**6. Start the server:**
```bash
uv run mcp-server-template
```
The log prints `MCP endpoint (public): https://your-name.ngrok-free.app/mcp`.

**7. Verify** from a third terminal in the project folder:
```bash
URL=$(grep MCP_PUBLIC_URL .env | cut -d= -f2); TOKEN=$(grep MCP_AUTH_TOKEN .env | cut -d= -f2)
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
curl -s $URL/healthz                                   # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' -X POST $URL/mcp -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$INIT"   # 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST $URL/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$INIT"   # 401
```

**8. Connect the Voice AI web application.** Add an MCP server in its settings:

| Field | Value |
|---|---|
| Server URL | `https://your-name.ngrok-free.app/mcp` |
| Header | `Authorization` = `Bearer <your MCP_AUTH_TOKEN>` (see `cat .env`) |

The example tool `add` should now be listed. Add your own tools in `src/mcp_server_template/tools.py` and restart the server (step 6).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` | The token in the web app doesn't match `MCP_AUTH_TOKEN` in `.env`. Include the `Bearer ` prefix. |
| `421` / `Invalid Host header` | `MCP_PUBLIC_URL` doesn't match the ngrok `Forwarding` URL. Fix `.env` and restart the server. |
| Server refuses to start: `MCP_AUTH_MODE=none is refused` | `.env` is missing `MCP_AUTH_MODE=bearer` or `MCP_AUTH_TOKEN`. Redo step 5. |
| ngrok warning page in the browser | Normal on the free plan for browsers only. The Voice AI backend isn't affected; for browser tests, send the header `ngrok-skip-browser-warning: 1`. |
| `ERR_NGROK_...`: endpoint already online | Another ngrok session uses your domain. Close it (or stop it in the [dashboard](https://dashboard.ngrok.com/agents)) and retry. |
| ngrok usage-limit error | You hit the free monthly limits (about 20k requests / 1 GB). Use your own account, not a shared one. |
| `502 Bad Gateway` from ngrok | The server isn't running on port 8000. Start it (step 6). |
| `address already in use` on start | Another program uses port 8000. Add `MCP_PORT=8001` to `.env` and run `ngrok http 8001` instead. |
