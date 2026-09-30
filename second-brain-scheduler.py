#!/usr/bin/env python3
# Version: 0.1.0
"""
第二大脑事件调度器 — 借鉴 Hermes cron/webhook 设计

三层触发机制：
  1. 定时任务 (cron-like) — 按频率触发训练/蒸馏/审核
  2. 事件钩子 (webhook-like) — 文件变更/对话结束触发
  3. 队列 (queue) — 后台待执行任务堆积

iOS 约束：iSH 无法常驻，真实定时需 Apple Shortcuts。
调度器负责"定义 + 检查 + 排队"，下次对话打开时自动执行到期任务。

用法:
  python3 /var/minis/shared/second-brain-scheduler.py check       # 检查到期任务并执行
  python3 /var/minis/shared/second-brain-scheduler.py add <name>  # 添加定时任务
  python3 /var/minis/shared/second-brain-scheduler.py list        # 查看任务列表
  python3 /var/minis/shared/second-brain-scheduler.py status      # 查看运行状态
  python3 /var/minis/shared/second-brain-scheduler.py --json      # JSON 输出
"""

import json, os, sys, subprocess, shlex
from datetime import datetime, timedelta
from pathlib import Path

STATE_DIR = "/var/minis/shared/.scheduler"
STATE_FILE = f"{STATE_DIR}/scheduler.json"
LOG_FILE = f"{STATE_DIR}/scheduler.log"
QUEUE_FILE = f"{STATE_DIR}/queue.json"
OBSIDIAN_ROOT = "/var/minis/mounts/loong"

DEFAULT_TASKS = [
    {
        "name": "pulse",
        "label": "训练脉冲",
        "command": "bash /var/minis/shared/second-brain-pulse.sh",
        "interval_hours": 12,
        "description": "轻量训练脉冲，采样关键指标+异常检测",
        "enabled": True,
    },
    {
        "name": "auto-learn",
        "label": "自动学习",
        "command": "python3 /var/minis/shared/obsidian-auto-learn.py",
        "interval_hours": 24,
        "description": "扫描Obsidian新笔记→摩擦度评分→蒸馏→审核→归档",
        "enabled": True,
    },
    {
        "name": "distill-review",
        "label": "卡片审核",
        "command": "python3 /var/minis/shared/obsidian-distill.py --review",
        "interval_hours": 72,
        "description": "检查待审核知识卡片",
        "enabled": True,
    },
    {
        "name": "tag-audit",
        "label": "标签审计",
        "command": "python3 /var/minis/shared/obsidian-tag.py --suggest",
        "interval_hours": 168,
        "description": "扫描缺标签笔记，建议标签",
        "enabled": True,
    },
    {
        "name": "blindspot",
        "label": "认知盲区",
        "command": "python3 /var/minis/shared/obsidian-blindspot.py",
        "interval_hours": 168,
        "description": "每周扫描认知盲区和浅涉领域",
        "enabled": False,
    },
    {
        "name": "model-watchdog",
        "label": "模型健康检测",
        "command": "python3 /var/minis/shared/model-watchdog.py check --quiet",
        "interval_hours": 6,
        "description": "已由独立 minis-scheduled 任务(08AE0260)覆盖，此处禁用避免 scheduler check 超时",
        "enabled": False,
    },
    {
        "name": "dreaming",
        "label": "记忆固化",
        "command": "python3 /var/minis/shared/obsidian-dreaming.py --report --archive --link --dry-run",
        "interval_hours": 168,
        "description": "每周离线记忆整理：标签冗余/近重复/张力/陈旧/孤立/补链接（dry-run 只出报告）",
        "enabled": True,
    },
]

