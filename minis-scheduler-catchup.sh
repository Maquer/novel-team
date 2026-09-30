#!/bin/bash
# Version: 0.1.0
# =============================================================================
# minis-scheduler-catchup.sh — Apple Shortcuts 触发入口
#
# 用途：被 Apple Shortcuts 调用，触发 countdown-scheduler 补跑
#
# 用法：
#   bash /var/minis/shared/minis-scheduler-catchup.sh          # 后台补跑（推荐）
#   bash /var/minis/shared/minis-scheduler-catchup.sh --now   # 同步执行并返回结果
#   bash /var/minis/shared/minis-scheduler-catchup.sh --status # 仅查看状态
# =============================================================================

set -u

SCRIPT="/var/minis/shared/countdown-scheduler.py"
LOG_DIR="/var/minis/shared/.scheduler/logs"
LOG_FILE="$LOG_DIR/$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$LOG_DIR"

case "${1:-}" in
  --status)
    python3 "$SCRIPT" status
    ;;
  --now)
    echo "[$(date '+%F %T')] Starting catchup..." >> "$LOG_FILE"
    python3 "$SCRIPT" check --catchup 2>&1 | tee -a "$LOG_FILE"
    echo "[$(date '+%F %T')] Done" >> "$LOG_FILE"
    ;;
  --help)
    echo "Usage: bash $0 [--now|--status|--help]"
    echo ""
    echo "  (no args)   Run catchup in background, log to $LOG_FILE"
    echo "  --now       Run synchronously, show output"
    echo "  --status    Show scheduler status"
    echo "  --help      Show this help"
    exit 0
    ;;
  *)
    # Default: background run (Safe for Shortcuts which have limited runtime)
    nohup python3 "$SCRIPT" check --catchup >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo "[$(date '+%F %T')] Started catchup in background (pid=$PID)" >> "$LOG_FILE"
    echo "Background process started. Log: $LOG_FILE"
    ;;
esac
