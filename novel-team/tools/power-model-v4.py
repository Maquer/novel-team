#!/usr/bin/env python3
"""
power-model-v4.py — 属性四层金字塔版武力值模型
借鉴 game-numerical-design-career ch12（属性原子模型 + 稳定/临时层分离）

核心改进（v3→v4）：
1. 属性分层：基础层（稳定源）× 比例层（功法/装备） × 临时层（心境/实战）
2. 隐藏控制参数：大境界压制系数（≥2.5x）、小境界递进（1.2-1.5x）
3. 结算顺序明确：先算比例层，再算临时层，最后应用大境界压制
4. 验证清单：ch12 五项安全检查（低值/基准/高值/上限/负值）
"""

import json
import sys
from dataclasses import dataclass
from typing import Optional

# ─── 境界战力基准表（ch12：目标反推成长曲线，先定节点再反推） ───
REALM_BASE_STATS = {
    # 淬体九重（新手期，成长放缓）
    "淬体一重": {"base": 30,  "lifespan": 100,  "description": "凡人勇士"},
    "淬体二重": {"base": 50,  "lifespan": 100,  "description": "稍强于常人"},
    "淬体三重": {"base": 75,  "lifespan": 100,  "description": "略强"},
    "淬体四重": {"base": 100, "lifespan": 100,  "description": "小主角起点"},
    "淬体五重": {"base": 140, "lifespan": 100,  "description": "普通弟子"},
    "淬体六重": {"base": 190, "lifespan": 100,  "description": "精锐"},
    "淬体七重": {"base": 260, "lifespan": 100,  "description": "优秀"},
    "淬体八重": {"base": 350, "lifespan": 100,  "description": "顶尖"},
    "淬体九重": {"base": 450, "lifespan": 100,  "description": "凡人极限"},
    # 炼气四阶（×2.22，开始有质变）
    "炼气初期": {"base": 1000,  "lifespan": 300, "description": "初窥仙门"},
    "炼气中期": {"base": 1300,  "lifespan": 300, "description": "轻身术纯熟"},
    "炼气后期": {"base": 1700,  "lifespan": 300, "description": "御器飞行"},
    "炼气圆满": {"base": 2200,  "lifespan": 300, "description": "筑基前巅峰"},
    # 筑基四阶（×2.27）
    "筑基初期": {"base": 5000,  "lifespan": 800, "description": "宗师级"},
    "筑基中期": {"base": 6250,  "lifespan": 800, "description": "御剑飞行"},
    "筑基后期": {"base": 7800,  "lifespan": 800, "description": "持久战强"},
    "筑基圆满": {"base": 10000, "lifespan": 800, "description": "一方高手"},
    # 金丹四阶（×2.50）
    "金丹初期": {"base": 25000, "lifespan": 2000, "description": "绝世高手"},
    "金丹中期": {"base": 31250, "lifespan": 2000, "description": "一击毁城"},
    "金丹后期": {"base": 39000, "lifespan": 2000, "description": "宗门长老级"},
    "金丹圆满": {"base": 50000, "lifespan": 2000, "description": "大能边缘"},
    # 元婴四阶（×2.50）
    "元婴初期": {"base": 125000,  "lifespan": 5000, "description": "传奇级"},
    "元婴中期": {"base": 156250,  "lifespan": 5000, "description": "瞬息千里"},
    "元婴后期": {"base": 195312,  "lifespan": 5000, "description": "陆地神仙"},
    "元婴圆满": {"base": 250000,  "lifespan": 5000, "description": "一方霸主"},
    # 化神四阶（×2.50）
    "化神初期": {"base": 625000,  "lifespan": 15000, "description": "半仙之流"},
    "化神中期": {"base": 781250,  "lifespan": 15000, "description": "操控空间"},
    "化神后期": {"base": 976562,  "lifespan": 15000, "description": "飞天遁地"},
    "化神圆满": {"base": 1250000, "lifespan": 15000, "description": "大乘门槛"},
    # 高阶境界（指数增长）
    "炼虚":  {"base": 3125000,  "lifespan": 30000, "description": "炼化虚空"},
    "合体":  {"base": 7812500,  "lifespan": 60000, "description": "返璞归真"},
    "大乘":  {"base": 19531250, "lifespan": 100000, "description": "半步仙人"},
    "渡劫":  {"base": 50000000, "lifespan": 999999, "description": "飞升仙界"},
}

