#!/usr/bin/env python3
# Version: 0.1.0
"""技能使用台账 —— 公众号流水线拆分观察期（2026-09-23 起）

规则：4 个子技能各调用 ≥8 次 且 零问题 → 可删除编排层 gongzhonghao-publish
用法：
  skill-usage.py bump <skill> [--issue "问题描述"]   # 每次使用某技能后 +1；发现问题时带 --issue
  skill-usage.py status                              # 观察期进度 + 是否可删
  skill-usage.py reset <skill|--all>                 # 问题修复后清零重计
诚实边界：iSH 没有技能调用的自动事件源，计数依赖"使用即 bump"的纪律。
"""
import json, sys, pathlib, argparse, datetime

DB = pathlib.Path("/var/minis/shared/skill-usage.json")
CHILDREN = ["gzh-chuang-gao", "gzh-pai-ban", "gzh-fa-qian-jian-cha", "gzh-api-tui-song"]
PARENT = "gongzhonghao-publish"
TARGET = 8

def load():
    if DB.exists():
        return json.loads(DB.read_text(encoding="utf-8"))
    return {s: {"count": 0, "issues": [], "last": None} for s in CHILDREN + [PARENT]}

def save(db):
    DB.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def status(db):
    print(f"{'技能':<24}{'次数':>4}  {'问题':>3}  最近使用")
    for s in CHILDREN:
        e = db.setdefault(s, {"count": 0, "issues": [], "last": None})
        print(f"{s:<24}{e['count']:>4}  {len(e['issues']):>3}  {e['last'] or '-'}")
    e = db.setdefault(PARENT, {"count": 0, "issues": [], "last": None})
    print(f"{PARENT:<24}{e['count']:>4}  {len(e['issues']):>3}  {e['last'] or '-'}  (待删的编排层)")
    short = {s: TARGET - db[s]["count"] for s in CHILDREN if db[s]["count"] < TARGET}
    probs = sum(len(db[s]["issues"]) for s in CHILDREN)
    if not short and probs == 0:
        print(f"\n✅ 判定：4 子技能均满 {TARGET} 次且零问题 → 可删除 {PARENT}（删除前仍需用户确认）")
    else:
        parts = [f"{s} 还差 {n} 次" for s, n in short.items()]
        if probs:
            parts.append(f"未结问题 {probs} 个")
        print(f"\n⏳ 观察中：{'；'.join(parts)}")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bump"); b.add_argument("skill"); b.add_argument("--issue")
    sub.add_parser("status")
    r = sub.add_parser("reset"); r.add_argument("skill"); r.add_argument("--all", action="store_true")
    a = ap.parse_args()
    db = load()
    if a.cmd == "bump":
        e = db.setdefault(a.skill, {"count": 0, "issues": [], "last": None})
        e["count"] += 1; e["last"] = now()
        if a.issue:
            e["issues"].append({"ts": now(), "desc": a.issue, "resolved": False})
        save(db)
        print(f"{a.skill}: {e['count']}/{TARGET if a.skill in CHILDREN else '—'}" + (f" +问题记录" if a.issue else ""))
        status(db)
    elif a.cmd == "reset":
        targets = CHILDREN + [PARENT] if a.all or a.skill == "all" else [a.skill]
        for s in targets:
            db[s] = {"count": 0, "issues": [], "last": None}
        save(db); print("已清零:", ", ".join(targets))
    else:
        status(db)

main()
