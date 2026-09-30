#!/bin/bash
# Version: 0.1.0
# pixelle-tts-setup.sh
# Edge-TTS 本地部署脚本 — 在 Mac/PC 上运行，为 Pixelle-Video 提供 TTS 能力
# 用法: bash pixelle-tts-setup.sh
# 输出: tts-engine/ 目录（含 edge-tts 环境 + 预设音色配置）

set -e

INSTALL_DIR="$(pwd)/tts-engine"
PYTHON_BIN=""

echo "=== Pixelle TTS Engine Setup ==="

# 检测 Python
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ 未找到 Python，请先安装 Python 3.8+"
    exit 1
fi

echo "✓ Python: $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))"

# 创建虚拟环境
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "→ 创建虚拟环境..."
    $PYTHON_BIN -m venv "$INSTALL_DIR/.venv"
fi

source "$INSTALL_DIR/.venv/bin/activate"

# 安装 edge-tts
echo "→ 安装 edge-tts..."
pip install edge-tts -q

# 创建预设音色配置
mkdir -p "$INSTALL_DIR/voices"
cat > "$INSTALL_DIR/voices/voices.json" << 'VOICES_EOF'
{
  "_comment": "Pixelle-Video TTS 中文音色预设",
  "_source": "Microsoft Edge TTS (https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)",
  "voices": [
    {
      "id": "zh-CN-XiaoxiaoNeural",
      "name": "晓晓（温柔女声）",
      "gender": "Female",
      "style": ["gentle", "soft", "calm"],
      "best_for": ["情感类", "治愈系", "睡前故事"]
    },
    {
      "id": "zh-CN-YunxiNeural",
      "name": "云希（沉稳男声）",
      "gender": "Male",
      "style": ["deep", "steady", "authoritative"],
      "best_for": ["知识科普", "历史解说", "商务"]
    },
    {
      "id": "zh-CN-YunjianNeural",
      "name": "云健（活力男声）",
      "gender": "Male",
      "style": ["energetic", "clear", "upbeat"],
      "best_for": ["励志", "运动", "科技"]
    },
    {
      "id": "zh-CN-XiaoyiNeural",
      "name": "晓毅（活泼女声）",
      "gender": "Female",
      "style": ["cheerful", "bright", "lively"],
      "best_for": ["儿童内容", "生活类", "轻松话题"]
    },
    {
      "id": "zh-CN-YunyangNeural",
      "name": "云扬（磁性男声）",
      "gender": "Male",
      "style": ["charismatic", "warm", "storytelling"],
      "best_for": ["小说解说", "故事讲述", "情感"]
    },
    {
      "id": "zh-CN-XiaochenNeural",
      "name": "晓辰（童声女）",
      "gender": "Female",
      "style": ["childlike", "innocent", "cute"],
      "best_for": ["儿童内容", "萌系"]
    },
    {
      "id": "zh-CN-XiaohanNeural",
      "name": "晓涵（知性女声）",
      "gender": "Female",
      "style": ["intellectual", "calm", "professional"],
      "best_for": ["知识分享", "读书", "学术"]
    },
    {
      "id": "zh-CN-XiaojuNeural",
      "name": "晓菊（亲切女声）",
      "gender": "Female",
      "style": ["friendly", "warm", "approachable"],
      "best_for": ["母婴", "家庭", "生活"]
    },
    {
      "id": "zh-CN-XiaolongNeural",
      "name": "晓龙（沉稳男声）",
      "gender": "Male",
      "style": ["steady", "mature", "confident"],
      "best_for": ["商业", "金融", "严肃话题"]
    },
    {
      "id": "zh-CN-XiaoniNeural",
      "name": "晓妮（甜美女声）",
      "gender": "Female",
      "style": ["sweet", "young", "pleasant"],
      "best_for": ["美妆", "时尚", "轻松"]
    }
  ]
}
VOICES_EOF

# 创建 TTS 合成脚本
cat > "$INSTALL_DIR/synthesize.sh" << 'SYNTH_EOF'
#!/bin/bash
# TTS 合成脚本 — 输入文本，输出 MP3
# 用法: bash synthesize.sh <文本> [音色ID] [语速] [音高]
# 示例: bash synthesize.sh "你好世界" zh-CN-YunxiNeural 1.0 0

set -e

VENV_DIR="$(cd "$(dirname "$0")" && pwd)/.venv"
source "$VENV_DIR/bin/activate"

TEXT="${1:?请提供要合成的文本}"
VOICE="${2:-zh-CN-YunxiNeural}"
SPEED="${3:-1.0}"
PITCH="${4:-0}"
OUTPUT_DIR="${5:-$(pwd)/output}"

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SAFE_TEXT=$(echo "$TEXT" | tr -c 'A-Za-z0-9_\-\.' '_' | cut -c1-30)
OUTPUT="$OUTPUT_DIR/${SAFE_TEXT}_${TIMESTAMP}.mp3"

