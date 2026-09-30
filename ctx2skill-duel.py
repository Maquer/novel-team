#!/usr/bin/env python3
# Version: 0.1.0
"""
ctx2skill-duel.py — 红蓝军自对弈 + 跨时间回放辅助脚本

借鉴 Ctx2Skill (清华大学自进化框架) 两个机制:
  1. 红蓝军对抗：蓝军(挑战者)出题挖漏洞 + 红军(推理者)解题暴露弱项
  2. 跨时间回放：双题库(困难/简单)历史版本回放，防对抗崩塌

用法:
  python3 ctx2skill-duel.py probe-banks <skill> list        # 列出题库内容
  python3 ctx2skill-duel.py probe-banks <skill> add-hard --prompt "..." --score 6
  python3 ctx2skill-duel.py probe-banks <skill> add-easy   --prompt "..." --score 9
  python3 ctx2skill-duel.py replay-history <skill> show     # 展示历史回放记录
  python3 ctx2skill-duel.py replay-history <skill> add --round 3 --version 18.07 --hard-acc 0.72 --easy-acc 0.95
  python3 ctx2skill-duel.py replay-history <skill> best     # 选最优(均衡)版本
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

PROBE_BANKS_DIR = "/var/minis/skills/darwin-skill/probe-banks"
REPLAY_HISTORY_DIR = "/var/minis/skills/darwin-skill/replay-history"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def probe_bank_path(skill):
    p = os.path.join(PROBE_BANKS_DIR, skill)
    ensure_dir(p)
    return p


def replay_dir_path(skill):
    p = os.path.join(REPLAY_HISTORY_DIR, skill)
    ensure_dir(p)
    return p


# ─── 题库操作 ───

def list_banks(skill):
    p = probe_bank_path(skill)
    hard_file = os.path.join(p, "hard.jsonl")
    easy_file = os.path.join(p, "easy.jsonl")
    for label, f in [("困难", hard_file), ("简单", easy_file)]:
        if os.path.exists(f):
            with open(f) as fh:
                lines = [l for l in fh if l.strip()]
            print(f"\n{label}题库 ({len(lines)}题):")
            for i, line in enumerate(lines):
                rec = json.loads(line)
                print(f"  [{i}] {rec.get('prompt','')[:80]}  (score={rec.get('score','?')})")
        else:
            print(f"\n{label}题库: 空")


def add_to_bank(skill, bank, prompt, score, round_num=None):
    p = probe_bank_path(skill)
    fname = "hard.jsonl" if bank == "hard" else "easy.jsonl"
    fpath = os.path.join(p, fname)
    rec = {
        "prompt": prompt,
        "score": score,
        "round": round_num or 0,
        "added_at": datetime.now(timezone.utc).isoformat()
    }
    with open(fpath, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"已加入{bank}题库: {prompt[:60]}... (score={score})")


# ─── 回放历史操作 ───

def add_replay(skill, round_num, version, hard_acc, easy_acc, total_score=None):
    d = replay_dir_path(skill)
    fpath = os.path.join(d, f"{round_num}-{version}.json")
    rec = {
        "round": round_num,
        "version": version,
        "hard_acc": hard_acc,
        "easy_acc": easy_acc,
        "total_score": total_score,
        "recorded_at": datetime.now(timezone.utc).isoformat()
    }
    with open(fpath, "w") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
    print(f"记录回放: round={round_num}, version={version}, hard_acc={hard_acc}, easy_acc={easy_acc}")


def show_replays(skill):
    d = replay_dir_path(skill)
    if not os.path.exists(d):
        print("无回放记录")
        return
    files = sorted(os.listdir(d), key=lambda x: (int(x.split("-")[0]), float(x.split("-")[1].replace(".json",""))))
    print(f"\n{'轮次':>4}  {'版本':>8}  {'困难准确率':>10}  {'简单准确率':>10}  {'综合分':>8}  均衡度")
    print("-" * 60)
    for f in files:
        rec = json.load(open(os.path.join(d, f)))
        # 均衡度 = min(hard_acc, easy_acc) — 短板决定强度
        balance = min(rec["hard_acc"], rec["easy_acc"])
        total = rec.get("total_score", "")
        print(f"  {rec['round']:>2}  {rec['version']:>8}  {rec['hard_acc']:>10.2f}  {rec['easy_acc']:>10.2f}  {str(total):>8}  {balance:.2f}")


def best_replay(skill, metric="balance"):
    """选择最优版本。metric=balance 取 min(hard_acc, easy_acc) 最大的；metric=hard 取困难准确率最高的"""
    d = replay_dir_path(skill)
    if not os.path.exists(d):
        print("无回放记录")
        return
    records = []
    for f in os.listdir(d):
        rec = json.load(open(os.path.join(d, f)))
        records.append(rec)
    if not records:
        print("无记录")
        return
    if metric == "balance":
        records.sort(key=lambda r: min(r["hard_acc"], r["easy_acc"]), reverse=True)
    else:
        records.sort(key=lambda r: r["hard_acc"], reverse=True)
    best = records[0]
    print(f"\n最优版本 ({metric}): round={best['round']}, version={best['version']}")
    print(f"  困难准确率: {best['hard_acc']:.2f}")
    print(f"  简单准确率: {best['easy_acc']:.2f}")
    print(f"  综合分: {best.get('total_score', 'N/A')}")
    print(f"  均衡度: {min(best['hard_acc'], best['easy_acc']):.2f}")


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="红蓝军自对弈 + 跨时间回放辅助")
    sub = parser.add_subparsers(dest="command")

    # probe-banks
    pb = sub.add_parser("probe-banks")
    pb.add_argument("skill")
    pb_sub = pb.add_subparsers(dest="sub")
    pb_list = pb_sub.add_parser("list")
    pb_add = pb_sub.add_parser("add-hard")
    pb_add.add_argument("--prompt", required=True)
    pb_add.add_argument("--score", type=float, default=6.0)
    pb_add.add_argument("--round", type=int, default=0)
    pb_add_e = pb_sub.add_parser("add-easy")
    pb_add_e.add_argument("--prompt", required=True)
    pb_add_e.add_argument("--score", type=float, default=9.0)
    pb_add_e.add_argument("--round", type=int, default=0)

    # replay-history
    rh = sub.add_parser("replay-history")
    rh.add_argument("skill")
    rh_sub = rh.add_subparsers(dest="sub")
    rh_list = rh_sub.add_parser("show")
    rh_add = rh_sub.add_parser("add")
    rh_add.add_argument("--round", type=int, required=True)
    rh_add.add_argument("--version", required=True)
    rh_add.add_argument("--hard-acc", type=float, required=True)
    rh_add.add_argument("--easy-acc", type=float, required=True)
    rh_add.add_argument("--total-score", type=float, default=None)
    rh_best = rh_sub.add_parser("best")
    rh_best.add_argument("--metric", choices=["balance", "hard"], default="balance")

    args = parser.parse_args()

    if args.command == "probe-banks":
        if args.sub == "list":
            list_banks(args.skill)
        elif args.sub == "add-hard":
            add_to_bank(args.skill, "hard", args.prompt, args.score, args.round)
        elif args.sub == "add-easy":
            add_to_bank(args.skill, "easy", args.prompt, args.score, args.round)
    elif args.command == "replay-history":
        if args.sub == "show":
            show_replays(args.skill)
        elif args.sub == "add":
            add_replay(args.skill, args.round, args.version, args.hard_acc, args.easy_acc, args.total_score)
        elif args.sub == "best":
            best_replay(args.skill, args.metric)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()