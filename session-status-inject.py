#!/usr/bin/env python3
# Version: 0.1.0
"""
session-status-inject.py — 状态注入脚本

读取最新状态文件并格式化为可注入 Agent 上下文的文本。
在会话启动时由 Agent 调用，实现"动态后缀追加"。

用法:
    python3 session-status-inject.py           # 输出格式化状态
    python3 session-status-inject.py --json     # JSON 模式
    python3 session-status-inject.py --help
"""
import argparse
import json
import os
import sys
from datetime import datetime

STATUS_JSON = "/var/minis/shared/.session-status.json"
STATUS_TXT = "/var/minis/shared/.session-status.txt"
STATUS_META = "/var/minis/shared/.session-status-meta.json"


def read_status() -> dict | None:
    """读取最新状态数据。"""
    if os.path.exists(STATUS_JSON):
        try:
            with open(STATUS_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[warn] 读取状态文件失败: {e}", file=sys.stderr)
    return None


def format_for_context(status_data: dict) -> str:
    """将状态数据格式化为可注入上下文的文本块。

    设计原则：
    - 用 <agent_status> 标签包裹，明确边界
    - 位于系统提示词之后（动态后缀）
    - 内容精简，不增加过多 token
    """
    if not status_data:
        return ""

    raw = status_data.get("raw", "")
    generated = status_data.get("generated_at", "")

    # 尝试解析 JSON 状态
    try:
        status = json.loads(raw) if raw.startswith('{') else None
    except Exception:
        status = None

    now = datetime.now().strftime("%H:%M:%S")
    age_str = ""
    if generated:
        try:
            gen_time = datetime.fromisoformat(generated)
            age_sec = (datetime.now() - gen_time).total_seconds()
            age_str = f" (延迟 {int(age_sec)}s)"
        except Exception:
            pass

    if status:
        top_tools = status.get("top_tools", [])
        tools_str = ", ".join(f"{n}:{c}" for n, c in top_tools) or "无"
        sid = status.get('session_id', 'N/A')
        sid_display = f"{sid[:8]}...{sid[-4:]}" if len(sid) > 12 else sid

        lines = [
            "<agent_status>",
            f"⏰ {now}{age_str}",
            f"📌 会话: {sid_display}",
            f"📊 轮次: {status.get('turns', 0)} | 工具: {status.get('total_tool_calls', 0)} (❌{status.get('total_errors', 0)})",
            f"📈 错误率: {status.get('error_rate_percent', 0)}%",
            f"🔧 高频: {tools_str}",
            "</agent_status>",
        ]
        return "\n".join(lines)

    # fallback: 直接输出原始文本
    return f"<agent_status>\n{raw}\n</agent_status>"


def main():
    parser = argparse.ArgumentParser(
        description="状态注入脚本 — 读取状态文件并格式化为上下文文本",
        epilog="示例: python3 session-status-inject.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    status_data = read_status()
    if not status_data:
        msg = "[warn] 状态文件不存在，请先运行 session-status-generator.py"
        if args.json:
            print(json.dumps({"error": msg}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)

    formatted = format_for_context(status_data)

    if args.json:
        print(json.dumps({
            "formatted": formatted,
            "generated_at": status_data.get("generated_at"),
            "source": "session-status-inject.py",
        }, ensure_ascii=False, indent=2))
    else:
        print(formatted)


if __name__ == "__main__":
    main()
