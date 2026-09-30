#!/usr/bin/env python3
"""world-sync-check.py — 定期检查世界包待确认实体，有待审条目时 Bark 主动提醒"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NOVEL_ID = "my-novel"
BASE = Path("/var/minis/shared/novel-team")
TOOLS = BASE / "tools"
WORLD_SYNC = TOOLS / "world-sync.py"


def run(cmd: list) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def send_bark(title: str, body: str) -> bool:
    """发送 Bark 通知（best-effort，失败不影响主流程）。"""
    bark_key = os.environ.get("BARK_KEY", "")
    if not bark_key:
        print("  [Bark] 未配置 BARK_KEY，跳过通知")
        return False
    url = f"https://api.day.app/{bark_key}/{title}/{body}"
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"{url}",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({
                 "group": "world-sync",
                 "icon": "https://img.shields.io/badge/sync/true/brightgreen",
                 "sound": "msg",
                 "level": "timeSensitive",
                 "isArchive": 1,
                 "cover": "✅",
             })],
            capture_output=True, timeout=15,
        )
        print(f"  [Bark] 通知已发送: {title}")
        return True
    except Exception as e:
        print(f"  [Bark] 发送失败: {e}")
        return False


def main():
    # Step 1: 消费新事件（scan）
    rc, out = run([sys.executable, str(WORLD_SYNC), "--novel-id", NOVEL_ID, "scan"])
    scan_info = ""
    for line in out.splitlines():
        if line.strip().startswith("{"):
            try:
                d = json.loads(line)
                scan_info = (
                    f"scan: {d.get('scanned_events',0)}事件 → "
                    f"{d.get('auto_approved',0)}自动入库, "
                    f"{d.get('needs_human',0)}待审核"
                )
                break
            except json.JSONDecodeError:
                continue

    # Step 2: 列出待审核
    rc, out = run([sys.executable, str(WORLD_SYNC), "--novel-id", NOVEL_ID,
                   "list", "--status", "pending"])
    # 统计 pending 条目数（用 JSON 数据更可靠）
    pending_count = 0
    pending_items = []
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("[W") or (s.startswith("⏳") and "[" in s):
            pending_count += 1
            # 提取实体名（"⏳ [W016] place：赵家" → "赵家"）
            m = re.search(r"place[：:]\s*(.+?)(?:\s*\||$)", s)
            if m:
                pending_items.append(m.group(1).strip())

    print(f"📊 {scan_info or 'scan ok'}")
    if pending_count == 0:
        print("✅ world-sync: 无待审核条目")
        return

    print(f"⏳ world-sync: {pending_count} 条待审核实体")
    for item in pending_items:
        print(f"  ⏳ {item}")

    # Step 3: Bark 主动提醒
    title = f"world-sync {pending_count}条待审核"
    body = " | ".join(pending_items[:3]) if pending_items else "请运行 list 查看详情"
    send_bark(title, body)


if __name__ == "__main__":
    main()
