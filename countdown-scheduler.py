#!/usr/bin/env python3
# Version: 0.1.0
"""
倒计时调度器 — 墙钟倒计时 + minis 存活执行 + 死亡后补跑

核心原则:
  - 任务用 wall clock 定义 next_fire_at = now + countdown_seconds
  - minis 存活: heartbeat minis-scheduled 任务定期 check, 到点即触发
  - minis 死亡: 任务状态持久化在 JSON, 不丢失
  - 下次启动: check --catchup 扫描所有到期任务, 按 next_fire_at 顺序补跑

两种任务类型:
  kind=shell   直接 subprocess 跑命令 (适合第二大脑脚本)
  kind=prompt  通过 minis-scheduled 触发 LLM 会话 (适合需要判断的任务)

用法:
  countdown-scheduler.py list              查看所有任务 + 倒计时
  countdown-scheduler.py add --name X --countdown 12h --kind shell --command "..."
  countdown-scheduler.py add --name X --countdown 30m --kind prompt --prompt "..."
  countdown-scheduler.py check             检查到期任务, 最多跑 1 个 (heartbeat 用)
  countdown-scheduler.py check --catchup   启动补跑, 按 next_fire_at 顺序跑所有到期
  countdown-scheduler.py remove --id X     删除任务
  countdown-scheduler.py enable/disable --id X
  countdown-scheduler.py status            系统状态摘要
  countdown-scheduler.py migrate           从 second-brain-scheduler 迁移
"""

import json, os, sys, subprocess, shlex, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEDULER_DIR = "/var/minis/shared/.scheduler"

STATE_DIR = Path("/var/minis/shared/.scheduler")
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "countdown-tasks.json"
TZ = timezone(timedelta(hours=8))  # Asia/Shanghai


def now():
    return datetime.now(TZ)


def parse_time(s):
    if s.endswith("Z"):
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)
    d = datetime.fromisoformat(s)
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)


def load():
    if not STATE_FILE.exists():
        return {"tasks": [], "history": [], "created_at": now().isoformat()}
    return json.loads(STATE_FILE.read_text())


