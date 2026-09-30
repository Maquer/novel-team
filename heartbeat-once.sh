#!/bin/bash
# Version: 0.1.0
set -u
# Minis 侧单次心跳上报脚本
# 每 1 分钟跑一次，检查下一个任务时间
# 如果差 1 分钟，上报一次心跳（其他时间不报）
# ⚠️ 所有时间戳使用北京时间（Asia/Shanghai）
# ⚠️ 修复：bash 会把 09 当八进制，用 10# 强制十进制

export TZ=Asia/Shanghai

MY_PLACE="https://loong.my-place.us/reminders"

# ★ 任务时间列表（需与 config.php 保持同步）
TASK_TIMES="09:00 14:00 22:00 23:59"

# 当前时间（分钟数）
NOW_H=$(date +%H)
NOW_M=$(date +%M)
NOW_MIN=$(( 10#$NOW_H * 60 + 10#$NOW_M ))

# 检查每个任务
for TASK in $TASK_TIMES; do
    TASK_H=$(echo $TASK | cut -d: -f1)
    TASK_M=$(echo $TASK | cut -d: -f2)
    TASK_MIN=$(( 10#$TASK_H * 60 + 10#$TASK_M ))
    
    # 计算差值（考虑跨天，如 23:59 → 00:00）
    DIFF=$(( TASK_MIN - NOW_MIN ))
    if [ $DIFF -lt 0 ]; then
        DIFF=$(( DIFF + 1440 ))
    fi
    
    # 如果差 1 分钟，上报心跳
    if [ $DIFF -eq 1 ]; then
        curl -s -G "$MY_PLACE/heartbeat.php" \
          --data-urlencode "source=minis-ios" \
          --data-urlencode "next_task=$TASK" > /dev/null 2>&1
        echo "[$(date)] Heartbeat sent, next task: $TASK"
        break
    fi
done
