#!/bin/bash
# Version: 1.0.0
# 批量为 shared/ 顶层脚本补 # Version: 头（幂等，已有版本头的跳过）
# 用法: bash add-version-headers.sh [--apply]   默认 dry-run

set -e
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1

count=0; skipped=0
for f in /var/minis/shared/*.py /var/minis/shared/*.sh; do
  [ -f "$f" ] || continue
  if head -5 "$f" | grep -q 'Version:'; then
    skipped=$((skipped+1)); continue
  fi
  count=$((count+1))
  if [ "$APPLY" = "1" ]; then
    ext="${f##*.}"
    tmp=$(mktemp)
    if [ "$ext" = "py" ]; then
      # 插在 shebang 之后（若有），否则文件首
      if head -1 "$f" | grep -q '^#!'; then
        head -1 "$f" > "$tmp"; echo "# Version: 0.1.0" >> "$tmp"; tail -n +2 "$f" >> "$tmp"
      else
        { echo "# Version: 0.1.0"; cat "$f"; } > "$tmp"
      fi
    else
      if head -1 "$f" | grep -q '^#!'; then
        head -1 "$f" > "$tmp"; echo "# Version: 0.1.0" >> "$tmp"; tail -n +2 "$f" >> "$tmp"
      else
        { echo "# Version: 0.1.0"; cat "$f"; } > "$tmp"
      fi
    fi
    mv "$tmp" "$f"
    echo "已加: $(basename "$f")"
  else
    echo "[dry-run] 将加: $(basename "$f")"
  fi
done

echo "---"
if [ "$APPLY" = "1" ]; then echo "✅ 写入完成: $count 个补版本头, $skipped 个已有跳过"
else echo "dry-run: $count 个待补, $skipped 个已有。加 --apply 执行"; fi