def save(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    os.replace(tmp, STATE_FILE)
    _sync_to_worker(state)


def _sync_to_worker(state):
    """任务变更后自动同步到 Cloudflare Worker（best-effort，失败不影响本地操作）"""
    import urllib.request
    worker_url = os.environ.get("WORKER_URL")
    auth_token = os.environ.get("WORKER_AUTH_TOKEN")
    if not worker_url or not auth_token:
        return  # 环境变量未配，跳过
    tasks = []
    for t in state.get("tasks", []):
        if not t.get("enabled", True):
            continue
        tasks.append({
            "tag": f"TASK:{t['name']}",
            "body": t.get("description") or t["name"],
            "params": {
                "isArchive": 1,
                "group": "cloudflare-cron",
                "level": "timeSensitive",
                "copy": t.get("command", ""),
                "url": "minis://open_terminal"
            }
        })
    payload = json.dumps({"tasks": tasks}).encode("utf-8")
    url = worker_url.rstrip("/") + "/sync"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {auth_token}")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass  # best-effort，同步失败不影响本地任务操作


def parse_duration(s):
    s = s.strip().lower()
    if s.endswith("w"): return int(float(s[:-1]) * 86400 * 7)
    if s.endswith("d"): return int(float(s[:-1]) * 86400)
    if s.endswith("h"): return int(float(s[:-1]) * 3600)
    if s.endswith("m"): return int(float(s[:-1]) * 60)
    if s.endswith("s"): return int(float(s[:-1]))
    raise ValueError(f"Cannot parse duration: {s}")


def fmt_eta(seconds):
    if seconds <= 0: return "due!"
    d = int(seconds // 86400); h = int((seconds % 86400) // 3600); m = int((seconds % 3600) // 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m or not parts: parts.append(f"{m}m")
    return " ".join(parts)


def _retry_pending_prompts():
    """Process prompts queued in pending-prompts.jsonl from previous failed
    attempts. Tries minis-scheduled first; removes the entry only on success.
    Returns the number of entries retried."""
    if not os.path.exists(PENDING_PROMPTS):
        return 0
    retried = 0
    remaining = []
    try:
        with open(PENDING_PROMPTS) as f:
            entries = [line.strip() for line in f if line.strip()]
    except Exception:
        return 0
    for raw in entries:
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        retried += 1
        cmd = (f'minis-scheduled create --prompt {shlex.quote(entry["prompt"])} '
               f'--trigger once --after 1s --target {entry.get("target", "new")}')
        if entry.get("label"):
            cmd += f' --label {shlex.quote(entry["label"])}'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"   🔄 retried pending prompt: {entry.get('label','(unnamed)')}")
                continue  # success → drop from pending
        except Exception:
            pass
        # Failed again → keep in pending for next retry
        remaining.append(raw)
    try:
        with open(PENDING_PROMPTS, "w") as f:
            f.write("\n".join(remaining) + ("\n" if remaining else ""))
    except Exception:
        pass
    return retried


def fire_task(task, env=None):
    kind = task.get("kind", "shell")
    started = now()
    timeout = task.get("timeout", 300)
    try:
        if kind == "shell":
            result = subprocess.run(task["command"], shell=True,
                                    capture_output=True, text=True, timeout=timeout,
                                    env=env)
            summary = (result.stdout + "\n---STDERR---\n" + result.stderr)[:1500]
            return {
                "status": "ok" if result.returncode == 0 else "fail",
                "exit_code": result.returncode,
                "summary": summary,
                "ran_at": started.isoformat(),
                "duration_ms": None,
            }
        elif kind == "prompt":
            target = task.get("target", "new")
            label = task.get("name", "")
            prompt = task["prompt"]
            # Write to pending-prompts.jsonl as the reliable delivery channel.
            # The prompt will be picked up at the next session start (or by a
            # future check run that processes the pending file).
            entry = json.dumps({
                "prompt": prompt,
                "target": target,
                "label": label,
                "task": task["name"],
                "task_id": task["id"],
                "enqueued_at": started.isoformat(),
            }, ensure_ascii=False)
            try:
                with open(PENDING_PROMPTS, "a") as f:
                    f.write(entry + "\n")
                pending_ok = True
            except Exception as e:
                pending_ok = False
            # Also try minis-scheduled as a best-effort fast path.
            cmd = f'minis-scheduled create --prompt {shlex.quote(prompt)} --trigger once --after 1s --target {target}'
            if label:
                cmd += f' --label {shlex.quote(label + "-catchup-" + started.strftime("%Y%m%d-%H%M"))}'
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, env=env)
                ms_ok = result.returncode == 0
            except Exception:
                ms_ok = False
            return {
                "status": "ok" if pending_ok else "fail",
                "exit_code": 0 if pending_ok else -1,
                "summary": f"pending={pending_ok} minis-scheduled={ms_ok} enqueued_to={PENDING_PROMPTS}",
                "ran_at": started.isoformat(),
                "duration_ms": None,
            }
        else:
            return {"status": "fail", "exit_code": -1, "summary": f"Unknown kind: {kind}",
                    "ran_at": started.isoformat(), "duration_ms": None}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "exit_code": -2, "summary": f"Timeout after {timeout}s",
                "ran_at": started.isoformat(), "duration_ms": None}
    except Exception as e:
        return {"status": "fail", "exit_code": -1, "summary": f"Error: {e}",
                "ran_at": started.isoformat(), "duration_ms": None}


CHECK_LOCK = f"{SCHEDULER_DIR}/countdown-scheduler-check.lock"
PENDING_PROMPTS = f"{SCHEDULER_DIR}/pending-prompts.jsonl"


