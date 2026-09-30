#!/bin/bash
# Version: 0.1.0
# Minis Portal 快速重启脚本
# 用法: bash /var/minis/shared/restart-portal.sh

echo "🔄 重启 Minis Portal 服务..."

# 清理旧进程
pkill -f "web-portal.py" 2>/dev/null
pkill -f "cloudflared" 2>/dev/null
pkill -f "localtunnel" 2>/dev/null
sleep 2

# 启动 web-portal
echo "🚀 启动 Web 服务..."
python3 /var/minis/shared/web-portal.py > /tmp/portal-api.log 2>&1 &
sleep 3

# 验证本地服务
if curl -sS --max-time 3 http://127.0.0.1:8765/api/health > /dev/null 2>&1; then
  echo "✅ Web 服务正常"
else
  echo "❌ Web 服务启动失败"
  cat /tmp/portal-api.log
  exit 1
fi

# 启动 localtunnel（临时方案）
echo "🚀 启动 Local Tunnel..."
npx -y localtunnel --port 8765 2>&1 &
LPID=$!
sleep 15

# 获取隧道 URL
URL=$(cat /proc/$LPID/fd/1 2>/dev/null | grep -o "https://[^ ]*" | head -1)

if [ -n "$URL" ]; then
  echo "✅ Tunnel 已启动"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🌐 访问地址: $URL"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "⚠️  注意: URL 每次重启会变"
  echo "💡 测试: curl -H \"bypass-tunnel-reminder: true\" $URL/api/health"
else
  echo "❌ Tunnel 启动失败"
  echo "尝试手动启动: npx -y localtunnel --port 8765"
fi

echo ""
echo "进程状态:"
ps aux | grep -E "web-portal|localtunnel" | grep -v grep | head -5