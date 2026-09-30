#!/bin/bash
# Version: 0.1.0
# =============================================================================
# second-brain-pulse.sh — 轻量训练脉冲（<3秒）
#
# 训练 Agent 的轻量版，只做关键指标采样，不跑全量扫描。
# 用于每次对话结束后的快速状态检查。
#
# 用法:
#   bash /var/minis/shared/second-brain-pulse.sh
#   bash /var/minis/shared/second-brain-pulse.sh --json
#   bash /var/minis/shared/second-brain-pulse.sh --notify
# =============================================================================

STATE_DIR="/var/minis/shared/.training-state"
OBSIDIAN_ROOT="/var/minis/mounts/loong"
LOG_FILE="${STATE_DIR}/pulse.log"
NOTIFY_DIR="${STATE_DIR}/notifications"
mkdir -p "$STATE_DIR" "$NOTIFY_DIR"

TIMESTAMP=$(date '+%F %H:%M:%S')

# 清空上次通知
> "${NOTIFY_DIR}/pending.txt"

log() { echo "$TIMESTAMP | $1" >> "$LOG_FILE"; }

echo ""
echo "🫀 训练脉冲 — ${TIMESTAMP}"
echo ""

# ===== 快速采样 =====

# 1. 笔记计数
NOTE_COUNT=$(find "$OBSIDIAN_ROOT" -name "*.md" 2>/dev/null | wc -l)

# 2. 搜索统计
SEARCH_STATS=$(python3 /var/minis/shared/obsidian-analytics.py --stats 2>/dev/null | grep -E "总搜索|命中率|点击率" || echo "")

# 3. 待审核卡片
PENDING_CARDS=$(python3 /var/minis/shared/obsidian-distill.py --pending 2>/dev/null | grep -c "卡片" || echo "0")

# 4. 缺标签笔记数
MISSING_TAGS=$(python3 /var/minis/shared/obsidian-tag.py --audit 2>/dev/null | grep "缺标签" | grep -o '[0-9][0-9]*' | head -1 || echo "0")

# 5. 图谱统计
GRAPH_OUT=$(python3 /var/minis/shared/obsidian-graph.py --stats 2>/dev/null || echo "")
NODES=$(echo "$GRAPH_OUT" | grep "总节点" | grep -o '[0-9][0-9]*' | head -1 || echo "0")
LINKS=$(echo "$GRAPH_OUT" | grep "总链接" | grep -o '[0-9][0-9]*' | head -1 || echo "0")
ISOLATED=$(echo "$GRAPH_OUT" | grep "孤立笔记" | grep -o '[0-9][0-9]*' | head -1 || echo "0")

# 6. 上次训练时间
LAST_TRAIN=$(cat "${STATE_DIR}/last-run.txt" 2>/dev/null || echo "never")

# ===== 发现异常并生成通知 =====

NOTIFICATIONS=()

# 孤立笔记增加检测
PREV_ISOLATED=$(python3 -c "import json; d=json.load(open('${STATE_DIR}/stats.json')); print(d.get('isolated','?'))" 2>/dev/null || echo "?")
if [ "$ISOLATED" != "?" ] && [ "$PREV_ISOLATED" != "?" ] && [ "$PREV_ISOLATED" != "?" ]; then
    if [ "$ISOLATED" -gt "$PREV_ISOLATED" ] 2>/dev/null; then
        DIFF=$((ISOLATED - PREV_ISOLATED))
        NOTIFICATIONS+=("🏝️ 孤立笔记 +${DIFF} (${PREV_ISOLATED}→${ISOLATED})")
    fi
fi

# 浅涉笔记（跳过：blindspot --scan 耗时 ~19s，pulse 设计目标 <3s；scheduler 有独立 blindspot 任务）
SHALLOW="skip"

# 待审核卡片
if [ "$PENDING_CARDS" -gt "0" ] 2>/dev/null; then
    NOTIFICATIONS+=("📝 待审核知识卡片: ${PENDING_CARDS} 张")
fi

# 缺标签
if [ "$MISSING_TAGS" -gt "30" ] 2>/dev/null; then
    NOTIFICATIONS+=("🏷️ 缺标签笔记: ${MISSING_TAGS} 篇")
fi

# 搜索命中率低
HITRATE=$(echo "$SEARCH_STATS" | grep "命中率" | grep -o '[0-9]*[.]?[0-9]*' | head -1 || echo "100")
if [ "$(echo "$HITRATE < 30" | bc 2>/dev/null)" = "1" ] 2>/dev/null; then
    NOTIFICATIONS+=("🔍 搜索命中率仅 ${HITRATE}%（建议扩展搜索范围）")
fi

# 长时间未训练
if [ "$LAST_TRAIN" != "never" ]; then
    LAST_EPOCH=$(date -d "$LAST_TRAIN" +%s 2>/dev/null || echo "0")
    NOW_EPOCH=$(date +%s)
    if [ "$LAST_EPOCH" -gt "0" ]; then
        HOURS_AGO=$(( (NOW_EPOCH - LAST_EPOCH) / 3600 ))
        if [ "$HOURS_AGO" -gt "6" ] 2>/dev/null; then
            NOTIFICATIONS+=("⏰ 上次全量训练: ${HOURS_AGO} 小时前")
        fi
    fi
fi

# ===== 输出 =====

echo "📊 状态:"
echo "  笔记: ${NOTE_COUNT} | 图谱: ${NODES}节点/${LINKS}链接 | 孤立: ${ISOLATED}"
echo "  搜索: ${SEARCH_STATS}"
echo "  待审核卡片: ${PENDING_CARDS} | 缺标签: ${MISSING_TAGS}"
echo "  上次全量训练: ${LAST_TRAIN}"
echo ""

if [ ${#NOTIFICATIONS[@]} -gt 0 ]; then
    echo "⚠️ 发现:"
    for n in "${NOTIFICATIONS[@]}"; do
        echo "  ${n}"
        echo "$n" >> "${NOTIFY_DIR}/pending.txt"
    done
else
    echo "✅ 一切正常"
fi

echo ""

# JSON 输出
if [ "${1:-}" = "--json" ]; then
    python3 -c "
import json
print(json.dumps({
    'timestamp': '${TIMESTAMP}',
    'notes': ${NOTE_COUNT},
    'nodes': ${NODES},
    'links': ${LINKS},
    'isolated': ${ISOLATED},
    'pending_cards': ${PENDING_CARDS},
    'missing_tags': ${MISSING_TAGS},
    'notifications': $(python3 -c "
import json
with open('${NOTIFY_DIR}/pending.txt') as f:
    print(json.dumps([l.strip() for l in f.readlines()]))
")
}, ensure_ascii=False, indent=2))
"
fi

# 写入状态快照
python3 -c "
import json
state = {
    'pulse_ts': '${TIMESTAMP}',
    'notes': ${NOTE_COUNT},
    'nodes': ${NODES},
    'links': ${LINKS},
    'isolated': ${ISOLATED},
    'pending_cards': ${PENDING_CARDS},
    'missing_tags': ${MISSING_TAGS},
}
with open('${STATE_DIR}/pulse-latest.json', 'w') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
"

log "pulse: notes=${NOTE_COUNT} nodes=${NODES} links=${LINKS} isolated=${ISOLATED} pending=${PENDING_CARDS} tags=${MISSING_TAGS}"