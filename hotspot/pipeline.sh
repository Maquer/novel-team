#!/usr/bin/env bash
# 一键跑完整热点轮询流水线
# 用法:
#   bash pipeline.sh              # 抓榜→构造输入→调 glm-5.2 评分→解析输出
#   bash pipeline.sh --dry        # 只抓榜和构造输入, 不调模型

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

DRY=false
[ "$1" = "--dry" ] && DRY=true

echo "== 1. 抓榜 =="
python3 hot-radar.py snap

echo "== 2. 追加选题池 =="
python3 hot-radar.py feed

echo "== 3. 构造评分输入 =="
python3 build-score-input.py

if [ "$DRY" = true ]; then
  echo "--dry: 跳过模型调用"
  exit 0
fi

echo "== 4. 调评分模型 (glm-5.2) =="
minis-model-use run --model glm-5.2 \
  --input "$DIR/score-input.json" \
  --output "$DIR/score-output.json" \
  --max-tokens 4000 > /dev/null 2>&1

echo "== 5. 解析输出 =="
python3 parse-score-output.py

echo "== done =="