edge-tts \
  --text "$TEXT" \
  --voice "$VOICE" \
  --rate "$((SPEED * 100))%" \
  --pitch "$((PITCH * 100))Hz" \
  --write-media "$OUTPUT"

echo "$OUTPUT"
SYNTH_EOF
chmod +x "$INSTALL_DIR/synthesize.sh"

# 创建批量合成脚本（用于多段视频配音）
cat > "$INSTALL_DIR/batch-synthesize.sh" << 'BATCH_EOF'
#!/bin/bash
# 批量 TTS 合成 — 读取 JSON 文件，逐段合成
# 用法: bash batch-synthesize.sh <segments.json> [音色ID]
# segments.json 格式: {"segments": ["第一段", "第二段", ...]}

set -e

VENV_DIR="$(cd "$(dirname "$0")" && pwd)/.venv"
source "$VENV_DIR/bin/activate"

JSON_FILE="${1:?请提供 segments.json}"
VOICE="${2:-zh-CN-YunxiNeural}"
OUTPUT_DIR="${3:-$(pwd)/output}"
mkdir -p "$OUTPUT_DIR"

python3 -c "
import json, subprocess, sys, os

with open('$JSON_FILE') as f:
    data = json.load(f)

segments = data.get('segments', data.get('narrations', []))
output_dir = '$OUTPUT_DIR'
voice = '$VOICE'

results = []
for i, text in enumerate(segments):
    safe = text[:20].replace(' ', '_').replace('/', '_')
    out = os.path.join(output_dir, f'segment_{i+1:02d}_{safe}.mp3')
    if os.path.exists(out):
        results.append({'index': i+1, 'path': out, 'status': 'cached'})
        continue
    cmd = ['edge-tts', '--text', text, '--voice', voice, '--write-media', out]
    subprocess.run(cmd, check=True)
    results.append({'index': i+1, 'path': out, 'status': 'generated'})

with open(os.path.join(output_dir, 'manifest.json'), 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f'✓ 完成 {len(results)} 段配音')
"

echo "→ 清单: $OUTPUT_DIR/manifest.json"
BATCH_EOF
chmod +x "$INSTALL_DIR/batch-synthesize.sh"

# 创建 Pixelle 集成脚本
cat > "$INSTALL_DIR/pixelle-tts.sh" << 'PIXELLE_EOF'
#!/bin/bash
# Pixelle-Video TTS 集成脚本
# 为 Pixelle 工作流生成音频文件
# 用法: bash pixelle-tts.sh <pixelle_dir> <segments.json> [音色ID]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIXELLE_DIR="${1:?请提供 Pixelle 项目目录}"
SEGMENTS="${2:?请提供 segments.json}"
VOICE="${3:-zh-CN-YunxiNeural}"

# Pixelle 的音频输出目录
AUDIO_DIR="$PIXELLE_DIR/output/audio"
mkdir -p "$AUDIO_DIR"

# 调用批量合成
bash "$SCRIPT_DIR/batch-synthesize.sh" "$SEGMENTS" "$VOICE" "$AUDIO_DIR"

echo "✓ 音频已生成到 $AUDIO_DIR"
echo "✓ 可在 Pixelle WebUI 中使用"
PIXELLE_EOF
chmod +x "$INSTALL_DIR/pixelle-tts.sh"

# 测试
echo ""
echo "=== 测试 TTS ==="
python3 -c "
import asyncio, edge_tts
async def test():
    communicate = edge_tts.Communicate('你好，这是 Pixelle TTS 引擎的测试。', 'zh-CN-YunxiNeural')
    await communicate.save('test_output.mp3')
    print('✓ TTS 合成成功')
    import os
    print(f'✓ 文件大小: {os.path.getsize(\"test_output.mp3\")} bytes')
asyncio.run(test())
" 2>&1 || echo "⚠️ TTS 测试失败（可能网络受限），部署到本地后重试"

echo ""
echo "=== 安装完成 ==="
echo ""
echo "📁 目录: $INSTALL_DIR"
echo "📋 预设音色: $INSTALL_DIR/voices/voices.json"
echo ""
echo "命令速查:"
echo "  单段合成:  bash $INSTALL_DIR/synthesize.sh \"文本内容\" [音色ID] [语速] [音高]"
echo "  批量合成:  bash $INSTALL_DIR/batch-synthesize.sh segments.json [音色ID]"
echo "  Pixelle集成: bash $INSTALL_DIR/pixelle-tts.sh <pixelle_dir> segments.json [音色ID]"
echo ""
echo "示例:"
echo "  bash $INSTALL_DIR/synthesize.sh \"你好世界\" zh-CN-YunxiNeural"
echo ""
echo "预设音色查看: cat $INSTALL_DIR/voices/voices.json"