EVENT_HOOKS = [
    {
        "name": "archive-article",
        "label": "归档新文章",
        "trigger": "file_create",
        "path_pattern": "03-Resources/公众号文章/*.md",
        "command": "python3 /var/minis/shared/obsidian-distill.py --from-file {path}",
        "description": "新文章归档后自动蒸馏知识卡片",
        "enabled": True,
    },
    {
        "name": "archive-tool",
        "label": "归档新工具",
        "trigger": "file_create",
        "path_pattern": "03-Resources/AI工具/*.md",
        "command": "python3 /var/minis/shared/obsidian-distill.py --from-file {path}",
        "description": "新工具归档后自动蒸馏知识卡片",
        "enabled": True,
    },
    {
        "name": "post-bridge",
        "label": "桥接后训练",
        "trigger": "session_start",
        "path_pattern": None,
        "command": "bash /var/minis/shared/second-brain-pulse.sh",
        "description": "每次对话开始时跑一次轻量脉冲",
        "enabled": True,
    },
]


def load_state():
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"tasks": DEFAULT_TASKS, "events": EVENT_HOOKS, "history": []}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def log(msg):
    os.makedirs(STATE_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{ts}] {msg}\n")


def load_queue():
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []


def save_queue(queue):
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def add_task(state, task_def):
    state["tasks"].append(task_def)
    save_state(state)
    log(f"TASK_ADDED: {task_def['name']}")
    return f"✅ 任务 '{task_def['name']}' ({task_def['label']}) 已添加"


def list_tasks(state):
    lines = ["📋 定时任务列表", "=" * 40]
    for t in state["tasks"]:
        status = "✅" if t.get("enabled") else "⏸️"
        last = t.get("last_run", "从未")
        lines.append(f"  {status} {t['name']:20s} | {t['label']:8s} | 每 {t['interval_hours']}h | 上次: {last}")
    lines.append("")
    lines.append("📋 事件钩子列表")
    lines.append("=" * 40)
    for e in state["events"]:
        status = "✅" if e.get("enabled") else "⏸️"
        trigger = e.get("trigger", "?")
        lines.append(f"  {status} {e['name']:20s} | {e['label']:8s} | 触发: {trigger}")
    return "\n".join(lines)


def check_tasks(state):
    """检查哪些任务到期了，执行并记录"""
    now = datetime.now()
    due_tasks = []
    results = []

    for task in state["tasks"]:
        if not task.get("enabled"):
            continue
        interval = task.get("interval_hours", 24)
        last_run = task.get("last_run")
        if last_run:
            last = datetime.fromisoformat(last_run)
            if (now - last).total_seconds() < interval * 3600:
                continue
        due_tasks.append(task)

    if not due_tasks:
        return None, results

    for task in due_tasks:
        cmd = task["command"]
        name = task["name"]
        log(f"RUNNING: {name} — {cmd}")
        task["last_run"] = now.isoformat()

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120
            )
            summary = result.stdout.strip()[:200] if result.stdout.strip() else ""
            exit_code = result.returncode
            status = "✅" if exit_code == 0 else "⚠️"
            results.append({
                "task": name,
                "label": task["label"],
                "status": status,
                "exit_code": exit_code,
                "summary": summary,
                "ran_at": now.isoformat(),
            })
            log(f"RESULT: {name} {status} (exit={exit_code})")
        except subprocess.TimeoutExpired:
            results.append({"task": name, "label": task["label"], "status": "⏰", "exit_code": -1, "summary": "超时120s"})
            log(f"TIMEOUT: {name}")
        except Exception as e:
            results.append({"task": name, "label": task["label"], "status": "❌", "exit_code": -1, "summary": str(e)})
            log(f"ERROR: {name} — {e}")

    state["history"] = state.get("history", []) + results
    state["history"] = state["history"][-100:]
    save_state(state)
    return due_tasks, results


def check_events(state):
    """检查事件钩子：检测新文件变更"""
    results = []
    for hook in state.get("events", []):
        if not hook.get("enabled") or hook.get("trigger") != "file_create":
            continue
        pattern = hook.get("path_pattern", "")
        command_tpl = hook.get("command", "")
        full_pattern = f"{OBSIDIAN_ROOT}/{pattern}"
        matched = list(Path(OBSIDIAN_ROOT).glob(pattern.replace("*", "*")))
        # 简化：只检查最近5分钟内有变更的
        for f in matched:
            if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() < 300:
                cmd = command_tpl.replace("{path}", str(f))
                log(f"EVENT_HOOK: {hook['name']} triggered by {f.name}")
                results.append({"hook": hook["name"], "file": f.name, "command": cmd})
    return results