def cmd_check(catchup=False):
    """Check and run due tasks. If --catchup, run all overdue tasks.
    Uses a lock file to prevent concurrent execution (e.g. two sessions starting at once)."""
    # Lock file: prevent concurrent check runs
    if os.path.exists(CHECK_LOCK):
        try:
            with open(CHECK_LOCK) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # check if process still exists
            print(f"Another check is already running (pid {pid}), exiting.")
            return 1
        except (ValueError, OSError):
            pass  # stale lock, remove it
    with open(CHECK_LOCK, 'w') as f:
        f.write(str(os.getpid()))
    try:
        state = load()
        now_ts = now()

        # --- Retry pending prompts from previous failed attempts ---
        pending_retried = _retry_pending_prompts()

        due = [t for t in state["tasks"]
               if t.get("enabled", True) and parse_time(t["next_fire_at"]) <= now_ts]
        due.sort(key=lambda t: parse_time(t["next_fire_at"]))

        if not due:
            print("✅ No tasks due" + (f" ({pending_retried} pending prompts retried)" if pending_retried else ""))
            return 0

        if not catchup:
            # heartbeat 模式: 只跑最紧迫的 1 个, 避免堆积
            to_fire = due[:1]
            skipped = len(due) - 1
        else:
            # catchup 模式: 按 next_fire_at 顺序跑全部
            to_fire = due
            skipped = 0

        fired = 0
        failed = 0
        for t in to_fire:
            overdue = (now_ts - parse_time(t["next_fire_at"])).total_seconds()
            print(f"\n🔥 Firing: {t['name']} [{t.get('kind','shell')}] (overdue {int(overdue)}s)")
            result = fire_task(t)
            t["last_run"] = result["ran_at"]
            t["last_status"] = result["status"]
            t["fired_count"] = t.get("fired_count", 0) + 1
            # 推进到 now + countdown (丢弃中间积压, 避免堆积)
            t["next_fire_at"] = (now_ts + timedelta(seconds=t["countdown_seconds"])).isoformat()
            state["history"].append({"task": t["name"], **result})
            state["history"] = state["history"][-100:]
            if result["status"] == "ok":
                fired += 1
                t["retry_count"] = 0  # reset retry counter on success
                print(f"   ✅ {t['name']} done, next: {fmt_eta(t['countdown_seconds'])} later")
            else:
                failed += 1
                rc = t.get("retry_count", 0) + 1
                t["retry_count"] = rc
                if rc >= 3:
                    # Give up after 3 consecutive failures; disable to avoid
                    # burning cycles on a permanently broken task.
                    t["enabled"] = False
                    print(f"   💀 {t['name']} failed {rc} times, auto-disabled. Fix and re-enable.")
                else:
                    # Back off the next fire so the task can be retried later
                    # without piling up in the same catchup window.
                    t["next_fire_at"] = (now_ts + timedelta(seconds=60 * rc)).isoformat()
                    print(f"   ❌ {t['name']} failed (retry {rc}/3, next in {60*rc}m): {result['summary'][:200]}")

        save(state)
        print(f"\n📊 Fired {fired} ok, {failed} failed" + (f", {skipped} skipped (heartbeat mode)" if skipped else ""))
        return 0 if failed == 0 else 1
    finally:
        try:
            os.unlink(CHECK_LOCK)
        except OSError:
            pass


def cmd_list():
    state = load()
    now_ts = now()
    tasks = state["tasks"]
    if not tasks:
        print("(no tasks)")
        return
    print(f"{'Status':6s} {'Name':22s} {'Kind':6s} {'Countdown':10s} {'Next Fire':12s} {'Fired':6s} {'Mode'}")
    print("-" * 82)
    for t in sorted(tasks, key=lambda x: parse_time(x["next_fire_at"])):
        nfa = parse_time(t["next_fire_at"])
        delta = (nfa - now_ts).total_seconds()
        eta = fmt_eta(delta)
        mark = "✅" if t.get("enabled", True) else "⏸️"
        if delta <= 0:
            eta = f"OVERDUE {fmt_eta(-delta)}"
        mode = ""
        if t.get("on_event"):
            mode = f"event:{t['on_event']}{' ✅' if t.get('event_triggered') else ' ⏳'}"
        print(f"{mark:6s} {t['name'][:22]:22s} {t.get('kind','shell'):6s} {t['countdown_seconds']:6d}s  {eta:12s} {t.get('fired_count',0):6d}  {mode}")


