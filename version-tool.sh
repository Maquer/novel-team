#!/bin/bash
# Version: 1.0.0
# 版本管理工具 — 规范见 /var/minis/shared/VERSIONING.md
# 用法:
#   version-tool.sh init <目录> [初始版本默认 0.1.0]
#   version-tool.sh bump <目录> patch|minor|major   # 升版本+插入 CHANGELOG 模板
#   version-tool.sh show <目录>
#   version-tool.sh audit                            # 全量审计

set -e
TOOL="版本管理"

# ---------- helpers ----------
get_version_file() { echo "$1/.version"; }

read_version() {
  local d="$1"
  if [ -f "$(get_version_file "$d")" ]; then cat "$(get_version_file "$d")"
  elif [ -f "$d/skill.meta.json" ]; then grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$d/skill.meta.json" | head -1 | sed 's/.*"\([0-9][^"]*\)"/\1/'
  else echo ""; fi
}

bump_calc() {
  local v="$1" level="$2"
  local major=$(echo "$v" | cut -d. -f1); local minor=$(echo "$v" | cut -d. -f2); local patch=$(echo "$v" | cut -d. -f3)
  major=${major:-0}; minor=${minor:-0}; patch=${patch:-0}
  case "$level" in
    major) echo "$((major+1)).0.0" ;;
    minor) echo "$major.$((minor+1)).0" ;;
    patch) echo "$major.$minor.$((patch+1))" ;;
    *) echo "未知级别: $level（须 patch|minor|major）" >&2; exit 1 ;;
  esac
}

today() { date +%Y-%m-%d; }

# ---------- init ----------
do_init() {
  local d="$1" v="${2:-0.1.0}"
  [ -d "$d" ] || { echo "目录不存在: $d" >&2; exit 1; }
  if [ -f "$(get_version_file "$d")" ]; then echo "已初始化: 当前 $(read_version "$d")"; return; fi
  echo -n "$v" > "$(get_version_file "$d")"
  [ -f "$d/CHANGELOG.md" ] || cat > "$d/CHANGELOG.md" <<EOF
# Changelog

本项目所有版本变更记录。格式见 /var/minis/shared/VERSIONING.md。

## [$v] - $(today)

### Added
- 初始版本
EOF
  echo "✅ 初始化完成: $d → v$v（.version + CHANGELOG.md）"
}

# ---------- bump ----------
do_bump() {
  local d="$1" level="$2"
  [ -d "$d" ] || { echo "目录不存在: $d" >&2; exit 1; }
  local old; old=$(read_version "$d")
  [ -n "$old" ] || { echo "未初始化，先执行: init" >&2; exit 1; }
  local new; new=$(bump_calc "$old" "$level")
  echo -n "$new" > "$(get_version_file "$d")"

  # 同步 skill.meta.json（若存在）
  if [ -f "$d/skill.meta.json" ]; then
    sed -i "s/\"version\":[[:space:]]*\"[^\"]*\"/\"version\": \"$new\"/" "$d/skill.meta.json"
  fi

  # CHANGELOG 插入模板（在第一个 ## [ 之前）
  local tmp; tmp=$(mktemp)
  {
    echo "## [$new] - $(today)"
    echo ""
    echo "### Added"
    echo "- TODO: 描述本次新增"
    echo ""
    echo "### Changed"
    echo "- TODO: 描述本次修改"
    echo ""
    echo "### Fixed"
    echo "- TODO: 描述本次修复"
    echo ""
  } > "$tmp"
  if [ -f "$d/CHANGELOG.md" ]; then
    if grep -q '^## \[' "$d/CHANGELOG.md"; then
      awk -v tplfile="$tmp" 'BEGIN{while((getline l < tplfile)>0) tpl=tpl l"\n"; close(tplfile)} /^## \[/{if(!done){printf "%s", tpl; done=1}} {print}' "$d/CHANGELOG.md" > "$d/.chlog.tmp" && mv "$d/.chlog.tmp" "$d/CHANGELOG.md"
    else
      cat "$tmp" >> "$d/CHANGELOG.md"
    fi
  else
    { echo "# Changelog"; echo ""; cat "$tmp"; } > "$d/CHANGELOG.md"
  fi
  rm -f "$tmp"
  echo "✅ bump: v$old → v$new  ($d)"
  echo "   提醒：补全 CHANGELOG 的 TODO，然后 git commit -a -m \"v$new: 描述\" && git tag -a v$new"
}

# ---------- show ----------
do_show() {
  local d="$1"
  local v; v=$(read_version "$d")
  [ -n "$v" ] || { echo "未初始化"; exit 1; }
  echo "$d → v$v"
}

# ---------- audit ----------
do_audit() {
  echo "=== 版本管理全量审计 ==="
  printf "%-40s %-12s %-8s %-6s %s\n" "对象" "版本" "CHANGELOG" "git" "状态"
  local issues=0
  audit_one() {
    local d="$1"
    local name; name=$(basename "$d")
    local v; v=$(read_version "$d")
    local ch="❌" gitst="—" st="✅"
    [ -f "$d/CHANGELOG.md" ] && ch="✅"
    if [ -d "$d/.git" ]; then
      gitst="✅"
      if ! git -C "$d" diff --quiet 2>/dev/null || ! git -C "$d" diff --cached --quiet 2>/dev/null; then gitst="dirty"; fi
    fi
    if [ -z "$v" ]; then st="❌缺版本"; issues=$((issues+1)); fi
    [ "$ch" = "❌" ] && { st="❌缺CHANGELOG"; issues=$((issues+1)); }
    [ "$gitst" = "—" ] && { st="⚠️ 无git"; issues=$((issues+1)); }
    printf "%-40s %-12s %-8s %-6s %s\n" "$name" "${v:-—}" "$ch" "$gitst" "$st"
  }
  for d in /var/minis/skills/*/; do audit_one "$d"; done
  echo "---"
  # shared 顶层的 py/sh 脚本
  local nocount=0
  for f in /var/minis/shared/*.py /var/minis/shared/*.sh; do
    [ -f "$f" ] || continue
    if ! head -5 "$f" | grep -qE '^# Version:|Version:'; then nocount=$((nocount+1)); fi
  done
  echo "shared/ 脚本: $(( $(ls /var/minis/shared/*.py /var/minis/shared/*.sh 2>/dev/null | wc -l) - nocount ))/$(( $(ls /var/minis/shared/*.py /var/minis/shared/*.sh 2>/dev/null | wc -l) )) 有 # Version: 头"
  echo "=== 问题对象数: $issues ==="
}

# ---------- main ----------
case "${1:-}" in
  init)   do_init "$2" "$3" ;;
  bump)   do_bump "$2" "$3" ;;
  show)   do_show "$2" ;;
  audit)  do_audit ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
