#!/usr/bin/env python3
"""
待确认区 — 借鉴 Biz Novel Studio 提案 vs 已入账分离机制

核心原则：AI 提取的推断结果不自动写为既成事实。
所有 AI 生成的角色状态/事件/物品变化先进入待确认区，
人工确认后才写入正式账本 (facts.json)。

用法：
  python pending-review.py add --novel-id my-novel --chapter 3 \\
    --category character --content "萧辰突破至淬体五重" --source "AI推理"
  python pending-review.py list --novel-id my-novel
  python pending-review.py approve --novel-id my-novel --id P001
  python pending-review.py reject --novel-id my-novel --id P001 --reason "与第2章冲突"
  python pending-review.py auto-approve --novel-id my-novel  # 批量确认低风险提案
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/var/minis/shared/novel-team")
LEDGER_DIR = BASE_DIR / "ledger"

# 低风险类别可直接确认（纯格式/元数据），其余需人工确认
AUTO_APPROVE_CATEGORIES = {"metadata", "formatting", "word_count_note"}


def pending_path(novel_id: str) -> Path:
    p = LEDGER_DIR / novel_id
    p.mkdir(parents=True, exist_ok=True)
    return p / "pending.json"


def facts_path(novel_id: str) -> Path:
    return LEDGER_DIR / novel_id / "facts.json"


def load_pending(novel_id: str) -> list:
    f = pending_path(novel_id)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return []


def save_pending(novel_id: str, data: list):
    pending_path(novel_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def next_id(pending: list) -> str:
    nums = []
    for p in pending:
        pid = p.get("id", "")
        if pid.startswith("P"):
            try:
                nums.append(int(pid[1:]))
            except ValueError:
                pass
    return f"P{max(nums, default=0)+1:03d}"


def add_pending(novel_id: str, chapter: int, category: str,
                content: str, source: str = "AI推理",
                confidence: float = 0.7) -> dict:
    """
    将 AI 提取结果写入待确认区。
    confidence >= 0.9 且 category 在白名单内时自动入账。
    """
    pending = load_pending(novel_id)
    pid = next_id(pending)

    entry = {
        "id": pid,
        "chapter": chapter,
        "category": category,
        "content": content,
        "source": source,
        "confidence": confidence,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "decided_at": None,
        "decision_note": "",
    }

    auto = (confidence >= 0.9 and category in AUTO_APPROVE_CATEGORIES)
    if auto:
        entry["status"] = "approved"
        entry["decided_at"] = datetime.now().isoformat()
        entry["decision_note"] = "自动确认（低风险类别）"

    pending.append(entry)
    save_pending(novel_id, pending)

    if auto:
        _write_to_facts(novel_id, entry)
        return {"id": pid, "status": "auto_approved", "action": "已自动入账"}
    return {"id": pid, "status": "pending", "action": "等待人工确认"}


def _write_to_facts(novel_id: str, entry: dict):
    """将已确认条目写入正式账本"""
    f = facts_path(novel_id)
    facts = {}
    if f.exists():
        facts = json.loads(f.read_text(encoding="utf-8"))

    existing_nums = []
    for k in facts:
        if k.startswith("F"):
            try:
                existing_nums.append(int(k[1:]))
            except ValueError:
                pass
    fid = f"F{max(existing_nums, default=0)+1:04d}"

    facts[fid] = {
        "id": fid,
        "category": entry["category"],
        "content": entry["content"],
        "source": f"第{entry['chapter']}章·{entry['source']}",
        "created_at": datetime.now().isoformat(),
        "verified": True,
        "pending_id": entry["id"],
    }
    f.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")


def approve(novel_id: str, pid: str, note: str = "") -> dict:
    pending = load_pending(novel_id)
    for e in pending:
        if e["id"] == pid:
            if e["status"] != "pending":
                return {"ok": False, "error": f"{pid} 状态为 {e['status']}，无法重复确认"}
            e["status"] = "approved"
            e["decided_at"] = datetime.now().isoformat()
            e["decision_note"] = note
            save_pending(novel_id, pending)
            _write_to_facts(novel_id, e)
            return {"ok": True, "msg": f"{pid} 已确认并入账 facts.json"}
    return {"ok": False, "error": f"未找到 {pid}"}


def reject(novel_id: str, pid: str, reason: str = "") -> dict:
    pending = load_pending(novel_id)
    for e in pending:
        if e["id"] == pid:
            if e["status"] != "pending":
                return {"ok": False, "error": f"{pid} 已处理，状态: {e['status']}"}
            e["status"] = "rejected"
            e["decided_at"] = datetime.now().isoformat()
            e["decision_note"] = reason
            save_pending(novel_id, pending)
            return {"ok": True, "msg": f"{pid} 已拒绝，原因: {reason}"}
    return {"ok": False, "error": f"未找到 {pid}"}


def list_pending(novel_id: str, status: str = "pending") -> list:
    pending = load_pending(novel_id)
    if status == "all":
        return pending
    return [e for e in pending if e["status"] == status]


def auto_approve_safe(novel_id: str) -> dict:
    """批量自动确认：只处理 confidence>=0.8 且 category 在白名单的条目"""
    pending = load_pending(novel_id)
    approved = []
    for e in pending:
        if (e["status"] == "pending"
                and e.get("confidence", 0) >= 0.8
                and e["category"] in AUTO_APPROVE_CATEGORIES):
            e["status"] = "approved"
            e["decided_at"] = datetime.now().isoformat()
            e["decision_note"] = "批量自动确认"
            _write_to_facts(novel_id, e)
            approved.append(e["id"])
    save_pending(novel_id, pending)
    return {"approved": approved, "count": len(approved)}


def main():
    parser = argparse.ArgumentParser(description="待确认区管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="添加待确认条目")
    p_add.add_argument("--novel-id", required=True)
    p_add.add_argument("--chapter", type=int, required=True)
    p_add.add_argument("--category", required=True,
                       choices=["character", "event", "item", "world",
                                "relationship", "metadata"])
    p_add.add_argument("--content", required=True)
    p_add.add_argument("--source", default="AI推理")
    p_add.add_argument("--confidence", type=float, default=0.7)

    p_list = sub.add_parser("list", help="列出待确认条目")
    p_list.add_argument("--novel-id", required=True)
    p_list.add_argument("--status", default="pending",
                        choices=["pending", "approved", "rejected", "all"])

    p_ap = sub.add_parser("approve", help="确认并写入正式账本")
    p_ap.add_argument("--novel-id", required=True)
    p_ap.add_argument("--id", required=True)
    p_ap.add_argument("--note", default="")

    p_rej = sub.add_parser("reject", help="拒绝条目")
    p_rej.add_argument("--novel-id", required=True)
    p_rej.add_argument("--id", required=True)
    p_rej.add_argument("--reason", default="")

    p_auto = sub.add_parser("auto-approve", help="批量确认低风险条目")
    p_auto.add_argument("--novel-id", required=True)

    args = parser.parse_args()

    if args.cmd == "add":
        r = add_pending(args.novel_id, args.chapter, args.category,
                        args.content, args.source, args.confidence)
        icon = "✅" if r["status"] in ("approved", "auto_approved") else "⏳"
        print(f"{icon} [{r['id']}] {r['action']}")
        print(f"   {args.category}: {args.content[:60]}")

    elif args.cmd == "list":
        items = list_pending(args.novel_id, args.status)
        if not items:
            print("✅ 无待确认条目")
            return
        print(f"共 {len(items)} 条（{args.status}）：")
        for e in items:
            icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
            print(f"  {icons.get(e['status'],'?')} [{e['id']}] ch{e['chapter']} "
                  f"{e['category']} (conf:{e.get('confidence','?')})")
            print(f"     {e['content'][:70]}")

    elif args.cmd == "approve":
        r = approve(args.novel_id, args.id, args.note)
        print(("✅ " if r["ok"] else "❌ ") + r.get("msg", r.get("error", "")))

    elif args.cmd == "reject":
        r = reject(args.novel_id, args.id, args.reason)
        print(("✅ " if r["ok"] else "❌ ") + r.get("msg", r.get("error", "")))

    elif args.cmd == "auto-approve":
        r = auto_approve_safe(args.novel_id)
        print(f"✅ 批量确认 {r['count']} 条: {r['approved']}")


if __name__ == "__main__":
    main()
