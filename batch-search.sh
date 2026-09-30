#!/bin/bash
# Version: 0.1.0
set -u
# 批量搜索多多视频素材 — 链式执行（airtap 同时只能跑1个）
# 用法：bash batch-search.sh

cd /var/minis/skills/airtap/scripts

SEARCHES=(
  "桌面增高架推荐|宿舍桌面收纳|桌面置物架|桌面增高架神器"
  "宿舍床帘推荐|宿舍床帘|床帘凉席套装"
  "挂脖风扇测评|挂脖风扇推荐|无叶挂脖风扇"
  "磁吸酷毙灯推荐|磁吸灯|宿舍磁吸灯|酷毙灯推荐"
  "冰丝凉感坐垫推荐|冰丝坐垫|凉感坐垫推荐|夏天坐垫"
  "保温杯推荐学生|大容量保温杯|保温杯推荐|保温杯测评"
  "床上书桌推荐|折叠床上书桌|宿舍床上桌"
  "挂脖风扇推荐|挂脖风扇测评"
)

echo "📡 开始批量搜索素材（共 ${#SEARCHES[@]} 个搜索）"
echo ""

for search in "${SEARCHES[@]}"; do
  IFS='|' read -ra TERMS <<< "$search"
  primary="${TERMS[0]}"
  fallback="${TERMS[*]}"

  echo "🔍 搜索：${primary}"

  # 等待前一个任务完成（最多等180秒）
  # 先检查一下是否有活跃任务
  TASKS=$(python3 airtap.py task get-list 2>/dev/null | grep -o '"taskId":"[^"]*"' | head -1 | tr -d '"')

  for i in $(seq 1 18); do
    sleep 10
    STATUS=$(python3 airtap.py task get-list 2>/dev/null | grep -oP '"state":"\K[^"]*' | head -1)
    if [ "$STATUS" != "EXECUTING" ] && [ "$STATUS" != "WAITING_FOR_USER_INPUT" ]; then
      break
    fi
  done

  # 检查最新任务状态
  LATEST_TASK=$(python3 airtap.py task get-list 2>/dev/null | grep -oP '"taskId":"\K[^"]*' | head -1)
  if [ -n "$LATEST_TASK" ]; then
    LATEST_STATUS=$(python3 airtap.py task get-list 2>/dev/null | grep -oP '"state":"\K[^"]*' | head -1)
    if [ "$LATEST_STATUS" = "EXECUTING" ]; then
      echo "  ⏳ 等待前一个任务完成..."
      for i in $(seq 1 30); do
        sleep 10
        STATUS=$(python3 airtap.py task get-list 2>/dev/null | grep -oP '"state":"\K[^"]*' | head -1)
        if [ "$STATUS" != "EXECUTING" ]; then break; fi
      done
    fi
  fi

  # 创建任务
  TASK_ID=$(python3 airtap.py task create \
    --receiver-id cloud \
    --model-id airtap-1.0-flash \
    --message "打开抖音App，搜索'${primary}'，找到3个热门带货视频（点赞量高、有商品链接的），记录每个视频的标题、点赞数、评论数、视频链接。如果搜索不到，依次尝试'${fallback}'" 2>&1 | grep -oP '"taskId":"\K[^"]*')

  echo "  ✅ 任务已创建：${TASK_ID}"
  echo ""
done

echo "✅ 所有搜索任务已排队提交"