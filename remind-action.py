#!/usr/bin/env python3
# Version: 0.1.0
"""
minis_url: minis://shared/remind-action.py

提醒系统完整生命周期管理
==========================
整合 remind.py（自然语言→提案）+ countdown-scheduler.py（调度）+ 队列管理

子命令:
  remind-action.py submit "自然语言" [--role XX]     # 提交新提案
  remind-action.py approve REM-XXXX                   # 审批通过
  remind-action.py reject REM-XXXX "驳回理由"          # 驳回
  remind-action.py list [pending|active|done]         # 列队列
  remind-action.py run REM-XXXX                       # 手动触发（测试用）
  remind-action.py status                             # 全局状态

完整链路:
  submit → pending.md → approve → active.md + countdown-scheduler → 执行 → done.md
"""

import argparse
import json
import os
import urllib.request
import urllib.parse
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────
BASE = "/var/minis/shared/gzh-team"
REMINDERS_DIR = f"{BASE}/docs/reminders"
PENDING = f"{REMINDERS_DIR}/pending.md"
ACTIVE = f"{REMINDERS_DIR}/active.md"
DONE = f"{REMINDERS_DIR}/done.md"
PROPOSALS = f"{REMINDERS_DIR}/proposals.md"
SCHEDULER = "/var/minis/shared/countdown-scheduler.py"
SCHEDULER_STATE = "/var/minis/shared/.scheduler/countdown-tasks.json"

ROLES = {
    "01": "01-lead", "02": "02-research", "03": "03-structure",
    "04": "04-writer", "05": "05-review", "06": "06-layout",
    "07": "07-publish", "08": "08-reader", "09": "09-data",
}

WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}


# ═══════════════════════════════════════════════════════════
# 时间解析（复用 remind.py 逻辑）
# ═══════════════════════════════════════════════════════════

def _next_weekday(m):
    target = WEEKDAY_MAP[m.group(1)]
    today = datetime.now(timezone.utc).astimezone()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return timedelta(days=days_ahead)


def _this_weekday(m):
    target = WEEKDAY_MAP[m.group(1)]
    today = datetime.now(timezone.utc).astimezone()
    days_ahead = (target - today.weekday()) % 7
    return timedelta(days=days_ahead)


TIME_PATTERNS = [
    (re.compile(r"(\d+)\s*天后"), lambda m: timedelta(days=int(m.group(1)))),
    (re.compile(r"(\d+)\s*h(?:our)?s?\s*后", re.I), lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r"(\d+)\s*小时后"), lambda m: timedelta(hours=int(m.group(1)))),
    (re.compile(r"(\d+)\s*分钟?后"), lambda m: timedelta(minutes=int(m.group(1)))),
    (re.compile(r"明天"), lambda m: timedelta(days=1)),
    (re.compile(r"后天"), lambda m: timedelta(days=2)),
    (re.compile(r"下周([一二三四五六日])"), _next_weekday),
    (re.compile(r"本周([一二三四五六日])"), _this_weekday),
    (re.compile(r"下个月"), lambda m: timedelta(days=30)),
]


def parse_time(text):
    for pattern, fn in TIME_PATTERNS:
        m = pattern.search(text)
        if m:
            return fn(m), m.group(0)
    return None, None


# ═══════════════════════════════════════════════════════════
# 队列文件操作
# ═══════════════════════════════════════════════════════════

def read_queue(path):
    """读取队列文件，返回 (header, entries, footer)"""
    if not Path(path).exists():
        return "", [], ""
    content = Path(path).read_text(encoding="utf-8")
    # 简单分割：找 "## " 开头的区域
    lines = content.split("\n")
    header = []
    entries = []
    footer = []
    current = header
    in_section = False
    for line in lines:
        if line.startswith("## ") and not in_section:
            in_section = True
            current = entries
            current.append(line)
        elif line.startswith("## ") and in_section:
            current = footer
            current.append(line)
        else:
            current.append(line)
    return "\n".join(header), entries, "\n".join(footer)