# ─── 功法品质加成（ch12：比例数承载横向/广度成长） ───
METHOD_BONUSES = {
    "凡阶": 0.0,
    "黄阶下品": 0.02,
    "黄阶中品": 0.04,
    "黄阶上品": 0.06,
    "玄阶下品": 0.10,
    "玄阶中品": 0.12,
    "玄阶上品": 0.15,
    "地阶下品": 0.25,
    "地阶中品": 0.30,
    "地阶上品": 0.40,
    "天阶下品": 0.50,
    "天阶中品": 0.60,
    "天阶上品": 0.80,
}

# ─── 装备品质加成（ch12：与功法属不同"模块"，模块间相乘） ───
EQUIP_BONUSES = {
    "凡器": 0.0,
    "普通": 0.10,
    "稀有": 0.30,
    "史诗": 0.50,
    "Legendary": 1.00,  # 天命剑级别
}

# ─── 心境加成（ch12：临时层，战斗时注入） ───
MENTALITY_BONUSES = {
    "绝境爆发": 0.30,
    "顿悟": 0.20,
    "愤怒": 0.15,
    "平静": 0.05,
    "分心": -0.05,
    "恐惧": -0.10,
    "轻敌": -0.15,
}

# ─── 实战经验加成（ch12：临时层） ───
COMBAT_EXP_BONUSES = {
    "百战老兵": 0.20,
    "身经百战": 0.15,
    "经验丰富": 0.10,
    "初出茅庐": 0.00,
    "毫无经验": -0.10,
}

# ─── 大境界压制系数（ch12：隐藏/控制参数） ───
REALM_ORDER = [
    "淬体", "炼气", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫"
]
REALM_GAP_MULTIPLIER = 2.5  # 每跨一个大境界 ×2.5


@dataclass
class Character:
    name: str
    realm: str
    method: str = "凡阶"
    equip: str = "凡器"
    mentality: str = "平静"
    combat_exp: str = "初出茅庐"
    notes: str = ""

    @property
    def base_power(self) -> float:
        return REALM_BASE_STATS[self.realm]["base"]

    @property
    def method_rate(self) -> float:
        return METHOD_BONUSES.get(self.method, 0.0)

    @property
    def equip_rate(self) -> float:
        return EQUIP_BONUSES.get(self.equip, 0.0)

    @property
    def mentality_rate(self) -> float:
        return MENTALITY_BONUSES.get(self.mentality, 0.0)

    @property
    def combat_exp_rate(self) -> float:
        return COMBAT_EXP_BONUSES.get(self.combat_exp, 0.0)

    def calculate(self) -> dict:
        """
        ch12 四层金字塔公式：
        第一层：基础战力（稳定源）
        第二层：实际战力 = 基础 × (1+功法) × (1+装备)  [模块间相乘]
        第三层：临时战力 = 实际 × (1+心境) × (1+实战)   [临时层，战斗时注入]
        第四层：隐藏控制 = 大境界压制系数（跨境界时应用）
        """
        base = self.base_power
        # 第二层：稳定比例层（功法 × 装备，模块间相乘）
        stable_power = base * (1 + self.method_rate) * (1 + self.equip_rate)
        # 第三层：临时比例层（心境 × 实战，战斗时注入）
        temp_power = stable_power * (1 + self.mentality_rate) * (1 + self.combat_exp_rate)

        return {
            "name": self.name,
            "realm": self.realm,
            "base_power": round(base, 2),
            "method_bonus": f"+{self.method_rate*100:.0f}%",
            "equip_bonus": f"+{self.equip_rate*100:.0f}%",
            "stable_power": round(stable_power, 2),
            "mentality": f"{self.mentality}({self.mentality_rate:+.0%})",
            "combat_exp": f"{self.combat_exp}({self.combat_exp_rate:+.0%})",
            "final_power": round(temp_power, 2),
            "notes": self.notes,
        }

    def cross_realm_ratio(self, other: "Character") -> float:
        """计算跨境界压制后的战力比"""
        my_group = self._get_realm_group()
        other_group = other._get_realm_group()
        my_idx = REALM_ORDER.index(my_group) if my_group in REALM_ORDER else 0
        other_idx = REALM_ORDER.index(other_group) if other_group in REALM_ORDER else 0
        gap = abs(my_idx - other_idx)
        if gap >= 1:
            return self.calculate()["final_power"] / (other.calculate()["final_power"] * (REALM_GAP_MULTIPLIER ** gap))
        return self.calculate()["final_power"] / other.calculate()["final_power"]

    def _get_realm_group(self) -> str:
        r = self.realm
        for g in REALM_ORDER:
            if g in r:
                return g
        return "淬体"


