#!/usr/bin/env python3
# Version: 0.1.0
"""
content-to-pixelle.py — Minis 内容 → Pixelle-Video 配置转换器

将 Minis 写作产出（Markdown 文章/笔记）转换为 Pixelle-Video 可直接消费的 JSON 配置。

用法:
  python3 content-to-pixelle.py <input.md> [--output pixelle-config.json] [--voice zh-CN-YunxiNeural]

输入格式:
  - Markdown 文件（H2 作为分镜段落）
  - 或纯文本文件（每段自动分段）

输出:
  - Pixelle 兼容的 video-config.json
  - segments.json（供 TTS 批量合成使用）

Pixelle API 参考:
  POST /api/content/narration       — 文案分段
  POST /api/content/image-prompt    — 配图提示词
  POST /api/content/title           — 视频标题
  POST /api/tts/synthesize          — 语音合成
  POST /api/video/generate/sync     — 同步生成
  POST /api/video/generate/async    — 异步生成（推荐）
"""

import json
import re
import sys
import os
import argparse
from pathlib import Path


def parse_markdown(filepath):
    """将 Markdown 文件解析为分镜段落列表"""
    text = Path(filepath).read_text(encoding='utf-8')
    
    # 尝试 H2 分割
    sections = re.split(r'\n##\s+', text)
    
    segments = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # 去除 H1 标题
        if section.startswith('# '):
            lines = section.split('\n')
            title = lines[0].lstrip('# ').strip()
            body = '\n'.join(lines[1:]).strip()
            # 如果是主标题且后面有内容，作为第一段
            if body:
                segments.append({'title': title, 'text': body})
        elif section.startswith('#') and '\n' in section:
            lines = section.split('\n', 1)
            title = lines[0].lstrip('#').strip()
            body = lines[1].strip() if len(lines) > 1 else ''
            if body:
                segments.append({'title': title, 'text': body})
        else:
            # 纯文本段落，按空行分段
            paragraphs = re.split(r'\n\s*\n', section)
            for p in paragraphs:
                p = p.strip()
                if len(p) > 10:  # 过滤太短的段落
                    segments.append({'title': p[:30], 'text': p})
    
    return segments


def split_long_paragraphs(segments, max_words=120):
    """将过长的段落拆分为更小的分镜"""
    result = []
    for seg in segments:
        text = seg['text']
        words = len(text)
        if words <= max_words:
            result.append(seg)
        else:
            # 按句子拆分
            sentences = re.split(r'(?<=[。！？])\s*', text)
            current = ''
            idx = 0
            for sent in sentences:
                if len(current) + len(sent) > max_words and current:
                    result.append({
                        'title': f"{seg['title']} ({len(result)+1})",
                        'text': current.strip()
                    })
                    current = sent
                else:
                    current += sent
            if current.strip():
                result.append({
                    'title': f"{seg['title']} ({len(result)+1})",
                    'text': current.strip()
                })
    return result


def generate_image_prompts(segments, prefix="Minimalist black-and-white matchstick figure style illustration"):
    """为每个分镜生成配图提示词模板（LLM 生成更精准）"""
    prompts = []
    for i, seg in enumerate(segments):
        prompts.append({
            'index': i + 1,
            'narration': seg['text'],
            'prompt_template': f"{prefix}, depicting: {seg['text'][:80]}",
            'style_hint': '保持一致的视觉风格'
        })
    return prompts