def cmd_trigger(rest):
    """手动触发事件驱动任务（由 event-bus.py 调用，或人工手动触发）"""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True, help="任务 ID 或 name")
    p.add_argument("--payload", default="{}", help="JSON 格式事件负载（注入 EVENT_PAYLOAD 环境变量）")
    p.add_argument("--payload-file", default=None, help="从文件读取 JSON 负载（避免引号嵌套问题）")
    p.add_argument("--reset-countdown", action="store_true", help="触发后重置倒计时（周期事件模式）")
    a = p.parse_args(rest)

    state = load()
    task = None
    for t in state["tasks"]:
        if t["id"] == a.id or t["name"] == a.id:
            task = t
            break

    if not task:
        print(f"No task with id/name: {a.id}")
        return 1

    if not task.get("on_event"):
        print(f"⚠️  Task '{task['name']}' is not event-driven. Firing anyway...")

    import os, json as _json
    # 优先从文件读取 payload
    if a.payload_file and os.path.exists(a.payload_file):
        try:
            payload = _json.loads(Path(a.payload_file).read_text(encoding="utf-8"))
        except _json.JSONDecodeError:
            payload = {"raw": a.payload}
    else:
        try:
            payload = _json.loads(a.payload)
        except _json.JSONDecodeError:
            payload = {"raw": a.payload}

    env = os.environ.copy()
    env["EVENT_PAYLOAD"] = _json.dumps(payload, ensure_ascii=False)
    env["TASK_NAME"] = task["name"]
    env["TASK_ID"] = task["id"]

    result = fire_task(task, env=env)
    task["last_run"] = result["ran_at"]
    task["last_status"] = result["status"]
    task["fired_count"] = task.get("fired_count", 0) + 1
    task["event_triggered"] = True

    if a.reset_countdown:
        task["next_fire_at"] = (now() + timedelta(seconds=task["countdown_seconds"])).isoformat()
    else:
        # 一次性：推到一年后 + 禁用
        task["next_fire_at"] = (now() + timedelta(days=365)).isoformat()
        task["enabled"] = False

    state["history"].append({"task": task["name"], "triggered_by": "event-bus", **result})
    state["history"] = state["history"][-100:]
    save(state)

    status_mark = "✅" if result["status"] == "ok" else "❌"
    print(f"{status_mark} 任务 '{task['name']}' 已触发 ({result['status']})")
    if result.get("summary"):
        print(f"   {result['summary'][:200]}")
    return 0 if result["status"] == "ok" else 1

def cmd_add(rest):
    import argparse
    import logging

    logger = logging.getLogger(__name__)
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--countdown", required=True)
    p.add_argument("--kind", choices=["shell", "prompt"], default="shell")
    p.add_argument("--command")
    p.add_argument("--prompt")
    p.add_argument("--target", default="new")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--description", default="")
    p.add_argument("--disabled", action="store_true")
    p.add_argument("--first-at", help="首次触发时间 (默认 now+countdown), 格式: ISO 或 countdown 字符串")
    p.add_argument("--event-at", help="事件锚定时间 (ISO), fire_at = event_at + countdown，避免用 created_at 计算导致提前触发（稿件发布后查阅读等场景必须填）")
    # 事件驱动选项
    p.add_argument("--on-event", dest="on_event", help="事件类型（设置后变为事件驱动，countdown 为超时兜底）")
    p.add_argument("--event-source", dest="event_source", default="default", help="事件源标识（默认 default）")
    a = p.parse_args(rest)

    if a.kind == "shell" and not a.command:
        print("Error: --command required for shell task"); return 1
    if a.kind == "prompt" and not a.prompt:
        print("Error: --prompt required for prompt task"); return 1

    state = load()
    cd = parse_duration(a.countdown)

    # 事件驱动模式：countdown 当作超时兜底，首次触发靠事件
    if a.on_event:
        # 事件驱动任务：next_fire_at = now + timeout 作为最后兜底
        # 实际首次触发由 event-bus.py trigger 命令驱动
        if cd > 86400:
            # 超过 1 天则截断为 1h（默认超时 1 小时）
            cd = 3600
        first_fire = now() + timedelta(seconds=cd)
        on_event_timeout = cd
    elif a.event_at:
        # Event-anchored: first_fire = event_at + countdown
        try:
            event_time = parse_time(a.event_at)
        except ValueError:
            print(f"Error: --event-at '{a.event_at}' is not a valid ISO time", file=sys.stderr); return 1
        first_fire = event_time + timedelta(seconds=cd)
        if first_fire <= now():
            print(f"Error: event_at ({a.event_at}) + countdown ({cd}s) = {first_fire.isoformat()} is in the past", file=sys.stderr); return 1
    elif a.first_at:
        try:
            first_fire = parse_time(a.first_at)
        except ValueError:
            first_fire = now() + timedelta(seconds=parse_duration(a.first_at))
    else:
        first_fire = now() + timedelta(seconds=cd)

    task = {
        "id": uuid.uuid4().hex[:8],
        "name": a.name,
        "kind": a.kind,
        "command": a.command if a.kind == "shell" else None,
        "prompt": a.prompt if a.kind == "prompt" else None,
        "target": a.target if a.kind == "prompt" else None,
        "countdown_seconds": cd,
        "event_at": a.event_at if a.event_at else None,
        "next_fire_at": first_fire.isoformat(),
        "enabled": not a.disabled,
        "timeout": a.timeout,
        "description": a.description,
        "created_at": now().isoformat(),
        "fired_count": 0,
        # 事件驱动字段
        "on_event": a.on_event,
        "event_source": a.event_source if a.on_event else None,
        "event_triggered": a.on_event is not None,  # 标记：已被事件触发过
    }
    state["tasks"].append(task)
    save(state)
    extra = f", event_at={a.event_at}" if a.event_at else ""
    print(f"Added: {task['id']} {task['name']} (countdown={cd}s, first fire: {task['next_fire_at']}{extra})")
    return 0


