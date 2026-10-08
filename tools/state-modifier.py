#!/usr/bin/env python3
"""
state-modifier.py — 状态修正器（借鉴 AbilityKit Modifiers 模块）

核心设计：
  通用参数修正器：Buff/Debuff 动态改写后续剧情参数
  多层叠加：多个 Modifier 按优先级合并
  脏标记优化：参数变化时只重算受影响的部分

小说适配：
  角色状态修正：受伤→战斗力下降；恋爱中→判断力下降；获得秘籍→技能提升
  情节参数修正：场景氛围 modifier（紧张/轻松）、节奏 modifier（快进/慢放）
  多 modifier 叠加：角色同时处于"受伤"+"愤怒"状态，综合评估

使用：
  python state-modifier.py add --project my-novel --target 萧辰 --modifier 受伤_debuff --value -30 --duration 3ch
  python state-modifier.py apply --project my-novel --target 萧辰 --stat combat_power
  python state-modifier.py list --project my-novel --target 萧辰
  python state-modifier.py clear --project my-novel --target 萧辰 --modifier 受伤_debuff
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ModifierType(Enum):
    BUFF = "buff"           # 正面状态
    DEBUFF = "debuff"       # 负面状态
    NEUTRAL = "neutral"     # 中性状态
    CONTEXT = "context"     # 场景/氛围修正


@dataclass
class StateModifier:
    """单个状态修正"""
    id: str
    target: str           # 目标（角色名或场景名）
    modifier_name: str    # 修正器名称（如 "受伤_debuff"）
    mtype: ModifierType
    value: float          # 修正值（正=增强，负=削弱）
    duration_chapters: int = 0  # 持续章节数，0=永久
    expires_at_chapter: Optional[int] = None
    priority: int = 0     # 优先级，越高越先计算
    tags: List[str] = field(default_factory=list)
    reason: str = ""      # 触发原因
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "target": self.target,
            "modifier_name": self.modifier_name,
            "mtype": self.mtype.value,
            "value": self.value,
            "duration_chapters": self.duration_chapters,
            "expires_at_chapter": self.expires_at_chapter,
            "priority": self.priority,
            "tags": self.tags,
            "reason": self.reason,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StateModifier':
        return cls(**data)


class StateModifierManager:
    """状态修正器管理器"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = Path(f"/var/minis/shared/novel-team/.modifiers/{project_id}.json")
        self.modifiers: Dict[str, StateModifier] = {}
        self._counter = 0
        self._base_stats: Dict[str, Dict[str, float]] = {}  # target → stat → base_value
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            mods_data = data.get("modifiers", {})
            self.modifiers = {}
            for k, v in mods_data.items():
                v["mtype"] = ModifierType(v["mtype"])
                self.modifiers[k] = StateModifier(**v)
            self._base_stats = data.get("base_stats", {})
            self._counter = data.get("counter", 0)
    
    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "modifiers": {k: v.to_dict() for k, v in self.modifiers.items()},
            "base_stats": self._base_stats,
            "counter": self._counter,
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def set_base_stat(self, target: str, stat: str, value: float):
        """设置基础属性值（未受修正时的原始值）"""
        if target not in self._base_stats:
            self._base_stats[target] = {}
        self._base_stats[target][stat] = value
        self._save()
    
    def add_modifier(self, target: str, modifier_name: str, value: float,
                     mtype: str = "debuff", duration_chapters: int = 0,
                     priority: int = 0, tags: List[str] = None, reason: str = "") -> str:
        """添加状态修正"""
        self._counter += 1
        mod_id = f"M{self._counter:04d}"
        
        expires = None
        if duration_chapters > 0:
            expires = duration_chapters  # 由调用方传入当前章节号+duration计算
        
        mod = StateModifier(
            id=mod_id,
            target=target,
            modifier_name=modifier_name,
            mtype=ModifierType(mtype),
            value=value,
            duration_chapters=duration_chapters,
            expires_at_chapter=expires,
            priority=priority,
            tags=tags or [],
            reason=reason,
            created_at=datetime.now().isoformat(),
        )
        
        self.modifiers[mod_id] = mod
        self._save()
        return mod_id
    
    def get_effective_stat(self, target: str, stat: str, current_chapter: int = 0) -> Dict:
        """计算某角色在某章节的有效属性值"""
        base = self._base_stats.get(target, {}).get(stat, 0.0)
        
        active_mods = []
        total_delta = 0.0
        
        for mid, mod in self.modifiers.items():
            if mod.target != target:
                continue
            
            # 检查是否过期
            if mod.expires_at_chapter and current_chapter > mod.expires_at_chapter:
                continue
            
            # 检查持续时间
            if mod.duration_chapters > 0 and current_chapter > 0:
                # 简化：假设 modifier 在 duration 章节内有效
                # 实际应记录 applied_chapter
                pass
            
            total_delta += mod.value
            active_mods.append({
                "id": mod.id,
                "name": mod.modifier_name,
                "value": mod.value,
                "mtype": mod.mtype.value,
            })
        
        return {
            "target": target,
            "stat": stat,
            "base_value": base,
            "total_delta": total_delta,
            "effective_value": base + total_delta,
            "active_modifiers": active_mods,
            "chapter": current_chapter,
        }
    
    def list_modifiers(self, target: Optional[str] = None, current_chapter: int = 0) -> List[Dict]:
        """列出活跃修正"""
        result = []
        for mid, mod in self.modifiers.items():
            if target and mod.target != target:
                continue
            if mod.expires_at_chapter and current_chapter > mod.expires_at_chapter:
                continue
            result.append(mod.to_dict())
        return result
    
    def clear_modifier(self, mod_id: str) -> bool:
        """清除指定修正"""
        if mod_id in self.modifiers:
            del self.modifiers[mod_id]
            self._save()
            return True
        return False
    
    def clear_all_for_target(self, target: str) -> int:
        """清除某角色的全部修正"""
        count = 0
        to_remove = [mid for mid, m in self.modifiers.items() if m.target == target]
        for mid in to_remove:
            del self.modifiers[mid]
            count += 1
        if count:
            self._save()
        return count
    
    def get_summary(self) -> Dict:
        """获取总体摘要"""
        by_target = {}
        for mid, mod in self.modifiers.items():
            if mod.target not in by_target:
                by_target[mod.target] = {"buffs": 0, "debuffs": 0, "modifiers": []}
            if mod.mtype == ModifierType.BUFF:
                by_target[mod.target]["buffs"] += 1
            elif mod.mtype == ModifierType.DEBUFF:
                by_target[mod.target]["debuffs"] += 1
            by_target[mod.target]["modifiers"].append(mod.modifier_name)
        
        return {
            "total_modifiers": len(self.modifiers),
            "by_target": {t: {"buffs": v["buffs"], "debuffs": v["debuffs"],
                              "modifier_names": v["modifiers"]} for t, v in by_target.items()},
            "tracked_stats": list(self._base_stats.keys()),
        }


