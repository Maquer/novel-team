#!/usr/bin/env python3
# Version: 0.1.0
"""
pixelle-client.py — Pixelle-Video API 客户端

通过 HTTP 调用已部署的 Pixelle-Video API 进行视频生成。
支持同步/异步模式、任务状态查询、结果获取。

用法:
  # 异步生成视频（推荐）
  python3 pixelle-client.py generate --config pixelle-config-video.json --pixelle http://localhost:8000

  # 查询任务状态
  python3 pixelle-client.py status --task-id <uuid> --pixelle http://localhost:8000

  # 生成文案分段
  python3 pixelle-client.py narrate --text "主题内容" --scenes 5 --pixelle http://localhost:8000

Pixelle API 端点:
  POST /api/video/generate/sync    — 同步生成（< 30s 视频）
  POST /api/video/generate/async   — 异步生成（推荐，支持长视频）
  GET  /api/tasks/{task_id}        — 查询任务状态
  POST /api/content/narration      — 文案分段
  POST /api/content/image-prompt   — 配图提示词
  POST /api/content/title          — 视频标题
  POST /api/tts/synthesize         — TTS 合成
  GET  /health                     — 健康检查
"""

import json
import sys
import time
import argparse
import urllib.request
import urllib.error


def api_call(pixelle_url, method, path, data=None, timeout=300):
    """发起 API 调用"""
    url = f"{pixelle_url.rstrip('/')}{path}"
    
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header('Content-Type', 'application/json')
    else:
        req = urllib.request.Request(url, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        print(f"❌ HTTP {e.code}: {error_body[:500]}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ 无法连接到 Pixelle: {e.reason}")
        print(f"   确保 Pixelle 正在运行: {pixelle_url}")
        sys.exit(1)


def cmd_health(pixelle_url):
    """健康检查"""
    print("🔍 健康检查...")
    result = api_call(pixelle_url, 'GET', '/health')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_generate(pixelle_url, config_file, sync=False):
    """生成视频"""
    if not config_file or not os.path.exists(config_file):
        print(f"❌ 配置文件不存在: {config_file}")
        sys.exit(1)
    
    with open(config_file) as f:
        config = json.load(f)
    
    endpoint = '/api/video/generate/sync' if sync else '/api/video/generate/async'
    print(f"🚀 提交视频生成任务 ({'同步' if sync else '异步'} mode)...")
    
    result = api_call(pixelle_url, 'POST', endpoint, config, timeout=600)
    
    if sync:
        print("✓ 视频生成完成")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        task_id = result.get('task_id') or result.get('id') or result.get('data', {}).get('task_id')
        if task_id:
            print(f"✓ 任务已提交: {task_id}")
            print("  使用以下命令查询进度:")
            print(f"  python3 pixelle-client.py status --task-id {task_id} --pixelle {pixelle_url}")
        else:
            print("⚠️ 未获取到 task_id，完整响应:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result


def cmd_status(pixelle_url, task_id):
    """查询任务状态"""
    print(f"📊 查询任务 {task_id}...")
    result = api_call(pixelle_url, 'GET', f'/api/tasks/{task_id}')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_narrate(pixelle_url, text, scenes, min_words, max_words):
    """生成文案分段"""
    print(f"✍️  生成 {scenes} 段文案...")
    data = {
        'text': text,
        'n_scenes': scenes,
        'min_words': min_words,
        'max_words': max_words
    }
    result = api_call(pixelle_url, 'POST', '/api/content/narration', data)
    narrations = result.get('narrations', [])
    print(f"✓ 生成 {len(narrations)} 段文案:")
    for i, n in enumerate(narrations, 1):
        print(f"  [{i}] {n[:80]}...")
    return narrations


def cmd_title(pixelle_url, text, style=''):
    """生成视频标题"""
    print("📝 生成视频标题...")
    data = {'text': text}
    if style:
        data['style'] = style
    result = api_call(pixelle_url, 'POST', '/api/content/title', data)
    print(f"✓ 标题: {result.get('title', result)}")
    return result


def cmd_tts(pixelle_url, text, workflow='', ref_audio=''):
    """TTS 语音合成"""
    print("🔊 TTS 合成...")
    data = {'text': text}
    if workflow:
        data['workflow'] = workflow
    if ref_audio:
        data['ref_audio'] = ref_audio
    result = api_call(pixelle_url, 'POST', '/api/tts/synthesize', data)
    print(f"✓ 音频: {result.get('audio_path', 'unknown')}")
    print(f"✓ 时长: {result.get('duration', 'unknown')}")
    return result


def cmd_poll(pixelle_url, task_id, interval=10, max_wait=3600):
    """轮询任务状态直到完成"""
    print(f"⏳ 轮询任务 {task_id} (间隔 {interval}s, 最多 {max_wait}s)...")
    elapsed = 0
    
    while elapsed < max_wait:
        result = api_call(pixelle_url, 'GET', f'/api/tasks/{task_id}')
        status = result.get('status', 'unknown')
        progress = result.get('progress', {})
        current = progress.get('current_step', '')
        total = progress.get('total_steps', '')
        
        bar = f" [{current}/{total}]" if current and total else ""
        print(f"  {status}{bar}", end='\r')
        
        if status == 'COMPLETED':
            print()
            output = result.get('result', {}).get('output_path', '')
            print(f"✓ 完成! 输出: {output}")
            return result
        elif status == 'FAILED':
            print()
            error = result.get('error', 'unknown error')
            print(f"❌ 失败: {error}")
            return result
        
        time.sleep(interval)
        elapsed += interval
    
    print()
    print(f"⚠️ 超时 ({max_wait}s)，任务仍在运行")
    return None


def main():
    parser = argparse.ArgumentParser(description='Pixelle-Video API 客户端')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # health
    p_health = subparsers.add_parser('health', help='健康检查')
    
    # generate
    p_gen = subparsers.add_parser('generate', help='生成视频')
    p_gen.add_argument('--config', required=True, help='视频配置文件')
    p_gen.add_argument('--sync', action='store_true', help='同步模式（默认异步）')
    
    # status
    p_status = subparsers.add_parser('status', help='查询任务状态')
    p_status.add_argument('--task-id', required=True, help='任务 ID')
    
    # poll
    p_poll = subparsers.add_parser('poll', help='轮询任务直到完成')
    p_poll.add_argument('--task-id', required=True, help='任务 ID')
    p_poll.add_argument('--interval', type=int, default=10, help='轮询间隔(秒)')
    p_poll.add_argument('--max-wait', type=int, default=3600, help='最大等待(秒)')
    
    # narrate
    p_narr = subparsers.add_parser('narrate', help='生成文案分段')
    p_narr.add_argument('--text', required=True, help='输入文本')
    p_narr.add_argument('--scenes', type=int, default=5, help='分段数')
    p_narr.add_argument('--min-words', type=int, default=50, help='每段最小字数')
    p_narr.add_argument('--max-words', type=int, default=150, help='每段最大字数')
    
    # title
    p_title = subparsers.add_parser('title', help='生成视频标题')
    p_title.add_argument('--text', required=True, help='输入文本')
    p_title.add_argument('--style', default='', help='风格提示')
    
    # tts
    p_tts = subparsers.add_parser('tts', help='TTS 语音合成')
    p_tts.add_argument('--text', required=True, help='输入文本')
    p_tts.add_argument('--workflow', default='', help='TTS 工作流')
    p_tts.add_argument('--ref-audio', default='', help='参考音频路径')
    
    # 全局参数
    parser.add_argument('--pixelle', default='http://localhost:8000', help='Pixelle API 地址')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    pixelle_url = args.pixelle
    
    if args.command == 'health':
        cmd_health(pixelle_url)
    elif args.command == 'generate':
        cmd_generate(pixelle_url, args.config, args.sync)
    elif args.command == 'status':
        cmd_status(pixelle_url, args.task_id)
    elif args.command == 'poll':
        cmd_poll(pixelle_url, args.task_id, args.interval, args.max_wait)
    elif args.command == 'narrate':
        cmd_narrate(pixelle_url, args.text, args.scenes, args.min_words, args.max_words)
    elif args.command == 'title':
        cmd_title(pixelle_url, args.text, args.style)
    elif args.command == 'tts':
        cmd_tts(pixelle_url, args.text, args.workflow, args.ref_audio)


if __name__ == '__main__':
    import os
    main()