def cmd_remove(rest):
    import argparse
    import logging

    logger = logging.getLogger(__name__)
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True)
    a = p.parse_args(rest)
    state = load()
    before = len(state["tasks"])
    state["tasks"] = [t for t in state["tasks"] if t["id"] != a.id and t["name"] != a.id]
    if len(state["tasks"]) == before:
        print(f"No task with id/name: {a.id}"); return 1
    save(state)
    print(f"Removed: {a.id}")
    return 0


def cmd_enable_disable(rest):
    import argparse
    import logging

    logger = logging.getLogger(__name__)
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True)
    p.add_argument("--state", choices=["enabled", "disabled"], required=True)
    a = p.parse_args(rest)
    state = load()
    for t in state["tasks"]:
        if t["id"] == a.id or t["name"] == a.id:
            t["enabled"] = (a.state == "enabled")
            save(state)
            print(f"{t['name']}: {a.state}")
            return 0
    print(f"No task: {a.id}"); return 1


def cmd_status():
    state = load()
    now_ts = now()
    total = len(state["tasks"])
    enabled = sum(1 for t in state["tasks"] if t.get("enabled", True))
    due = sum(1 for t in state["tasks"] if t.get("enabled", True)
              and parse_time(t["next_fire_at"]) <= now_ts)
    overdue_hours = 0
    if due > 0:
        earliest = min(parse_time(t["next_fire_at"]) for t in state["tasks"]
                       if t.get("enabled", True) and parse_time(t["next_fire_at"]) <= now_ts)
        overdue_hours = (now_ts - earliest).total_seconds() / 3600
    print(f"Total:    {total}  (enabled {enabled}, due {due})")
    print(f"Overdue:  {'N/A' if due == 0 else f'{overdue_hours:.1f}h since earliest'}")
    print(f"State:    {STATE_FILE}")
    if STATE_FILE.exists():
        mtime = datetime.fromtimestamp(STATE_FILE.stat().st_mtime).astimezone(TZ)
        print(f"Last w:   {mtime.isoformat()}")
    if state.get("history"):
        print(f"History:  {len(state['history'])} entries, last: {state['history'][-1]['task']} @ {state['history'][-1]['ran_at'][:19]}")


def cmd_migrate():
    """Migrate tasks from second-brain-scheduler.json (5 tasks) — 幂等"""
    old_file = STATE_DIR / "scheduler.json"
    if not old_file.exists():
        print("No old scheduler file at", old_file); return 1
    old = json.loads(old_file.read_text())
    state = load()
    existing = {t["name"] for t in state["tasks"]}
    migrated = 0
    for t in old.get("tasks", []):
        if t["name"] in existing:
            print(f"⏭️  Skip {t['name']} (already exists)"); continue
        task = {
            "id": uuid.uuid4().hex[:8],
            "name": t["name"],
            "kind": "shell",
            "command": t["command"],
            "countdown_seconds": t["interval_hours"] * 3600,
            "next_fire_at": (now() + timedelta(seconds=t["interval_hours"] * 3600)).isoformat(),
            "enabled": t.get("enabled", True),
            "description": t.get("description", ""),
            "created_at": now().isoformat(),
            "fired_count": 0,
            "migrated_from": "second-brain-scheduler",
        }
        state["tasks"].append(task)
        migrated += 1
    save(state)
    print(f"Migrated {migrated} tasks from second-brain-scheduler")
    return 0


def cmd_enable(rest):
    import argparse
    import logging

    logger = logging.getLogger(__name__)
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True)
    a = p.parse_args(rest)
    return cmd_enable_disable(["--id", a.id, "--state", "enabled"])


def cmd_disable(rest):
    import argparse
    import logging

    logger = logging.getLogger(__name__)
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True)
    a = p.parse_args(rest)
    return cmd_enable_disable(["--id", a.id, "--state", "disabled"])


# ============================================================================
# 小说创作统计模块
# ============================================================================

