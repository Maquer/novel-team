#!/bin/bash
# Version: 0.1.0
# =============================================================================
# Obsidian 双向同步管道（09-24 重写版：原 08-21 脚本误删后按原 spec 重建）
#
# 用法:
#   bash obsidian-sync.sh                          # 默认：minis → obsidian (daily log)
#   bash obsidian-sync.sh --direction minis-to-obsidian
#   bash obsidian-sync.sh --direction obsidian-to-minis
#   bash obsidian-sync.sh --date 2026-08-21
#   bash obsidian-sync.sh --all                    # 全量同步（daily log + inbox 检查）
#   bash obsidian-sync.sh --status                 # 查看同步状态
#
# 行为:
#   minis-to-obsidian   daily log → 04-Archives/Minis-Memory/（逐字拷贝）
#   obsidian-to-minis   反向检查：未同步回 Obsidian 侧的 daily log + 00-Inbox 新文件清单
#   冲突处理：目标文件已存在且与源不同 → 内容追加（带同步分隔头），不覆盖
# =============================================================================

set -euo pipefail

OBSIDIAN_ROOT="/var/minis/mounts/loong"
MINIS_MEMORY="/var/minis/memory"
OBSIDIAN_ARCHIVE="${OBSIDIAN_ROOT}/04-Archives/Minis-Memory"
OBSIDIAN_INBOX="${OBSIDIAN_ROOT}/00-Inbox"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --direction|-d) DIRECTION="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --all) ALL=1; shift ;;
        --status) STATUS=1; shift ;;
        *) shift ;;
    esac
done

: "${DATE:=$(date +%F)}"
DAILY_LOG="${MINIS_MEMORY}/${DATE}.md"

: "${DIRECTION:=minis-to-obsidian}"
: "${ALL:=0}"
: "${STATUS:=0}"

# =============================================================================
# 状态检查
# =============================================================================
if [[ "${STATUS}" == "1" ]]; then
    echo "=== Obsidian 同步状态 ==="
    echo ""
    echo "Obsidian 根目录: ${OBSIDIAN_ROOT}"
    if [[ -d "${OBSIDIAN_ROOT}" ]]; then
        echo "  状态: ✅ 已挂载"
    else
        echo "  状态: ❌ 未挂载"
        exit 1
    fi
    echo ""
    echo "Obsidian 目录结构:"
    find "${OBSIDIAN_ROOT}" -maxdepth 1 -type d | sort | while read -r d; do
        name=$(basename "$d")
        count=$(find "$d" -name "*.md" 2>/dev/null | wc -l)
        echo "  📂 ${name}/  (${count} files)"
    done
    echo ""
    echo "Minis 记忆目录: ${MINIS_MEMORY}"
    log_count=$(find "${MINIS_MEMORY}" -name "20*.md" 2>/dev/null | wc -l)
    echo "  日志文件数: ${log_count}"
    echo ""
    if [[ -d "${OBSIDIAN_ARCHIVE}" ]]; then
        synced_count=$(find "${OBSIDIAN_ARCHIVE}" -name "20*.md" 2>/dev/null | wc -l)
        echo "已同步到 Obsidian: ${OBSIDIAN_ARCHIVE} (${synced_count} files)"
        echo ""
        echo "未同步的 daily log:"
        unsynced=0
        for f in "${MINIS_MEMORY}"/20*.md; do
            [[ -e "$f" ]] || continue
            base=$(basename "$f")
            if [[ ! -f "${OBSIDIAN_ARCHIVE}/${base}" ]]; then
                echo "  - ${base}"
                unsynced=1
            fi
        done
        [[ "${unsynced}" == "1" ]] || echo "  (无)"
    else
        echo "⚠️  归档目录不存在: ${OBSIDIAN_ARCHIVE}"
    fi
    exit 0
fi

# =============================================================================
# minis → obsidian
# =============================================================================
minis_to_obsidian() {
    local date_arg="$1"
    local src="${MINIS_MEMORY}/${date_arg}.md"
    local dst_dir="${OBSIDIAN_ARCHIVE}"
    local dst="${dst_dir}/${date_arg}.md"

    if [[ ! -d "${OBSIDIAN_ROOT}" ]]; then
        echo "❌ Obsidian 未挂载: ${OBSIDIAN_ROOT}"
        exit 1
    fi
    if [[ ! -f "${src}" ]]; then
        echo "❌ 日志不存在: ${src}"
        exit 1
    fi

    mkdir -p "${dst_dir}"

    if [[ -f "${dst}" ]]; then
        if cmp -s "${src}" "${dst}"; then
            echo "✅ ${date_arg}.md 已同步（无变化）"
            return 0
        fi
        # 冲突处理：追加而非覆盖
        {
            echo ""
            echo "<!-- ===== minis 同步追加 $(date '+%Y-%m-%d %H:%M:%S') ===== -->"
            cat "${src}"
        } >> "${dst}"
        echo "➕ ${date_arg}.md 已追加到 ${dst}（原文件保留）"
    else
        cp "${src}" "${dst}"
        echo "✅ ${date_arg}.md → ${dst}"
    fi
}

# =============================================================================
# obsidian → minis（反向：报告 + inbox 检查，不回写 daily log）
# =============================================================================
obsidian_to_minis() {
    if [[ ! -d "${OBSIDIAN_ROOT}" ]]; then
        echo "❌ Obsidian 未挂载: ${OBSIDIAN_ROOT}"
        exit 1
    fi

    echo "=== obsidian → minis 检查（${DATE}）==="
    echo ""
    echo "Minis daily log: ${DAILY_LOG}"
    [[ -f "${DAILY_LOG}" ]] && echo "  状态: ✅ 存在" || echo "  状态: ⚠️ 不存在"
    echo ""
    echo "00-Inbox 新文件（待处理）:"
    if [[ -d "${OBSIDIAN_INBOX}" ]]; then
        inbox_items=$(find "${OBSIDIAN_INBOX}" -name "*.md" 2>/dev/null | head -20)
        if [[ -n "${inbox_items}" ]]; then
            echo "${inbox_items}" | while read -r f; do
                echo "  - $(basename "$f")"
            done
        else
            echo "  (空)"
        fi
    else
        echo "  ⚠️ inbox 目录不存在: ${OBSIDIAN_INBOX}"
    fi
    echo ""
    echo "提示: daily log 归属 Minis，本方向只报告不回写；如需归档请用 minis-to-obsidian"
}

# =============================================================================
# 主流程
# =============================================================================
case "${DIRECTION}" in
    minis-to-obsidian)
        if [[ "${ALL}" == "1" ]]; then
            for f in "${MINIS_MEMORY}"/20*.md; do
                [[ -e "$f" ]] || continue
                minis_to_obsidian "$(basename "$f" .md)"
            done
        else
            minis_to_obsidian "${DATE}"
        fi
        ;;
    obsidian-to-minis)
        obsidian_to_minis
        ;;
    *)
        echo "❌ 未知方向: ${DIRECTION}（可选 minis-to-obsidian / obsidian-to-minis）"
        exit 1
        ;;
esac