def extract_entries(content):
    """从 Markdown 内容中提取条目（以 ### REM- 开头的块）"""
    pattern = re.compile(r'### REM-\d{8}-\d+.*?(?=\n### REM-|\n## |\Z)', re.DOTALL)
    return [m.group(0) for m in pattern.finditer(content)]


def remove_placeholder(content):
    """移除占位注释"""
    return content.replace("<!-- 无待审批条目 -->\n", "")


def add_placeholder(content):
    """添加占位注释（如果队列为空）"""
    if "无待审批条目" not in content and "无活跃条目" not in content and "无已完成" not in content:
        # 在最后一个 ## 区域前插入
        pass
    return content


# ═══════════════════════════════════════════════════════════
# ID 生成
# ═══════════════════════════════════════════════════════════

def next_rem_id():
    """从所有队列中找最大的 REM-YYYYMMDD-NN，+1"""
    today = datetime.now().strftime("%Y%m%d")
    max_n = 0
    for q in [PENDING, ACTIVE, DONE]:
        if Path(q).exists():
            content = Path(q).read_text(encoding="utf-8")
            for m in re.finditer(rf"REM-{today}-(\d+)", content):
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
    return f"REM-{today}-{max_n + 1:02d}"


# ═══════════════════════════════════════════════════════════
# Bark 通知
# ═══════════════════════════════════════════════════════════