NOVEL_PROJECTS_FILE = STATE_DIR / "novel-projects.json"
NOVEL_LOG_FILE = STATE_DIR / "novel-log.json"
NOVEL_STATS_FILE = STATE_DIR / "novel-stats.json"


def load_novel_projects():
    """加载小说项目列表"""
    if not NOVEL_PROJECTS_FILE.exists():
        return {"projects": [], "created_at": now().isoformat()}
    return json.loads(NOVEL_PROJECTS_FILE.read_text())


def save_novel_projects(data):
    """保存小说项目列表"""
    tmp = NOVEL_PROJECTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(tmp, NOVEL_PROJECTS_FILE)


def load_novel_log():
    """加载创作日志"""
    if not NOVEL_LOG_FILE.exists():
        return {"entries": [], "created_at": now().isoformat()}
    return json.loads(NOVEL_LOG_FILE.read_text())


def save_novel_log(data):
    """保存创作日志"""
    tmp = NOVEL_LOG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(tmp, NOVEL_LOG_FILE)


def cmd_novel_list():
    """列出所有小说项目"""
    data = load_novel_projects()
    projects = data.get("projects", [])
    
    if not projects:
        print("未创建任何小说项目")
        print("使用 'novel add' 创建新项目")
        return
    
    print(f"\n{'ID':<12} {'名称':<20} {'类型':<10} {'字数':<10} {'状态':<8} {'创建时间'}")
    print("-" * 80)
    for p in projects:
        word_count = p.get("word_count", 0)
        status = "✅" if p.get("status") == "active" else "⏸️"
        created = p.get("created_at", "未知")[:10]
        print(f"{p['id']:<12} {p['name']:<20} {p.get('genre', '未知'):<10} {word_count:<10,} {status:<8} {created}")
    print(f"\n总计 {len(projects)} 个项目")


def cmd_novel_add(rest):
    """添加新小说项目"""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True, help="小说名称")
    p.add_argument("--genre", required=True, help="题材类型（玄幻/都市/科幻/历史/言情/末日）")
    p.add_argument("--platform", default="起点", help="发布平台（起点/番茄/晋江/七猫）")
    p.add_argument("--target-words", type=int, default=100000, help="目标字数（默认10万）")
    p.add_argument("--project-dir", help="项目目录路径")
    a = p.parse_args(rest)
    
    data = load_novel_projects()
    project_id = uuid.uuid4().hex[:8]
    
    # 确定项目目录
    if a.project_dir:
        project_path = Path(a.project_dir)
    else:
        project_path = Path(f"/var/minis/shared/novel-team/projects/{a.name}")
    
    project_path.mkdir(parents=True, exist_ok=True)
    
    project = {
        "id": project_id,
        "name": a.name,
        "genre": a.genre,
        "platform": a.platform,
        "target_words": a.target_words,
        "current_words": 0,
        "status": "active",
        "created_at": now().isoformat(),
        "project_dir": str(project_path),
        "chapters": [],
        "last_update": now().isoformat()
    }
    
    data["projects"].append(project)
    save_novel_projects(data)
    
    print(f"✅ 小说项目已创建")
    print(f"   ID: {project_id}")
    print(f"   名称: {a.name}")
    print(f"   题材: {a.genre}")
    print(f"   平台: {a.platform}")
    print(f"   目标字数: {a.target_words:,}")
    print(f"   目录: {project_path}")
    
    # 创建初始文件结构
    (project_path / "outline.md").write_text(f"# {a.name} - 大纲\n\n> 题材：{a.genre}\n> 平台：{a.platform}\n> 目标字数：{a.target_words:,}\n\n## 一句话简介\n\n（待填写）\n\n## 核心卖点\n\n（待填写）\n\n## 主角设定\n\n- 姓名：\n- 性格：\n- 金手指：\n")
    (project_path / "characters.md").write_text(f"# {a.name} - 角色设定\n\n## 主角\n\n（待填写）\n\n## 配角\n\n（待填写）\n")
    (project_path / "worldbuilding.md").write_text(f"# {a.name} - 世界观\n\n## 时代背景\n\n（待填写）\n\n## 力量体系\n\n（待填写）\n\n## 主要势力\n\n（待填写）\n")
    
    print(f"\n📁 初始文件结构已创建")


