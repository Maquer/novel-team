#!/bin/bash
# Version: 0.1.0
set -u
# suji.sh v2 — 速记（分类 + 标签管理）
# 本地存储 + 同步 Obsidian 00-Inbox/notes/
#
# 用法:
#   suji add [-c 分类] [-t 标签]... "内容"
#       标签可多个: -t 重要 -t 待办; 不带 # 也行
#       示例: suji add -c 工作 -t 重要 -t 待办 "周五前交周报"
#   suji list [-c 分类] [-t 标签] [N]      列出最近 N 条（默认 20），可过滤
#   suji tags                               标签使用统计（按次数排序）
#   suji cats                               分类统计
#   suji tag <id> <标签> [标签2...]         给某条加标签
#   suji untag <id> <标签>                  去掉某条标签
#   suji cat <id> <分类>                    设置某条分类
#   suji move-cat <旧分类> <新分类>          分类改名/合并
#   suji search 关键词 [-c 分类]            搜索，可按分类过滤
#   suji del <id>                           删除
#   suji sync                               全量同步到 Obsidian
#   suji show <id>                          查看某条全文

LOCAL_DIR="/var/minis/shared/suji"
OBSIDIAN_INBOX="/var/minis/mounts/loong/00-Inbox/notes"

mkdir -p "$LOCAL_DIR"

get_id() { date +%Y%m%d%H%M%S; }

# 从 frontmatter 读字段
fm_field() {
  local file="$1" field="$2"
  sed -n "s/^$field: //p" "$file" 2>/dev/null | head -1
}

# 写一条笔记
# $1=id  $2=category  $3=tags_csv  $4..=content
write_note() {
  local id="$1" cat="$2" tags="$3"; shift 3
  local content="$*"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  cat > "$LOCAL_DIR/$id.md" <<EOF
---
id: $id
created: $ts
category: $cat
tags: [$tags]
---

# $ts

$content
EOF
  echo "$LOCAL_DIR/$id.md"
}

# 同步单条到 Obsidian
sync_one() {
  local file="$1"
  [ -f "$file" ] || return 1
  mkdir -p "$OBSIDIAN_INBOX" 2>/dev/null || return 1
  cp "$file" "$OBSIDIAN_INBOX/" 2>/dev/null
}

# 取正文摘要（第一行，跳过 frontmatter 和标题）
body_summary() {
  local file="$1" len="${2:-60}"
  sed -n '/^# /,$p' "$file" | sed '1d;/^$/d' | head -1 | cut -c1-"$len"
}

# 去掉标签前缀的 #
clean_tag() { local t="$1"; t="${t#\#}"; echo "$t"; }

