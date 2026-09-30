#!/bin/sh
# Version: 0.1.0
# archify-render.sh — archify 在 iSH 上的安全渲染包装
#
# 每条约束都对应 2026-09-23 在 iSH + Node 22.23.2 上的实测，不是推测：
#   坑1  render 输出到 /var/minis/** 时 renderers/shared/output-path.mjs 的
#        realpathSync.native 恒报 ENOENT（shell 里目录明明可见）→ 未捕获异常 exit=1
#   坑2  render 对非法 spec 会 exit=0 且【不产出任何文件】= 无声失败
#        （例：edges[0].from 指向不存在的节点）
#   坑3  子进程校验回执在 iSH 下不可解析，CLI 侧 JSON.parse 失败后把真实原因丢掉，
#        只剩 artifact/check-failed + check:"unknown" + supportedFixes:[]
#   坑4  stderr 恒被 "Warning: disabling flag --expose_wasm" 污染，不能整串当 JSON
#   坑5  校验路径极慢：validate 实测 >215s，成功 render 约 60-90s
#
# 因此本包装做四件事：输出走 /tmp 中转、硬超时、产物存在性+体积双闸门、诊断剥噪。
#
# 用法:
#   archify-render.sh <type> <spec.json> [output.html]
#   archify-render.sh check <output.html>
#   archify-render.sh validate <type> <spec.json>
#   archify-render.sh doctor
#
# 退出码（语义化，区别于 archify 自身退出码）:
#   0  成功，产物已就位
#   2  参数/环境错误（无 node、无 skill、spec 不存在）
#   3  无声失败：进程 exit=0 但产物缺失或过小 —— 最危险，archify 自己不会报
#   4  超时被杀
#   5  渲染完成但产物校验未过
#   6  渲染失败且无产物（exit≠0，报错首行已抛到终端）

set -u

SKILL="${ARCHIFY_SKILL:-/var/minis/skills/archify}"
[ -d "$SKILL" ] || SKILL="/var/minis/shared/archived-skills/archify"
CLI="$SKILL/bin/archify.mjs"

RENDER_TIMEOUT="${ARCHIFY_RENDER_TIMEOUT:-300}"
VALIDATE_TIMEOUT="${ARCHIFY_VALIDATE_TIMEOUT:-480}"
MIN_HTML_BYTES="${ARCHIFY_MIN_BYTES:-20000}"

TYPES="architecture workflow sequence dataflow lifecycle"
RUNDIR="/tmp/archify-run/$(date +%s)-$$"

die() { printf 'archify-render: %s\n' "$2" >&2; exit "$1"; }

[ -f "$CLI" ] || die 2 "找不到 archify CLI: $CLI（设 ARCHIFY_SKILL 指定）"
command -v node >/dev/null 2>&1 || die 2 "node 不在 PATH"
command -v timeout >/dev/null 2>&1 || die 2 "timeout 不在 PATH（BusyBox 自带，缺失说明环境异常）"

mkdir -p "$RUNDIR" || die 2 "无法创建 $RUNDIR"
OUT_JSON="$RUNDIR/stdout.json"
OUT_ERR="$RUNDIR/stderr.log"

# 剥掉 iSH Node 的 --expose_wasm 噪音后，尝试把剩余内容当 JSON 打印
emit_json() {
  [ -s "$OUT_JSON" ] || return 0
  node -e '
    const fs = require("fs");
    const raw = fs.readFileSync(process.argv[1], "utf8");
    const lines = raw.split("\n").filter(l => !/--expose_wasm|^Warning:/.test(l));
    const s = lines.join("\n").trim();
    if (!s) process.exit(0);
    try { process.stdout.write(JSON.stringify(JSON.parse(s), null, 2) + "\n"); }
    catch { process.stdout.write(s + "\n"); }
  ' "$OUT_JSON" 2>/dev/null || cat "$OUT_JSON"
}

run_archify() { # run_archify <timeout_sec> <args...>
  _t="$1"; shift
  ( cd "$SKILL" && timeout "$_t" node "$CLI" "$@" ) >"$OUT_JSON" 2>"$OUT_ERR"
  _rc=$?
  # 过滤噪音后的 stderr（非 JSON 部分才有价值）
  grep -v -- '--expose_wasm' "$OUT_ERR" 2>/dev/null | grep -v '^Warning:' >"$RUNDIR/stderr.clean.log" || true
  return $_rc
}

case "${1:-}" in
  doctor)
    run_archify "${VALIDATE_TIMEOUT}" doctor; rc=$?
    emit_json; [ "$rc" = 0 ] || { sed -n '1,20p' "$RUNDIR/stderr.clean.log" >&2; exit "$rc"; }
    exit 0 ;;

  check)
    [ $# -eq 2 ] || die 2 "用法: $0 check <output.html>"
    [ -f "$2" ] || die 2 "文件不存在: $2"
    run_archify "${VALIDATE_TIMEOUT}" check "$2"; rc=$?
    emit_json
    [ "$rc" = 0 ] || { [ -s "$RUNDIR/stderr.clean.log" ] && sed -n '1,20p' "$RUNDIR/stderr.clean.log" >&2; }
    exit "$rc" ;;

  validate)
    [ $# -eq 3 ] || die 2 "用法: $0 validate <type> <spec.json>"
    [ -f "$3" ] || die 2 "spec 不存在: $3"
    # spec 同样要 /tmp 中转（坑1 影响输入路径），校验本身不写目标目录
    cp "$3" "$RUNDIR/$(basename "$3")" || die 2 "复制 spec 失败"
    run_archify "${VALIDATE_TIMEOUT}" validate "$2" "$RUNDIR/$(basename "$3")" --json; rc=$?
    [ "$rc" = 124 ] && die 4 "validate 超时（${VALIDATE_TIMEOUT}s）。iSH 实测 validate >215s，可调 ARCHIFY_VALIDATE_TIMEOUT"
    emit_json; exit "$rc" ;;

  render)
    [ $# -ge 3 ] && [ $# -le 4 ] || die 2 "用法: $0 <type> <spec.json> [output.html]"
    TYPE="$2"; SPEC="$3"
    DEST="${4:-/var/minis/workspace/${TYPE##*/}.html}"
    case " $TYPES " in *" $TYPE "*) ;; *) die 2 "未知 type: $TYPE（支持: $TYPES）" ;; esac
    [ -f "$SPEC" ] || die 2 "spec 不存在: $SPEC"
    ;;

  *) sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//' >&2; die 2 "未知子命令: ${1:-<空>}" ;;
