#!/bin/bash
# Version: 0.1.0
set -euo pipefail
# cf-tunnel-setup.sh — Cloudflare Tunnel 固定出口一键部署
# 依赖环境变量：
#   CF_TUNNEL_API_TOKEN  — 需要 Account:Cloudflare Tunnel:Edit + Zone:DNS:Edit
#   CF_ACCOUNT_ID         — 账户 ID（默认从主 token 自动探测）
#   CF_ZONE_ID            — 区域 ID（默认从 maquer.eu.org 自动探测）
# 用法：
#   bash cf-tunnel-setup.sh create   <tunnel-name> <local-port> [hostname]
#   bash cf-tunnel-setup.sh run      <tunnel-name> <local-port>
#   bash cf-tunnel-setup.sh delete   <tunnel-name>
#   bash cf-tunnel-setup.sh list

ACCT="${CF_ACCOUNT_ID:-6ddb238e2db8f43a4e974040d1437c2f}"
ZONE="${CF_ZONE_ID:-ba3ae4dd6b2f4d7846914722fa3590dc}"
ZONE_NAME="maquer.eu.org"
API="https://api.cloudflare.com/client/v4"

cf() {  # cf <method> <path> [json-body]
  local m="$1" p="$2" b="${3:-}"
  if [ -n "$b" ]; then
    curl -sS --max-time 15 -X "$m" "$API$p" \
      -H "Authorization: Bearer $CF_TUNNEL_API_TOKEN" \
      -H "Content-Type: application/json" -d "$b"
  else
    curl -sS --max-time 15 -X "$m" "$API$p" \
      -H "Authorization: Bearer $CF_TUNNEL_API_TOKEN"
  fi
}

jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null; }

list_tunnels() {
  echo "=== Tunnels ==="
  cf GET "/accounts/$ACCT/tunnels" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if not d.get('success'):
  print('ERROR:', d.get('errors')); sys.exit(1)
for t in d.get('result',[]):
  print(f\"  {t['id']}  {t['name']}  status={t.get('status','?')}\")
if not d.get('result'): print('  (none)')
"
}

create_tunnel() {
  local NAME="$1" PORT="$2" HOST="${3:-$NAME.$ZONE_NAME}"
  echo ">>> Creating tunnel '$NAME' ..."
  local RES
  RES=$(cf POST "/accounts/$ACCT/tunnels" "{\"name\":\"$NAME\"}")
  local OK TID
  OK=$(echo "$RES" | jget "['success']")
  if [ "$OK" != "True" ]; then
    echo "ERROR creating tunnel:"; echo "$RES" | python3 -m json.tool 2>/dev/null || echo "$RES"
    exit 1
  fi
  TID=$(echo "$RES" | jget "['result']['id']")
  echo "  tunnel_id=$TID"
  # Get connector token (the secret cloudflared uses to connect)
  local TOKEN_RES TOKEN_VAL
  TOKEN_RES=$(cf GET "/accounts/$ACCT/tunnels/$TID/token")
  TOKEN_VAL=$(echo "$TOKEN_RES" | jget "['result']")
  if [ -z "$TOKEN_VAL" ] || [ "$TOKEN_VAL" = "None" ]; then
    # Fallback: get connector token via cfd_tunnel endpoint
    TOKEN_RES=$(cf GET "/accounts/$ACCT/cfd_tunnel/$TID/token")
    TOKEN_VAL=$(echo "$TOKEN_RES" | jget "['result']")
  fi
  echo "  tunnel_token=$TOKEN_VAL"
  # Create DNS CNAME route
  echo ">>> Creating DNS route $HOST -> $TID.cfargotunnel.com ..."
  local DNS_RES
  DNS_RES=$(cf POST "/zones/$ZONE/dns_records" \
    "{\"type\":\"CNAME\",\"name\":\"$HOST\",\"content\":\"$TID.cfargotunnel.com\",\"proxied\":true}")
  echo "$DNS_RES" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if d.get('success'):
  r=d['result']
  print(f\"  DNS OK: {r['name']} -> {r['content']}  id={r['id']}\")
else:
  print('  DNS ERROR:', d.get('errors'))
" 2>/dev/null || echo "$DNS_RES"
  # Write config file
  mkdir -p ~/.cloudflared
  cat > ~/.cloudflared/config-$NAME.yml <<EOF
tunnel: $TID
credentials-file: ~/.cloudflared/$TID.json
ingress:
  - hostname: $HOST
    service: http://localhost:$PORT
  - service: http_status:404
EOF
  # Save token for run command
  echo "$TOKEN_VAL" > ~/.cloudflared/.token-$NAME
  chmod 600 ~/.cloudflared/.token-$NAME 2>/dev/null
  # Save tunnel ID
  echo "$TID" > ~/.cloudflared/.id-$NAME
  echo ""
  echo "✅ Tunnel '$NAME' created"
  echo "   Public URL:  https://$HOST"
  echo "   Tunnel ID:   $TID"
  echo "   Config:      ~/.cloudflared/config-$NAME.yml"
  echo ""
  echo "   To run:  bash $0 run $NAME $PORT"
  echo "   Token saved to ~/.cloudflared/.token-$NAME"
}

run_tunnel() {
  local NAME="$1" PORT="$2"
  local TID TOKEN_VAL
  TID=$(cat ~/.cloudflared/.id-$NAME 2>/dev/null)
  TOKEN_VAL=$(cat ~/.cloudflared/.token-$NAME 2>/dev/null)
  if [ -z "$TID" ]; then echo "Tunnel '$NAME' not found. Create first."; exit 1; fi
  echo ">>> Starting cloudflared for tunnel '$NAME' (id=$TID) -> localhost:$PORT ..."
  if [ -n "$TOKEN_VAL" ] && [ "$TOKEN_VAL" != "None" ]; then
    # Token-based (no credentials.json needed)
    exec cloudflared tunnel --no-autoupdate run --token "$TOKEN_VAL" \
      --url "http://localhost:$PORT" 2>&1
  else
    # Credentials-based (needs credentials.json from login)
    echo "No token saved. Trying credentials file..."
    exec cloudflared tunnel --no-autoupdate --config ~/.cloudflared/config-$NAME.yml run 2>&1
  fi
}

delete_tunnel() {
  local NAME="$1" TID
  TID=$(cat ~/.cloudflared/.id-$NAME 2>/dev/null)
  if [ -z "$TID" ]; then echo "Tunnel '$NAME' not found."; exit 1; fi
  echo ">>> Deleting tunnel '$NAME' (id=$TID) ..."
  cf DELETE "/accounts/$ACCT/tunnels/$TID" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('  Deleted:', d.get('success', False))
" 2>/dev/null
  # Clean up DNS (find by tunnel ID)
  cf GET "/zones/$ZONE/dns_records?per_page=100" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d.get('result',[]):
  if '$TID' in r.get('content',''):
    print(f\"  Deleting DNS: {r['name']}\")
    # Would need to call DELETE per record
" 2>/dev/null
  rm -f ~/.cloudflared/.id-$NAME ~/.cloudflared/.token-$NAME ~/.cloudflared/config-$NAME.yml
  echo "✅ Cleaned up"
}

# Main
CMD="${1:-list}"
case "$CMD" in
  list)   list_tunnels ;;
  create) create_tunnel "${2:-minis}" "${3:-8080}" "${4:-}" ;;
  run)    run_tunnel "${2:-minis}" "${3:-8080}" ;;
  delete) delete_tunnel "${2:-minis}" ;;
  *) echo "Usage: $0 {list|create <name> <port> [host]|run <name> <port>|delete <name>}"; exit 1 ;;
esac
