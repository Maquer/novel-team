#!/bin/bash
# Version: 0.1.0
# pixelle-pipeline.sh — Minis → Pixelle 一键视频流水线
# 
# 完整流程: Minis Markdown → 分镜拆分 → TTS 配音 → Pixelle 视频合成
#
# 前置条件:
#   1. Pixelle-Video 已在本地运行 (默认 http://localhost:8000)
#   2. TTS 引擎已部署 (bash pixelle-tts-setup.sh)
#   3. ffmpeg 已安装
#
# 用法:
#   # 完整流程
#   bash pixelle-pipeline.sh article.md
#
#   # 仅转换内容（不调用 Pixelle）
#   bash pixelle-pipeline.sh article.md --convert-only
#
#   # 指定参数
#   bash pixelle-pipeline.sh article.md --voice zh-CN-XiaoxiaoNeural --pixelle http://192.168.1.100:8000

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIXELLE_URL="${PIXELLE_URL:-http://localhost:8000}"
VOICE="${VOICE:-zh-CN-YunxiNeural}"
IMAGE_WORKFLOW="${IMAGE_WORKFLOW:-runninghub/image_flux.json}"
CONVERT_ONLY=false
OUTPUT_PREFIX="${OUTPUT_PREFIX:-pixelle_output}"

# 解析参数
INPUT=""
for arg in "$@"; do
    case "$arg" in
        --voice=*) VOICE="${arg#*=}" ;;
        --pixelle=*) PIXELLE_URL="${arg#*=}" ;;
        --workflow=*) IMAGE_WORKFLOW="${arg#*=}" ;;
        --convert-only) CONVERT_ONLY=true ;;
        --output=*) OUTPUT_PREFIX="${arg#*=}" ;;
        --help|-h)
            echo "用法: bash pixelle-pipeline.sh <文章.md> [选项]"
            echo ""
            echo "选项:"
            echo "  --voice=音色ID         TTS 音色 (默认: zh-CN-YunxiNeural)"
            echo "  --pixelle=地址         Pixelle API (默认: http://localhost:8000)"
            echo "  --workflow=路径        图像工作流 (默认: runninghub/image_flux.json)"
            echo "  --convert-only         仅转换内容，不调用 Pixelle"
            echo "  --output=前缀          输出文件前缀"
            echo ""
            echo "预设音色:"
            echo "  zh-CN-XiaoxiaoNeural  晓晓（温柔女声）"
            echo "  zh-CN-YunxiNeural     云希（沉稳男声）"
            echo "  zh-CN-YunjianNeural   云健（活力男声）"
            echo "  zh-CN-XiaoyiNeural    晓毅（活泼女声）"
            echo "  zh-CN-YunyangNeural   云扬（磁性男声）"
            exit 0
            ;;
        -*)
            echo "未知选项: $arg (使用 --help 查看用法)"
            exit 1
            ;;
        *)
            if [ -z "$INPUT" ]; then
                INPUT="$arg"
            fi
            ;;
    esac
done

if [ -z "$INPUT" ]; then
    echo "❌ 请指定输入文件"
    echo "用法: bash pixelle-pipeline.sh <文章.md> [选项]"
    exit 1
fi

if [ ! -f "$INPUT" ]; then
    echo "❌ 文件不存在: $INPUT"
    exit 1
fi

echo "============================================"
echo "  Minis → Pixelle 视频流水线"
echo "============================================"
echo ""
echo "📄 输入: $INPUT"
echo "🔊 音色: $VOICE"
echo "🌐 Pixelle: $PIXELLE_URL"
echo "🎨 工作流: $IMAGE_WORKFLOW"
echo ""

# Step 1: 内容转换
echo "━━━ Step 1/4: 内容转换 ━━━"
python3 "$SCRIPT_DIR/content-to-pixelle.py" \
    "$INPUT" \
    --output "$OUTPUT_PREFIX" \
    --voice "$VOICE" \
    --image-workflow "$IMAGE_WORKFLOW"

echo ""

if [ "$CONVERT_ONLY" = true ]; then
    echo "✓ 转换完成 (--convert-only)"
    echo "  输出: ${OUTPUT_PREFIX}-video.json"
    echo "  清单: ${OUTPUT_PREFIX}-segments.json"
    exit 0
fi

# Step 2: TTS 配音
echo "━━━ Step 2/4: TTS 配音 ━━━"
if [ -d "tts-engine" ]; then
    bash tts-engine/batch-synthesize.sh "${OUTPUT_PREFIX}-segments.json" "$VOICE" output/audio 2>&1 || \
        echo "⚠️ TTS 批量合成失败，将使用 Pixelle 内置 TTS"
else
    echo "⚠️ tts-engine 未部署，跳过本地 TTS（Pixelle 将使用内置 TTS）"
    echo "   部署: bash $SCRIPT_DIR/pixelle-tts-setup.sh"
fi

echo ""

# Step 3: 提交视频生成
echo "━━━ Step 3/4: 提交视频生成 ━━━"
python3 "$SCRIPT_DIR/pixelle-client.py" generate \
    --config "${OUTPUT_PREFIX}-video.json" \
    --pixelle "$PIXELLE_URL" 2>&1 || {
        echo ""
        echo "⚠️ Pixelle 未运行，无法提交视频生成任务"
        echo "   请先启动 Pixelle: uv run python api/app.py"
        echo "   或使用 Docker: docker compose up"
        echo ""
        echo "已生成配置，Pixelle 启动后可手动提交:"
        echo "  python3 $SCRIPT_DIR/pixelle-client.py generate --config ${OUTPUT_PREFIX}-video.json --pixelle $PIXELLE_URL"
        exit 1
    }

echo ""

# Step 4: 提示下一步
echo "━━━ Step 4/4: 流水线完成 ━━━"
echo ""
echo "✓ 输出文件:"
echo "  ${OUTPUT_PREFIX}-video.json   — 视频配置"
echo "  ${OUTPUT_PREFIX}-segments.json — TTS 分镜清单"
echo ""
echo "后续操作:"
echo "  1. 在 Pixelle WebUI (http://localhost:8501) 查看生成进度"
echo "  2. 或使用 API 轮询:"
echo "     python3 $SCRIPT_DIR/pixelle-client.py poll --task-id <task_id> --pixelle $PIXELLE_URL"
echo ""
echo "============================================"