#!/usr/bin/env python3
# Version: 0.1.0
"""
worker-sync.py — countdown-scheduler 任务变更后自动同步到 Cloudflare Worker

读取本地 countdown-tasks.json，转成 Worker 任务格式，POST /sync 推送到 Worker KV。
幂等：每次全量覆盖 KV tasks，不会累积。

用法:
  python3 worker-sync.py                    # 同步当前所有 enabled 任务
  python3 worker-sync.py --dry-run          # 只打印不推送
  python3 worker-sync.py --include-disabled # 包含 disabled 任务（默认不推）

环境变量:
  WORKER_URL       — Worker 的 HTTPS URL
  WORKER_AUTH_TOKEN — 认证 token（对应 Worker 的 AUTH_TOKEN secret）
"""

import json, os, sys, urllib.request, urllib.error
from pathlib import Path

STATE_FILE = Path("/var/minis/shared/.scheduler/countdown-tasks.json")

def load_tasks():
    if not STATE_FILE.exists():
        print("❌ No scheduler state file", file=sys.stderr)
        sys.exit(1)
    return json.loads(STATE_FILE.read_text())

def build_worker_tasks(state, include_disabled=False):
    """把 countdown-scheduler 任务转成 Worker Bark push 格式

    每条任务的 params 包含:
      level=timeSensitive — 时效性通知（iOS 横幅高亮、通知中心置顶）
      copy=<command>     — 命令自动复制到剪切板，用户粘贴到终端即可执行
      url=minis://open_terminal — 点击通知打开 Minis 终端
    """
    worker_tasks = []
    for t in state.get("tasks", []):
        if not t.get("enabled", True) and not include_disabled:
            continue
        worker_tasks.append({
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
    return worker_tasks

def sync(worker_url, auth_token, tasks, dry_run=False):
    payload = json.dumps({"tasks": tasks}).encode("utf-8")
    if dry_run:
        print(f"[dry-run] Would POST {len(tasks)} tasks to {worker_url}/sync")
        for t in tasks:
            print(f"  {t['tag']:30s} → {t['body']}")
        return

    url = worker_url.rstrip("/") + "/sync"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {auth_token}")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")  # 绕过 CF bot 检测

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"✅ Synced {result.get('count', '?')} tasks to Worker")
            if result.get("synced_at"):
                print(f"   Worker accepted at: {result['synced_at']}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

def main():
    dry_run = "--dry-run" in sys.argv
    include_disabled = "--include-disabled" in sys.argv

    worker_url = os.environ.get("WORKER_URL")
    auth_token = os.environ.get("WORKER_AUTH_TOKEN")
    if not worker_url or not auth_token:
        print("❌ WORKER_URL or WORKER_AUTH_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    state = load_tasks()
    tasks = build_worker_tasks(state, include_disabled)

    if not tasks:
        print("⚠️  No enabled tasks to sync")
        return

    print(f"📋 Syncing {len(tasks)} tasks to Worker:")
    for t in tasks:
        print(f"  {t['tag']:30s} → {t['body']}")
    print()

    sync(worker_url, auth_token, tasks, dry_run)

if __name__ == "__main__":
    main()