def send_bark(title, body):
    """发送 Bark 通知（best-effort）"""
    bark_key = os.environ.get("BARK_KEY", "")
    if not bark_key:
        return False
    url = f"https://api.day.app/{bark_key}/{title}/{body}"
    try:
        subprocess.run(["curl", "-s", "-X", "POST", url],
                       capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def send_bark_url(title, body, url):
    """发送带 URL 的 Bark 通知（点击通知直接打开 URL）"""
    bark_key = os.environ.get("BARK_KEY", "")
    if not bark_key:
        return False
    encoded_url = urllib.parse.quote(url, safe="")
    bark_url = f"https://api.day.app/{bark_key}/{title}/{body}?url={encoded_url}"
    try:
        subprocess.run(["curl", "-s", "-X", "POST", bark_url],
                       capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def parse_entry(entry_text):
    """从条目文本中提取字段"""
    result = {}
    for pattern in [
        (r'\*\*rem_id\*\*:\s*(.+)', 'rem_id'),
        (r'\*\*action\*\*:\s*(.+)', 'action'),
        (r'\*\*trigger_kind\*\*:\s*(.+)', 'kind'),
        (r'\*\*created_by\*\*:\s*(.+)', 'role'),
        (r'\*\*fire_at\*\*:\s*(.+)', 'fire_at'),
    ]:
        match = re.search(pattern[0], entry_text)
        if match:
            result[pattern[1]] = match.group(1).strip()
    result['raw'] = entry_text
    return result if result.get('action') else None


# ═══════════════════════════════════════════════════════════
# SUBMIT — 提交新提案
# ═══════════════════════════════════════════════════════════

def cmd_submit(args):
    text = args.text
    now = datetime.now(timezone.utc).astimezone()
    now_str = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    print(f"📝 解析: \"{text}\"")

    # 1. 时间
    delta, matched = parse_time(text)
    if delta is None:
        delta = timedelta(days=7)
        matched = "默认:7天后"
    fire_at = (now + delta).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    print(f"  ⏰ 时间: \"{matched}\" → {fire_at}")

    # 2. 岗位
    role_code, role_name = None, None
    for code, name in ROLES.items():
        if code in text or name in text:
            role_code, role_name = code, name
            break
    if args.role:
        role_code = args.role
        role_name = ROLES.get(args.role, args.role)
    if not role_code:
        role_code, role_name = "01", "01-lead"
    print(f"  👤 发起: {role_code} ({role_name})")

    # 3. 档位
    if re.search(r"和\s*\d+\s*\w+?\s*一起|跨岗位|协作", text):
        kind = "cross"
    elif re.search(r"规则内置|10\s*篇|复盘提醒|自动", text):
        kind = "auto"
    else:
        kind = "role"
    kind_label = {"auto": "规则内置（自动通过）", "role": "单岗位", "cross": "跨岗位协作"}
    print(f"  📋 档位: {kind}（{kind_label[kind]}）")

    # 4. ID
    rid = next_rem_id()
    print(f"  🆔 ID: {rid}")

    # 5. 构建条目
    confirmed_by = "auto:rule-10-articles" if kind == "auto" else ""
    confirmed_at = now_str if kind == "auto" else ""
    status = "active" if kind == "auto" else "pending"

    entry = f"""### {rid} · {role_name} 提案

- **created_at**: {now_str}
- **created_by**: {role_name}
- **fire_at**: {fire_at}
- **confirmed_by**: {confirmed_by}
- **confirmed_at**: {confirmed_at}
- **trigger_kind**: {kind}
- **reason**: {text}
- **action**: {text}
- **status**: {status}
- **result**: （待触发）
- **related_task**: （待填）

"""

    # 6. 写入队列
    if kind == "auto":
        # A 档：直接进 active.md
        target = ACTIVE
        print("  ⚡ A 档规则内置 → 直接进 active.md，无需审批")
    else:
        target = PENDING
        print("  📋 B/C 档 → 进 pending.md，等待 01-lead 审批")

    content = Path(target).read_text(encoding="utf-8")
    content = remove_placeholder(content)

    # 在 "## 待审批" 或 "## 活跃任务" 后插入
    section_header = "## 待审批" if target == PENDING else "## 活跃任务"
    insert_pos = content.find(section_header)
    if insert_pos >= 0:
        end_pos = content.find("\n## ", insert_pos + len(section_header))
        if end_pos < 0:
            end_pos = len(content)
        content = content[:end_pos] + f"\n{entry}" + content[end_pos:]

    Path(target).write_text(content, encoding="utf-8")
    print(f"  ✅ 已写入 {target}")

    # 7. 如果是 A 档，注册调度器
    if kind == "auto":
        countdown_sec = int(delta.total_seconds())
        cmd = [
            "python3", SCHEDULER, "add",
            "--name", rid,
            "--countdown", f"{countdown_sec}s",
            "--kind", "prompt",
            "--prompt", text,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  🔧 调度器: {result.stdout.strip()}")

    # 8. Bark 通知 — 包含 Worker 审批 URL（Minis 被杀后台也能处理）
    if kind != "auto":
        worker_url = os.environ.get("WORKER_URL", "").rstrip("/")
        if worker_url:
            approve_url = f"{worker_url}/remind/approve?rem_id={rid}"
            reject_url = f"{worker_url}/remind/reject?rem_id={rid}&reason=未提供理由"
            body = f"{role_name}: {text[:60]}\n\n✅ 批: {approve_url}\n❌ 驳: {reject_url}"
            send_bark_url(f"待审批提醒 · {rid}", body, approve_url)
        else:
            send_bark(f"待审批提醒 · {rid}",
                      f"{role_name}: {text[:60]}\n回复'批 {rid}'或'驳回 {rid} 理由'")
        print("  📡 Bark 通知已发送给 01-lead")

    print(f"\n✅ 提交完成: {rid}")
    return 0


# ═══════════════════════════════════════════════════════════
# APPROVE — 审批通过
# ═══════════════════════════════════════════════════════════

def cmd_approve(args):
    rid = args.id
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # 从 pending.md 找条目
    content = Path(PENDING).read_text(encoding="utf-8")
    pattern = re.compile(rf'### {re.escape(rid)}.*?(?=\n### |\n## |\Z)', re.DOTALL)
    match = pattern.search(content)
    if not match:
        print(f"错误: {rid} 不在 pending.md 中")
        return 1

    entry = match.group(0)
    print(f"📋 审批: {rid}")

    # 提取字段
    fire_at = re.search(r'\*\*fire_at\*\*:\s*(.+)', entry).group(1).strip()
    action = re.search(r'\*\*action\*\*:\s*(.+)', entry).group(1).strip()
    kind = re.search(r'\*\*trigger_kind\*\*:\s*(.+)', entry).group(1).strip()
    role = re.search(r'\*\*created_by\*\*:\s*(.+)', entry).group(1).strip()

    print(f"   发起: {role}  |  触发: {fire_at}  |  档位: {kind}")
    print(f"   action: {action}")

    # 更新 confirmed_by / confirmed_at / status
    entry = re.sub(r'\*\*confirmed_by\*\*:\s*.+', f"**confirmed_by**: 01-lead", entry)
    entry = re.sub(r'\*\*confirmed_at\*\*:\s*.+', f"**confirmed_at**: {now_str}", entry)
    entry = re.sub(r'\*\*status\*\*:\s*pending', f"**status**: active", entry)

    # 从 pending.md 移除
    content = content.replace(match.group(0), "")
    content = remove_placeholder(content)
    # 确保占位符存在
    if "无待审批条目" not in content:
        content = content.replace("## 待审批\n", "## 待审批\n\n<!-- 无待审批条目 -->\n")
    Path(PENDING).write_text(content, encoding="utf-8")
    print(f"  ✅ 已从 pending.md 移除")

    # 追加到 active.md
    active_content = Path(ACTIVE).read_text(encoding="utf-8")
    active_content = remove_placeholder(active_content)
    insert_pos = active_content.find("## 活跃任务")
    if insert_pos >= 0:
        end_pos = active_content.find("\n## ", insert_pos + len("## 活跃任务"))
        if end_pos < 0:
            end_pos = len(active_content)
        active_content = active_content[:end_pos] + f"\n{entry}" + active_content[end_pos:]
    Path(ACTIVE).write_text(active_content, encoding="utf-8")
    print(f"  ✅ 已写入 active.md")

    # 计算倒计时
    fire_dt = datetime.fromisoformat(fire_at)
    now_dt = datetime.now(timezone.utc).astimezone()
    countdown_sec = max(1, int((fire_dt - now_dt).total_seconds()))

    # 注册调度器
    cmd = [
        "python3", SCHEDULER, "add",
        "--name", rid,
        "--countdown", f"{countdown_sec}s",
        "--kind", "prompt",
        "--prompt", action,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"  🔧 调度器: {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"  ⚠️  stderr: {result.stderr.strip()}")

    send_bark(f"已批准 · {rid}", f"{role}: {action[:60]}")
    print(f"\n✅ {rid} 已批准并注册调度器")
    return 0


# ═══════════════════════════════════════════════════════════
# SYNC-FROM-WORKER — 拉取 Worker 端的审批决定
# ═══════════════════════════════════════════════════════════
# 用途：Minis 被杀后台时，Bark 审批通过 Worker 处理。
# Minis 恢复后运行此命令，把 Worker KV 里的决定同步到本地队列。

def cmd_sync_from_worker(args):
    """从 Worker 拉取审批决定并应用"""
    worker_url = os.environ.get("WORKER_URL", "").rstrip("/")
    if not worker_url:
        print("❌ WORKER_URL 未设置")
        return 1

    print(f"🔍 拉取 Worker 审批决定: {worker_url}/remind/decisions")
    try:
        req = urllib.request.Request(f"{worker_url}/remind/decisions")
        req.add_header("User-Agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)")
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        return 1

    decisions = data.get("decisions", [])
    if not decisions:
        print("✅ 无待处理的审批决定")
        return 0

    print(f"📋 找到 {len(decisions)} 条审批决定:")
    for d in decisions:
        rid = d["rem_id"]
        status = d["status"]
        print(f"  {rid}: {status} @ {d.get('decided_at', '?')}")

        # 查找对应的 pending 条目
        pending_path = Path(PENDING)
        if not pending_path.exists():
            print(f"  ⚠️  pending.md 不存在，跳过 {rid}")
            continue

        content = pending_path.read_text(encoding="utf-8")
        pattern = re.compile(rf'### {re.escape(rid)}.*?(?=\n### |\n## |\Z)', re.DOTALL)
        match = pattern.search(content)
        if not match:
            print(f"  ⚠️  {rid} 不在 pending.md 中（可能已被处理）")
            continue

        entry_text = match.group(0)
        entry = parse_entry(entry_text)
        if not entry:
            print(f"  ⚠️  解析 {rid} 失败")
            continue

        if status == "approved":
            print(f"  ✅ 自动批准 {rid}: {entry['action'][:60]}")
            # 直接调用 approve 逻辑
            _approve_entry(rid, entry)
        elif status == "rejected":
            reason = d.get("reason", "未提供理由")
            print(f"  ❌ 自动驳回 {rid}: {reason}")
            _reject_entry(rid, entry, reason)

    # 清空已处理的决定
    try:
        req = urllib.request.Request(
            f"{worker_url}/remind/delete-decisions",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # best-effort

    print("\n✅ 同步完成")
    return 0


def _approve_entry(rid, entry):
    """审批条目（从 pending → active + 调度器）"""
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    role = entry.get("role", "unknown")
    fire_at = entry.get("fire_at", "")
    action = entry.get("action", "")
    kind = entry.get("kind", "role")

    # 构建 active 格式条目
    active_line = (
        f"### {rid} · {role} 提案\n\n"
        f"- **created_at**: {entry.get('created_at', '')}\n"
        f"- **created_by**: {role}\n"
        f"- **fire_at**: {fire_at}\n"
        f"- **confirmed_by**: 01-lead\n"
        f"- **confirmed_at**: {now_str}\n"
        f"- **trigger_kind**: {kind}\n"
        f"- **reason**: {action}\n"
        f"- **action**: {action}\n"
        f"- **status**: active\n"
        f"- **result**: （待触发）\n"
        f"- **related_task**: （待填）\n"
    )

    # 从 pending.md 移除
    pending_path = Path(PENDING)
    content = pending_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'### {re.escape(rid)}.*?(?=\n### |\n## |\Z)', re.DOTALL)
    content = pattern.sub('', content).strip() + '\n'
    pending_path.write_text(content, encoding="utf-8")

    # 追加到 active.md
    active_path = Path(ACTIVE)
    content = active_path.read_text(encoding="utf-8")
    content = content.replace("<!-- 无活跃条目 -->\n", "")
    insert_pos = content.find("## 活跃任务")
    if insert_pos >= 0:
        end_pos = content.find("\n## ", insert_pos + len("## 活跃任务"))
        if end_pos < 0:
            end_pos = len(content)
        content = content[:end_pos] + active_line + content[end_pos:]
    else:
        content += active_line
    active_path.write_text(content, encoding="utf-8")

    # 注册调度器
    countdown_sec = 86400  # 默认 1 天
    if fire_at:
        try:
            fire_dt = datetime.fromisoformat(fire_at)
            now_dt = datetime.now(timezone.utc).astimezone()
            countdown_sec = max(1, int((fire_dt - now_dt).total_seconds()))
        except Exception:
            pass
    cmd = [
        "python3", SCHEDULER, "add",
        "--name", rid,
        "--countdown", f"{countdown_sec}s",
        "--kind", "prompt",
        "--prompt", action,
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    send_bark(f"已批准 · {rid}", f"{role}: {action[:60]}")


def _reject_entry(rid, entry, reason):
    """驳回条目（从 pending → done.md）"""
    # 从 pending.md 移除
    pending_path = Path(PENDING)
    content = pending_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'### {re.escape(rid)}.*?(?=\n### |\n## |\Z)', re.DOTALL)
    content = pattern.sub('', content).strip() + '\n'
    pending_path.write_text(content, encoding="utf-8")

    # 追加到 done.md
    done_path = Path(DONE)
    content = done_path.read_text(encoding="utf-8")
    content = content.replace("<!-- 无已完成条目 -->\n", "")
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    content += f"### {rid}\n{entry['raw']}\n- **状态**: rejected\n- **决定时间**: {now_str}\n- **驳回原因**: {reason}\n\n"
    done_path.write_text(content, encoding="utf-8")

    send_bark(f"已驳回 · {rid}", f"{entry['role']}: {entry['action'][:60]}\n原因: {reason}")


# ═══════════════════════════════════════════════════════════
# REJECT — 驳回
# ═══════════════════════════════════════════════════════════

def cmd_reject(args):
    rid = args.id
    reason = args.reason or "未提供理由"

    content = Path(PENDING).read_text(encoding="utf-8")
    pattern = re.compile(rf'### {re.escape(rid)}.*?(?=\n### |\n## |\Z)', re.DOTALL)
    match = pattern.search(content)
    if not match:
        print(f"错误: {rid} 不在 pending.md 中")
        return 1

    entry = match.group(0)
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # 更新状态
    entry = re.sub(r'\*\*status\*\*:\s*pending', '**status**: rejected', entry)
    entry += f"\n- **reject_reason**: {reason}\n- **rejected_at**: {now_str}\n"

    # 从待审批移除，移到已驳回
    content = content.replace(match.group(0), "")
    content = remove_placeholder(content)
    if "无待审批条目" not in content:
        content = content.replace("## 待审批\n", "## 待审批\n\n<!-- 无待审批条目 -->\n")

    # 追加到已驳回区域
    reject_pos = content.find("## 已驳回")
    if reject_pos >= 0:
        end_pos = content.find("\n## ", reject_pos + len("## 已驳回"))
        if end_pos < 0:
            end_pos = len(content)
        content = content[:end_pos] + f"\n{entry}" + content[end_pos:]

    Path(PENDING).write_text(content, encoding="utf-8")
    print(f"❌ {rid} 已驳回: {reason}")
    return 0


# ═══════════════════════════════════════════════════════════
# LIST — 列队列
# ═══════════════════════════════════════════════════════════

def cmd_list(args):
    queue = args.queue or "pending"
    path_map = {"pending": PENDING, "active": ACTIVE, "done": DONE}
    path = path_map.get(queue)
    if not path or not Path(path).exists():
        print(f"队列 {queue} 不存在")
        return 1

    content = Path(path).read_text(encoding="utf-8")
    entries = extract_entries(content)

    if not entries:
        print(f"📄 {queue}.md — 空队列")
        return 0

    print(f"📄 {queue}.md — {len(entries)} 条目")
    print("-" * 80)
    for e in entries:
        rid = re.search(r'### (REM-\S+)', e).group(1)
        role = re.search(r'\*\*created_by\*\*:\s*(.+)', e).group(1).strip()
        status = re.search(r'\*\*status\*\*:\s*(.+)', e).group(1).strip()
        fire = re.search(r'\*\*fire_at\*\*:\s*(.+)', e).group(1).strip()
        action = re.search(r'\*\*action\*\*:\s*(.+)', e).group(1).strip()
        print(f"  {rid} | {role:14s} | {status:8s} | {fire} | {action[:50]}")
    return 0


# ═══════════════════════════════════════════════════════════
# RUN — 手动触发
# ═══════════════════════════════════════════════════════════

def cmd_run(args):
    rid = args.id
    # 从 active.md 找
    content = Path(ACTIVE).read_text(encoding="utf-8")
    pattern = re.compile(rf'### {re.escape(rid)}.*?(?=\n### |\n## |\Z)', re.DOTALL)
    match = pattern.search(content)
    if not match:
        print(f"错误: {rid} 不在 active.md 中")
        return 1

    entry = match.group(0)
    action = re.search(r'\*\*action\*\*:\s*(.+)', entry).group(1).strip()
    role = re.search(r'\*\*created_by\*\*:\s*(.+)', entry).group(1).strip()

    print(f"🔥 手动触发: {rid}")
    print(f"   发起: {role}")
    print(f"   action: {action}")
    print(f"   (实际执行需对应岗位在会话中处理)")

    # 标记为完成
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    entry = re.sub(r'\*\*status\*\*:\s*active', '**status**: done', entry)
    entry = re.sub(r'\*\*result\*\*:\s*（待触发）', f"**result**: 手动触发，{action[:100]}", entry)

    # 从 active.md 移除
    content = content.replace(match.group(0), "")
    content = remove_placeholder(content)
    if "无活跃条目" not in content:
        content = content.replace("## 活跃任务\n", "## 活跃任务\n\n<!-- 无活跃条目 -->\n")
    Path(ACTIVE).write_text(content, encoding="utf-8")

    # 从调度器移除
    scheduler_path = Path(SCHEDULER).parent / ".scheduler" / "countdown-tasks.json"
    if scheduler_path.exists():
        state = json.loads(scheduler_path.read_text(encoding="utf-8"))
        old_count = len(state.get("tasks", []))
        state["tasks"] = [t for t in state.get("tasks", []) if t.get("name") != rid]
        new_count = len(state["tasks"])
        if old_count != new_count:
            scheduler_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  🗑️  调度器: 移除 {old_count - new_count} 条")
        else:
            print(f"  ⚠️  调度器: 未找到对应任务")

    # 追加到 done.md
    done_content = Path(DONE).read_text(encoding="utf-8")
    done_content = remove_placeholder(done_content)
    insert_pos = done_content.find("## 已完成")
    if insert_pos >= 0:
        end_pos = done_content.find("\n## ", insert_pos + len("## 已完成"))
        if end_pos < 0:
            end_pos = len(done_content)
        done_content = done_content[:end_pos] + f"\n{entry}" + done_content[end_pos:]
    Path(DONE).write_text(done_content, encoding="utf-8")

    print(f"  ✅ 已从 active.md 移除 → done.md")
    return 0


# ═══════════════════════════════════════════════════════════
# STATUS — 全局状态
# ═══════════════════════════════════════════════════════════

def cmd_status(args):
    print("╔══════════════════════════════════════╗")
    print("║     提醒系统全局状态                  ║")
    print("╚══════════════════════════════════════╝")
    print()

    for name, path in [("pending", PENDING), ("active", ACTIVE), ("done", DONE)]:
        if Path(path).exists():
            content = Path(path).read_text(encoding="utf-8")
            entries = extract_entries(content)
            print(f"  📄 {name}.md: {len(entries)} 条")
        else:
            print(f"  📄 {name}.md: 不存在")

    # 调度器状态
    print()
    subprocess.run(["python3", SCHEDULER, "status"])
    return 0


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="提醒系统完整生命周期管理",
        epilog="示例: remind-action.py submit \"3天后检查这篇稿子的72h阅读量\" --role 07"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # submit
    p_submit = sub.add_parser("submit", help="提交新提案")
    p_submit.add_argument("text", help="自然语言描述")
    p_submit.add_argument("--role", help="指定发起岗位")

    # approve
    p_approve = sub.add_parser("approve", help="审批通过")
    p_approve.add_argument("id", help="REM-XXXX")

    # reject
    p_reject = sub.add_parser("reject", help="驳回")
    p_reject.add_argument("id", help="REM-XXXX")
    p_reject.add_argument("reason", help="驳回理由")

    # list
    p_list = sub.add_parser("list", help="列队列")
    p_list.add_argument("queue", nargs="?", default="pending",
                        choices=["pending", "active", "done"])

    # run
    p_run = sub.add_parser("run", help="手动触发（测试）")
    p_run.add_argument("id", help="REM-XXXX")

    # status
    sub.add_parser("status", help="全局状态")

    # sync-from-worker
    sub.add_parser("sync-from-worker", help="从 Worker 拉取审批决定")

    args = parser.parse_args()

    commands = {
        "submit": cmd_submit,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "list": cmd_list,
        "run": cmd_run,
        "status": cmd_status,
        "sync-from-worker": cmd_sync_from_worker,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)