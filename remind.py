#!/usr/bin/env python3
# Version: 0.1.0
"""
minis_url: minis://shared/remind.py

自然语言 → 标准化提醒提案
==========================
用法:
  python3 remind.py "3天后检查这篇稿子的72h阅读量"
  python3 remind.py "下周二复盘10篇稿件的G0门禁结果"
  python3 remind.py "和09数据一起复盘这篇稿子的传播路径"

输出:
  - 解析自然语言 → 标准化字段
  - 写入 pending.md（待审批队列）
  - Bark 通知 01 负责人审批

设计原则（01 负责人 09-22 讨论结论）:
  岗位只需要说一句话，系统自动解析、写入、通知。
  审批环节异步化——01 在 Bark 里回"批"或"驳回理由"即可。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ── 路径 ──────────────────────────────────────────────
BASE = "/var/minis/shared/gzh-team"
PENDING = f"{BASE}/docs/reminders/pending.md"
PROPOSALS = f"{BASE}/docs/reminders/proposals.md"
RULES = f"{BASE}/docs/rules/reminders.md"

# ── 岗位映射 ──────────────────────────────────────────
ROLES = {
    "01": "01-lead",
    "02": "02-research",
    "03": "03-structure",
    "04": "04-writer",
    "05": "05-review",
    "06": "06-layout",
    "07": "07-publish",
    "08": "08-reader",
    "09": "09-data",
}

# ── 时间解析 ──────────────────────────────────────────
# 支持: 3天后 / 下周二 / 2小时后 / 72h后 / 明天 / 本周五 / 下个月
WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}


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
    # "3天后" / "3天后" / "3 日后"
    (re.compile(r"(\d+)\s*天后"), lambda m: timedelta(days=int(m.group(1)))),
    # "72h后" / "72小时后" / "72h 后"
    (re.compile(r"(\d+)\s*h(?:our)?s?\s*后", re.I), lambda m: timedelta(hours=int(m.group(1)))),
    # "2小时后" / "2 小时后"
    (re.compile(r"(\d+)\s*小时后"), lambda m: timedelta(hours=int(m.group(1)))),
    # "30分钟后" / "30 分钟后"
    (re.compile(r"(\d+)\s*分钟?后"), lambda m: timedelta(minutes=int(m.group(1)))),
    # "明天"
    (re.compile(r"明天"), lambda m: timedelta(days=1)),
    # "后天"
    (re.compile(r"后天"), lambda m: timedelta(days=2)),
    # "下周二" ~ "下周日"
    (re.compile(r"下周([一二三四五六日])"), _next_weekday),
    # "本周五" ~ "本周日"
    (re.compile(r"本周([一二三四五六日])"), _this_weekday),
    # "下个月"
    (re.compile(r"下个月"), lambda m: timedelta(days=30)),
]


def parse_time(text):
    """从自然语言中解析相对时间，返回 timedelta。"""
    for pattern, fn in TIME_PATTERNS:
        m = pattern.search(text)
        if m:
            return fn(m), m.group(0)
    return None, None


# ── 岗位识别 ──────────────────────────────────────────
def detect_role(text):
    """从自然语言中识别发起岗位。"""
    # 优先匹配 "和09数据一起" 这种跨岗位表述
    for code, name in ROLES.items():
        if code in text or name in text:
            return code, name
    return None, None


# ── 档位判断 ──────────────────────────────────────────
def detect_kind(text):
    """判断触发档位：auto / role / cross。"""
    if re.search(r"和\s*\d+\s*\w+?\s*一起|跨岗位|协作", text):
        return "cross"
    if re.search(r"规则内置|10\s*篇|复盘提醒|自动", text):
        return "auto"
    return "role"


# ── ID 生成 ───────────────────────────────────────────
def next_id():
    """从 pending.md 中读取已有 REM- 条目，生成下一个 REM-YYYYMMDD-NN。"""
    today = datetime.now().strftime("%Y%m%d")
    max_n = 0
    if os.path.exists(PENDING):
        with open(PENDING, "r") as f:
            content = f.read()
        for m in re.finditer(rf"REM-{today}-(\d+)", content):
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"REM-{today}-{max_n + 1:02d}"


# ── Bark 通知 ──────────────────────────────────────────
def send_bark(title, body):
    """发送 Bark 通知（best-effort，失败不影响主流程）。"""
    bark_key = os.environ.get("BARK_KEY", "")
    if not bark_key:
        print("  [Bark] 未配置 BARK_KEY，跳过通知")
        return
    url = f"https://api.day.app/{bark_key}/{title}/{body}"
    try:
        subprocess.run(["curl", "-s", "-X", "POST", url],
                       capture_output=True, timeout=10)
        print("  [Bark] 通知已发送")
    except Exception as e:
        print(f"  [Bark] 发送失败: {e}")


# ── 写入 pending.md ────────────────────────────────────
def write_pending(entry):
    """将提案追加到 pending.md 的待审批队列。"""
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(PENDING):
        print(f"错误: {PENDING} 不存在")
        sys.exit(1)

    with open(PENDING, "r") as f:
        content = f.read()

    # 移除旧的占位注释
    content = content.replace("<!-- 无待审批条目 -->\n", "")

    # 在 "## 待审批" 后、"## 已驳回" 前插入
    insert_pos = content.find("## 待审批")
    if insert_pos >= 0:
        end_of_section = content.find("\n## 已驳回", insert_pos)
        if end_of_section >= 0:
            content = content[:end_of_section] + f"\n{entry}\n" + content[end_of_section:]
        else:
            content = content[:insert_pos] + "## 待审批\n" + f"\n{entry}\n" + content[insert_pos + len("## 待审批"):]

    with open(PENDING, "w") as f:
        f.write(content)
    print(f"  [Pending] 已写入 {PENDING}")


# ── 主流程 ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="自然语言 → 标准化提醒提案",
        epilog="示例: python3 remind.py \"3天后检查这篇稿子的72h阅读量\""
    )
    parser.add_argument("text", help="自然语言描述的提醒内容")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="只解析不写入")
    parser.add_argument("--role", help="手动指定发起岗位（如 07）")
    args = parser.parse_args()

    text = args.text
    now = datetime.now(timezone.utc).astimezone()
    now_str = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    print(f"📝 解析: \"{text}\"")
    print()

    # 1. 时间解析
    delta, matched_time = parse_time(text)
    if delta is None:
        # 无时间表达式时默认 7 天后（A 档规则内置提醒常用）
        delta = timedelta(days=7)
        matched_time = "默认:7天后"
    fire_at = (now + delta).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    print(f"  ⏰ 时间: \"{matched_time}\" → {fire_at}")

    # 2. 岗位识别
    role_code, role_name = detect_role(text)
    if args.role:
        role_code = args.role
        role_name = ROLES.get(args.role, args.role)
    if not role_code:
        print("  ⚠️  无法识别发起岗位，请用 --role 指定（如 --role 07）")
        role_code = "01"
        role_name = "01-lead"

    print(f"  👤 发起: {role_code} ({role_name})")

    # 3. 档位判断
    kind = detect_kind(text)
    kind_label = {"auto": "规则内置（自动通过）", "role": "单岗位", "cross": "跨岗位协作"}
    print(f"  📋 档位: {kind}（{kind_label[kind]}）")

    # 4. ID 生成
    rid = next_id()
    print(f"  🆔 ID: {rid}")

    # 5. 构建提案条目
    entry = f"""### {rid} · {role_name} 提案

- **created_at**: {now_str}
- **created_by**: {role_name}
- **fire_at**: {fire_at}
- **confirmed_by**: （待 01-lead 审批）
- **confirmed_at**: （待 01-lead 审批）
- **trigger_kind**: {kind}
- **reason**: {text}
- **action**: {text}
- **status**: pending
- **result**: （待触发）
- **related_task**: （待填）

"""

    if args.dry_run:
        print()
        print("=== DRY RUN · 未写入 ===")
        print(entry)
        return

    # 6. 写入 pending.md
    write_pending(entry)

    # 7. Bark 通知
    bark_title = f"待审批提醒 · {rid}"
    bark_body = f"{role_name}: {text[:60]}"
    send_bark(bark_title, bark_body)

    print()
    print(f"✅ 提案已创建: {rid}")
    print(f"   审批入口: 01-lead 在 Bark 回 \"批 {rid}\" 或 \"驳回 {rid} 理由\"")


if __name__ == "__main__":
    main()