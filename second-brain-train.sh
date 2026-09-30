#!/bin/bash
# Version: 0.1.0
# =============================================================================
# second-brain-train.sh — 第二大脑持续训练 Agent
#
# 每次对话时自动执行一轮训练步：
#   1. 扫描 Obsidian 变更 → 蒸馏知识卡片
#   2. 重建知识图谱 → 检测新链接/孤立笔记
#   3. 交叉验证 → 发现矛盾/弱引用
#   4. 认知盲区扫描 → 发现缺口/浅涉笔记
#   5. 搜索热度统计 → 更新权重
#   6. 标签一致性审计
#   7. 生成训练日志 → 写入 Obsidian 04-Archives/Training/
#
# 用法:
#   bash /var/minis/shared/second-brain-train.sh
#   bash /var/minis/shared/second-brain-train.sh --full   # 全量训练（较慢）
#   bash /var/minis/shared/second-brain-train.sh --status # 查看训练状态
# =============================================================================

set -u

# 路径
OBSIDIAN_ROOT="/var/minis/mounts/loong"
TRAINING_DIR="${OBSIDIAN_ROOT}/04-Archives/Training"
STATE_DIR="/var/minis/shared/.training-state"
LOG_FILE="${STATE_DIR}/training.log"
LAST_RUN="${STATE_DIR}/last-run.txt"
STATS_FILE="${STATE_DIR}/stats.json"

mkdir -p "$TRAINING_DIR" "$STATE_DIR"
TODAY=$(date +%F)
TIMESTAMP=$(date '+%F %H:%M:%S')
SESSION_LOG="${TRAINING_DIR}/training-${TODAY}.md"

# 记录日志
log_msg() {
    echo "$TIMESTAMP | $1" >> "$LOG_FILE"
}

# 安全运行 python 脚本，输出捕获到变量
run_step() {
    local desc="$1"
    shift
    log_msg "START: $desc"
    # 重定向 stdout 到临时文件，stderr 到 /dev/null
    local tmpout
    tmpout=$(mktemp)
    "$@" > "$tmpout" 2>/dev/null || true
    local result
    result=$(cat "$tmpout")
    rm -f "$tmpout"
    log_msg "END: $desc"
    echo "$result"
}

echo ""
echo "══════════════════════════════════════════════"
echo "  🧠 第二大脑训练步 — ${TIMESTAMP}"
echo "══════════════════════════════════════════════"
echo ""

# =============================================================================
# Step 0: 检查 Obsidian 挂载状态
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 0/12: 环境检查"
echo "└──────────────────────────────────────────────┘"

if [[ ! -d "$OBSIDIAN_ROOT" ]]; then
    echo "❌ Obsidian 未挂载，跳过训练步"
    exit 1
fi

NOTE_COUNT=$(find "$OBSIDIAN_ROOT" -name "*.md" 2>/dev/null | wc -l)
echo "  ✅ Obsidian 已挂载 (${NOTE_COUNT} 篇笔记)"

# 检查上次运行时间
if [[ -f "$LAST_RUN" ]]; then
    LAST=$(cat "$LAST_RUN")
    echo "  📅 上次运行: $LAST"
else
    echo "  🆕 首次运行"
fi
echo ""

# =============================================================================
# Step 1: 知识蒸馏 — 扫描 Inbox 待处理文件
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 1/12: 知识蒸馏 (Inbox 待处理)"
echo "└──────────────────────────────────────────────┘"

# 2026-09-04 变更：自动 --batch 蒸馏已禁用（避免 13 天堆积 234 个未审核 draft 卡片污染 PARA）
# 需要蒸馏时手动执行: python3 /var/minis/shared/obsidian-distill.py --batch
# 或者只审核已有 pending: python3 /var/minis/shared/obsidian-distill.py --review
PENDING=$(python3 /var/minis/shared/obsidian-distill.py --pending 2>/dev/null || echo "")
if echo "$PENDING" | grep -qE "待审核|待蒸馏|卡片"; then
    echo "  ⚠️ Inbox 有待蒸馏文件（未自动处理，避免堆积）"
    echo "$PENDING"
else
    echo "  ✅ Inbox 无待处理文件"
fi
echo ""

# =============================================================================
# Step 2: 知识图谱 — 统计 + 孤立笔记检测
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 2/12: 知识图谱更新"
echo "└──────────────────────────────────────────────┘"

GRAPH_STATS=$(python3 /var/minis/shared/obsidian-graph.py --stats 2>/dev/null || echo "")
echo "$GRAPH_STATS" | head -8
echo ""

# =============================================================================
# Step 3: 交叉验证 — 最近变更的笔记对
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 3/12: 交叉验证 (Top 4)"
echo "└──────────────────────────────────────────────┘"

# 取最近 7 天的笔记做重点验证
CROSSQ_RESULT=$(python3 /var/minis/shared/obsidian-crossq.py --top 4 2>/dev/null || echo "")
# 只取验证标题行和发现行，避免过长
echo "$CROSSQ_RESULT" | head -25
echo "  ... (完整结果见 --report)"
echo ""