esac

# ---- render 主路径 ----
case "$DEST" in
  /*) ;;
  *) DEST="$(pwd)/$DEST" ;;
esac
DEST_DIR=$(dirname "$DEST")
TMP_HTML="$RUNDIR/artifact.html"
# 输入也必须走 /tmp —— 坑1 的真实边界比想象宽：canonicalize() 对【输入 spec】
# 同样 realpath，spec 放在 /var/minis/** 下就会 ENOENT（不只是输出目录受影响）
TMP_SPEC="$RUNDIR/$(basename "$SPEC")"
cp "$SPEC" "$TMP_SPEC" || die 2 "复制 spec 到 $TMP_SPEC 失败"

printf 'archify-render: 渲染 %s → /tmp 中转（spec 与产物均不落 minis 挂载）\n' "$TYPE" >&2
run_archify "$RENDER_TIMEOUT" render "$TYPE" "$TMP_SPEC" "$TMP_HTML"
rc=$?

if [ "$rc" = 124 ]; then
  emit_json
  die 4 "渲染超时（${RENDER_TIMEOUT}s）。可调 ARCHIFY_RENDER_TIMEOUT；或先跑 validate"
fi

# 闸门1：产物必须存在（坑2 无声失败的唯一检法）
if [ ! -f "$TMP_HTML" ]; then
  emit_json
  # CLI 侧会吞掉子进程诊断，真实原因几乎只在 stderr —— 直接抛到终端，别让人去翻文件
  if [ -s "$RUNDIR/stderr.clean.log" ]; then
    printf 'archify-render: 报错 → %s\n' "$(grep -m1 -E 'Error:' "$RUNDIR/stderr.clean.log" | head -1 | cut -c1-200)" >&2
    grep -m4 -E 'must NOT|must have|additionalProperty|supportedFixes' "$RUNDIR/stderr.clean.log" | sed 's/^[[:space:]]*/    /' >&2
  fi
  if [ "$rc" = 0 ]; then
    printf 'archify-render: 退出码=0 却【没有产出文件】= 无声失败，退出码完全不可信\n' >&2
    printf 'archify-render: 下一步: %s validate %s %s\n' "$0" "$TYPE" "$SPEC" >&2
    die 3 "exit=0 但产物缺失（无声失败）"
  fi
  printf 'archify-render: 渲染失败 exit=%s 且无产物。完整日志: %s/stderr.clean.log\n' "$rc" "$RUNDIR" >&2
  die 6 "exit=$rc 且产物缺失（报错见上）"
fi

GOT=$(wc -c <"$TMP_HTML" | tr -d ' ')
# 闸门2：体积下限（截断/空壳 HTML 逃得过 exit code）
if [ "$GOT" -lt "$MIN_HTML_BYTES" ]; then
  emit_json
  printf 'archify-render: 产物仅 %sB（下限 %sB），疑似截断或空壳\n' "$GOT" "$MIN_HTML_BYTES" >&2
  die 3 "产物过小 ${GOT}B"
fi

# 闸门3：产物自检（可选，archify 自带 check）
if [ "${ARCHIFY_SKIP_CHECK:-0}" != "1" ]; then
  run_archify "${VALIDATE_TIMEOUT}" check "$TMP_HTML"
  chk=$?
  if [ "$chk" != 0 ]; then
    emit_json
    printf 'archify-render: 产物已生成 %sB 但 check 未过（rc=%s）\n' "$GOT" "$chk" >&2
    printf 'archify-render: 注意坑3 —— 诊断可能退化为 artifact/check-failed 且 supportedFixes 为空，\n' >&2
    printf '                真实原因需直跑 renderer 取 stderr 首行 JSON:\n' >&2
    printf '                cd %s && node renderers/%s/render.mjs %s\n' "$SKILL" "$TYPE" "$SPEC" >&2
    cp "$TMP_HTML" "$RUNDIR/unverified.html"
    printf 'archify-render: 未验证产物留在 %s/unverified.html\n' "$RUNDIR" >&2
    exit 5
  fi
fi

# 全部闸门通过才落到目标目录
mkdir -p "$DEST_DIR" 2>/dev/null || die 2 "无法创建 $DEST_DIR"
cp "$TMP_HTML" "$DEST" || die 2 "cp 到 $DEST 失败"
FINAL=$(wc -c <"$DEST" | tr -d ' ')
[ "$FINAL" = "$GOT" ] || die 3 "落地字节 $FINAL != 源字节 $GOT，复制被截断"

printf 'archify-render: OK  %s\n' "$DEST"
printf 'archify-render: 字节 %s / 临时目录 %s\n' "$FINAL" "$RUNDIR"
exit 0
