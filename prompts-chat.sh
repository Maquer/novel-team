#!/bin/sh
# Version: 0.1.0
# prompts-chat MCP 调用包装器
#
# 为什么需要它（两条独立故障，均已实测）：
#  A. 空闲 ~3-5 分钟后 stdio 连接失效 → `call` 返回 0 字节且 exit 0（静默失败），
#     只有 `minis-mcp-cli tools prompts-chat --refresh` 能复活。已用外网探针做对照排除网络因素。
#  B. 上游 TLS 失败 → 返回合法 JSON 但 {"error":...} 且 "isError": true。
#     只判空输出会把它当成功，必须一起拦。
#
# 判定逻辑刻意不用 python3：iSH 内存紧张时 python3 会 OOM 起不来
# （"Out of memory (needed by /usr/bin/python3)"），用它当门禁会误杀正常响应。
#
# 用法:
#   prompts-chat.sh search <关键词> [limit]
#   prompts-chat.sh get <prompt_id>
#   prompts-chat.sh raw <tool> '<json-args>'
set -u

refresh() { minis-mcp-cli tools prompts-chat --refresh >/dev/null 2>&1; }

# 0=可用 1=不可用。纯 shell，零子进程依赖（grep 除外）。
usable() {
  case "$1" in
    "") return 1 ;;
  esac
  case "$1" in
    *'"isError":true'*|*'"isError": true'*) return 1 ;;
  esac
  case "$1" in
    *'"content"'*) return 0 ;;
  esac
  return 1
}

# 从响应里抠一句失败原因，纯 sed，不用 python
reason_of() {
  printf '%s' "$1" | sed -n 's/.*"text":"\(.\{1,140\}\).*/\1/p' | head -1
}

raw() {
  _tool="$1"; _args="$2"
  _out=$(minis-mcp-cli call prompts-chat "$_tool" --input "$_args" 2>/dev/null)
  if usable "$_out"; then
    printf '%s\n' "$_out"
    return 0
  fi
  _first="$_out"
  refresh
  _out=$(minis-mcp-cli call prompts-chat "$_tool" --input "$_args" 2>/dev/null)
  if usable "$_out"; then
    printf '%s\n' "$_out"
    return 0
  fi
  _r=$(reason_of "$_first")
  [ -n "$_r" ] || _r="空输出（stdio 连接失效）"
  printf 'ERROR: prompts-chat 调用失败（已重连重试一次）。首次原因: %s\n' "$_r" >&2
  return 1
}

# 仅用于把 query 安全塞进 JSON：转义反斜杠和双引号，不依赖 python
json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

case "${1:-}" in
  search)
    [ $# -ge 2 ] || { echo "usage: prompts-chat.sh search <query> [limit]" >&2; exit 2; }
    _q=$(json_escape "$2")
    _n="${3:-5}"
    raw search_prompts "{\"query\":\"$_q\",\"limit\":$_n}"
    ;;
  get)
    [ $# -ge 2 ] || { echo "usage: prompts-chat.sh get <prompt_id>" >&2; exit 2; }
    raw get_prompt "{\"id\":\"$(json_escape "$2")\"}"
    ;;
  raw)
    [ $# -ge 3 ] || { echo "usage: prompts-chat.sh raw <tool> '<json>'" >&2; exit 2; }
    raw "$2" "$3"
    ;;
  *)
    echo "usage: prompts-chat.sh search <query> [limit] | get <id> | raw <tool> '<json>'" >&2
    exit 2
    ;;
esac
