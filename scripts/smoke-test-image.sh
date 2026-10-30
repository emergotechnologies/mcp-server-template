#!/usr/bin/env bash
# Start the image with bearer auth and check /healthz plus an authenticated MCP initialize.
# Usage: scripts/smoke-test-image.sh [image]   (default: mcp-server-template:dev)
set -euo pipefail

IMAGE="${1:-mcp-server-template:dev}"
PORT=18000
TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
NAME="mcp-smoke-$$"
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'

docker run -d --name "$NAME" -p "$PORT:8000" -e MCP_AUTH_MODE=bearer -e MCP_AUTH_TOKEN="$TOKEN" "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null' EXIT

for _ in $(seq 1 30); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$NAME")" = healthy ] && break
  sleep 2
done
[ "$(docker inspect -f '{{.State.Health.Status}}' "$NAME")" = healthy ] || { docker logs "$NAME"; echo "container not healthy"; exit 1; }

mcp_status() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "http://localhost:$PORT/mcp" \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' "$@" -d "$INIT"
}
[ "$(mcp_status -H "Authorization: Bearer $TOKEN")" = 200 ] || { echo "authenticated initialize failed"; exit 1; }
[ "$(mcp_status)" = 401 ] || { echo "unauthenticated initialize was not rejected"; exit 1; }
[ "$(docker exec "$NAME" id -u)" != 0 ] || { echo "container runs as root"; exit 1; }
echo "smoke test passed"
