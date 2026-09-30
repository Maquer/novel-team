#!/bin/bash
# Version: 0.1.0
set -u
# Minis 侧心跳上报脚本
# 每 1 分钟执行一次（通过 countdown-scheduler 或 crontab）
# 向 my-place 上报 Minis 存活状态

MY_PLACE="https://loong.my-place.us/reminders/heartbeat.php"

curl -s -G "$MY_PLACE" \
  --data-urlencode "source=minis-ios" \
  --data-urlencode "ts=$(date +%s)" > /dev/null 2>&1
