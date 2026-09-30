#!/bin/sh
# Version: 0.1.0
# prompts-chat.sh 的黄金测试（已知答案断言，13 项）
# 从真脚本抽出 usable/json_escape，断言其行为，防止改脚本时悄悄退化。
# 用法: sh /var/minis/shared/prompts-chat-test.sh
set -u
LIB=/var/minis/shared/prompts-chat.sh

sed -n '/^usable() {/,/^}/p; /^json_escape() {/,/^}/p' "$LIB" > /tmp/_lib.sh
[ -s /tmp/_lib.sh ] || { echo "FATAL: 从 $LIB 抽不出 usable/json_escape" >&2; exit 2; }
. /tmp/_lib.sh

pass=0; fail=0
chk() {
  [ "$2" = ok ] && want=0 || want=1
  usable "$3"; got=$?; [ $got -eq 0 ] && got=0 || got=1
  if [ "$got" -eq "$want" ]; then pass=$((pass+1)); printf '  PASS  %s\n' "$1"; else fail=$((fail+1)); printf '  FAIL  %s\n' "$1"; fi
}
chk "空字符串"              no  ""
chk "空格串"                no  "   "
chk "isError 紧凑"          no  '{"result":{"content":[{"type":"text","text":"x"}],"isError":true}}'
chk "isError 带空格"        no  '{"result":{"content":[],"isError": true}}'
chk "正常含 content"        ok  '{"result":{"content":[{"type":"text","text":"hi"}]}}'
chk "正常含中文"            ok  '{"result":{"content":[{"type":"text","text":"小红书标题"}]}}'
chk "非 JSON 垃圾"          no  'Traceback (most recent call last)'
chk "daemon 报错无 content" no  '{"server":"prompts-chat","error":"boom"}'
printf 'usable: PASS=%s FAIL=%s\n' "$pass" "$fail"

p2=0; f2=0
esc() {
  got=$(json_escape "$2")
  if [ "$got" = "$3" ]; then p2=$((p2+1)); printf '  PASS  %s\n' "$1"; else f2=$((f2+1)); printf '  FAIL  %s got=[%s]\n' "$1" "$got"; fi
}
esc '双引号+反斜杠' 'a"b\c'     'a\"b\\c'
esc '中文原样'      '小红书 标题' '小红书 标题'
esc '美元不展开'    '$HOME $(y)' '$HOME $(y)'
esc '反引号不展开'  '`x`'        '`x`'
esc '空串'          ''           ''
printf 'json_escape: PASS=%s FAIL=%s\n' "$p2" "$f2"

rm -f /tmp/_lib.sh
[ "$fail" -eq 0 ] && [ "$f2" -eq 0 ] || exit 1
echo "ALL OK"
