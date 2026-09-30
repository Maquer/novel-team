#!/usr/bin/env python3
"""
world-maintainer.py — 世界包自动维护器

功能：
  1. 合并重复条目（init和extend两阶段写入导致的同名问题）
  2. 自动建立缺失的关系（解决孤岛条目）
  3. 批量标记正典条目为草稿（无出处时）
  4. 定期一致性检查

使用：
  python world-maintainer.py fix --name "玄天大陆" --dry-run
  python world-maintainer.py fix --name "玄天大陆" --apply
  python world-maintainer.py report --name "玄天大陆"
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

# 配置
WORLD_DIR = Path("/var/minis/shared/novel-team/.world-packs")


def load_world(name: str) -> Dict:
    """加载世界包"""
    world_file = WORLD_DIR / f"{name}.json"
    if not world_file.exists():
        print(f"❌ 世界包不存在: {name}")
        return None
    return json.loads(world_file.read_text(encoding='utf-8'))


def save_world(name: str, data: Dict):
    """保存世界包"""
    world_file = WORLD_DIR / f"{name}.json"
    tmp = world_file.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(world_file)
    print(f"✅ 已保存: {name}")


def find_duplicates(entries: Dict) -> List[Dict]:
    """
    查找重复条目
    
    策略：
    - 同 kind + 同 name（忽略大小写）→ 重复
    - 优先保留带 relations 的条目
    """
    by_key = {}
    for entry_id, entry in entries.items():
        key = f"{entry['kind']}::{entry['name'].lower()}"
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(entry_id)
    
    duplicates = []
    for key, ids in by_key.items():
        if len(ids) > 1:
            duplicates.append({
                "key": key,
                "ids": ids,
                "names": [entries[i]["name"] for i in ids]
            })
    
    return duplicates


def find_orphans(entries: Dict) -> List[str]:
    """
    查找孤岛条目（没有 relations 的条目）
    
    排除根节点：world, law, myth, secret, power, era
    """
    root_kinds = {"world", "law", "myth", "secret", "power", "era"}
    orphans = []
    
    for entry_id, entry in entries.items():
        # 根节点跳过
        if entry["kind"] in root_kinds:
            continue
        # 已有关系的跳过
        if entry.get("relations"):
            continue
        orphans.append(entry_id)
    
    return orphans


def suggest_relations(entry_id: str, entry: Dict, entries: Dict) -> List[Dict]:
    """
    为孤立条目建议关系
    
    策略：
    1. region → located_in world
    2. place → located_in 所属 region
    3. figure → member_of 所属 org
    4. thing → owned_by 所属 figure
    5. event → during 所属 era
    """
    suggestions = []
    kind = entry["kind"]
    name = entry["name"]
    
    # 策略1: 地域 → 属于世界
    if kind == "region":
        world_id = next((eid for eid, e in entries.items() if e["kind"] == "world"), None)
        if world_id:
            suggestions.append({"type": "located_in", "to": world_id, "reason": "地域属于世界"})
    
    # 策略2: 地点 → 属于某地域（通过名称匹配）
    elif kind == "place":
        # 从名称中提取可能的父级地域
        for eid, e in entries.items():
            if e["kind"] == "region" and e["name"] in name:
                suggestions.append({"type": "located_in", "to": eid, "reason": f"地点名包含地域名 '{e['name']}'"})
                break
    
    # 策略3: 人物 → 属于某势力（通过名称匹配）
    elif kind == "figure":
        # 尝试从 fields 中提取组织信息
        fields = entry.get("fields", [])
        for field in fields:
            if field.get("name") == "身份" or field.get("name") == "组织":
                org_name = field.get("value", "")
                # 模糊匹配
                for eid, e in entries.items():
                    if e["kind"] == "org" and org_name in e["name"]:
                        suggestions.append({"type": "member_of", "to": eid, "reason": f"身份包含组织名 '{org_name}'"})
                        break
                break
        
        # 如果没找到，尝试从名称匹配
        if not suggestions:
            for eid, e in entries.items():
                if e["kind"] == "org" and name in e["name"]:
                    suggestions.append({"type": "member_of", "to": eid, "reason": f"人物名包含组织名 '{e['name']}'"})
                    break
    
    # 策略4: 事件 → 发生于某地域
    elif kind == "event":
        for eid, e in entries.items():
            if e["kind"] == "region" and e["name"] in name:
                suggestions.append({"type": "during", "to": eid, "reason": f"事件名包含地域名 '{e['name']}'"})
                break
    
    return suggestions


def auto_link_orphans(entries: Dict) -> List[Dict]:
    """
    自动为孤立条目建立关系
    
    Returns:
        list of (entry_id, relation_dict)
    """
    links = []
    orphans = find_orphans(entries)
    
    for orphan_id in orphans:
        entry = entries[orphan_id]
        suggestions = suggest_relations(orphan_id, entry, entries)
        
        for sug in suggestions:
            # 检查目标是否存在
            if sug["to"] in entries:
                rel = {
                    "type": sug["type"],
                    "to": sug["to"],
                    "evidence": {"source": "auto-maintainer", "reason": sug["reason"]}
                }
                entries[orphan_id]["relations"].append(rel)
                links.append({
                    "from": orphan_id,
                    "relation": rel,
                    "reason": sug["reason"]
                })
    
    return links


def merge_duplicates(entries: Dict, duplicates: List[Dict]) -> Dict:
    """
    合并重复条目
    
    策略：
    1. 保留带 relations 的条目
    2. 把另一个条目加到 aliases
    3. 删除重复条目
    4. 更新所有指向被删除条目的关系
    """
    changes = []
    
    for dup in duplicates:
        ids = dup["ids"]
        names = dup["names"]
        
        # 选择保留的条目（优先保留带 relations 的）
        keep_id = None
        remove_id = None
        
        for id in ids:
            if entries[id].get("relations"):
                keep_id = id
                break
        
        if not keep_id:
            keep_id = ids[0]
        
        for id in ids:
            if id != keep_id:
                remove_id = id
                break
        
        if not remove_id:
            continue
        
        # 合并 aliases
        keep_entry = entries[keep_id]
        remove_entry = entries[remove_id]
        
        existing_aliases = set(keep_entry.get("aliases", []))
        existing_aliases.add(remove_entry["name"])
        keep_entry["aliases"] = list(existing_aliases)
        
        # 合并 relations（指向被删除条目的改指向保留的）
        for eid, entry in entries.items():
            for rel in entry.get("relations", []):
                if rel.get("to") == remove_id:
                    rel["to"] = keep_id
                    changes.append({
                        "type": "relation_update",
                        "from": eid,
                        "old_target": remove_id,
                        "new_target": keep_id
                    })
        
        # 删除重复条目
        del entries[remove_id]
        changes.append({
            "type": "merge",
            "kept": keep_id,
            "removed": remove_id,
            "name": names[0]
        })
    
    return changes


def downgrade_non_canon(entries: Dict) -> List[Dict]:
    """
    批量降级：将 canon 但无 evidence 的条目降级为 draft
    
    这适用于"作者设定"而非"AI抽取"的内容
    """
    changes = []
    
    for entry_id, entry in entries.items():
        if entry.get("status") == "canon" and not entry.get("evidence"):
            entry["status"] = "draft"
            changes.append({
                "type": "downgrade",
                "entry_id": entry_id,
                "name": entry["name"],
                "reason": "正典无出处"
            })
    
    return changes


def generate_report(world_data: Dict, changes: Dict) -> str:
    """生成维护报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("世界包维护报告")
    lines.append("=" * 60)
    lines.append(f"世界包: {world_data['name']}")
    lines.append(f"总条目: {len(world_data['entries'])}")
    lines.append(f"更新时间: {datetime.now().isoformat()}")
    lines.append("")
    
    # 统计
    lines.append("【变更统计】")
    lines.append(f"  合并重复: {len([c for c in changes.get('duplicates', []) if c.get('type') == 'merge'])} 组")
    lines.append(f"  建立关系: {len(changes.get('links', []))} 条")
    lines.append(f"  降级条目: {len(changes.get('downgrades', []))} 条")
    lines.append("")
    
    # 显示具体变更
    if changes.get("links"):
        lines.append("【建立的关系】")
        for link in changes["links"][:10]:  # 只显示前10条
            lines.append(f"  {link['from']}: {link['relation']['type']} → {link['relation']['to']}")
            lines.append(f"    原因: {link['reason']}")
        if len(changes["links"]) > 10:
            lines.append(f"  ... 还有 {len(changes['links']) - 10} 条")
        lines.append("")
    
    if changes.get("downgrades"):
        lines.append("【降级的条目】")
        for d in changes["downgrades"][:10]:
            lines.append(f"  {d['name']}: canon → draft")
        if len(changes["downgrades"]) > 10:
            lines.append(f"  ... 还有 {len(changes["downgrades"]) - 10} 条")
        lines.append("")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="世界包自动维护器")
    parser.add_argument("--name", "-n", required=True, help="世界包名称")
    parser.add_argument("--dry-run", action="store_true", help="只报告不修改")
    parser.add_argument("--apply", action="store_true", help="应用修改")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument("--fix-orphans", action="store_true", help="只修复孤岛条目")
    parser.add_argument("--fix-duplicates", action="store_true", help="只合并重复条目")
    parser.add_argument("--downgrade", action="store_true", help="批量降级无出处条目")
    
    args = parser.parse_args()
    
    # 加载世界包
    world_data = load_world(args.name)
    if not world_data:
        return 1
    
    entries = world_data["entries"]
    changes = {
        "links": [],
        "duplicates": [],
        "downgrades": []
    }
    
    # 执行修复
    if args.apply or args.report or args.fix_orphans:
        links = auto_link_orphans(entries)
        changes["links"] = links
    
    if args.apply or args.report or args.fix_duplicates:
        duplicates = find_duplicates(entries)
        merge_changes = merge_duplicates(entries, duplicates)
        changes["duplicates"] = merge_changes
    
    if args.apply or args.report or args.downgrade:
        downgrades = downgrade_non_canon(entries)
        changes["downgrades"] = downgrades
    
    # 输出
    if args.report or args.dry_run:
        report = generate_report(world_data, changes)
        print(report)
    
    if args.apply:
        save_world(args.name, world_data)
        print(f"\n✅ 已应用 {len(changes['links']) + len(changes['duplicates']) + len(changes['downgrades'])} 项变更")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