# ===== add =====
cmd_add() {
  local cat="未分类"
  local -a tags=()
  local -a content=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -c|--cat) cat="$2"; shift 2 ;;
      -t|--tag) tags+=("$(clean_tag "$2")"); shift 2 ;;
      --) shift; content+=("$@"); break ;;
      -*) echo "未知选项: $1"; return 1 ;;
      *) content+=("$1"); shift ;;
    esac
  done
  if [ ${#content[@]} -eq 0 ]; then
    echo "用法: suji add [-c 分类] [-t 标签]... \"内容\""
    return 1
  fi
  # tags → 逗号分隔
  local tags_csv=""
  if [ ${#tags[@]} -gt 0 ]; then
    tags_csv=$(IFS=,; echo "${tags[*]}")
  fi
  local id; id=$(get_id)
  # 避免同秒冲突
  local n=0
  while [ -f "$LOCAL_DIR/$id.md" ]; do n=$((n+1)); id="${id}${n}"; done
  local file
  file=$(write_note "$id" "$cat" "$tags_csv" "${content[*]}")
  echo "✅ 已记 [$id] 分类:$cat"
  [ -n "$tags_csv" ] && echo "   标签:$tags_csv"
  if sync_one "$file"; then
    echo "   已同步到 Obsidian"
  else
    echo "⚠️  Obsidian 同步失败（挂载点可能不可用）"
  fi
  echo "   内容: ${content[*]}"
}

# ===== list =====
cmd_list() {
  local cat="" tag="" n=20
  while [ $# -gt 0 ]; do
    case "$1" in
      -c|--cat) cat="$2"; shift 2 ;;
      -t|--tag) tag="$(clean_tag "$2")"; shift 2 ;;
      *) n="$1"; shift ;;
    esac
  done
  local -a files
  files=($(ls -1r "$LOCAL_DIR"/*.md 2>/dev/null))
  if [ ${#files[@]} -eq 0 ]; then echo "（空）还没有速记"; return; fi
  local i=0 shown=0
  for f in "${files[@]}"; do
    [ $shown -ge "$n" ] && break
    local fc ft ftags
    fc=$(fm_field "$f" category)
    ftags=$(fm_field "$f" tags)
    # 过滤
    [ -n "$cat" ] && [ "$fc" != "$cat" ] && continue
    if [ -n "$tag" ]; then
      # tags 字段是 [a, b, c] 格式
      echo "$ftags" | grep -qi "$tag" || continue
    fi
    local id; id=$(basename "$f" .md)
    local ts; ts=$(fm_field "$f" created)
    local body; body=$(body_summary "$f" 50)
    printf "%-3s %-16s [%-4s] %-20s %s\n" "$((shown+1))" "$ts" "$fc" "$ftags" "$body"
    shown=$((shown+1))
  done
  [ $shown -eq 0 ] && echo "没有匹配的速记"
  echo "---"
  echo "共 $shown 条"$([ -n "$cat" ] && echo " | 分类:$cat")$([ -n "$tag" ] && echo " | 标签:$tag")
}

# ===== tags 统计 =====
cmd_tags() {
  local -A tag_count=()
  for f in "$LOCAL_DIR"/*.md; do
    [ -f "$f" ] || continue
    local ftags; ftags=$(fm_field "$f" tags)
    [ -z "$ftags" ] && continue
    # 解析 [a, b, c]，统一去空格
    ftags="${ftags#\[}"; ftags="${ftags%\]}"
    ftags="${ftags// /}"
    IFS=',' read -ra arr <<< "$ftags"
    for t in "${arr[@]}"; do
      t="${t// /}"
      [ -z "$t" ] && continue
      tag_count["$t"]=$(( ${tag_count["$t"]:-0} + 1 ))
    done
  done
  if [ ${#tag_count[@]} -eq 0 ]; then echo "还没有标签"; return; fi
  for t in "${!tag_count[@]}"; do
    printf "%-16s %d 条\n" "$t" "${tag_count[$t]}"
  done | sort -t' ' -k2 -rn
}

# ===== cats 分类统计 =====
cmd_cats() {
  local -A cat_count=()
  for f in "$LOCAL_DIR"/*.md; do
    [ -f "$f" ] || continue
    local fc; fc=$(fm_field "$f" category)
    [ -z "$fc" ] && fc="未分类"
    cat_count["$fc"]=$(( ${cat_count["$fc"]:-0} + 1 ))
  done
  if [ ${#cat_count[@]} -eq 0 ]; then echo "还没有速记"; return; fi
  for c in "${!cat_count[@]}"; do
    printf "%-16s %d 条\n" "$c" "${cat_count[$c]}"
  done | sort -t' ' -k2 -rn
}

# ===== tag <id> <标签>... =====
cmd_tag() {
  local id="$1"; shift
  [ $# -eq 0 ] && { echo "用法: suji tag <id> <标签>..."; return 1; }
  local file="$LOCAL_DIR/$id.md"
  [ ! -f "$file" ] && { echo "找不到 [$id]"; return 1; }
  local cur; cur=$(fm_field "$file" tags)
  cur="${cur#\[}"; cur="${cur%\]}"
  cur="${cur// /}"  # 统一去空格
  for t in "$@"; do
    t="$(clean_tag "$t")"
    echo "$cur" | grep -qi "$t" && continue  # 已有
    [ -n "$cur" ] && cur="$cur,$t" || cur="$t"
  done
  sed -i "s/^tags: .*/tags: [$cur]/" "$file"
  sync_one "$file"
  echo "🏷️  [$id] 标签: [$cur]"
}

# ===== untag <id> <标签> =====
cmd_untag() {
  local id="$1" tag="$2"
  local file="$LOCAL_DIR/$id.md"
  [ ! -f "$file" ] && { echo "找不到 [$id]"; return 1; }
  tag="$(clean_tag "$tag")"
  local cur; cur=$(fm_field "$file" tags)
  cur="${cur#\[}"; cur="${cur%\]}"
  cur="${cur// /}"  # 统一去空格
  IFS=',' read -ra arr <<< "$cur"
  local new=""
  for t in "${arr[@]}"; do
    t="${t// /}"
    [ "$t" = "$tag" ] && continue
    [ -n "$new" ] && new="$new,$t" || new="$t"
  done
  sed -i "s/^tags: .*/tags: [$new]/" "$file"
  sync_one "$file"
  echo "✂️  [$id] 已去标签 $tag → [$new]"
}

# ===== cat <id> <分类> =====
cmd_cat() {
  local id="$1" cat="$2"
  local file="$LOCAL_DIR/$id.md"
  [ ! -f "$file" ] && { echo "找不到 [$id]"; return 1; }
  [ -z "$cat" ] && { echo "用法: suji cat <id> <分类>"; return 1; }
  sed -i "s/^category: .*/category: $cat/" "$file"
  sync_one "$file"
  echo "📂 [$id] 分类: $cat"
}

# ===== move-cat <旧> <新> =====
cmd_move_cat() {
  local old="$1" new="$2"
  [ -z "$new" ] && { echo "用法: suji move-cat <旧分类> <新分类>"; return 1; }
  local count=0
  for f in "$LOCAL_DIR"/*.md; do
    [ -f "$f" ] || continue
    local fc; fc=$(fm_field "$f" category)
    [ "$fc" = "$old" ] || continue
    sed -i "s/^category: .*/category: $new/" "$f"
    sync_one "$f"
    count=$((count+1))
  done
  echo "📂 「$old」→「$new」，迁移 $count 条"
}

# ===== search =====
cmd_search() {
  local kw="" cat=""
  local -a words=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -c|--cat) cat="$2"; shift 2 ;;
      *) words+=("$1"); shift ;;
    esac
  done
  kw=$(IFS=' '; echo "${words[*]}")
  [ -z "$kw" ] && { echo "用法: note search 关键词 [-c 分类]"; return 1; }
  local hits=0
  for f in "$LOCAL_DIR"/*.md; do
    [ -f "$f" ] || continue
    grep -qil "$kw" "$f" 2>/dev/null || continue
    if [ -n "$cat" ]; then
      local fc; fc=$(fm_field "$f" category)
      [ "$fc" = "$cat" ] || continue
    fi
    local id; id=$(basename "$f" .md)
    local ts; ts=$(fm_field "$f" created)
    local fc; fc=$(fm_field "$f" category)
    local body; body=$(body_summary "$f" 50)
    printf "%-16s [%-4s] %s\n" "$ts" "$fc" "$body"
    hits=$((hits+1))
  done
  [ $hits -eq 0 ] && echo "没找到 \"$kw\"" || true
  return 0
}

# ===== del =====
cmd_del() {
  local id="$1"
  local file="$LOCAL_DIR/$id.md"
  [ ! -f "$file" ] && { echo "找不到 [$id]"; return 1; }
  rm "$file"
  rm -f "$OBSIDIAN_INBOX/$id.md"
  echo "🗑️  已删 [$id]"
}

# ===== show =====
cmd_show() {
  local id="$1"
  local file="$LOCAL_DIR/$id.md"
  [ ! -f "$file" ] && { echo "找不到 [$id]"; return 1; }
  cat "$file"
}

# ===== sync =====
cmd_sync() {
  if [ ! -d "$OBSIDIAN_INBOX" ]; then
    mkdir -p "$OBSIDIAN_INBOX" 2>/dev/null || {
      echo "❌ Obsidian 挂载点不可用: $OBSIDIAN_INBOX"
      return 1
    }
  fi
  local count=0
  for f in "$LOCAL_DIR"/*.md; do
    [ -f "$f" ] || continue
    cp "$f" "$OBSIDIAN_INBOX/" && count=$((count+1))
  done
  echo "✅ 同步 $count 条到 Obsidian"
}

# ===== main =====
case "${1:-}" in
  add)      shift; cmd_add "$@" ;;
  list|ls)  shift; cmd_list "$@" ;;
  tags)     shift; cmd_tags "$@" ;;
  cats)     shift; cmd_cats "$@" ;;
  tag)      shift; cmd_tag "$@" ;;
  untag)    shift; cmd_untag "$@" ;;
  cat)      shift; cmd_cat "$@" ;;
  move-cat) shift; cmd_move_cat "$@" ;;
  search)   shift; cmd_search "$@" ;;
  del)      shift; cmd_del "$@" ;;
  show)     shift; cmd_show "$@" ;;
  sync)     shift; cmd_sync "$@" ;;
  ""|help|-h|--help)
    cat <<USAGE
速记 v2 — 分类 + 标签管理

  suji add [-c 分类] [-t 标签]... "内容"
      示例: suji add -c 工作 -t 重要 -t 待办 "周五前交周报"
  suji list [-c 分类] [-t 标签] [N]      列出（可过滤，默认 20 条）
  suji tags                               标签使用统计
  suji cats                               分类统计
  suji tag <id> <标签> [标签2...]         加标签
  suji untag <id> <标签>                  去标签
  suji cat <id> <分类>                    设分类
  suji move-cat <旧分类> <新分类>          分类改名/合并
  suji search 关键词 [-c 分类]            搜索
  suji show <id>                          查看全文
  suji del <id>                           删除
  suji sync                               手动全量同步到 Obsidian

  存储位置: $LOCAL_DIR
  Obsidian: $OBSIDIAN_INBOX
USAGE
    ;;
  *) echo "未知命令: $1 （输入 suji help 查看用法）"; exit 1 ;;
esac
