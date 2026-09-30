#!/bin/bash
# Version: 1.0.0
# 批量初始化 skill 版本管理：.version（取 skill.meta.json 现有版本）+ CHANGELOG.md（可从 review_history 播种）
set -e

count=0
for d in /var/minis/skills/*/; do
  name=$(basename "$d")
  # 已有 .version 跳过
  if [ -f "$d/.version" ]; then echo "跳过（已初始化）: $name"; continue; fi

  # 取 skill.meta.json 的 version 作为初始版本
  v=""
  if [ -f "$d/skill.meta.json" ]; then
    v=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$d/skill.meta.json" | head -1 | sed 's/.*"\([0-9][^"]*\)"/\1/' || true)
  fi
  # frontmatter fallback
  if [ -z "$v" ] && [ -f "$d/SKILL.md" ]; then
    v=$(grep -m1 '^version:' "$d/SKILL.md" | sed 's/version:[[:space:]]*//' | tr -d '"' | tr -d "'" || true)
  fi
  [ -z "$v" ] && v="0.1.0"

  echo -n "$v" > "$d/.version"

  # CHANGELOG 播种
  if [ ! -f "$d/CHANGELOG.md" ]; then
    {
      echo "# Changelog"
      echo ""
      echo "本 skill 所有版本变更记录。格式见 /var/minis/shared/VERSIONING.md。"
      echo ""
      # 从 skill.meta.json review_history 播种历史
      if [ -f "$d/skill.meta.json" ] && grep -q 'review_history' "$d/skill.meta.json"; then
        python3 - "$d/skill.meta.json" <<'PY'
import json, sys
try:
    meta = json.load(open(sys.argv[1]))
    for r in reversed(meta.get("review_history", [])):
        print(f"## [{r.get('version','?')}] - {r.get('date','?')}")
        print()
        print(f"- {r.get('change','')}")
        print()
except Exception as e:
    print(f"- 历史播种失败: {e}")
    print()
PY
      else
        echo "## [$v] - $(date +%Y-%m-%d)"
        echo ""
        echo "### Added"
        echo "- 初始版本纳入版本管理"
        echo ""
      fi
    } > "$d/CHANGELOG.md"
  fi
  echo "✅ init: $name → v$v"
  count=$((count+1))
done
echo "---"
echo "共初始化 $count 个 skill"