# =============================================================================
# Step 4: 认知盲区 — 浅涉笔记 + 认知差距
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 4/12: 认知盲区扫描"
echo "└──────────────────────────────────────────────┘"

BLINDSPOT_RESULT=$(python3 /var/minis/shared/obsidian-blindspot.py --scan 2>/dev/null || echo "")
echo "$BLINDSPOT_RESULT" | head -20
echo ""

# =============================================================================
# Step 5: 搜索热度 + 标签审计
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 5/12: 搜索热度 + 标签审计"
echo "└──────────────────────────────────────────────┘"

ANALYTICS_RESULT=$(python3 /var/minis/shared/obsidian-analytics.py --stats 2>/dev/null || echo "")
echo "$ANALYTICS_RESULT" | head -12

TAG_AUDIT=$(python3 /var/minis/shared/obsidian-tag.py --audit 2>/dev/null | head -5 || echo "")
echo "$TAG_AUDIT"
echo ""

# =============================================================================
# Step 6: 生成训练日志 → Obsidian
# =============================================================================
echo "┌──────────────────────────────────────────────┐"
echo "│ Step 6/12: 写入训练日志 → Obsidian"
echo "└──────────────────────────────────────────────┘"

# 提取关键数据用于日志
NODES=$(echo "$GRAPH_STATS" | grep "总节点" | awk -F': ' '{print $2}' || echo "?")
LINKS=$(echo "$GRAPH_STATS" | grep "总链接" | awk -F': ' '{print $2}' || echo "?")
ISOLATED=$(echo "$GRAPH_STATS" | grep "孤立笔记" | awk -F': ' '{print $2}' || echo "?")
CONNECTED=$(echo "$GRAPH_STATS" | grep "已连接" | awk -F': ' '{print $2}' || echo "?")
HITRATE=$(echo "$ANALYTICS_RESULT" | grep "命中率" | awk -F': ' '{print $2}' || echo "?")
CLICKRATE=$(echo "$ANALYTICS_RESULT" | grep "点击率" | awk -F': ' '{print $2}' || echo "?")

TRAINING_ENTRY=$(cat << EOF

## 🧠 训练步 — ${TIMESTAMP}

| 维度 | 数值 |
|------|------|
| 笔记总数 | ${NOTE_COUNT} |
| 图谱节点 | ${NODES} |
| 图谱链接 | ${LINKS} |
| 孤立笔记 | ${ISOLATED} |
| 已连接笔记 | ${CONNECTED} |
| 搜索命中率 | ${HITRATE}% |
| 点击率 | ${CLICKRATE}% |

### 交叉验证摘要
${CROSSQ_RESULT}

### 认知盲区摘要
${BLINDSPOT_RESULT}
EOF
)

# 追加到今天的训练日志
echo "$TRAINING_ENTRY" >> "$SESSION_LOG"
echo "  ✅ 训练日志已写入: ${SESSION_LOG}"

# 更新状态
echo "$TIMESTAMP" > "$LAST_RUN"

# 生成状态 JSON
python3 -c "
import json
state = {
    'last_run': '${TIMESTAMP}',
    'notes': ${NOTE_COUNT},
    'nodes': '${NODES}',
    'links': '${LINKS}',
    'isolated': '${ISOLATED}',
    'connected': '${CONNECTED}',
    'hit_rate': '${HITRATE}',
    'click_rate': '${CLICKRATE}',
}
with open('${STATS_FILE}', 'w') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
" 2>/dev/null || true

echo ""
echo "══════════════════════════════════════════════"
echo "  🔄 Step 7/12: 自动学习管道"
echo "══════════════════════════════════════════════"

AUTO_LEARN_RESULT=$(python3 /var/minis/shared/obsidian-auto-learn.py --mode manual 2>/dev/null | grep -E "批准|跳过|等级|处理|摩擦度" | head -12 || echo "  ℹ️ 自动学习管道无新内容")
echo "$AUTO_LEARN_RESULT"
echo "  💡 想自动批准: --mode semi 或 --mode auto"

echo ""
echo "══════════════════════════════════════════════"
echo "  📊 Step 8/12: 健康仪表盘"
echo "══════════════════════════════════════════════"

python3 /var/minis/shared/second-brain-dashboard.py 2>/dev/null

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅ 训练步完成"
echo "══════════════════════════════════════════════"
echo ""
echo "📊 训练摘要:"
echo "  笔记: ${NOTE_COUNT} | 图谱: ${NODES}节点/${LINKS}链接"
echo "  孤立: ${ISOLATED} | 搜索命中率: ${HITRATE}%"
echo "  日志: ${SESSION_LOG}"

# =============================================================================
# Step 9/12: PEV 反馈层 — 确定性传感器校验
# =============================================================================
echo ""
echo "══════════════════════════════════════════════"
echo "  🔬 Step 9/12: PEV 反馈层校验 (确定性传感器)"
echo "══════════════════════════════════════════════"

