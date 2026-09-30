#!/bin/bash
# novel-team-start.sh — 小说团队工作流启动脚本
# 用途：一键启动世界包构建或大纲创作流程

set -e

NOVEL_TEAM_ROOT="/var/minis/shared/novel-team"
TOOLS_DIR="$NOVEL_TEAM_ROOT/tools"
PROJECT_ID="${2:-helper-creator}"

usage() {
    echo "用法: $0 <world|outline|full> [project-id]"
    echo ""
    echo "子命令:"
    echo "  world   - 启动世界包核心逻辑追问（Phase 1→3）"
    echo "  outline - 启动大纲结构追问（Phase 4a）"
    echo "  full    - 完整流程：世界包追问 → 大纲追问 → 细纲生成"
    echo ""
    echo "示例:"
    echo "  $0 world helper-creator"
    echo "  $0 outline my-novel"
    echo "  $0 full"
    exit 1
}

check_project() {
    local pid="$1"
    if [ ! -d "$NOVEL_TEAM_ROOT/novel-team/projects/$pid" ] && [ ! -d "$NOVEL_TEAM_ROOT/projects/$pid" ]; then
        echo "❌ 项目 '$pid' 不存在"
        echo "   可用项目:"
        ls -1 "$NOVEL_TEAM_ROOT/novel-team/projects/" 2>/dev/null || ls -1 "$NOVEL_TEAM_ROOT/projects/" 2>/dev/null || echo "   (无)"
        exit 1
    fi
}

run_world() {
    local pid="$1"
    check_project "$pid"
    echo "============================================================"
    echo "🍳 世界包核心逻辑追问启动"
    echo "============================================================"
    echo ""
    echo "项目: $pid"
    echo ""
    echo "即将启动 grill-me 追问模式。"
    echo "追问领域：Q01~Q05（力量体系/社会结构/核心矛盾/主角特殊性/第一卷任务）"
    echo ""
    echo "步骤1: 在对话中说 'grill me' 或 '先追问我'"
    echo "步骤2: 回答5个领域的追问问题"
    echo "步骤3: 追问完成后，运行以下命令落地："
    echo ""
    echo "  python3 $TOOLS_DIR/grill-world-bridge.py build --project $pid"
    echo ""
    echo "💡 提示: 追问时回答要具体，避免'差不多''大概'等模糊词"
}

run_outline() {
    local pid="$1"
    check_project "$pid"
    echo "============================================================"
    echo "📝 大纲结构追问启动"
    echo "============================================================"
    echo ""
    echo "项目: $pid"
    echo ""
    echo "即将启动 grill-me 大纲追问模式。"
    echo "追问领域：OQ01~OQ05（五卷结构/章节数分配/爽点节奏/关键转折/伏笔分布）"
    echo ""
    echo "步骤1: 在对话中说 'grill me' 或 '先追问我'"
    echo "步骤2: 回答5个领域的追问问题"
    echo "步骤3: 追问完成后，运行以下命令落地："
    echo ""
    echo "  python3 $TOOLS_DIR/outline-grill-bridge.py build --project $pid"
    echo ""
    echo "💡 提示: 五卷框架是起点不是终点，创作中可动态调整"
}

run_full() {
    local pid="$1"
    check_project "$pid"
    echo "============================================================"
    echo "🚀 小说团队全流程启动"
    echo "============================================================"
    echo ""
    echo "项目: $pid"
    echo ""
    echo "流程:"
    echo "  Phase 1: 世界包核心逻辑追问（grill-me）"
    echo "  Phase 2: 交叉验证（第二模型）"
    echo "  Phase 3: 逻辑落地（core-logic.md + iron-laws.md）"
    echo "  Phase 4a: 大纲结构追问（grill-me）"
    echo "  Phase 4b: 卷细纲落地（vol-001~005-brief.yaml）"
    echo "  Phase 4c: 单章细纲生成（ch-001~XXX-brief.md）"
    echo "  Phase 5: 正文创作（SOP C+）"
    echo "  Phase 6: 世界同步（world-sync.py）"
    echo "  Phase 7: 动态调整（outline-dynamic-adjust.py）"
    echo ""
    echo "开始执行 Phase 1..."
    echo ""
    run_world "$pid"
}

# 主逻辑
case "${1:-}" in
    world)
        run_world "$PROJECT_ID"
        ;;
    outline)
        run_outline "$PROJECT_ID"
        ;;
    full)
        run_full "$PROJECT_ID"
        ;;
    status)
        echo "============================================================"
        echo "📊 小说团队状态检查"
        echo "============================================================"
        echo ""
        python3 "$TOOLS_DIR/world-logic-builder.py" status --project "$PROJECT_ID"
        echo ""
        python3 "$TOOLS_DIR/outline-grill-bridge.py" status --project "$PROJECT_ID"
        echo ""
        python3 "$TOOLS_DIR/outline-dynamic-adjust.py" status --project "$PROJECT_ID"
        ;;
    *)
        usage
        ;;
esac

run_gate() {
    local pid="$1"
    check_project "$pid"
    echo "============================================================"
    echo "🍳 质量门禁阈值决策追问启动"
    echo "============================================================"
    echo ""
    echo "项目: $pid"
    echo ""
    echo "即将启动 grill-me 阈值决策追问模式。"
    echo "追问领域：GQ01~GQ05（字数下限/AI味阻断线/AI味预警线/超长警告线/其他插件阈值）"
    echo ""
    echo "步骤1: 在对话中说 'grill me' 或 '先追问我'"
    echo "步骤2: 回答5个领域的追问问题"
    echo "步骤3: 追问完成后，运行以下命令落地："
    echo ""
    echo "  python3 $TOOLS_DIR/grill-gate-bridge.py build --project $pid"
    echo ""
    echo "💡 提示: 追问时提供具体数据（如当前章节字数分布），便于决策"
}

case "${1:-}" in
    ...
    gate)
        run_gate "$PROJECT_ID"
        ;;
    ...
esac