def cmd_novel_log(rest):
    """记录创作活动"""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True, help="小说项目ID")
    p.add_argument("--action", required=True, choices=["write", "outline", "character", "polish", "publish"], help="行动类型")
    p.add_argument("--words", type=int, default=0, help="本次字数（可选）")
    p.add_argument("--chapter", help="章节号（可选）")
    p.add_argument("--note", help="备注（可选）")
    a = p.parse_args(rest)
    
    # 验证项目存在
    data = load_novel_projects()
    project = None
    for p in data["projects"]:
        if p["id"] == a.project_id:
            project = p
            break
    
    if not project:
        print(f"❌ 项目不存在: {a.project_id}")
        return 1
    
    # 创建日志条目
    entry = {
        "id": uuid.uuid4().hex[:8],
        "project_id": a.project_id,
        "action": a.action,
        "words": a.words,
        "chapter": a.chapter,
        "note": a.note,
        "timestamp": now().isoformat()
    }
    
    # 保存日志
    log_data = load_novel_log()
    log_data["entries"].append(entry)
    log_data["entries"] = log_data["entries"][-500:]  # 保留最近500条
    save_novel_log(log_data)
    
    # 更新项目数据
    if a.words > 0:
        project["current_words"] = project.get("current_words", 0) + a.words
        project["last_update"] = now().isoformat()
    
    if a.chapter:
        project.setdefault("chapters", []).append({
            "number": a.chapter,
            "words": a.words,
            "action": a.action,
            "timestamp": now().isoformat()
        })
    
    save_novel_projects(data)
    
    print(f"✅ 已记录创作活动")
    print(f"   项目: {project['name']}")
    print(f"   行动: {a.action}")
    if a.words > 0:
        print(f"   字数: +{a.words:,}")
    if a.chapter:
        print(f"   章节: 第{a.chapter}章")


