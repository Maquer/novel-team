#!/usr/bin/env python3
"""
auto-connect.py — 自动补全孤立实体关系（借鉴 Nexus-Lore 关系图）

策略：
  1. realm → power（修炼体系）
  2. org_detail → org（所属宗门）
  3. place → region（所属地域）
  4. thing → 用途/出处（通过 tagline 关键词匹配）
  5. work（功法）→ org（所属门派）/ figure（使用者）
  6. race（种族/妖兽）→ region（栖息地）
  7. law → org/place（制定者）
  8. secret → 关联实体（通过名称关键词）
  9. foreshadow → 关联实体（通过名称关键词）
  10. event → 关联实体（通过名称关键词）

使用：
  python auto-connect.py --world "玄天大陆" --dry-run   # 预览
  python auto-connect.py --world "玄天大陆" --apply      # 执行
  python auto-connect.py --world "玄天大陆" --report     # 生成报告
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

WORLD_DIR = Path("/var/minis/shared/novel-team/.world-packs")

# ============================================================
# 关系映射规则
# ============================================================

# realm → power
REALM_TO_POWER = {
    "realm": "power_修炼_0001",
}

# org_detail → org
ORG_DETAIL_TO_ORG = {
    "org_天剑宗_详细": "org_天剑宗_0001",
    "org_血煞门_详细": "org_血煞门_0001",
    "org_逍遥阁_详细": "org_逍遥阁_0001",
}

# place → region（通过名称关键词）
PLACE_TO_REGION = {
    "万剑剑冢": "region_天剑山脉_0001",
    "天剑宗外门": "org_天剑宗_0001",  # 属于宗门
    "天剑宗内门": "org_天剑宗_0001",
    "天剑城": "org_天剑宗_0001",
    "血煞殿": "org_血煞门_0001",
    "逍遥阁总坛": "org_逍遥阁_0001",
    "青云殿": "org_青云宗_0001",
    "寒渊秘境": "region_北荒_0001",
    "毒瘴谷": "region_南岭_0001",
    "沉船墓": "region_东海_0001",
    "藏经洞": "org_天剑宗_0001",
}

# work（功法）→ org（所属门派）
WORK_TO_ORG = {
    "天剑诀": "org_天剑宗_0001",
    "血煞真经": "org_血煞门_0001",
    "天青符诀": "org_青云宗_0001",
    "百草丹经": "org_逍遥阁_0001",
    "轻身术": "org_天剑宗_0001",
    "御剑术": "org_天剑宗_0001",
}

# race（妖兽）→ region（栖息地）
RACE_TO_REGION = {
    "剑齿虎": "region_天剑山脉_0001",
    "炎蛇": "region_南岭_0001",
    "蛟": "region_东海_0001",
    "风刃鹰": "region_天剑山脉_0001",
    "影魔": "region_血煞深渊_0001",
}

# law → org（制定者）
LAW_TO_ORG = {
    "正道禁忌": "org_天剑宗_0001",
    "万剑剑冢规矩": "org_天剑宗_0001",
}

# figure → org（通过名称匹配）
FIGURE_TO_ORG = {
    "血煞老祖": "org_血煞门_0001",
    "鲛人王": "org_东海鲛族_0001",
}

# thing → org/region（通过关键词匹配）
# 灵石类是通用货币，不归入任何势力
THING_TO_TARGET = {
    "下品灵石": {"target": "world_玄天_0001", "rel_type": "currency_of", "reason": "通用货币"},
    "中品灵石": {"target": "world_玄天_0001", "rel_type": "currency_of", "reason": "通用货币"},
    "上品灵石": {"target": "world_玄天_0001", "rel_type": "currency_of", "reason": "通用货币"},
    "极品灵石": {"target": "world_玄天_0001", "rel_type": "currency_of", "reason": "通用货币"},
    "疗伤丹": {"target": "org_逍遥阁_0001", "rel_type": "supplied_by", "reason": "丹药商会"},
    "聚气丹": {"target": "org_逍遥阁_0001", "rel_type": "supplied_by", "reason": "丹药商会"},
    "辟瘴丹": {"target": "org_逍遥阁_0001", "rel_type": "supplied_by", "reason": "丹药商会"},
    "寒铁": {"target": "region_天剑山脉_0001", "rel_type": "found_in", "reason": "特产"},
    "血玉": {"target": "org_血煞门_0001", "rel_type": "supplied_by", "reason": "魔道特产"},
    "传音石": {"target": "org_天剑宗_0001", "rel_type": "supplied_by", "reason": "宗门配发"},
    "护身符": {"target": "org_天剑宗_0001", "rel_type": "supplied_by", "reason": "入门礼物"},
}

# secret/foreshadow → 关联实体（通过名称关键词）
SECRET_KEYWORD_MAP = {
    "天命剑秘辛": "item_天命剑_0001",
    "萧辰身世之谜": "char_萧辰_0001",
    "上古剑圣": "secret_天裂之劫_0001",  # 或 event
    "外神降临": "event_天裂之劫_0001",
    "血族后裔": "char_血姬_0001",
}

FORESHADOW_KEYWORD_MAP = {
    "天命剑来历": "item_天命剑_0001",
    "萧辰身世之谜": "char_萧辰_0001",
    "血煞门渗透计划": "org_血煞门_0001",
}

# event → 关联实体
EVENT_MAP = {
    "天裂之劫": "world_玄天_0001",
}


# ============================================================
# 核心逻辑
# ============================================================

class AutoConnector:
    def __init__(self, world_name: str):
        self.world_name = world_name
        self.path = WORLD_DIR / f"{world_name}.json"
        self.data = self._load()
        self.entries: Dict[str, dict] = self.data.get("entries", {})
        self.changes: List[dict] = []

    def _load(self) -> dict:
        if not self.path.exists():
            print(f"❌ 世界包不存在: {self.path}", file=sys.stderr)
            sys.exit(1)
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self):
        self.data["entries"] = self.entries
        self.data["updated_at"] = __import__("datetime").datetime.now().isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_entity(self, eid: str) -> Optional[dict]:
        return self.entries.get(eid)

    def resolve_by_name(self, name: str) -> Optional[str]:
        """通过名字解析实体 ID"""
        for eid, e in self.entries.items():
            if e["name"] == name:
                return eid
        return None

    def add_relation(self, from_id: str, to_id: str, rel_type: str, reason: str):
        """添加关系并记录变更"""
        if from_id not in self.entries:
            return
        if to_id not in self.entries:
            return  # 目标不存在，跳过

        from_entry = self.entries[from_id]
        existing_rels = from_entry.get("relations", [])

        # 检查是否已存在相同关系
        for rel in existing_rels:
            target = rel.get("to") or rel.get("target")
            if target == to_id and rel.get("type") == rel_type:
                return  # 已存在，跳过

        new_rel = {"to": to_id, "type": rel_type, "source": "auto_connect", "reason": reason}
        from_entry.setdefault("relations", []).append(new_rel)
        self.changes.append({
            "from": from_id,
            "to": to_id,
            "type": rel_type,
            "reason": reason,
        })

    # ----------------------------------------------------------
    # 各类自动连接规则
    # ----------------------------------------------------------

    def connect_realms(self):
        """realm → power"""
        for eid, e in self.entries.items():
            if e.get("kind") == "realm":
                self.add_relation(eid, "power_修炼_0001", "part_of", "境界属于修炼体系")

    def connect_org_details(self):
        """org_detail → org"""
        for eid, detail in self.entries.items():
            if detail.get("kind") == "org_detail":
                target = ORG_DETAIL_TO_ORG.get(eid)
                if target:
                    self.add_relation(eid, target, "details_of", "详细条目属于主实体")

    def connect_places(self):
        """place → region/org"""
        for eid, place in self.entries.items():
            if place.get("kind") == "place":
                # 先检查名称映射
                target = PLACE_TO_REGION.get(place["name"])
                if target:
                    rel_type = "located_in" if target.startswith("region_") else "belongs_to"
                    self.add_relation(eid, target, rel_type, f"地点属于{target.split('_')[1]}")
                    continue

                # 通过 tagline 关键词匹配
                tagline = place.get("tagline", "")
                if "天剑宗" in tagline:
                    self.add_relation(eid, "org_天剑宗_0001", "belongs_to", "天剑宗地点")
                elif "血煞" in tagline:
                    self.add_relation(eid, "org_血煞门_0001", "belongs_to", "血煞门地点")
                elif "逍遥" in tagline:
                    self.add_relation(eid, "org_逍遥阁_0001", "belongs_to", "逍遥阁地点")

    def connect_works(self):
        """work（功法）→ org"""
        for eid, work in self.entries.items():
            if work.get("kind") == "work":
                target = WORK_TO_ORG.get(work["name"])
                if target:
                    self.add_relation(eid, target, "taught_by", f"功法由{target}传授")

    def connect_races(self):
        """race（妖兽）→ region"""
        for eid, race in self.entries.items():
            if race.get("kind") in ("race", "creature"):
                target = RACE_TO_REGION.get(race["name"])
                if target:
                    self.add_relation(eid, target, "habitat", f"栖息于{target.split('_')[1]}")

    def connect_laws(self):
        """law → org"""
        for eid, law in self.entries.items():
            if law.get("kind") == "law":
                target = LAW_TO_ORG.get(law["name"])
                if target:
                    self.add_relation(eid, target, "enforced_by", f"规矩由{target}制定")

    def connect_secrets(self):
        """secret → 关联实体"""
        for eid, secret in self.entries.items():
            if secret.get("kind") == "secret":
                # 尝试通过名称匹配
                target = SECRET_KEYWORD_MAP.get(secret["name"])
                if not target:
                    # 尝试部分匹配
                    for keyword, tid in SECRET_KEYWORD_MAP.items():
                        if keyword in secret["name"] or secret["name"] in keyword:
                            target = tid
                            break
                if target:
                    self.add_relation(eid, target, "related_to", f"秘辛与{target}相关")

    def connect_foreshadows(self):
        """foreshadow → 关联实体"""
        for eid, fs in self.entries.items():
            if fs.get("kind") == "foreshadow":
                target = FORESHADOW_KEYWORD_MAP.get(fs["name"])
                if not target:
                    for keyword, tid in FORESHADOW_KEYWORD_MAP.items():
                        if keyword in fs["name"] or fs["name"] in keyword:
                            target = tid
                            break
                if target:
                    self.add_relation(eid, target, "foreshadows", f"伏笔指向{target}")

    def connect_events(self):
        """event → 关联实体"""
        for eid, event in self.entries.items():
            if event.get("kind") == "event":
                target = EVENT_MAP.get(event["name"])
                if not target:
                    # 尝试通过内容匹配
                    content = event.get("content", "")
                    if "天裂" in content:
                        target = "world_玄天_0001"
                if target:
                    self.add_relation(eid, target, "affects", f"事件影响{target}")

    def connect_figures(self):
        """figure → org"""
        for eid, fig in self.entries.items():
            if fig.get("kind") == "figure":
                target = FIGURE_TO_ORG.get(fig["name"])
                if target:
                    self.add_relation(eid, target, "member_of", f"属于{target}")

    def connect_things(self):
        """thing → org/region/world"""
        for eid, thing in self.entries.items():
            if thing.get("kind") == "thing":
                mapping = THING_TO_TARGET.get(thing["name"])
                if mapping:
                    self.add_relation(eid, mapping["target"], mapping["rel_type"], mapping["reason"])

    def connect_power_details(self):
        """power detail → power"""
        for eid, p in self.entries.items():
            if p.get("kind") == "power" and "详细" in p["name"]:
                self.add_relation(eid, "power_修炼_0001", "details_of", "详细体系属于修炼体系")

    # ----------------------------------------------------------
    # 批量执行
    # ----------------------------------------------------------

    def run_all(self):
        """执行所有连接规则"""
        self.connect_realms()
        self.connect_org_details()
        self.connect_places()
        self.connect_works()
        self.connect_races()
        self.connect_laws()
        self.connect_secrets()
        self.connect_foreshadows()
        self.connect_events()
        self.connect_figures()
        self.connect_things()
        self.connect_power_details()

    def get_orphans_after(self) -> List[str]:
        """获取应用后仍孤立的实体"""
        connected = set()
        for e in self.entries.values():
            for rel in e.get("relations", []):
                target = rel.get("to") or rel.get("target")
                if target:
                    connected.add(target)
                    connected.add(e["id"])

        orphans = []
        for eid, e in self.entries.items():
            if eid not in connected and not e.get("relations"):
                orphans.append((eid, e["name"], e.get("kind")))
        return orphans

    def generate_report(self) -> str:
        """生成变更报告"""
        lines = []
        lines.append(f"=== Nexus-Lore 自动补全报告 ===")
        lines.append(f"世界: {self.world_name}")
        lines.append(f"总变更数: {len(self.changes)}\n")

        # 按类型分组
        by_type = defaultdict(list)
        for c in self.changes:
            by_type[c["type"]].append(c)

        for rtype, changes in sorted(by_type.items()):
            lines.append(f"── [{rtype}] ({len(changes)} 条)")
            for c in changes[:10]:
                from_e = self.entries.get(c["from"], {})
                to_e = self.entries.get(c["to"], {})
                lines.append(f"  {from_e.get('name', c['from'])} ──[{rtype}]──> {to_e.get('name', c['to'])}")
                if len(changes) > 10:
                    lines.append(f"  ... 还有 {len(changes)-10} 条")
            lines.append("")

        # 剩余孤立实体
        orphans = self.get_orphans_after()
        lines.append(f"── 剩余孤立实体: {len(orphans)} 个 ──")
        if orphans:
            for eid, name, kind in orphans[:15]:
                lines.append(f"  • {name} ({kind})")
            if len(orphans) > 15:
                lines.append(f"  ... 还有 {len(orphans)-15} 个")
        else:
            lines.append("  ✅ 全部实体已连接！")

        return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def cmd_apply(args):
    connector = AutoConnector(args.world)
    connector.run_all()
    connector._save()
    print(f"\n✅ 已应用 {len(connector.changes)} 条关系变更")
    print(connector.generate_report())


def cmd_dryrun(args):
    connector = AutoConnector(args.world)
    connector.run_all()
    print(f"\n📋 预览模式 — 将应用 {len(connector.changes)} 条变更\n")
    print(connector.generate_report())


def cmd_report(args):
    connector = AutoConnector(args.world)
    connector.run_all()
    print(connector.generate_report())


def main():
    parser = argparse.ArgumentParser(description="自动补全孤立实体关系")
    parser.add_argument("--world", "-w", required=True, help="世界包名称")
    sub = parser.add_subparsers(dest="command", required=True)

    p_apply = sub.add_parser("apply", help="执行变更")
    p_dry = sub.add_parser("dry-run", help="预览变更")
    p_rep = sub.add_parser("report", help="生成报告")

    args = parser.parse_args()
    if args.command == "apply":
        cmd_apply(args)
    elif args.command == "dry-run":
        cmd_dryrun(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