def queue_task(task_name):
    """将任务加入队列（对话结束时触发）"""
    queue = load_queue()
    queue.append({"task": task_name, "queued_at": datetime.now().isoformat()})
    save_queue(queue)
    log(f"QUEUED: {task_name}")
    return f"✅ '{task_name}' 已加入队列"


def show_status(state):
    lines = ["📊 调度器状态", "=" * 40]
    for t in state["tasks"]:
        last = t.get("last_run", "从未")
        status = "✅" if t.get("enabled") else "⏸️"
        next_run = "—"
        if last != "从未" and t.get("enabled"):
            try:
                lt = datetime.fromisoformat(last)
                interval = timedelta(hours=t["interval_hours"])
                nr = lt + interval
                if nr < datetime.now():
                    next_run = "⏰ 已到期"
                else:
                    next_run = nr.strftime('%m-%d %H:%M')
            except:
                next_run = "—"
        lines.append(f"  {status} {t['name']:20s} | 上次: {last:20s} | 下次: {next_run}")

    # 队列
    queue = load_queue()
    if queue:
        lines.append("")
        lines.append(f"📥 待执行队列 ({len(queue)} 项)")
        for q in queue:
            lines.append(f"     {q['task']} ({q['queued_at']})")

    return "\n".join(lines)


def main():
    state = load_state()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: scheduler.py <check|add|list|status|queue>"}))
        sys.exit(1)

    cmd = sys.argv[1]
    use_json = "--json" in sys.argv

    if cmd == "check":
        due, results = check_tasks(state)
        events = check_events(state)
        if not results and not events:
            print("⏳ 没有到期任务，系统正常")
        else:
            if results:
                print(f"🏃 执行了 {len(results)} 个到期任务：")
                for r in results:
                    print(f"  {r['status']} {r['task']} ({r['label']}) — {r.get('summary','')}")
            if events:
                print(f"🔗 触发了 {len(events)} 个事件钩子：")
                for e in events:
                    print(f"  {e['hook']}: {e['file']}")
    elif cmd == "list":
        print(list_tasks(state))
    elif cmd == "status":
        print(show_status(state))
    elif cmd == "add":
        if len(sys.argv) < 4:
            print("Usage: scheduler.py add <name> <command> [--interval-hours N] [--label L]")
            sys.exit(1)
        name = sys.argv[2]
        command = sys.argv[3]
        interval = 24
        label = name
        for i, a in enumerate(sys.argv[4:], 4):
            if a == "--interval-hours" and i+1 < len(sys.argv):
                interval = int(sys.argv[i+1])
            elif a == "--label" and i+1 < len(sys.argv):
                label = sys.argv[i+1]
        task_def = {"name": name, "label": label, "command": command, "interval_hours": interval, "description": "", "enabled": True}
        msg = add_task(state, task_def)
        print(msg)
    elif cmd == "queue":
        if len(sys.argv) < 3:
            print("Usage: scheduler.py queue <task_name>")
            sys.exit(1)
        msg = queue_task(sys.argv[2])
        print(msg)
    elif cmd == "disable":
        if len(sys.argv) < 3:
            print("Usage: scheduler.py disable <task_name>")
            sys.exit(1)
        for t in state["tasks"]:
            if t["name"] == sys.argv[2]:
                t["enabled"] = False
                save_state(state)
                print(f"⏸️ '{t['name']}' 已禁用")
                return
        print(f"❌ 任务 '{sys.argv[2]}' 未找到")
    elif cmd == "enable":
        if len(sys.argv) < 3:
            print("Usage: scheduler.py enable <task_name>")
            sys.exit(1)
        for t in state["tasks"]:
            if t["name"] == sys.argv[2]:
                t["enabled"] = True
                save_state(state)
                print(f"✅ '{t['name']}' 已启用")
                return
        print(f"❌ 任务 '{sys.argv[2]}' 未找到")
    else:
        print(f"未知命令: {cmd}")
        print("用法: check | list | status | add | queue | enable | disable")


if __name__ == "__main__":
    main()