#!/bin/sh
# Version: 0.1.0
# minis-dashboard.sh — Minis 系统健康检查面板
# 用法: bash minis-dashboard.sh
# 输出：记忆/工作区/Skill/共享 状态一览

echo "=============================================="
echo "  Minis 系统健康检查 — $(date '+%Y-%m-%d %H:%M')"
echo "=============================================="
echo ""

# --- 记忆系统 ---
echo "📝 记忆系统"
echo "  ├─ L1 (daily logs):  $(find /var/minis/memory/ -maxdepth 1 -name '2026-*.md' 2>/dev/null | wc -l)"
echo "  ├─ L2 (周报):         $(if [ -f /var/minis/memory/L2-weekly-summaries.md ]; then echo '✅ 已生成'; else echo '❌ 缺失'; fi)"
echo "  ├─ L3 (知识图谱):     $(if [ -f /var/minis/memory/L3-knowledge-graph.md ]; then echo '✅ 已生成'; else echo '❌ 缺失'; fi)"
echo "  ├─ GLOBAL:            $(if [ -f /var/minis/memory/GLOBAL.md ]; then echo '✅'; else echo '❌'; fi)"
echo "  └─ SOUL:              $(if [ -f /var/minis/memory/SOUL.md ]; then echo '✅'; else echo '❌'; fi)"

# L2 新鲜度
if [ -f /var/minis/memory/L2-weekly-summaries.md ]; then
    L2_DATE=$(stat -c %y /var/minis/memory/L2-weekly-summaries.md 2>/dev/null | cut -d. -f1 | cut -d' ' -f1)
    echo "  L2 最后更新: $L2_DATE"
fi

# L3 新鲜度
if [ -f /var/minis/memory/L3-knowledge-graph.md ]; then
    L3_DATE=$(stat -c %y /var/minis/memory/L3-knowledge-graph.md 2>/dev/null | cut -d. -f1 | cut -d' ' -f1)
    echo "  L3 最后更新: $L3_DATE"
fi
echo ""

# --- 工作区 ---
echo "📁 工作区 (workspace)"
if [ -d /var/minis/workspace ] && [ "$(ls -A /var/minis/workspace/ 2>/dev/null)" ]; then
    WS_COUNT=$(find /var/minis/workspace/ -type f 2>/dev/null | wc -l)
    echo "  状态: ✅ 有内容 ($WS_COUNT 个文件)"
else
    echo "  状态: ⚠️  工作区为空（可能已丢失）"
fi
echo ""

# --- 共享区 ---
echo "📦 共享区 (shared)"
SHARED_COUNT=$(find /var/minis/shared/ -type f 2>/dev/null | wc -l)
SHARED_SIZE=$(du -sh /var/minis/shared/ 2>/dev/null | cut -f1)
echo "  文件数: $SHARED_COUNT | 大小: $SHARED_SIZE"
echo "  内容: $(ls /var/minis/shared/ 2>/dev/null | tr '\n' ' ')"
echo ""

# --- Skill 系统 ---
echo "🧩 Skill 系统"
SKILL_COUNT=$(find /var/minis/skills/ -name "SKILL.md" 2>/dev/null | wc -l)
echo "  已安装 Skill: $SKILL_COUNT"
for skill_dir in /var/minis/skills/*/; do
    name=$(basename "$skill_dir")
    if [ -f "$skill_dir/SKILL.md" ]; then
        lines=$(wc -l < "$skill_dir/SKILL.md")
        echo "    ✅ $name ($lines 行)"
    else
        echo "    ❌ $name (缺少 SKILL.md)"
    fi
done
echo ""

# --- 集成 ---
echo "🔗 集成"
echo "  ├─ Obsidian vault:   $(if [ -d /var/minis/mounts/loong ]; then echo '✅ 已挂载'; else echo '❌ 未挂载'; fi)"
echo "  ├─ 浏览器自动化:     $(if command -v minis-browser-use >/dev/null 2>&1; then echo '✅'; else echo '❌'; fi)"
echo "  ├─ 多模型调用:       $(if command -v minis-model-use >/dev/null 2>&1; then echo '✅'; else echo '❌'; fi)"
echo "  └─ GitHub MCP:       $(minis-mcp-cli tools github >/dev/null 2>&1 && echo '✅' || echo '❌')"
echo ""

# --- 系统快照 ---
echo "💻 环境"
echo "  OS: $(uname -a | awk '{print $1, $3, $4}')"
echo "  Python: $(python3 --version 2>&1)"
echo "  Shell: $SHELL"
echo ""
echo "=============================================="
echo "  检查完毕"
echo "=============================================="