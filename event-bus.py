#!/usr/bin/env python3
# Version: 0.1.0
"""
event-bus.py — 通用文件事件总线

核心设计：
  - 事件源：任何工具完成某动作后，调用 emit 追加到 JSONL 文件
  - 事件链：注册"某事件发生 → 触发某任务"的映射
  - 消费方式：pull 式，调用 consume/watch 时扫描新事件并触发
  - 游标持久化：中断可续，事件安全留存

命令：
  emit        追加一条事件
  watch       注册事件监听（事件→任务映射）
  unwatch     移除监听
  chains      查看已注册的事件链
  consume     扫描新事件并触发对应任务（可接 countdown-scheduler）
  events      查看某源的最近事件
  cursor      查看/重置游标
  status      全量状态摘要

用法示例：
  # 写入事件
  python3 event-bus.py emit --source my-novel --type GATE_PASSED --payload '{"chapter":1,"score":94}'

  # 注册监听：当 GATE_PASSED 发生时，运行指定命令
  python3 event-bus.py watch --source my-novel --type GATE_PASSED \\
    --action shell --command "python3 /path/to/world-sync.py scan my-novel" \\
    --label "门检通过→世界包扫描"

  # 注册监听：prompt 类型（触发 LLM 会话）
  python3 event-bus.py watch --source my-novel --type CHAPTER_PUBLISHED \\
    --action prompt --prompt "第{chapter}章已发布：{{payload}}" \\
    --target new --label "发布→数据追踪"

  # 消费新事件（手动或定时驱动）
  python3 event-bus.py consume --source my-novel
  python3 event-bus.py consume --all           # 消费所有已注册源

  # 加进 countdown-scheduler 定期自动 consume（时间驱动兜底）
  python3 countdown-scheduler.py add --name "event-consume" \\
    --countdown 1h --kind shell \\
    --command "python3 /var/minis/shared/event-bus.py consume --all"
"""

import json, os, sys, uuid, shlex, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path("/var/minis/shared/.events")
CHAINS_FILE = BASE / "chains.json"
TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(TZ)


def ensure_base():
    BASE.mkdir(parents=True, exist_ok=True)


def _chain_path() -> Path:
    ensure_base()
    return CHAINS_FILE


def load_chains() -> dict:
    p = _chain_path()
    if not p.exists():
        return {"chains": [], "created_at": now().isoformat()}
    return json.loads(p.read_text())


def save_chains(state):
    p = _chain_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    os.replace(tmp, p)


def _events_file(source: str) -> Path:
    ensure_base()
    return BASE / f"{source}.jsonl"


def _cursor_file(source: str) -> Path:
    ensure_base()
    return BASE / f"{source}.cursor"


def _get_cursor(source: str) -> int:
    p = _cursor_file(source)
    if p.exists():
        try:
            return int(p.read_text().strip())
        except ValueError:
            pass
    return 0


def _set_cursor(source: str, n: int):
    _cursor_file(source).write_text(str(n))


def read_events_since(source: str, cursor: int = 0) -> list:
    p = _events_file(source)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    events = []
    for i, line in enumerate(lines[cursor:], cursor):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