FEEDBACK_RESULT=$(python3 /var/minis/shared/second-brain-feedback.py --regression --json 2>/dev/null || echo "[]")
SENSOR_PASS=$(echo "$FEEDBACK_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(sum(1 for x in r if x.get('passed')))" 2>/dev/null || echo "?")
SENSOR_FAIL=$(echo "$FEEDBACK_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(sum(1 for x in r if not x.get('passed')))" 2>/dev/null || echo "?")
SENSOR_TOTAL=$(echo "$FEEDBACK_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(len(r))" 2>/dev/null || echo "?")

echo "  📡 传感器: ${SENSOR_PASS}/${SENSOR_TOTAL} 通过"
if [ "$SENSOR_FAIL" != "0" ] && [ "$SENSOR_FAIL" != "?" ]; then
    echo "  🔴 ${SENSOR_FAIL} 个传感器失败 — 详情:"
    echo "$FEEDBACK_RESULT" | python3 -c "
import sys,json
r=json.load(sys.stdin)
for x in r:
    if not x.get('passed'):
        print(f'    ❌ {x[\"sensor\"]}: {x[\"detail\"][:80]}')
    else:
        print(f'    ✅ {x[\"sensor\"]}: {x[\"detail\"][:80]}')
" 2>/dev/null || true
fi

# 把反馈层结果写进训练日志
FEEDBACK_LOG=$(python3 -c "
import json
r=json.loads('''$FEEDBACK_RESULT''')
passed=sum(1 for x in r if x.get('passed'))
failed=sum(1 for x in r if not x.get('passed'))
print(f'| 传感器校验 | ✅ {passed} / ❌ {failed} |')
for x in r:
    if not x.get('passed'):
        print(f'| {x[\"sensor\"]} | ❌ {x[\"detail\"][:40]} |')
" 2>/dev/null)
echo "$FEEDBACK_LOG" >> "$SESSION_LOG"
# =============================================================================
# Step 10/12: 错误模式学习 — 扫描日志提取错误模式
# =============================================================================
echo ""
echo "══════════════════════════════════════════════"
echo "  🐛 Step 10/12: 错误模式学习"
echo "══════════════════════════════════════════════"

ERROR_LEARN_RESULT=$(python3 /var/minis/shared/obsidian-error-learn.py --scan 2>/dev/null || echo "")
ERROR_STATS=$(echo "$ERROR_LEARN_RESULT" | grep -E "总错误|自动修复|人工介入|扫描次数" | tail -4 || echo "")
echo "$ERROR_STATS"

# 提取数字写入日志
ERR_TOTAL=$(echo "$ERROR_LEARN_RESULT" | grep "总错误" | grep -oE '[0-9]+' | head -1 || echo "?")
ERR_AUTO=$(echo "$ERROR_LEARN_RESULT" | grep "可自动修复" | grep -oE '[0-9]+' | head -1 || echo "?")
ERR_MANUAL=$(echo "$ERROR_LEARN_RESULT" | grep "人工介入" | grep -oE '[0-9]+' | head -1 || echo "?")
echo "| 错误模式 | 🐛 总 ${ERR_TOTAL} / 自动修 ${ERR_AUTO} / 人工 ${ERR_MANUAL} |" >> "$SESSION_LOG"
echo ""

# =============================================================================
# Step 11/12: Skill 生命周期 — 检测弃用候选
# =============================================================================
echo "══════════════════════════════════════════════"
echo "  🔄 Step 11/12: Skill 生命周期管理"
echo "══════════════════════════════════════════════"

SKILL_OVERVIEW=$(python3 /var/minis/shared/obsidian-skill-lifecycle.py --overview 2>/dev/null || echo "")
SKILL_STATS=$(echo "$SKILL_OVERVIEW" | grep -E "总计|Draft|Approved|Deprecated" | head -6 || echo "")
echo "$SKILL_STATS"

# 检测弃用候选（仅输出摘要）
DEPRECAT_TOTAL=$(python3 /var/minis/shared/obsidian-skill-lifecycle.py --detect-deprecated --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('candidates',[])))" 2>/dev/null || echo "?")
if [ "$DEPRECAT_TOTAL" != "0" ] && [ "$DEPRECAT_TOTAL" != "?" ]; then
    echo "  ⚠️  检测到 ${DEPRECAT_TOTAL} 张弃用候选卡片（详见 --detect-deprecated）"
fi
echo "| Skill 生命周期 | ✅ 已批准 / 🗑️ 弃用候选 ${DEPRECAT_TOTAL} |" >> "$SESSION_LOG"
echo ""
# =============================================================================
# Step 12/12: Session 自动记忆提交 — OpenViking 模式
# =============================================================================
echo "══════════════════════════════════════════════"
echo "  💾 Step 12/12: Session 自动记忆提交"
echo "══════════════════════════════════════════════"

SESSION_COMMIT_RESULT=$(python3 /var/minis/shared/session-commit.py --days 1 2>/dev/null || echo "")
echo "$SESSION_COMMIT_RESULT"
SESSION_STATS=$(echo "$SESSION_COMMIT_RESULT" | grep -E "提取|提交|扫描" || echo "")
echo "$SESSION_STATS" >> "$SESSION_LOG"
echo ""