def cmd_novel_stats(rest):
    """查看创作统计"""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", help="查看特定项目统计（可选）")
    a = p.parse_args(rest)
    
    projects_data = load_novel_projects()
    log_data = load_novel_log()
    
    if a.project_id:
        # 查看单项目统计
        project = None
        for proj in projects_data["projects"]:
            if proj["id"] == a.project_id:
                project = proj
                break
        
        if not project:
            print(f"❌ 项目不存在: {a.project_id}")
            return 1
        
        # 计算该项目的统计数据
        entries = [e for e in log_data["entries"] if e["project_id"] == a.project_id]
        total_words = sum(e.get("words", 0) for e in entries)
        
        # 按行动类型统计
        by_action = {}
        for e in entries:
            action = e.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1
        
        # 按日期统计（最近7天）
        last_7d = now() - timedelta(days=7)
        daily_words = {}
        for e in entries:
            if parse_time(e["timestamp"]) >= last_7d:
                day = e["timestamp"][:10]
                daily_words[day] = daily_words.get(day, 0) + e.get("words", 0)
        
        print(f"\n📊 小说统计 - {project['name']}")
        print("=" * 50)
        print(f"题材: {project.get('genre', '未知')}")
        print(f"平台: {project.get('platform', '未知')}")
        print(f"目标字数: {project.get('target_words', 0):,}")
        print(f"当前字数: {total_words:,}")
        print(f"完成度: {total_words/project.get('target_words', 1)*100:.1f}%")
        print()
        print("行动统计:")
        for action, count in sorted(by_action.items()):
            print(f"  {action}: {count}次")
        print()
        print("最近7天每日字数:")
        for day in sorted(daily_words.keys())[-7:]:
            bar = "█" * (daily_words[day] // 100)
            print(f"  {day}: {daily_words[day]:,} {bar}")
        
    else:
        # 查看所有项目概览
        print(f"\n📊 小说创作统计概览")
        print("=" * 50)
        
        total_projects = len(projects_data["projects"])
        active_projects = sum(1 for proj in projects_data["projects"] if proj.get("status") == "active")
        total_words = sum(proj.get("current_words", 0) for proj in projects_data["projects"])
        
        print(f"总项目数: {total_projects} (活跃: {active_projects})")
        print(f"总字数: {total_words:,}")
        print()
        
        if total_projects > 0:
            print("项目详情:")
            for proj in projects_data["projects"]:
                words = proj.get("current_words", 0)
                target = proj.get("target_words", 0)
                progress = words / target * 100 if target > 0 else 0
                status = "✅" if proj.get("status") == "active" else "⏸️"
                print(f"  {status} {proj['name']}: {words:,}/{target:,} ({progress:.1f}%)")
        
        # 最近创作活动（最近30天）
        last_30d = now() - timedelta(days=30)
        recent_entries = [e for e in log_data["entries"] if parse_time(e["timestamp"]) >= last_30d]
        
        if recent_entries:
            print()
            print(f"最近30天创作活动: {len(recent_entries)}次")
            daily_count = {}
            for e in recent_entries:
                day = e["timestamp"][:10]
                daily_count[day] = daily_count.get(day, 0) + 1
            
            print("创作活跃度:")
            for day in sorted(daily_count.keys())[-14:]:
                bar = "█" * daily_count[day]
                print(f"  {day}: {daily_count[day]}次 {bar}")


def cmd_novel_report():
    """生成创作报告"""
    projects_data = load_novel_projects()
    log_data = load_novel_log()
    
    projects = projects_data.get("projects", [])
    entries = log_data.get("entries", [])
    
    if not projects:
        print("暂无小说项目")
        return
    
    # 计算总体统计
    total_words = sum(p.get("current_words", 0) for p in projects)
    total_target = sum(p.get("target_words", 0) for p in projects)
    completion_rate = total_words / total_target * 100 if total_target > 0 else 0
    
    # 计算平均日产量
    from datetime import timedelta
    first_entry = min(parse_time(e["timestamp"]) for e in entries) if entries else now()
    days_active = max((now() - first_entry).days, 1)
    avg_daily = total_words // days_active
    
    # 行动类型分布
    action_counts = {}
    action_words = {}
    for e in entries:
        action = e.get("action", "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
        action_words[action] = action_words.get(action, 0) + e.get("words", 0)
    
    # 生成报告
    print("\n" + "=" * 60)
    print("📈 小说创作统计报告")
    print("=" * 60)
    print(f"报告时间: {now().strftime('%Y-%m-%d %H:%M')}")
    print(f"统计周期: {first_entry.strftime('%Y-%m-%d')} ~ {now().strftime('%Y-%m-%d')}")
    print(f"活跃天数: {days_active}天")
    print()
    print("【整体数据】")
    print(f"  项目数量: {len(projects)}个")
    print(f"  总字数: {total_words:,}字")
    print(f"  目标字数: {total_target:,}字")
    print(f"  完成进度: {completion_rate:.1f}%")
    print(f"  日均产量: {avg_daily:,}字/天")
    print()
    print("【行动分布】")
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        words = action_words.get(action, 0)
        pct = count / len(entries) * 100 if entries else 0
        print(f"  {action}: {count}次 ({pct:.1f}%), 贡献{words:,}字")
    print()
    print("【项目明细】")
    for p in projects:
        words = p.get("current_words", 0)
        target = p.get("target_words", 0)
        progress = words / target * 100 if target > 0 else 0
        status = "✅" if p.get("status") == "active" else "⏸️"
        print(f"  {status} {p['name']}: {words:,}/{target:,} ({progress:.1f}%)")
    print()
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    try:
        if cmd == "list": cmd_list()
        elif cmd == "check": cmd_check(catchup="--catchup" in rest)
        elif cmd == "add": sys.exit(cmd_add(rest))
        elif cmd == "remove": sys.exit(cmd_remove(rest))
        elif cmd == "enable": sys.exit(cmd_enable(rest))
        elif cmd == "disable": sys.exit(cmd_disable(rest))
        elif cmd == "status": cmd_status()
        elif cmd == "migrate": sys.exit(cmd_migrate())
        # 小说创作统计命令
        elif cmd == "novel":
            if len(rest) < 1:
                print("小说创作统计命令")
                print("用法:")
                print("  novel list              列出所有小说项目")
                print("  novel add --name X --genre Y  添加新小说项目")
                print("  novel log --project-id X --action write --words 2000  记录创作活动")
                print("  novel stats [--project-id X]  查看创作统计")
                print("  novel report            生成创作报告")
                sys.exit(1)
            subcmd = rest[0]
            subrest = rest[1:]
            if subcmd == "list": cmd_novel_list()
            elif subcmd == "add": sys.exit(cmd_novel_add(subrest))
            elif subcmd == "log": sys.exit(cmd_novel_log(subrest))
            elif subcmd == "stats": cmd_novel_stats(subrest)
            elif subcmd == "report": cmd_novel_report()
            else:
                print(f"未知命令: novel {subcmd}")
                sys.exit(1)
        elif cmd == "trigger": sys.exit(cmd_trigger(rest))
        elif cmd in ("-h", "--help"): print(__doc__)
        else:
            print(f"Unknown command: {cmd}"); sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted"); sys.exit(130)
