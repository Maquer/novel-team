#!/usr/bin/env python3
"""质量债务管理器 CLI 兼容垫片（v2 Phase 3）。

v1 的 tools/quality-debt.py（约 260 行：账本读写 + CLI 混在一起，
且 BASE_DIR 硬编码 /var/minis/shared/novel-team 无视 NOVEL_TEAM_ROOT）
已拆分：
- 账本访问层 → novelkit.stores.debt_store.DebtStore
  （根路径改走 novel_team_root()，修复 D3 同类 bug；
   账本文件位置约定不变：<root>/ledger/<novel_id>/quality-debt.json；
   写盘改为原子写 tmp+replace）
- 本文件只保留：参数解析、输出格式——与 v1 完全一致。

v1 原文件已冻结在基线（~/workspace/novel-assistant-audit/novel-team-fixed/），
此处为兼容垫片。
"""

import argparse
import sys
from pathlib import Path

# 让 novelkit 可导入（无论从哪个目录调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novelkit.stores.debt_store import (
    BLOCKING_LEVELS,
    DEBT_LEVELS,
    DebtStore,
)

_LEVEL_ICONS = {
    "local_patch_plan": "🔧",
    "continue_with_warning": "⚠️",
    "patchable_obligation_gap": "📌",
    "defer_and_continue": "💤",
    "stop_for_replan": "🛑",
    "data_integrity_failure": "💥",
}


def main():
    parser = argparse.ArgumentParser(description="质量债务管理器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="添加质量债务")
    p_add.add_argument("--novel-id", required=True)
    p_add.add_argument("--chapter", type=int, required=True)
    p_add.add_argument("--level", required=True,
                       choices=DEBT_LEVELS + list(BLOCKING_LEVELS))
    p_add.add_argument("--desc", required=True)
    p_add.add_argument("--gate", default="")

    p_list = sub.add_parser("list", help="列出质量债务")
    p_list.add_argument("--novel-id", required=True)
    p_list.add_argument("--chapter", type=int)
    p_list.add_argument("--status", default="open",
                        choices=["open", "resolved", "all"])

    p_res = sub.add_parser("resolve", help="标记债务已修复")
    p_res.add_argument("--novel-id", required=True)
    p_res.add_argument("--debt-id", required=True)
    p_res.add_argument("--note", default="")

    p_stats = sub.add_parser("stats", help="质量债务统计")
    p_stats.add_argument("--novel-id", required=True)

    args = parser.parse_args()
    store = DebtStore(args.novel_id)

    if args.cmd == "add":
        r = store.add_debt(args.chapter, args.level, args.desc, args.gate)
        icon = "🛑" if r["blocking"] else "✅"
        print(f"{icon} 债务已记录: {r['entry']['id']}")
        print(f"   级别: {args.level} — {r['suggestion']}")
        print(f"   继续创作: {'是' if r['continue_creation'] else '否（需人工介入）'}")

    elif args.cmd == "list":
        debts = store.list_debts(args.chapter, args.status)
        if not debts:
            print("✅ 无质量债务")
            return
        print(f"共 {len(debts)} 条：")
        for d in debts:
            icon = _LEVEL_ICONS.get(d["level"], "•")
            print(f"  {icon} [{d['id']}] ch{d['chapter']} {d['level']}")
            print(f"     {d['description'][:80]}")

    elif args.cmd == "resolve":
        r = store.resolve_debt(args.debt_id, args.note)
        if r["ok"]:
            print(f"✅ {args.debt_id} 已标记为已修复")
        else:
            print(f"❌ {r['error']}")

    elif args.cmd == "stats":
        st = store.stats()
        print(f"质量债务统计 — {args.novel_id}")
        print(f"  未解决: {st['total_open']}")
        print(f"  已解决: {st['total_resolved']}")
        if st["open_by_level"]:
            print("  按级别：")
            for lvl, cnt in sorted(st["open_by_level"].items()):
                print(f"    {lvl}: {cnt}")


if __name__ == "__main__":
    main()
