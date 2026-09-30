#!/bin/sh
# Version: 0.1.0
# minis-capture.sh — 一键闪念捕捉（QuickAdd 等价物）
# 用法:
#   minis-capture "今天发现 XX 工具很好用"
#   minis-capture -t 任务 "明天要归档 Firecrawl"
#   minis-capture -i "Obsidian 笔记名" "补充笔记内容"
# 所有捕捉自动追加到当日 daily log + Obsidian 00-Inbox/闪念/

DAILY_LOG="/var/minis/memory/$(date '+%Y-%m-%d').md"
INBOX_FLASH="/var/minis/mounts/loong/00-Inbox/闪念/$(date '+%Y-%m-%d').md"
OBSDIAN_MNT="/var/minis/mounts/loong"

usage() {
    echo "用法: minis-capture [选项] <内容>"
    echo ""
    echo "选项:"
    echo "  -t TYPE    类型：任务 | 想法 | 资源 | 备忘（默认：备忘）"
    echo "  -i NAME    关联 Obsidian 笔记名（自动创建到 Inbox）"
    echo "  -h        显示帮助"
    echo ""
    echo "示例:"
    echo "  minis-capture \"今天写了公众号文章\""
    echo "  minis-capture -t 任务 \"明天要归档 Firecrawl\""
    echo "  minis-capture -i \"AI工具/Firecrawl\" \"补充：支持 MCP\""
}

TYPE="备忘"
NOTES=""

while [ $# -gt 0 ]; do
    case "$1" in
        -t) TYPE="$2"; shift 2 ;;
        -i) NOTES="$2"; shift 2 ;;
        -h) usage; exit 0 ;;
        *) CONTENT="$CONTENT $1"; shift ;;
    esac
done

if [ -z "$CONTENT" ]; then
    usage
    exit 1
fi

TIMESTAMP=$(date '+%H:%M')
ICON="📝"
case "$TYPE" in
    "任务") ICON="✅" ;;
    "想法") ICON="💡" ;;
    "资源") ICON="🔖" ;;
    "备忘") ICON="📝" ;;
esac

ENTRY="<!-- 自动捕捉 -->\n## ${ICON} ${TYPE}（${TIMESTAMP}）\n\n${CONTENT}"

# 追加到 daily log
if [ -f "$DAILY_LOG" ]; then
    printf '\n%s\n' "$ENTRY" >> "$DAILY_LOG"
    echo "✅ 已写入 daily log: $(date '+%Y-%m-%d')"
else
    printf '%s\n' "$ENTRY" > "$DAILY_LOG"
    echo "✅ 已创建 daily log: $(date '+%Y-%m-%d')"
fi

# 写入 Obsidian Inbox 闪念
if [ -d "$OBSDIAN_MNT" ]; then
    mkdir -p "$(dirname "$INBOX_FLASH")"
    if [ -f "$INBOX_FLASH" ]; then
        printf '\n%s\n' "$ENTRY" >> "$INBOX_FLASH"
    else
        printf '%s\n' "$ENTRY" > "$INBOX_FLASH"
    fi
    echo "✅ 已同步 Obsidian Inbox: 闪念/$(date '+%Y-%m-%d').md"
fi

# 如果有关联笔记，同步到 Inbox
if [ -n "$NOTES" ]; then
    OBSIDIAN_FILE="$OBSDIAN_MNT/00-Inbox/${NOTES}.md"
    mkdir -p "$(dirname "$OBSIDIAN_FILE")"
    if [ -f "$OBSIDIAN_FILE" ]; then
        printf '\n> %s（${TIMESTAMP}）\n\n%s\n' "$ICON" "$CONTENT" >> "$OBSIDIAN_FILE"
        echo "✅ 已关联笔记: 00-Inbox/${NOTES}.md"
    else
        printf '# %s\n\n%s\n' "$NOTES" "$CONTENT" > "$OBSIDIAN_FILE"
        echo "✅ 已创建笔记: 00-Inbox/${NOTES}.md"
    fi
fi

echo ""
echo "📥 闪念已捕捉！(${TYPE})"