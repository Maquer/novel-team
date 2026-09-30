#!/usr/bin/env python3
# Version: 0.1.0
"""
session-status-generator.py — 自动状态文件生成器

定期运行 session-status.py 并将结果保存到固定位置，
供 Agent 在会话启动时读取并注入上下文。

用法:
    python3 session-status-generator.py          # 生成一次
    python3 session-status-generator.py --interval 300  # 持续运行（每 N 秒）
    python3 session-status-generator.py --help
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

STATUS_DIR = "/var/minis/shared"
STATUS_JSON = os.path.join(STATUS_DIR, ".session-status.json")
STATUS_TXT = os.path.join(STATUS_DIR, ".session-status.txt")
STATUS_META = os.path.join(STATUS_DIR, ".session-status-meta.json")

STATUS_SCRIPT = os.path.join(STATUS_DIR, "session-status.py")


def generate_once() -> bool:
    """运行 session-status.py 并保存结果。"""
    try:
        result = subprocess.run(
            ["python3", STATUS_SCRIPT, "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip()
            # 保存 JSON
            with open(STATUS_JSON, 'w', encoding='utf-8') as f:
                json.dump({
                    "generated_at": datetime.now().isoformat(),
                    "raw": raw
                }, f, ensure_ascii=False, indent=2)
            # 保存文本
            with open(STATUS_TXT, 'w', encoding='utf-8') as f:
                f.write(raw)
            # 保存元数据
            with open(STATUS_META, 'w', encoding='utf-8') as f:
                json.dump({
                    "generated_at": datetime.now().isoformat(),
                    "source": "session-status.py --json",
                    "status_json": STATUS_JSON,
                    "status_txt": STATUS_TXT,
                }, f, ensure_ascii=False, indent=2)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 状态文件已更新")
            return True

        # fallback: 文本模式
        result = subprocess.run(
            ["python3", STATUS_SCRIPT],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip()
            with open(STATUS_JSON, 'w', encoding='utf-8') as f:
                json.dump({
                    "generated_at": datetime.now().isoformat(),
                    "raw": raw
                }, f, ensure_ascii=False, indent=2)
            with open(STATUS_TXT, 'w', encoding='utf-8') as f:
                f.write(raw)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 状态文件已更新（文本模式）")
            return True

        print(f"[error] session-status.py 失败: {result.stderr}", file=sys.stderr)
        return False

    except subprocess.TimeoutExpired:
        print("[error] session-status.py 超时", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[error] 生成状态文件失败: {e}", file=sys.stderr)
        return False


def generate_loop(interval: int = 300):
    """持续运行，每 interval 秒生成一次。"""
    print(f"🔄 状态生成循环启动，间隔 {interval}s")
    while True:
        generate_once()
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="自动状态文件生成器 — 定期生成 session-status 文件",
        epilog="示例:\n  python3 session-status-generator.py\n  python3 session-status-generator.py --interval 300",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--interval", type=int, default=0,
                        help="持续运行间隔（秒），0=仅生成一次")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.interval > 0:
        generate_loop(args.interval)
    else:
        success = generate_once()
        if args.json:
            print(json.dumps({"success": success}, ensure_ascii=False))
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