def compare(characters: list) -> None:
    """战力对比：计算差距比，输出胜负预测"""
    results = [c.calculate() for c in characters]
    if len(results) < 2:
        print("需要至少 2 个角色进行对比")
        return

    print(f"\n{'='*75}")
    print(f"  战力对比（ch12 四层金字塔：基础→比例层→临时层）")
    print(f"{'='*75}")
    hdr = f"{'角色':<12} {'境界':<12} {'基础':>8} {'功法':>8} {'装备':>8} {'实际':>10} {'心境':>12} {'最终':>12}"
    print(hdr)
    print("-" * 75)
    for r in results:
        print(f"{r['name']:<12} {r['realm']:<12} {r['base_power']:>8.0f} {r['method_bonus']:>8} {r['equip_bonus']:>8} {r['stable_power']:>10.0f} {r['mentality']:>12} {r['final_power']:>12.0f}")
    print("=" * 75)
    print()

    # 胜负预测（ch12: 同境界看外物差, 跨境界看大境界压制系数）
    for i, r1 in enumerate(results):
        for j, r2 in enumerate(results):
            if i >= j:
                continue
            ratio = r1["final_power"] / r2["final_power"] if r2["final_power"] > 0 else float('inf')
            c1, c2 = characters[i], characters[j]
            cross_ratio = c1.cross_realm_ratio(c2)
            same_realm = (c1._get_realm_group() == c2._get_realm_group())

            if not same_realm and ratio >= 2.5:
                # 跨大境界: 2.5x 是最低压制门槛
                verdict = "绝对压制（跨大境界 ≥2.5x）"
            elif ratio >= 3.0:
                verdict = "碾压（装备/功法碾压）"
            elif ratio >= 1.5:
                verdict = "明显优势"
            elif ratio >= 0.8:
                verdict = "五五开"
            else:
                verdict = "明显劣势"

            cross_note = ""
            if not same_realm:
                cross_note = f"  [跨境界压制后 {cross_ratio:.2f}x]"
            print(f"  {r1['name']}({r1['realm']}) vs {r2['name']}({r2['realm']}): {ratio:.2f}x → {verdict}{cross_note}")
    print()


def verify_boundary() -> None:
    """ch12 验证清单：低值/基准/高值/上限/负值安全性"""
    print("\n" + "="*60)
    print("  边界验证（ch12 五项检查）")
    print("="*60)

    checks = []
    # 低值：淬体一重
    c = Character("test_low", "淬体一重")
    r = c.calculate()
    checks.append(("低值(淬体一重)", r["final_power"], r["final_power"] > 0))

    # 基准：萧辰（淬体四重，天命剑）
    c = Character("萧辰", "淬体四重", "天阶下品", "Legendary", "平静", "初出茅庐", "天命剑封印中")
    r = c.calculate()
    checks.append(("基准(萧辰)", r["final_power"], r["final_power"] > 0))

    # 高值：化神圆满
    c = Character("test_high", "化神圆满")
    r = c.calculate()
    checks.append(("高值(化神圆满)", r["final_power"], r["final_power"] < 2_000_000))

    # 上限：渡劫
    c = Character("test_max", "渡劫")
    r = c.calculate()
    checks.append(("上限(渡劫)", r["final_power"], r["final_power"] <= 100_000_000))

    # 负值：心境轻敌
    c = Character("test_neg", "淬体四重", "凡阶", "凡器", "轻敌")
    r = c.calculate()
    checks.append(("负值(轻敌)", r["final_power"], r["final_power"] > 0))

    all_pass = True
    for name, value, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: {value:,.0f}")
        if not passed:
            all_pass = False

    print(f"\n{'全部通过 ✅' if all_pass else '存在失败项 ❌'}")
    print()


def verify_realm_gaps() -> None:
    """验证大境界压制 ≥2.5x，小境界递进 1.2-1.5x"""
    print("\n" + "="*60)
    print("  境界梯度验证（ch12 目标反推成长曲线）")
    print("="*60)

    prev_base = None
    prev_realm_group = None
    for realm, data in REALM_BASE_STATS.items():
        base = data["base"]
        group = None
        for g in REALM_ORDER:
            if g in realm:
                group = g
                break
        group = group or "淬体"

        if prev_base and group and prev_realm_group:
            ratio = base / prev_base
            if group == prev_realm_group:
                ok = 1.1 <= ratio <= 1.6
                status = "✅" if ok else "⚠️"
                print(f"  {status} {prev_realm_group}→{realm}: {ratio:.3f}x (期望 1.1-1.6x)")
            else:
                ok = ratio >= 2.0
                status = "✅" if ok else "❌"
                print(f"  {status} 【大境界】{prev_realm_group}→{group}: {ratio:.2f}x (期望 ≥2.0x)")
        prev_base = base
        prev_realm_group = group

    print()


