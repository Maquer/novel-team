#!/usr/bin/env python3
"""
breakthrough-probability.py — 境界突破概率系统
借鉴 game-numerical-design-career ch14（概率系统与尾部体验）

设计原则：
- 软保底：连续失败后概率递增，改善尾部体验
- 硬保底：第 N 次失败必成功，控制最坏成本
- 状态转移：每次突破是"状态→转移边"的图遍历
- 体验指标：输出期望/中位/P80/P90/最坏成本
"""

import random
import json
from dataclasses import dataclass
from typing import List, Tuple

BREAKTHROUGH_CONFIG = {
    "base_rate": 0.30,
    "soft_boost": 0.05,
    "hard_cap": 10,
    "fail_penalty": {"item": "聚气丹", "cost": 1},
    "quest_independent": True,
}

REALM_BREAKTHROUGH = {
    "淬体": {"base_rate": 0.35, "soft_boost": 0.05, "hard_cap": 8},
    "炼气": {"base_rate": 0.30, "soft_boost": 0.05, "hard_cap": 10},
    "筑基": {"base_rate": 0.25, "soft_boost": 0.06, "hard_cap": 10},
    "金丹": {"base_rate": 0.20, "soft_boost": 0.07, "hard_cap": 12},
    "元婴": {"base_rate": 0.15, "soft_boost": 0.08, "hard_cap": 12},
    "化神": {"base_rate": 0.10, "soft_boost": 0.10, "hard_cap": 15},
    "炼虚": {"base_rate": 0.08, "soft_boost": 0.10, "hard_cap": 15},
    "合体": {"base_rate": 0.05, "soft_boost": 0.12, "hard_cap": 20},
    "大乘": {"base_rate": 0.03, "soft_boost": 0.15, "hard_cap": 20},
}


@dataclass
class BreakthroughResult:
    attempts: int
    succeeded_on: int
    penalty_items: int
    quest_count: int = 0
    is_hard_cap: bool = False


def simulate_once(base_rate, soft_boost, hard_cap, current_fails, quest_prob=0.01):
    if random.random() < quest_prob:
        return True, True
    current_rate = min(base_rate + soft_boost * current_fails, 1.0)
    if random.random() < current_rate:
        return True, False
    current_fails += 1
    if current_fails >= hard_cap:
        return True, False
    return False, False


def simulate_breakthrough(realm_group, simulations=10000):
    cfg = REALM_BREAKTHROUGH.get(realm_group, BREAKTHROUGH_CONFIG)
    base_rate = cfg["base_rate"]
    soft_boost = cfg["soft_boost"]
    hard_cap = cfg["hard_cap"]

    results = []
    for _ in range(simulations):
        fails = 0
        quest_count = 0
        penalty = 0
        for attempt in range(hard_cap + 5):
            success, is_quest = simulate_once(base_rate, soft_boost, hard_cap, fails)
            if is_quest:
                quest_count += 1
                break
            elif success:
                break
            else:
                fails += 1
                penalty += 1
                if fails >= hard_cap:
                    break
        results.append(BreakthroughResult(
            attempts=fails + 1, succeeded_on=fails + 1,
            penalty_items=penalty, quest_count=quest_count,
            is_hard_cap=(fails >= hard_cap - 1)
        ))

    attempts_list = sorted([r.attempts for r in results])
    n = len(attempts_list)

    def pct(p):
        idx = min(int(n * p), n - 1)
        return attempts_list[idx]

    return {
        "realm": realm_group,
        "config": cfg,
        "simulations": simulations,
        "mean_attempts": sum(attempts_list) / n,
        "median_attempts": attempts_list[n // 2],
        "p80_attempts": pct(0.80),
        "p90_attempts": pct(0.90),
        "p95_attempts": pct(0.95),
        "worst_case": hard_cap,
        "hard_cap_trigger_rate": sum(1 for r in results if r.is_hard_cap) / n,
        "quest_trigger_rate": sum(r.quest_count for r in results) / n / simulations,
        "avg_penalty_items": sum(r.penalty_items for r in results) / n,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="突破概率模拟器（ch14）")
    parser.add_argument("--realm", nargs="+", help="指定境界组模拟")
    parser.add_argument("--simulations", type=int, default=10000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    realms = args.realm or list(REALM_BREAKTHROUGH.keys())

    if args.json:
        all_results = {r: simulate_breakthrough(r, args.simulations) for r in realms}
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
        return

    print("\n" + "="*90)
    print("  境界突破概率系统（ch14：期望+分位数+保底）")
    print("="*90)
    print(f"{'境界组':<8} {'平均':>6} {'中位':>5} {'P80':>5} {'P90':>5} {'P95':>5} {'最坏':>5} {'硬保底率':>8} {'奇遇率':>8}")
    print("-"*90)
    for r in realms:
        res = simulate_breakthrough(r, args.simulations)
        print(f"{r:<8} {res['mean_attempts']:>6.1f} {res['median_attempts']:>5} "
              f"{res['p80_attempts']:>5} {res['p90_attempts']:>5} {res['p95_attempts']:>5} "
              f"{res['worst_case']:>5} {res['hard_cap_trigger_rate']*100:>7.1f}% "
              f"{res['quest_trigger_rate']*100:>7.1f}%")
    print("="*90)
    print("\n说明：")
    print("  平均=期望尝试次数  P80/P90/P95=对应分位数的尝试次数")
    print("  最坏=硬保底触发次数（玩家绝对上限）")
    print("  奇遇率=不占保底计数、直接成功的比例")
    print()


if __name__ == "__main__":
    main()