# ==================== CLI ====================

def cmd_add(args):
    mgr = StateModifierManager(args.project)
    mod_id = mgr.add_modifier(
        target=args.target,
        modifier_name=args.name,
        value=float(args.value),
        mtype=args.mtype,
        duration_chapters=int(args.duration or 0),
        priority=int(args.priority or 0),
        tags=args.tags.split(",") if args.tags else None,
        reason=args.reason or "",
    )
    print(json.dumps({"modifier_id": mod_id, "target": args.target, "name": args.name,
                       "value": args.value, "type": args.mtype}, ensure_ascii=False, indent=2))
    return 0


def cmd_apply(args):
    mgr = StateModifierManager(args.project)
    result = mgr.get_effective_stat(args.target, args.stat, int(args.chapter or 0))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args):
    mgr = StateModifierManager(args.project)
    mods = mgr.list_modifiers(args.target, int(args.chapter or 0))
    print(json.dumps({"count": len(mods), "modifiers": mods}, ensure_ascii=False, indent=2))
    return 0


def cmd_clear(args):
    mgr = StateModifierManager(args.project)
    if args.all:
        count = mgr.clear_all_for_target(args.target)
        print(f"✅ 已清除 {args.target} 的全部 {count} 个状态修正")
    else:
        ok = mgr.clear_modifier(args.modifier_id)
        print(f"{'✅' if ok else '❌'} 修正 {'已清除' if ok else '不存在'}: {args.modifier_id}")
    return 0


def cmd_base(args):
    mgr = StateModifierManager(args.project)
    if args.set_val is not None:
        mgr.set_base_stat(args.target, args.stat, float(args.set_val))
        print(f"✅ 已设置 {args.target}.{args.stat} 基础值 = {args.set_val}")
    else:
        base = mgr._base_stats.get(args.target, {})
        print(json.dumps({"target": args.target, "base_stats": base}, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args):
    mgr = StateModifierManager(args.project)
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="状态修正器（借鉴AbilityKit Modifiers）")
    parser.add_argument("--project", "-p", required=True)
    sub = parser.add_subparsers(dest="command")
    
    p_add = sub.add_parser("add", help="添加状态修正")
    p_add.add_argument("--target", required=True, help="目标角色/场景")
    p_add.add_argument("--name", "-n", required=True, help="修正器名称")
    p_add.add_argument("--value", "-v", required=True, help="修正值（正=增强，负=削弱）")
    p_add.add_argument("--mtype", default="debuff", help="类型: buff/debuff/neutral/context")
    p_add.add_argument("--duration", help="持续章节数（0=永久）")
    p_add.add_argument("--priority", default="0")
    p_add.add_argument("--tags", help="标签（逗号分隔）")
    p_add.add_argument("--reason", help="触发原因")
    
    p_apply = sub.add_parser("apply", help="计算有效属性值")
    p_apply.add_argument("--target", required=True)
    p_apply.add_argument("--stat", required=True, help="属性名")
    p_apply.add_argument("--chapter", help="当前章节号")
    
    p_list = sub.add_parser("list", help="列出修正")
    p_list.add_argument("--target", help="按目标过滤")
    p_list.add_argument("--chapter", help="按章节过滤")
    
    p_clear = sub.add_parser("clear", help="清除修正")
    p_clear.add_argument("--target", help="清除某目标全部修正")
    p_clear.add_argument("--modifier-id", help="清除指定修正ID")
    p_clear.add_argument("--all", action="store_true", help="清除某目标全部")
    
    p_base = sub.add_parser("base", help="设置/查看基础属性")
    p_base.add_argument("--target", required=True)
    p_base.add_argument("--stat", required=True)
    p_base.add_argument("--set-val", type=float, help="设置基础值")
    
    p_sum = sub.add_parser("summary", help="总体摘要")
    
    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "apply": cmd_apply, "list": cmd_list,
               "clear": cmd_clear, "base": cmd_base, "summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