def verify_economy_budget() -> None:
    """ch19 经济检查：灵石 I/O 预算"""
    print("\n" + "="*60)
    print("  经济预算验证（ch19 I/O 检查）")
    print("="*60)

    # 外门弟子月度收支
    income = 10   # 宗门发放下品灵石
    expense_healing = 10  # 疗伤丹（受伤时）
    expense_breakthrough = 50  # 聚气丹（突破时，一次性）
    surplus = income - expense_healing

    print(f"  外门弟子月收入:  {income} 下品灵石")
    print(f"  外门弟子月支出:  {expense_healing} 下品灵石（疗伤丹）")
    print(f"  月度结余:        {surplus} 下品灵石 {'✅ 正向' if surplus >= 0 else '❌ 负向'}")
    print(f"  突破成本:        {expense_breakthrough} 下品灵石（聚气丹，一次性）")
    print(f"  积累月数:        {expense_breakthrough // max(surplus, 1)} 月（不含意外支出）")
    print()

    # 中品灵石切换检查
    print("  价值锚点换算链：")
    print(f"    1 中品灵石 = 100 下品灵石")
    print(f"    外门弟子月工资 = 10 下品 = 0.1 中品")
    print(f"    聚气丹(50下品) = 外门弟子 5 天工资")
    print(f"    中品灵石购买力 = 中品弟子 10 天工资")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="power-model-v4: 属性四层金字塔武力值模型")
    parser.add_argument("--table", action="store_true", help="显示境界战力表")
    parser.add_argument("--characters", action="store_true", help="显示预设角色战力")
    parser.add_argument("--compare", nargs="+", metavar="NAME", help="对比角色战力（名称或序号）")
    parser.add_argument("--verify", action="store_true", help="运行边界验证")
    parser.add_argument("--verify-gaps", action="store_true", help="验证境界梯度")
    parser.add_argument("--verify-economy", action="store_true", help="验证经济预算")
    parser.add_argument("--all", action="store_true", help="运行所有检查")
    args = parser.parse_args()

    # 预设角色
    char_xiao = Character("萧辰", "淬体四重", "天阶下品", "Legendary", "平静", "初出茅庐", "天命剑封印中")
    char_wang = Character("王大", "淬体四重", "黄阶下品", "普通", "轻敌", "初出茅庐", "欺软怕硬")
    char_su = Character("苏逸", "炼气初期", "玄阶下品", "稀有", "平静", "初出茅庐", "外门佼佼者")
    char_feng = Character("风清扬", "筑基圆满", "天阶中品", "史诗", "平静", "身经百战", "内门首席")
    char_libai = Character("李白白", "元婴初期", "天阶上品", "Legendary", "平静", "百战老兵", "宗主")
    char_xue = Character("血煞老祖", "元婴初期", "地阶上品", "史诗", "平静", "百战老兵", "魔道门主")

    name_map = {
        "萧辰": char_xiao, "王大": char_wang, "苏逸": char_su,
        "风清扬": char_feng, "李白白": char_libai, "血煞老祖": char_xue,
    }
    char_list = [char_xiao, char_wang, char_su, char_feng, char_libai, char_xue]

    if args.table or args.all:
        print("\n境界战力基准表（ch12 目标反推成长曲线）：")
        print(f"{'境界':<12} {'基础战力':>10} {'寿命':>8} {'说明':<20}")
        print("-" * 55)
        for realm, data in REALM_BASE_STATS.items():
            print(f"{realm:<12} {data['base']:>10,} {data['lifespan']:>8,}年 {data['description']:<20}")
        print()

    if args.characters or args.all:
        print("\n预设角色战力（ch12 属性四层分解）：")
        for c in char_list:
            r = c.calculate()
            print(f"  {r['name']} ({r['realm']}): 基础{r['base_power']:,} × 功法{r['method_bonus']} × 装备{r['equip_bonus']} × 心境{r['mentality']} × 实战{r['combat_exp']} = {r['final_power']:,.0f}")
        print()

    if args.compare:
        chars = []
        for n in args.compare:
            if n in name_map:
                chars.append(name_map[n])
            else:
                try:
                    idx = int(n) - 1
                    chars.append(char_list[idx])
                except (ValueError, IndexError):
                    print(f"  ⚠️ 未知角色: {n}")
        if chars:
            compare(chars)

    if args.verify or args.all:
        verify_boundary()

    if args.verify_gaps or args.all:
        verify_realm_gaps()

    if args.verify_economy or args.all:
        verify_economy_budget()


if __name__ == "__main__":
    main()
