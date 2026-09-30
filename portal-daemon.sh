#!/bin/bash
# Version: 0.1.0
# Minis Portal 守护启动器
# 同时启动 API 服务 + Cloudflare Tunnel，并用 watchdog 循环保活
# 用法: nohup bash /var/minis/shared/portal-daemon.sh &

LOG_API=/tmp/portal-api.log
LOG_TUNNEL=/tmp/cloudflared-minis.log
PID_API=/tmp/portal-api.pid
PID_TUNNEL=/tmp/cloudflared-tunnel.pid

cleanup() {
  kill $(cat $PID_API 2>/dev/null) 2>/dev/null
  kill $(cat $PID_TUNNEL 2>/dev/null) 2>/dev/null
  pkill -f "web-portal.py" 2>/dev/null
  pkill -f "cloudflared.*config-minis" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

while true; do
  # 检查 API 是否存活
  if ! kill -0 $(cat $PID_API 2>/dev/null) 2>/dev/null; then
    echo "$(date): 启动 API 服务..."
    python3 /var/minis/shared/web-portal.py > $LOG_API 2>&1 &
    echo $! > $PID_API
    sleep 2
  fi

  # 检查隧道是否存活
  if ! kill -0 $(cat $PID_TUNNEL 2>/dev/null) 2>/dev/null; then
    echo "$(date): 启动 Cloudflare Tunnel..."
    cloudflared tunnel --config /root/.cloudflared/config-minis.yml --no-autoupdate run minis > $LOG_TUNNEL 2>&1 &
    echo $! > $PID_TUNNEL
    sleep 5
  fi

  # 每 30 秒检查一次
  sleep 30
done
