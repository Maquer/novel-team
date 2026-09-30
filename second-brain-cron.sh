#!/bin/bash
# Version: 0.1.0
# =============================================================================
# second-brain-cron.sh — 第二大脑定时任务（Hermes cron 适配）
#
# 用于 Apple Shortcuts 每日自动化，每天 08:00 执行：
#   1. 检查并执行到期调度任务
#   2. 跑轻量训练脉冲
#   3. 可选：用 apple-speak 播报关键结果
#
# 用法:
#   bash /var/minis/shared/second-brain-cron.sh              # 运行，不播报
#   bash /var/minis/shared/second-brain-cron.sh --speak      # 运行并播报结果
#   bash /var/minis/shared/second-brain-cron.sh --status     # 仅查看状态
# =============================================================================

set -u

CRON_LOG="/var/minis/shared/.training-state/cron.log"
TIMESTAMP=$(date '+%F %H:%M:%S')
SPEAK=${1:-}

mkdir -p "$(dirname "$CRON_LOG")"

log() {
    echo "[$TIMESTAMP] $1" >> "$CRON_LOG"
}

echo ""
echo "══════════════════════════════════════════════"
echo "  ⏰ 第二大脑定时任务 — $TIMESTAMP"
echo "══════════════════════════════════════════════"
echo ""

# Step 1: 检查到期任务
log "=== 开始定时任务 ==="
echo "📋 检查调度任务..."
SCHED_RESULT=$(python3 /var/minis/shared/second-brain-scheduler.py check 2>&1)
SCHED_EXIT=$?
echo "$SCHED_RESULT"
log "scheduler check exit=$SCHED_EXIT"

# Step 2: 轻量脉冲
echo ""
echo "🫀 运行训练脉冲..."
PULSE_RESULT=$(bash /var/minis/shared/second-brain-pulse.sh 2>&1)
PULSE_EXIT=$?
echo "$PULSE_RESULT"
log "pulse exit=$PULSE_EXIT"

# Step 3: 汇总结果
SUMMARY="第二大脑定时任务完成"
if [ $SCHED_EXIT -eq 0 ]; then
    SUMMARY="$SUMMARY，调度检查正常"
else
    SUMMARY="$SUMMARY，调度检查有异常"
fi
if [ $PULSE_EXIT -eq 0 ]; then
    SUMMARY="$SUMMARY，训练脉冲正常"
else
    SUMMARY="$SUMMARY，训练脉冲有异常"
fi
# 提取关键指标
STATUS_LINE=$(echo "$PULSE_RESULT" | grep "状态:" | head -1)
if [ -n "$STATUS_LINE" ]; then
    SUMMARY="$SUMMARY，$STATUS_LINE"
fi
log "$SUMMARY"

echo ""
echo "📊 $SUMMARY"
echo ""

# Step 4: 播报结果（可选）
if [ "$SPEAK" = "--speak" ]; then
    echo "🔊 播报结果..."
    apple-speak speak --text "$SUMMARY" --voice zh-CN --rate 0.45 2>/dev/null || true
fi

log "=== 定时任务结束 ==="