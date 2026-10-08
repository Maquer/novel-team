#!/bin/bash
# 多模型并行改写第1章
DIR="/var/minis/shared/novel-team/multi-model"
INPUT="$DIR/input.json"

# 模型列表
MODELS=(
  "Radeon Cloud/DeepSeek-V4-Flash"
  "OpenRouter/z.ai: GLM 5.3 Flash"
  "Radeon Cloud/Qwen3.8-27B"
  "OpenRouter/Agnes 2.5 Flash"
)

# 并行调用
for i in "${!MODELS[@]}"; do
  IFS='/' read -r instance model <<< "${MODELS[$i]}"
  OUT="$DIR/output_model_${i}.txt"
  echo "[$(date +%H:%M:%S)] 启动模型 $i: $instance / $model"
  nohup minis-model-use run \
    --model "$model" \
    --provider "$instance" \
    --input "$INPUT" \
    --output "$OUT" \
    --max-tokens 4096 \
    --temperature 0.7 \
    > "$DIR/log_model_${i}.txt" 2>&1 &
  PIDS[$i]=$!
  echo "  PID: ${PIDS[$i]}"
done

echo ""
echo "[$(date +%H:%M:%S)] 4个模型已并行启动，等待完成..."
echo ""

# 等待所有完成
FAIL=0
for i in "${!PIDS[@]}"; do
  wait ${PIDS[$i]}
  RC=$?
  if [ $RC -eq 0 ]; then
    SIZE=$(wc -c < "$DIR/output_model_${i}.txt" 2>/dev/null || echo 0)
    echo "[$(date +%H:%M:%S)] 模型 $i 完成 (PID=${PIDS[$i]}, rc=$RC, size=${SIZE}B)"
  else
    echo "[$(date +%H:%M:%S)] 模型 $i 失败 (PID=${PIDS[$i]}, rc=$RC)"
    FAIL=$((FAIL+1))
  fi
done

echo ""
echo "[$(date +%H:%M:%S)] 全部完成。失败: $FAIL/4"
echo ""
echo "=== 输出文件 ==="
for i in "${!MODELS[@]}"; do
  IFS='/' read -r instance model <<< "${MODELS[$i]}"
  SIZE=$(wc -c < "$DIR/output_model_${i}.txt" 2>/dev/null || echo 0)
  echo "  模型${i} ($model): ${SIZE}B"
done
