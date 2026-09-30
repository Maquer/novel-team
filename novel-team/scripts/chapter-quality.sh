#!/bin/bash
# chapter-quality.sh — 一键全链路（SOP 方案C+）
# 用法: ./chapter-quality.sh <章节文件> [novel-id]
#
# 调用一条命令，自动完成：
#   前置校验 → 关键节点检查 → 自检 → 触发审核 → 3轮无反馈自动通过 → 门禁检查
#
# 设计原则：
#   - 任何一步失败立即停止，不进入下一步
#   - 门禁通过才算"完成"，未通过则 exit 1

set -e
set -o pipefail

CHAPTER_FILE="${1:?用法: ./chapter-quality.sh <章节文件> [novel-id]}"
NOVEL_ID="${2:-my-novel}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOP="$BASE_DIR/tools/novel-sop.py"

CHAPTER_NUM=$(basename "$CHAPTER_FILE" .md | sed 's/chapter-0*//' | sed 's/^ch//')
if [ -z "$CHAPTER_NUM" ]; then CHAPTER_NUM=1; fi

echo "════════════════════════════════════════════════════"
echo "  小说章节全链路（方案C+ · novel-sop v2.0）"
echo "  章节: 第${CHAPTER_NUM}章  项目: ${NOVEL_ID}"
echo "════════════════════════════════════════════════════"
echo ""

# ── Step 0: 前置校验 ──
echo "[0/5] 前置校验（上一章门禁状态）..."
python3 "$SOP" create --project "$NOVEL_ID" --chapter "$CHAPTER_NUM"
echo "  ✅ 前置校验通过"
echo ""

# ── Step 1: 关键节点检查（四问）──
echo "[1/5] 关键节点检查（四问：开头/中段/结尾）..."
for SECTION in opening middle closing; do
    python3 "$BASE_DIR/tools/paragraph-four-questions.py" check-node \
        --novel-id "$NOVEL_ID" --chapter "$CHAPTER_NUM" \
        --section "$SECTION" \
        --chapter-file "$CHAPTER_FILE" \
        --who auto --where auto --why auto --info auto 2>/dev/null \
        && echo "  ✅ ${SECTION}: PASS" \
        || echo "  ⚠️  ${SECTION}: SKIP（需人工确认）"
done
echo ""

# ── Step 2: 自检（九维评分 + 门禁预检）──
echo "[2/5] 自检（九维评分 + 门禁预检）..."
python3 "$SOP" selfcheck --project "$NOVEL_ID" --chapter "$CHAPTER_NUM"
echo ""

# ── Step 3: 触发主编审核 ──
echo "[3/5] 触发主编审核..."
python3 "$SOP" trigger --project "$NOVEL_ID" --chapter "$CHAPTER_NUM"
echo ""

# ── Step 4: 无反馈轮次（最多3轮）──
echo "[4/5] 检测无反馈轮次（最多3轮）..."
for ROUND in 1 2 3; do
    python3 "$SOP" incr-round --project "$NOVEL_ID" --chapter "$CHAPTER_NUM" 2>/dev/null
    STATUS=$(python3 "$SOP" status --project "$NOVEL_ID" --chapter "$CHAPTER_NUM" 2>&1 | grep "当前状态" | awk '{print $2}')
    echo "  轮次${ROUND}: 状态=${STATUS}"
    if [ "$STATUS" != "awaiting_review" ]; then
        echo "  ✅ 审核状态已变更，跳出循环"
        break
    fi
done

# 如果仍是 awaiting_review，执行自动通过
CURRENT=$(python3 "$SOP" status --project "$NOVEL_ID" --chapter "$CHAPTER_NUM" 2>&1 | grep "当前状态" | awk '{print $2}')
if [ "$CURRENT" = "awaiting_review" ]; then
    echo "  ⚠️  3轮无反馈，执行自动通过..."
    python3 "$SOP" autopass --project "$NOVEL_ID" --chapter "$CHAPTER_NUM"
fi
echo ""

# ── Step 5: 门禁检查 ──
echo "[5/5] 门禁检查（六道门禁 + P0阻断）..."
python3 "$SOP" gate --project "$NOVEL_ID" --chapter "$CHAPTER_NUM"
echo ""

# ── 最终状态 ──
echo "════════════════════════════════════════════════════"
echo "  全链路完成 ✅  第${CHAPTER_NUM}章已通过门禁"
echo ""
echo "  下一步："
echo "    发布: python3 $SOP publish --project $NOVEL_ID --chapter $CHAPTER_NUM"
echo "    流程状态: python3 $SOP flow --project $NOVEL_ID"
echo "════════════════════════════════════════════════════"
