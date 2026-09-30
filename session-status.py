#!/usr/bin/env python3
# Version: 0.1.0
"""session-status.py — 会话状态栏生成器

从 minis-sessions-cli 获取当前会话信息，统计工具调用、对话轮次、错误率，
并输出格式化状态栏（可选 JSON 模式）。

用法:
    python3 session-status.py                 # 文本状态栏
    python3 session-status.py --json          # JSON 模式
    python3 session-status.py --help          # 帮助信息
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime


def run_cmd(cmd: list[str]) -> tuple[str, str, int]:
    """运行命令，返回 (stdout, stderr, returncode)。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except Exception as e:
        return "", str(e), 1


def get_current_session_id() -> str | None:
    """从 minis-sessions-cli list 获取当前会话 ID。"""
    stdout, stderr, rc = run_cmd(["minis-sessions-cli", "list", "--json"])
    if rc != 0:
        # fallback: 尝试非 JSON 模式
        stdout, stderr, rc = run_cmd(["minis-sessions-cli", "list"])
        if rc != 0:
            print(f"[error] minis-sessions-cli list 失败: {stderr.strip() or stdout.strip()}", file=sys.stderr)
            return None
        # 表格模式：取第一条
        lines = [l.strip() for l in stdout.splitlines() if l.strip() and not l.startswith("---")]
        if lines:
            parts = lines[0].split("|")
            if len(parts) >= 2:
                sid = parts[1].strip()
                if sid:
                    return sid
        return None

    # JSON 模式：取最新活跃的会话
    try:
        data = json.loads(stdout)
        sessions = data.get("data", {}).get("sessions", []) if isinstance(data, dict) else []
        if sessions:
            # 按 last_active 降序排序，取最新的
            sessions.sort(key=lambda s: s.get("last_active", ""), reverse=True)
            sid = sessions[0].get("session_id", "")
            if sid:
                return sid
    except json.JSONDecodeError:
        pass
    return None


def get_session_messages(session_id: str) -> list[dict] | None:
    """获取会话消息列表。"""
    stdout, stderr, rc = run_cmd(
        ["minis-sessions-cli", "messages", "--id", session_id, "--full", "--limit", "100"]
    )
    if rc != 0:
        print(f"[error] 获取消息失败: {stderr.strip()}", file=sys.stderr)
        return None
    try:
        data = json.loads(stdout)
        # 新格式: {"action": "messages", "data": {"messages": [...]}}
        if isinstance(data, dict):
            msgs = data.get("data", {}).get("messages", [])
            return msgs if isinstance(msgs, list) else None
        # 旧格式: 直接是列表
        if isinstance(data, list):
            return data
    except json.JSONDecodeError as e:
        print(f"[warn] JSON 解析失败: {e}", file=sys.stderr)
    return None


def analyze_session(messages: list[dict], session_id: str = "") -> dict:
    """分析会话消息，返回统计结果。"""
    tool_calls: Counter = Counter()
    tool_errors: Counter = Counter()
    turns = 0
    total_tool_calls = 0
    total_errors = 0

    for msg in messages:
        role = msg.get("role", "")
        if role == "user":
            turns += 1
        elif role == "assistant":
            tool_calls_used = msg.get("tool_calls", [])
            for tc in tool_calls_used:
                name = tc.get("function", {}).get("name", "unknown")
                tool_calls[name] += 1
                total_tool_calls += 1
                # 检查是否有错误
                if tc.get("error") or tc.get("is_error", False):
                    tool_errors[name] += 1
                    total_errors += 1

    error_rate = (total_errors / total_tool_calls * 100) if total_tool_calls > 0 else 0.0
    top_tools = tool_calls.most_common(5)

    return {
        "session_id": session_id,
        "turns": turns,
        "total_tool_calls": total_tool_calls,
        "total_errors": total_errors,
        "error_rate": round(error_rate, 1),
        "tool_calls": dict(tool_calls),
        "tool_errors": dict(tool_errors),
        "top_tools": top_tools,
    }


def format_textbar(stats: dict) -> str:
    """生成格式化状态栏字符串。"""
    now = datetime.now().strftime("%H:%M:%S")
    top_tools_str = ", ".join(f"{name}:{count}" for name, count in stats["top_tools"])
    if not top_tools_str:
        top_tools_str = "无"

    lines = [
        "<agent_status>",
        f"当前会话: {stats['session_id'][:12]}...",
        f"总轮次: {stats['turns']} | 工具调用: {stats['total_tool_calls']} (错误: {stats['total_errors']})",
        f"高频工具: {top_tools_str}",
        f"错误率: {stats['error_rate']}%",
        f"生成时间: {now}",
        "</agent_status>",
    ]
    return "\n".join(lines)


def format_json(stats: dict) -> str:
    """生成 JSON 输出。"""
    output = {
        "session_id": stats["session_id"],
        "turns": stats["turns"],
        "total_tool_calls": stats["total_tool_calls"],
        "total_errors": stats["total_errors"],
        "error_rate_percent": stats["error_rate"],
        "tool_calls": stats["tool_calls"],
        "tool_errors": stats["tool_errors"],
        "top_tools": stats["top_tools"],
        "generated_at": datetime.now().isoformat(),
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="会话状态栏生成器 — 统计当前会话的工具调用、轮次和错误率",
        epilog="示例: python3 session-status.py --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_mode",
        help="以 JSON 格式输出",
    )
    args = parser.parse_args()

    # Step 1: 获取当前会话 ID
    session_id = get_current_session_id()
    if not session_id:
        print("[error] 无法获取当前会话 ID", file=sys.stderr)
        sys.exit(1)

    # Step 2: 获取消息
    messages = get_session_messages(session_id)
    if messages is None:
        print("[error] 无法获取会话消息", file=sys.stderr)
        sys.exit(1)

    # Step 3: 分析
    stats = analyze_session(messages, session_id)

    # Step 4: 输出
    if args.json_mode:
        print(format_json(stats))
    else:
        print(format_textbar(stats))


if __name__ == "__main__":
    main()