def build_pixelle_config(segments, config):
    """构建 Pixelle-Video 完整的视频配置"""
    voice = config.get('voice', 'zh-CN-YunxiNeural')
    speed = config.get('speed', '100%')
    pitch = config.get('pitch', '0Hz')
    image_workflow = config.get('image_workflow', 'runninghub/image_flux.json')
    tts_workflow = config.get('tts_workflow', 'selfhost/tts_edge.json')
    template = config.get('template', '')
    image_size = config.get('image_size', '1024x1024')
    prompt_prefix = config.get('prompt_prefix', 'Minimalist black-and-white matchstick figure style illustration')
    dimensions = image_size.split('x') if 'x' in image_size else ['1024', '1024']
    
    narrations = [{'text': s['text'], 'title': s['title']} for s in segments]
    
    video_config = {
        'project_name': config.get('project_name', 'Minis Video'),
        'llm': {
            'base_url': config.get('llm_base_url', ''),
            'model': config.get('llm_model', ''),
            '_note': '在 Pixelle WebUI 中配置 LLM API Key'
        },
        'narrations': narrations,
        'tts': {
            'workflow': tts_workflow,
            'voice': voice,
            'speed': speed,
            'pitch': pitch,
            'segments_file': 'segments.json'
        },
        'image': {
            'workflow': image_workflow,
            'width': int(dimensions[0]),
            'height': int(dimensions[1]),
            'prompt_prefix': prompt_prefix
        },
        'template': template or None,
        'bgm': config.get('bgm', ''),
        'output_dir': config.get('output_dir', './output')
    }
    
    return video_config


def build_segments_json(segments):
    """构建 TTS 批量合成所需的 segments.json"""
    return {
        'segments': [s['text'] for s in segments],
        'titles': [s['title'] for s in segments],
        '_note': '供 pixelle-tts.sh 批量合成使用'
    }


def main():
    parser = argparse.ArgumentParser(description='Minis 内容 → Pixelle 视频配置')
    parser.add_argument('input', help='输入 Markdown/文本文件')
    parser.add_argument('-o', '--output', default='pixelle-config', help='输出前缀 (默认: pixelle-config)')
    parser.add_argument('--voice', default='zh-CN-YunxiNeural', help='TTS 音色 (默认: zh-CN-YunxiNeural)')
    parser.add_argument('--speed', default='100%', help='语速 (默认: 100%%)')
    parser.add_argument('--pitch', default='0Hz', help='音高偏移 (默认: 0Hz)')
    parser.add_argument('--image-workflow', default='runninghub/image_flux.json', help='图像生成工作流')
    parser.add_argument('--tts-workflow', default='selfhost/tts_edge.json', help='TTS 工作流')
    parser.add_argument('--image-size', default='1024x1024', help='图像尺寸 (默认: 1024x1024)')
    parser.add_argument('--prompt-prefix', default='', help='图像提示词前缀')
    parser.add_argument('--template', default='', help='视频模板 (如 templates/1080x1920/static_story.html)')
    parser.add_argument('--max-words', type=int, default=120, help='每段最大字数')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)
    
    # 解析内容
    segments = parse_markdown(args.input)
    if not segments:
        print("❌ 未能解析出有效段落")
        sys.exit(1)
    
    # 拆分过长段落
    segments = split_long_paragraphs(segments, args.max_words)
    
    # 构建配置
    config = {
        'voice': args.voice,
        'speed': args.speed,
        'pitch': args.pitch,
        'image_workflow': args.image_workflow,
        'tts_workflow': args.tts_workflow,
        'image_size': args.image_size,
        'prompt_prefix': args.prompt_prefix,
        'template': args.template
    }
    
    video_config = build_pixelle_config(segments, config)
    segments_json = build_segments_json(segments)
    
    # 输出
    output_dir = os.path.dirname(args.output) or '.'
    os.makedirs(output_dir, exist_ok=True)
    
    video_path = f"{args.output}-video.json"
    seg_path = f"{args.output}-segments.json"
    
    with open(video_path, 'w', encoding='utf-8') as f:
        json.dump(video_config, f, ensure_ascii=False, indent=2)
    
    with open(seg_path, 'w', encoding='utf-8') as f:
        json.dump(segments_json, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 分镜数: {len(segments)}")
    print(f"✓ 视频配置: {video_path}")
    print(f"✓ TTS 清单:  {seg_path}")
    print()
    print("下一步:")
    print(f"  1. TTS 配音: bash tts-engine/pixelle-tts.sh <pixelle_dir> {seg_path} {args.voice}")
    print(f"  2. 在 Pixelle WebUI 中导入配置，或使用 API:")
    print(f"     curl -X POST http://localhost:8000/api/video/generate/async \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d @'{video_path}'")


if __name__ == '__main__':
    main()