# ──────────────────────────────────────────────
# emit
# ──────────────────────────────────────────────
def cmd_emit(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="事件源标识（项目名/模块名）")
    p.add_argument("--type", required=True, dest="event_type", help="事件类型（如 GATE_PASSED）")
    p.add_argument("--payload", default="{}", help="JSON 格式的附加数据")
    p.add_argument("--quiet", action="store_true", help="不输出结果")
    a = p.parse_args(rest)

    ensure_base()
    pfile = _events_file(a.source)

    try:
        payload = json.loads(a.payload)
    except json.JSONDecodeError:
        print(f"Error: --payload is not valid JSON: {a.payload}", file=sys.stderr)
        return 1

    event = {
        "event": a.event_type,
        "source": a.source,
        "timestamp": now().isoformat(),
        "event_id": uuid.uuid4().hex[:8],
        **payload,
    }
    with open(pfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    if not a.quiet:
        print(f"✅ 事件已写入 {pfile.name}: [{a.event_type}] {json.dumps(payload, ensure_ascii=False)[:200]}")
        print(f"   event_id: {event['event_id']}")


# ──────────────────────────────────────────────
# watch
# ──────────────────────────────────────────────
def cmd_watch(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="事件源标识")
    p.add_argument("--type", required=True, dest="event_type", help="监听的事件类型")
    p.add_argument("--action", required=True, choices=["shell", "prompt", "scheduler"],
                   help="触发动作类型")
    p.add_argument("--command", help="shell 命令（action=shell 时必填）")
    p.add_argument("--prompt", help="LLM 提示词（action=prompt 时必填），支持 {payload} 占位符")
    p.add_argument("--target", default="new", choices=["new", "follow-up", "child-of-current"],
                   help="prompt 任务的 target")
    p.add_argument("--label", default="", help="人类可读标签")
    p.add_argument("--timeout", type=int, default=300, help="shell 命令超时秒数")
    p.add_argument("--once", action="store_true", help="触发一次后自动移除监听")
    # scheduler 专用参数
    p.add_argument("--scheduler-id", dest="scheduler_id",
                   help="action=scheduler 时指定 countdown-scheduler 任务 ID 或 name")
    p.add_argument("--scheduler-reset", dest="scheduler_reset", action="store_true",
                   help="action=scheduler 时触发后重置倒计时（周期事件）")
    a = p.parse_args(rest)

    if a.action == "shell" and not a.command:
        print("Error: --command required for shell action", file=sys.stderr)
        return 1
    if a.action == "prompt" and not a.prompt:
        print("Error: --prompt required for prompt action", file=sys.stderr)
        return 1
    if a.action == "scheduler" and not a.scheduler_id:
        print("Error: --scheduler-id required for scheduler action", file=sys.stderr)
        return 1

    state = load_chains()
    chain_id = uuid.uuid4().hex[:8]
    chain = {
        "id": chain_id,
        "source": a.source,
        "event_type": a.event_type,
        "action": a.action,
        "command": a.command,
        "prompt": a.prompt,
        "target": a.target if a.action == "prompt" else None,
        "label": a.label,
        "timeout": a.timeout,
        "once": a.once,
        "created_at": now().isoformat(),
        "enabled": True,
        "fire_count": 0,
        # scheduler 专用字段
        "scheduler_id": a.scheduler_id if a.action == "scheduler" else None,
        "scheduler_reset": a.scheduler_reset if a.action == "scheduler" else False,
    }
    state["chains"].append(chain)
    save_chains(state)
    print(f"✅ 监听已注册: {chain_id}")
    print(f"   源: {a.source} / 类型: {a.event_type}")
    if a.action == "scheduler":
        print(f"   动作: scheduler → 任务 {a.scheduler_id}" +
              (" (周期)" if a.scheduler_reset else " (一次性)"))
    else:
        print(f"   动作: {a.action}" +
              (f" → {a.command[:80]}" if a.command else f" → {a.prompt[:60]}..."))
    if a.once:
        print(f"   模式: 触发一次后自动移除")


def cmd_unwatch(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--id", help="chain_id")
    p.add_argument("--source", help="按源+类型批量删除（需同时指定 --type）")
    p.add_argument("--type", dest="event_type", help="配合 --source")
    a = p.parse_args(rest)

    state = load_chains()
    removed = []
    if a.id:
        before = len(state["chains"])
        state["chains"] = [c for c in state["chains"] if c["id"] != a.id]
        removed = before - len(state["chains"])
    elif a.source and a.event_type:
        before = len(state["chains"])
        state["chains"] = [c for c in state["chains"] if not (
            c["source"] == a.source and c["event_type"] == a.event_type)]
        removed = before - len(state["chains"])
    else:
        print("Error: provide --id or (--source AND --type)", file=sys.stderr)
        return 1

    save_chains(state)
    print(f"✅ 已移除 {removed} 条监听")


# ──────────────────────────────────────────────
# chains
# ──────────────────────────────────────────────
def cmd_chains(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", help="只看某源的监听")
    p.add_argument("--type", dest="event_type", help="只看某事件类型")
    a = p.parse_args(rest)

    state = load_chains()
    chains = state["chains"]
    if a.source:
        chains = [c for c in chains if c["source"] == a.source]
    if a.event_type:
        chains = [c for c in chains if c["event_type"] == a.event_type]

    if not chains:
        print("(无已注册监听)")
        return

    print(f"{'ID':10s} {'Source':16s} {'Event':30s} {'Action':8s} {'Label':30s} {'Fires':6s} {'Enabled'}")
    print("-" * 110)
    for c in chains:
        mark = "✅" if c.get("enabled", True) else "⏸️"
        label = c.get("label", "")[:30]
        fires = c.get("fire_count", 0)
        print(f"{c['id']:10s} {c['source']:16s} {c['event_type']:30s} "
              f"{c['action']:8s} {label:30s} {fires:6d} {mark}")


# ──────────────────────────────────────────────
# consume
# ──────────────────────────────────────────────
def cmd_consume(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", help="只消费某源")
    p.add_argument("--all", action="store_true", help="消费所有有监听的源")
    p.add_argument("--dry-run", action="store_true", help="只报告将触发什么，不实际执行")
    a = p.parse_args(rest)

    state = load_chains()
    chains = [c for c in state["chains"] if c.get("enabled", True)]

    if not a.source and not a.all:
        print("Error: specify --source or --all", file=sys.stderr)
        return 1

    if a.source:
        sources = [a.source]
    else:
        sources = sorted(set(c["source"] for c in chains))

    total_fired = 0
    for source in sources:
        cursor = _get_cursor(source)
        new_events = read_events_since(source, cursor)
        if not new_events:
            continue

        triggered = 0
        for ev in new_events:
            etype = ev.get("event", "")
            matching = [c for c in chains if c["source"] == source and c["event_type"] == etype]

            if not matching:
                # 没有对应监听，跳过（不阻塞游标）
                continue

            for chain in matching:
                triggered += 1
                label = chain.get("label", chain["event_type"])
                print(f"🔥 触发: [{source}] {etype} → {label}")

                if a.dry_run:
                    print(f"   (dry-run) 将执行: " +
                          (f"{chain.get('command','')[:60]}" if chain["action"]=="shell"
                           else f"prompt: {chain.get('prompt','')[:50]}..."))
                    continue

                # 实际执行
                result = _fire_chain(chain, ev)
                if result:
                    chain["fire_count"] = chain.get("fire_count", 0) + 1
                    if chain.get("once"):
                        chain["enabled"] = False
                        print(f"   ⚡ 一次性监听已触发，自动禁用")

        # 推进游标（即使部分事件无监听也推进，防止重复处理）
        if new_events:
            new_cursor = cursor + len(new_events)
            _set_cursor(source, new_cursor)
            print(f"   游标推进: {cursor} → {new_cursor} ({len(new_events)} 条新事件, 触发 {triggered} 次)")

        total_fired += triggered

    print(f"\n📊 consume 完成: 共触发 {total_fired} 条监听")

    # 如果有任何一次性监听被触发，保存 chains 更新
    save_chains(state)


def _fire_chain(chain: dict, event: dict) -> bool:
    """执行 chain 定义的动作，返回是否成功。"""
    import shlex
    action = chain["action"]
    timeout = chain.get("timeout", 300)

    if action == "scheduler":
        # ===== 方案：fire-and-forget =====
        # 从调度器状态文件直接查找任务命令，后台执行（避免三层嵌套子进程）
        sched_id = chain.get("scheduler_id", "")
        sched_reset = chain.get("scheduler_reset", False)
        import json as _json
        state_path = Path("/var/minis/shared/.scheduler/countdown-tasks.json")
        if not state_path.exists():
            print(f"   ❌ 调度器状态文件不存在")
            return False
        try:
            sched_state = _json.loads(state_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   ❌ 读取调度器状态失败: {e}")
            return False

        task = next((t for t in sched_state["tasks"] if t["id"] == sched_id or t["name"] == sched_id), None)
        if not task:
            print(f"   ❌ 调度器任务不存在: {sched_id}")
            return False

        task_cmd = task.get("command", "")
        if not task_cmd:
            print(f"   ❌ 调度器任务无命令: {sched_id}")
            return False

        # 注入事件环境变量后，在后台执行（nohup + & 实现 fire-and-forget）
        payload_str = json.dumps(event, ensure_ascii=False)
        env_prefix = f"TRGLER_EVENT_PAYLOAD='{payload_str}'"
        # 后台执行，不等待结果，避免超时
        bg_cmd = f"nohup bash -c {repr(task_cmd)} > /var/minis/shared/.events/last-trigger.log 2>&1 &"
        try:
            subprocess.Popen(bg_cmd, shell=True)
            # 更新调度器任务状态（标记已触发）
            task["event_triggered"] = True
            task["fired_count"] = task.get("fired_count", 0) + 1
            task["last_run"] = now().isoformat()
            from datetime import timedelta as _td
            if sched_reset:
                sched_state["tasks"] = sched_state["tasks"]  # just mark
                task["next_fire_at"] = (now() + _td(seconds=task["countdown_seconds"])).isoformat()
            tmp = state_path.with_suffix(".tmp")
            tmp.write_text(_json.dumps(sched_state, ensure_ascii=False, indent=2))
            import os as _os
            _os.replace(tmp, state_path)
            print(f"   → scheduler 任务已后台触发: {task['name']}")
            return True
        except Exception as e:
            print(f"   ❌ scheduler trigger error: {e}")
            return False

    if action == "shell":
        cmd = chain.get("command", "")
        # 将 event 数据注入环境变量
        import os, json as _json
        env = os.environ.copy()
        env["EVENT_TYPE"] = event.get("event", "")
        env["EVENT_ID"] = event.get("event_id", "")
        env["EVENT_SOURCE"] = event.get("source", "")
        env["EVENT_PAYLOAD"] = _json.dumps(event, ensure_ascii=False)
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                     text=True, timeout=timeout, env=env)
            summary = (result.stdout + "\n---STDERR---\n" + result.stderr)[:500]
            print(f"   → exit={result.returncode}")
            if summary.strip():
                print(f"   {summary[:200]}")
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"   ❌ timeout after {timeout}s")
            return False
        except Exception as e:
            print(f"   ❌ error: {e}")
            return False

    elif action == "prompt":
        prompt = chain.get("prompt", "")
        target = chain.get("target", "new")
        # 替换 {payload} 占位符
        payload_str = json.dumps(event, ensure_ascii=False)
        prompt = prompt.replace("{payload}", payload_str)
        label = chain.get("label", "event-trigger")

        import shlex
        cmd = (f'minis-scheduled create '
               f'--prompt {shlex.quote(prompt)} '
               f'--target {shlex.quote(target)} '
               f'--label {shlex.quote(label + "-" + event.get("event_id", ""))}')
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                    text=True, timeout=30)
            ok = result.returncode == 0
            print(f"   → minis-scheduled {'OK' if ok else 'FAIL'}")
            if not ok:
                print(f"   {result.stderr[:200]}")
            return ok
        except Exception as e:
            print(f"   ❌ error: {e}")
            return False

    return False


# ──────────────────────────────────────────────
# events
# ──────────────────────────────────────────────
def cmd_events(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--limit", type=int, default=10, help="显示最近 N 条")
    a = p.parse_args(rest)

    pfile = _events_file(a.source)
    if not pfile.exists():
        print(f"(源 {a.source} 无事件记录)")
        return

    lines = pfile.read_text(encoding="utf-8").strip().splitlines()
    shown = lines[-a.limit:]
    cursor = _get_cursor(a.source)

    print(f"📋 源: {a.source} | 总事件: {len(lines)} | 游标: {cursor} | 未消费: {len(lines)-cursor}")
    print("-" * 80)
    for i, line in enumerate(shown, start=len(lines)-len(shown)+1):
        consumed = i <= cursor
        mark = "✓" if consumed else "·"
        try:
            ev = json.loads(line)
            ts = ev.get("timestamp", "")[:16]
            etype = ev.get("event", "?")
            payload_str = json.dumps({k:v for k,v in ev.items() if k not in ("event","timestamp","event_id","source")}, ensure_ascii=False)[:80]
            print(f"  {mark} #{i:4d} {ts}  {etype:30s} {payload_str}")
        except json.JSONDecodeError:
            print(f"  ? #{i:4d} (invalid JSON)")


# ──────────────────────────────────────────────
# cursor
# ──────────────────────────────────────────────
def cmd_cursor(rest):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--reset", type=int, default=None, help="重置为指定行号")
    a = p.parse_args(rest)

    cur = _get_cursor(a.source)
    total = len(_events_file(a.source).read_text(encoding="utf-8").strip().splitlines()) \
        if _events_file(a.source).exists() else 0

    if a.reset is not None:
        _set_cursor(a.source, a.reset)
        print(f"✅ 游标已重置: {cur} → {a.reset} (源: {a.source}, 总事件: {total})")
    else:
        print(f"📍 源: {a.source} | 游标: {cur} | 总事件: {total} | 未消费: {total-cur}")


# ──────────────────────────────────────────────
# status
# ──────────────────────────────────────────────
def cmd_status(rest):
    state = load_chains()
    chains = state["chains"]

    # 找所有有事件的源
    event_files = list(BASE.glob("*.jsonl")) if BASE.exists() else []
    sources = set(f.stem for f in event_files) | set(c["source"] for c in chains)

    print(f"📊 事件总线状态 ({now().strftime('%Y-%m-%d %H:%M')})")
    print(f"   已注册监听: {len(chains)} 条")
    print(f"   事件源: {len(event_files)} 个\n")

    for source in sorted(sources):
        pfile = _events_file(source)
        exists = pfile.exists()
        total = len(pfile.read_text(encoding="utf-8").strip().splitlines()) if exists else 0
        cursor = _get_cursor(source)
        unconsumed = max(0, total - cursor)
        src_chains = [c for c in chains if c["source"] == source]
        enabled_chains = [c for c in src_chains if c.get("enabled", True)]

        mark = "✅" if unconsumed == 0 else "⚠️"
        print(f"  {mark} {source}")
        print(f"     事件: {total} 条 (未消费: {unconsumed})")
        print(f"     监听: {len(enabled_chains)}/{len(src_chains)} 启用")
        for c in enabled_chains:
            print(f"       - {c['event_type']} → {c.get('label', c['action'])} "
                  f"(fires: {c.get('fire_count', 0)})")


# ──────────────────────────────────────────────
# main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    try:
        if cmd == "emit":
            sys.exit(cmd_emit(rest))
        elif cmd == "watch":
            sys.exit(cmd_watch(rest))
        elif cmd == "unwatch":
            sys.exit(cmd_unwatch(rest))
        elif cmd == "chains":
            cmd_chains(rest)
        elif cmd == "consume":
            cmd_consume(rest)
        elif cmd == "events":
            cmd_events(rest)
        elif cmd == "cursor":
            cmd_cursor(rest)
        elif cmd == "status":
            cmd_status(rest)
        elif cmd in ("-h", "--help"):
            print(__doc__)
        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
