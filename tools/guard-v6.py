#!/usr/bin/env python3
"""
guard-v6.py — 四道一致性防线（借鉴 ai-novel-writer v6）

核心功能：
  ① 状态约束   → 推演前：把已确定的事实喂给模型，防止凭空改变
  ② 因果校验   → 推演后：检查事件是否依赖不存在的前提
  ③ hidden tracker → 推演中：性格变化缓慢积累，防角色突变
  ④ 用户否决权 → 推演后："这条不算"的最终手段

使用：
  python guard-v6.py --check events.json --facts facts.json
  python guard-v6.py --build-constraints novel.json
  python guard-v6.py --tracker character.json
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class IssueLevel(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class CausalIssue:
    """因果校验问题"""
    level: IssueLevel
    kind: str
    message: str
    event_title: str = ""
    fix_hint: str = ""
    layer: str = "event"
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "kind": self.kind,
            "message": self.message,
            "event_title": self.event_title,
            "fix_hint": self.fix_hint,
            "layer": self.layer,
        }
    
    def __repr__(self):
        return f"[{self.level.value}/{self.kind}] {self.message}"


class WorldGuard:
    """四道一致性防线"""
    
    def __init__(self):
        self.facts: Dict[str, any] = {}
        self.characters: Dict[str, Dict] = {}
        self.characters_history: Dict[str, List[Dict]] = {}
        self.issues: List[CausalIssue] = []
    
    # ============================================================ ① 状态约束
    
    def build_state_constraints(self, novel_data: Dict) -> str:
        """
        把世界当前"已确定的事实"整理成硬约束文本，喂给推演模型。
        
        目的：防止模型凭空改变已经写定的事实（比如把已死的角色写活）。
        """
        lines = []
        
        # 角色硬事实：死亡/失踪是不可逆的
        chars = novel_data.get("characters", [])
        dead = [c["name"] for c in chars if c.get("status") == "dead"]
        missing = [c["name"] for c in chars if c.get("status") == "missing"]
        
        if dead:
            lines.append(f"- 已死亡角色（不得作为行动主体出现）：{', '.join(dead)}")
        if missing:
            lines.append(f"- 已失踪角色：{', '.join(missing)}")
        
        alive = [c for c in chars if c.get("status") == "alive"]
        if alive:
            brief = []
            for c in alive[:20]:
                item = c["name"]
                if c.get("location"):
                    item += f"（在{c['location']}）"
                brief.append(item)
            lines.append(f"- 在世角色及位置：{'；'.join(brief)}")
        
        # 世界实体硬事实
        entities = novel_data.get("entities", [])
        active_ents = [e for e in entities if e.get("status") == "active"]
        destroyed_ents = [e for e in entities if e.get("status") == "destroyed"]
        
        if active_ents:
            brief = [f"{e['name']}({e.get('type', 'entity')})" for e in active_ents[:20]]
            lines.append(f"- 活跃世界实体：{', '.join(brief)}")
        
        if destroyed_ents:
            lines.append(f"- 已被摧毁/终结的实体（不得复原）：{', '.join(e['name'] for e in destroyed_ents)}")
        
        # 世界状态硬数字
        states = novel_data.get("world_state", {})
        if states:
            brief = [f"{k}={v}" for k, v in states.items()]
            lines.append(f"- 已确定的世界状态量（变更必须有事件依据）：{'；'.join(brief)}")
        
        # 正史事实
        facts = novel_data.get("facts", [])
        if facts:
            lines.append("- 正史已写定的事实（不得违反）：")
            for f in facts[:25]:
                lines.append(f"  - {f.get('content', '')}")
        
        if not lines:
            return "（世界尚无已确定的事实，本次推演可自由展开）"
        
        return "\n".join(lines)
    
    # ============================================================ ② 因果校验
    
    def validate_causality(self, events: List[Dict], characters: Dict[str, Dict],
                          entities: Dict[str, Dict]) -> List[CausalIssue]:
        """
        校验推演产出的事件是否依赖了不存在的前提。
        
        error   = 必须修正（逻辑硬伤）
        warning = 需要人确认（可疑但可能合理）
        """
        issues = []
        
        for ev in events:
            title = ev.get("title", "")
            actor = (ev.get("actor") or "").strip()
            involved = ev.get("involved_characters") or []
            ent_names = ev.get("involved_entities") or []
            
            # 1) 已死角色作为行动主体
            if actor and actor in characters:
                if characters[actor].get("status") == "dead":
                    issues.append(CausalIssue(
                        IssueLevel.ERROR, "dead_actor",
                        f"已死亡的角色「{actor}」作为行动主体出现", title,
                        "改成回忆/他人转述，或修正死亡事实"
                    ))
                elif characters[actor].get("status") == "missing":
                    issues.append(CausalIssue(
                        IssueLevel.WARNING, "missing_actor",
                        f"失踪角色「{actor}」作为行动主体出现", title,
                        "补一个'他回来了'的事件"
                    ))
            
            # 2) 不存在的角色
            unknown = [n for n in ([actor] + list(involved))
                      if n and n not in characters]
            if unknown:
                issues.append(CausalIssue(
                    IssueLevel.WARNING, "unknown_character",
                    f"事件提到未建档角色：{', '.join(set(unknown))}", title,
                    "确认是否需要为新角色建档"
                ))
            
            # 3) 引用了不存在的世界实体
            unknown_ent = [n for n in ent_names if n and n not in entities]
            if unknown_ent:
                issues.append(CausalIssue(
                    IssueLevel.WARNING, "unknown_entity",
                    f"事件引用未登记的世界实体：{', '.join(set(unknown_ent))}", title,
                    "落定时会自动建档"
                ))
            
            # 4) 已被摧毁的实体作为行动主体
            for n in ent_names:
                e = entities.get(n)
                if e and e.get("status") == "destroyed":
                    issues.append(CausalIssue(
                        IssueLevel.ERROR, "destroyed_entity",
                        f"已摧毁的实体「{n}」再次行动", title,
                        "若非回忆，需修正"
                    ))
            
            # 5) 状态变更缺少依据
            changes = (ev.get("state_changes") or {}).get("world") or []
            for ch in changes:
                if not ch.get("reason"):
                    issues.append(CausalIssue(
                        IssueLevel.WARNING, "state_change_no_reason",
                        f"世界状态「{ch.get('key', '?')}」发生变化但未说明依据", title,
                        "补上 reason"
                    ))
            
            # 6) 角色知识越界
            for k in (ev.get("knowledge_changes") or []):
                if k.get("know_type") == "know":
                    name = k.get("name", "").strip()
                    present = {actor} | set(involved)
                    if name and name not in present:
                        issues.append(CausalIssue(
                            IssueLevel.WARNING, "knowledge_out_of_band",
                            f"「{name}」没有在场，却写成了「知道」", title,
                            "改成believe/suspect，或补一个'他听说了'的事件",
                            layer="knowledge"
                        ))
        
        return issues
    
    # ============================================================ ③ hidden tracker
    
    def apply_trait_deltas(self, character: Dict, deltas: Dict[str, float],
                          threshold: float = 30.0) -> Dict:
        """
        把事件里的性格变化累加进tracker。
        
        小变化只进pending，累积到阈值才真正落到value上，
        从而避免"角色突然变了"。
        """
        results = []
        name = character.get("name", "?")
        
        for trait, delta in deltas.items():
            current = character.get("traits", {}).get(trait, 0)
            pending = character.get("trait_trackers", {}).get(trait, {}).get("pending", 0)
            
            new_pending = pending + delta
            
            # 检查是否达到阈值
            jumped = False
            new_value = current
            if abs(new_pending) >= threshold:
                new_value = current + new_pending
                jumped = True
                new_pending = 0
            
            results.append({
                "name": name,
                "trait": trait,
                "value": new_value,
                "pending": new_pending,
                "jumped": jumped,
            })
            
            # 更新character
            if "traits" not in character:
                character["traits"] = {}
            character["traits"][trait] = new_value
            
            if "trait_trackers" not in character:
                character["trait_trackers"] = {}
            character["trait_trackers"][trait] = {"pending": new_pending}
        
        return results
    
    def check_trait_jump(self, character: Dict, old_traits: Dict,
                        new_traits: Dict) -> List[CausalIssue]:
        """检查角色是否有突变（跳过了积累过程）"""
        issues = []
        name = character.get("name", "?")
        
        for trait in set(old_traits.keys()) | set(new_traits.keys()):
            old_val = old_traits.get(trait, 0)
            new_val = new_traits.get(trait, 0)
            delta = abs(new_val - old_val)
            
            if delta >= 30:  # 突变阈值
                issues.append(CausalIssue(
                    IssueLevel.WARNING, "trait_jump",
                    f"角色「{name}」的「{trait}」属性突变（{old_val}→{new_val}，变化{delta}）",
                    "",
                    "通过事件缓慢积累，不要一步到位",
                    layer="character"
                ))
        
        return issues
    
    # ============================================================ ④ 用户否决权
    
    def rollback_event(self, event_id: str, events_log: List[Dict]) -> bool:
        """
        用户否决：撤销一条事件。
        
        这是最终手段，只在极端情况下使用。
        """
        for i, ev in enumerate(events_log):
            if ev.get("id") == event_id:
                events_log.pop(i)
                return True
        return False
    
    def get_review_queue(self, issues: List[CausalIssue]) -> List[Dict]:
        """获取需要用户复核的问题列表"""
        return [issue.to_dict() for issue in issues if issue.level == IssueLevel.ERROR]
    
    # ============================================================ 工具方法
    
    def print_report(self, issues: List[CausalIssue]):
        """打印校验报告"""
        errors = [i for i in issues if i.level == IssueLevel.ERROR]
        warnings = [i for i in issues if i.level == IssueLevel.WARNING]
        
        print("\n" + "=" * 60)
        print("🛡️  四道一致性防线校验报告")
        print("=" * 60)
        print(f"错误数: {len(errors)}  警告数: {len(warnings)}")
        print("-" * 60)
        
        if errors:
            print("\n【❌ 错误（必须修正）】")
            for i, issue in enumerate(errors, 1):
                print(f"\n  {i}. {issue.kind}")
                print(f"     事件: {issue.event_title or '全局'}")
                print(f"     问题: {issue.message}")
                print(f"     建议: {issue.fix_hint}")
        
        if warnings:
            print("\n【⚠️  警告（需要确认）】")
            for i, issue in enumerate(warnings, 1):
                print(f"\n  {i}. {issue.kind}")
                print(f"     事件: {issue.event_title or '全局'}")
                print(f"     问题: {issue.message}")
        
        print("\n" + "=" * 60)
        
        if errors:
            print("❌ 校验未通过，请修正错误后重新推演")
            return False
        else:
            print("✅ 校验通过（含警告）")
            return True


def cmd_check(args):
    """执行因果校验"""
    guard = WorldGuard()
    
    # 加载数据
    try:
        with open(args.events, 'r', encoding='utf-8') as f:
            events = json.load(f)
    except Exception as e:
        print(f"❌ 加载事件文件失败: {e}")
        return 1
    
    try:
        with open(args.characters, 'r', encoding='utf-8') as f:
            characters = json.load(f)
    except Exception as e:
        print(f"❌ 加载角色文件失败: {e}")
        return 1
    
    try:
        with open(args.entities, 'r', encoding='utf-8') as f:
            entities = json.load(f)
    except Exception as e:
        print(f"❌ 加载实体文件失败: {e}")
        return 1
    
    # 执行校验
    print(f"🔍 正在校验 {len(events)} 条事件...")
    issues = guard.validate_causality(events, characters, entities)
    
    # 打印报告
    passed = guard.print_report(issues)
    
    # 保存结果
    if args.output:
        result = {
            "passed": passed,
            "errors": len([i for i in issues if i.level == IssueLevel.ERROR]),
            "warnings": len([i for i in issues if i.level == IssueLevel.WARNING]),
            "issues": [i.to_dict() for i in issues],
        }
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n📄 结果已保存到: {args.output}")
    
    return 0 if passed else 1


def cmd_constrain(args):
    """构建状态约束"""
    guard = WorldGuard()
    
    try:
        with open(args.novel, 'r', encoding='utf-8') as f:
            novel_data = json.load(f)
    except Exception as e:
        print(f"❌ 加载小说数据失败: {e}")
        return 1
    
    constraints = guard.build_state_constraints(novel_data)
    
    if args.output:
        Path(args.output).write_text(constraints, encoding='utf-8')
        print(f"✅ 约束已保存到: {args.output}")
    else:
        print("\n=== 状态约束 ===")
        print(constraints)
    
    return 0


def cmd_tracker(args):
    """测试hidden tracker"""
    guard = WorldGuard()
    
    # 示例角色
    character = {
        "name": "林默",
        "traits": {" courage ": 50, " caution ": 40},
        "trait_trackers": {}
    }
    
    # 模拟多次小变化
    deltas_list = [
        {"courage": 5, "caution": -3},
        {"courage": 8, "caution": -5},
        {"courage": 10, "caution": -8},
        {"courage": 12, "caution": -10},
    ]
    
    print("\n=== Hidden Tracker 测试 ===")
    print(f"初始状态: {character['traits']}")
    print("-" * 40)
    
    for i, deltas in enumerate(deltas_list, 1):
        results = guard.apply_trait_deltas(character, deltas, threshold=30)
        print(f"\n第{i}次变化: {deltas}")
        for r in results:
            status = "✅ 跃迁!" if r["jumped"] else "⏳ 累积中"
            print(f"  {r['trait']}: {r['value']} ({status}, pending={r['pending']})")
    
    print(f"\n最终状态: {character['traits']}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="四道一致性防线（借鉴ai-novel-writer v6）")
    subparsers = parser.add_subparsers(dest="command")
    
    # check命令
    p_check = subparsers.add_parser("check", help="因果校验")
    p_check.add_argument("--events", required=True, help="事件JSON文件")
    p_check.add_argument("--characters", required=True, help="角色JSON文件")
    p_check.add_argument("--entities", required=True, help="实体JSON文件")
    p_check.add_argument("--output", "-o", help="输出结果文件")
    
    # constrain命令
    p_constrain = subparsers.add_parser("constrain", help="构建状态约束")
    p_constrain.add_argument("--novel", required=True, help="小说数据JSON文件")
    p_constrain.add_argument("--output", "-o", help="输出约束文件")
    
    # tracker命令
    subparsers.add_parser("tracker", help="测试hidden tracker")
    
    args = parser.parse_args()
    
    if args.command == "check":
        sys.exit(cmd_check(args))
    elif args.command == "constrain":
        sys.exit(cmd_constrain(args))
    elif args.command == "tracker":
        cmd_tracker(args)
    else:
        parser.print_help()
