#!/bin/bash
set -u
# 小红书爆款文章采集脚本 - 串行执行多个关键词
# 使用方法: bash collect-xhs-viral.sh

KEYWORDS=(
    "职场干货"
    "AI工具"
    "穿搭技巧"
    "副业赚钱"
    "护肤测评"
    "美食教程"
    "读书笔记"
    "情感语录"
    "省钱攻略"
    "旅行攻略"
    "居家收纳"
    "健身塑形"
    "母婴好物"
    "数码测评"
    "手账日记"
)

OUTPUT_DIR="/var/minis/shared/xhs-team/research/collected-data"
mkdir -p "$OUTPUT_DIR"

cd /var/minis/skills/airtap/scripts

for keyword in "${KEYWORDS[@]}"; do
    echo "=== 开始采集: $keyword ==="
    
    # 创建任务
    TASK_ID=$(python3 airtap.py task create \
        --message "小红书批量采集任务：搜索「$keyword」关键词，进入综合结果页，向上滑动加载至少3页内容（约60条笔记），对每条笔记记录：标题、作者名、点赞数、发布时间。只记录点赞数≥10000的10W+爆款笔记，每条笔记点击进去记录完整标题和内容摘要。最终输出JSON数组格式的结果。" \
        --receiver-id cloud \
        --model-id airtap-1.1 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['taskId'])")
    
    if [ -z "$TASK_ID" ]; then
        echo "创建任务失败，跳过 $keyword"
        continue
    fi
    
    echo "任务ID: $TASK_ID"
    
    # 轮询等待完成
    while true; do
        sleep 30
        STATE=$(python3 airtap.py task get-details --task-id $TASK_ID 2>&1 | grep -o '"taskState": "[^"]*"' | cut -d'"' -f4)
        echo "  状态: $STATE"
        if [ "$STATE" = "COMPLETED" ] || [ "$STATE" = "FAILED" ]; then
            break
        fi
    done
    
    # 提取结果
    RESULT=$(python3 airtap.py task get-details --task-id $TASK_ID 2>&1 | grep -A 9999 '"text"' | grep -B 9999 '```json' | tail -n +2 | head -n -1)
    
    # 保存结果
    echo "$RESULT" > "$OUTPUT_DIR/${keyword}.json"
    echo "已保存: ${keyword}.json"
    
    # 统计数量
    COUNT=$(echo "$RESULT" | grep -o '"title"' | wc -l)
    echo "采集到 $COUNT 条笔记"
    echo ""
done

echo "=== 全部采集完成 ==="
echo "输出目录: $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
