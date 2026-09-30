#!/usr/bin/env bash
# 页面监控最小可用示例
# 用法：bash tinyfish-monitor.sh <url> [label]
# 语义：抓取 URL → 计算 sha256 → 与上次比对 → 有变更则存快照 + 写状态
#      无变更则静默。可被 cron/Apple Shortcuts 或手动触发。
#
# 存储位置：/var/minis/shared/tinyfish/monitor/
#   - <label>.json  历史状态（digest 变化时间线）
#   - <label>-<ts>.md  每次变更的 Markdown 快照（最多保留最近 20 份）

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法：bash tinyfish-monitor.sh <url> [label]"
  echo "示例：bash tinyfish-monitor.sh https://example.com mypage"
  exit 1
fi

URL="$1"
LABEL="${2:-$(echo -n "$URL" | sha1sum | cut -c1-10)}"

# 若 key 未设置，退出码 2 表示"阻塞于凭证"
python3 /var/minis/shared/tinyfish/tinyfish.py monitor "$URL" --label "$LABEL" \
  --out /var/minis/shared/tinyfish/monitor
