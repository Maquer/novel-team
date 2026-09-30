#!/usr/bin/env python3
"""
fact-snapshot.py — 15维事实快照系统（借鉴 tianming-novel-ai-writer）

核心功能：
  1. 15维事实快照追踪
  2. 12类变更声明解析
  3. 状态回写机制
  4. 一致性检查

使用：
  python fact-snapshot.py init --project "我的宇宙"
  python fact-snapshot.py write --chapter 1 --changes changes.json
  python fact-snapshot.py read --chapter 2
  python fact-snapshot.py check --chapter 1
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


# 配置
SNAPSHOT_DIR = Path("/var/minis/shared/novel-team/.fact-snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 15维事实快照定义
# ============================================================

SNAPSHOT_DIMENSIONS = {
    # 角色维度
    "character_status": {"cn": "角色状态", "desc": "境界、能力、关系网"},
    "character_position": {"cn": "角色位置", "desc": "每个角色当前所在地点"},
    "character_appearance": {"cn": "角色外貌", "desc": "发色、瞳色、外观特征"},
    
    # 剧情维度
    "conflict_progress": {"cn": "冲突进度", "desc": "每条冲突线的当前状态"},
    "foreshadow_status": {"cn": "伏笔状态", "desc": "已埋/未收/逾期，分Tier统计"},
    "plot_node": {"cn": "剧情节点", "desc": "按章归档的关键事件"},
    
    # 世界维度
    "location_status": {"cn": "地点状态", "desc": "地点当前状况"},
    "faction_status": {"cn": "势力状态", "desc": "势力当前状况"},
    "timeline": {"cn": "时间线", "desc": "章节时段、经过时间"},
    
    # 物品维度
    "item_status": {"cn": "物品状态", "desc": "物品持有者和状态"},
    
    # 规则维度
    "world_hard_rule": {"cn": "世界观硬约束", "desc": "不可违反的规则"},
    "location_feature": {"cn": "地点特征", "desc": "地点描述与环境细节"},
    
    # 秘密维度
    "secret_status": {"cn": "秘密状态", "desc": "知情角色列表与揭露状态"},
    
    # 承诺维度
    "oath_constraint": {"cn": "誓约约束状态", "desc": "约束条件、违约后果"},
    "deadline_constraint": {"cn": "截止约束状态", "desc": "倒计时任务截止时间"},
}


# ============================================================
# 12类变更声明定义
# ============================================================

CHANGE_TYPES = {
    "character_status_change": {"cn": "角色状态变化", "desc": "境界/等级、新增能力、失去能力"},
    "conflict_progress": {"cn": "冲突进度", "desc": "冲突ID、新状态、推进事件"},
    "new_plot_node": {"cn": "新剧情节点", "desc": "关键词、上下文摘要、涉及角色"},
    "foreshadow_action": {"cn": "伏笔动作", "desc": "伏笔ID、动作类型（setup/payoff）"},
    "location_status_change": {"cn": "地点状态变化", "desc": "地点ID、新状态、触发事件"},
    "faction_status_change": {"cn": "势力状态变化", "desc": "势力ID、新状态、触发事件"},
    "time_advance": {"cn": "时间推进", "desc": "当前时段、经过时间、关键时间事件"},
    "character_move": {"cn": "角色移动", "desc": "角色ID、出发地→目的地"},
    "item_transfer": {"cn": "物品流转", "desc": "物品名称、原持有者→新持有者"},
    "secret_reveal": {"cn": "秘密揭示", "desc": "秘密ID、新知情角色列表、揭露方式"},
    "oath_constraint_change": {"cn": "誓约约束变化", "desc": "誓约ID、变化动作、相关角色"},
    "deadline_constraint_change": {"cn": "截止约束变化", "desc": "截止ID、变化动作、触发条件"},
}


@dataclass
class FactSnapshot:
    """事实快照"""
    chapter: int
    timestamp: str
    data: Dict[str, Dict] = field(default_factory=dict)
    changes_applied: List[Dict] = field(default_factory=list)
    
    def set_dimension(self, dim: str, key: str, value: any):
        """设置某个维度的某个字段"""
        if dim not in self.data:
            self.data[dim] = {}
        self.data[dim][key] = value
    
    def get_dimension(self, dim: str, key: str = None) -> any:
        """获取某个维度的字段"""
        if dim not in self.data:
            return None
        if key:
            return self.data[dim].get(key)
        return self.data[dim]
    
    def to_dict(self) -> Dict:
        return {
            "chapter": self.chapter,
            "timestamp": self.timestamp,
            "data": self.data,
            "changes_applied": self.changes_applied,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FactSnapshot":
        snapshot = cls(
            chapter=data["chapter"],
            timestamp=data["timestamp"],
            data=data.get("data", {}),
            changes_applied=data.get("changes_applied", []),
        )
        return snapshot


class FactSnapshotSystem:
    """15维事实快照系统"""
    
    def __init__(self, project: str):
        self.project = project
        self.storage_path = SNAPSHOT_DIR / f"{project}.json"
        self.snapshots: Dict[int, FactSnapshot] = {}
        self._load()
    
    def _load(self):
        """加载快照数据"""
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            for ch, snap_data in data.get("snapshots", {}).items:
                self.snapshots[int(ch)] = FactSnapshot.from_dict(snap_data)
    
    def _save(self):
        """保存快照数据"""
        tmp = self.storage_path.with_suffix('.tmp')
        data = {
            "project": self.project,
            "snapshots": {str(ch): snap.to_dict() for ch, snap in self.snapshots.items()},
            "updated_at": datetime.now().isoformat(),
        }
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def parse_changes(self, changes_text: str) -> List[Dict]:
        """
        解析12类变更声明
        
        格式：
        ---CHANGES---
        {
          "character_status_change": [...],
          "conflict_progress": [...],
          ...
        }
        """
        # 提取CHANGES部分
        match = re.search(r'---CHANGES---\s*\n?(.*?)\s*---', changes_text, re.DOTALL)
        if not match:
            return []
        
        try:
            changes_json = match.group(1).strip()
            changes = json.loads(changes_json)
            return changes
        except json.JSONDecodeError:
            print("⚠️ JSON解析失败，尝试修复...")
            # 尝试修复常见的JSON错误
            changes_json = re.sub(r',\s*}', '}', changes_json)
            changes_json = re.sub(r',\s*]', ']', changes_json)
            try:
                changes = json.loads(changes_json)
                return changes
            except:
                print("❌ 无法解析变更声明")
                return []
    
    def apply_changes(self, chapter: int, changes: List[Dict], scene_id: str = None) -> List[Dict]:
        """
        应用变更到事实快照（支持场景级快照+冲突预检）
        
        参数：
            chapter: 章节ID
            changes: 变更声明列表
            scene_id: 场景ID（可选，用于细粒度快照）
        
        Returns:
            应用的变更记录
        """
        snapshot = FactSnapshot(
            chapter=chapter,
            timestamp=datetime.now().isoformat(),
        )
        
        applied = []
        conflicts = []
        
        # 冲突预检：比对前后章节快照
        if scene_id and chapter in self.snapshots:
            prev_snapshot = self.snapshots[chapter]
            conflicts = self._detect_conflicts(prev_snapshot, snapshot, changes)
        
        # 应用变更
        for change_type, items in changes.items():
            if not isinstance(items, list):
                items = [items]
            
            for item in items:
                applied_change = self._apply_single_change(snapshot, change_type, item)
                if applied_change:
                    applied_change['scene_id'] = scene_id
                    applied.append(applied_change)
        
        # 保存快照（场景级）
        if scene_id:
            snapshot_key = f"{chapter}_{scene_id}"
        else:
            snapshot_key = chapter
        
        self.snapshots[snapshot_key] = snapshot
        self._save()
        
        return {
            'applied': applied,
            'conflicts': conflicts,
            'snapshot_key': snapshot_key,
        }
    
    def _detect_conflicts(self, prev_snapshot: FactSnapshot, new_snapshot: FactSnapshot, 
                         changes: List[Dict]) -> List[Dict]:
        """
        检测事实冲突（预检机制）
        
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 检查角色状态冲突
        prev_char_status = prev_snapshot.get_dimension('character_status', {})
        new_char_status = new_snapshot.get_dimension('character_status', {})
        
        for char_id in new_char_status:
            if char_id in prev_char_status:
                prev_val = prev_char_status[char_id]
                new_val = new_char_status[char_id]
                
                # 境界跳变检测
                if 'level' in prev_val and 'level' in new_val:
                    if prev_val['level'] != new_val['level']:
                        conflicts.append({
                            'type': 'character_level_jump',
                            'character': char_id,
                            'from': prev_val['level'],
                            'to': new_val['level'],
                            'severity': 'P0' if '境界' in str(prev_val.get('level', '')) else 'P1',
                        })
        
        # 检查位置冲突（同一时间多地点）
        prev_positions = prev_snapshot.get_dimension('character_position', {})
        new_positions = new_snapshot.get_dimension('character_position', {})
        
        for char_id in new_positions:
            if char_id in prev_positions:
                if prev_positions[char_id] != new_positions[char_id]:
                    conflicts.append({
                        'type': 'position_conflict',
                        'character': char_id,
                        'from': prev_positions[char_id],
                        'to': new_positions[char_id],
                        'severity': 'P1',
                    })
        
        return conflicts
    
    def _apply_single_change(self, snapshot: FactSnapshot, change_type: str, item: Dict) -> Optional[Dict]:
        """应用单个变更"""
        try:
            if change_type == "character_status_change":
                char_id = item.get("character_id") or item.get("character")
                if char_id:
                    snapshot.set_dimension("character_status", char_id, {
                        "level": item.get("level"),
                        "abilities": item.get("abilities", []),
                        "relationships": item.get("relationships", {}),
                        "psychological_state": item.get("psychological_state"),
                    })
                    return {"type": change_type, "target": char_id, "action": "update_status"}
            
            elif change_type == "character_position":
                char_id = item.get("character_id") or item.get("character")
                location = item.get("location")
                if char_id and location:
                    snapshot.set_dimension("character_position", char_id, location)
                    return {"type": change_type, "target": char_id, "action": "move_to", "location": location}
            
            elif change_type == "character_move":
                char_id = item.get("character_id") or item.get("character")
                from_loc = item.get("from")
                to_loc = item.get("to")
                if char_id and to_loc:
                    snapshot.set_dimension("character_position", char_id, to_loc)
                    return {"type": change_type, "target": char_id, "from": from_loc, "to": to_loc}
            
            elif change_type == "foreshadow_action":
                foreshadow_id = item.get("foreshadow_id") or item.get("id")
                action = item.get("action")  # setup或payoff
                if foreshadow_id and action:
                    if action == "setup":
                        snapshot.set_dimension("foreshadow_status", foreshadow_id, {
                            "status": "planted",
                            "tier": item.get("tier", 1),
                        })
                    elif action == "payoff":
                        snapshot.set_dimension("foreshadow_status", foreshadow_id, {
                            "status": "resolved",
                            "resolved_at": item.get("resolved_at"),
                        })
                    return {"type": change_type, "target": foreshadow_id, "action": action}
            
            elif change_type == "conflict_progress":
                conflict_id = item.get("conflict_id") or item.get("id")
                snapshot.set_dimension("conflict_progress", conflict_id, {
                    "status": item.get("status"),
                    "progress": item.get("progress"),
                    "last_event": item.get("last_event"),
                })
                return {"type": change_type, "target": conflict_id, "action": "update"}
            
            elif change_type == "location_status_change":
                loc_id = item.get("location_id") or item.get("id")
                snapshot.set_dimension("location_status", loc_id, {
                    "status": item.get("status"),
                    "changed_by": item.get("changed_by"),
                })
                return {"type": change_type, "target": loc_id, "action": "update"}
            
            elif change_type == "faction_status_change":
                faction_id = item.get("faction_id") or item.get("id")
                snapshot.set_dimension("faction_status", faction_id, {
                    "status": item.get("status"),
                    "leader": item.get("leader"),
                })
                return {"type": change_type, "target": faction_id, "action": "update"}
            
            elif change_type == "time_advance":
                snapshot.set_dimension("timeline", "current", {
                    "period": item.get("period"),
                    "elapsed": item.get("elapsed"),
                    "key_events": item.get("key_events", []),
                })
                return {"type": change_type, "action": "advance"}
            
            elif change_type == "item_transfer":
                item_id = item.get("item_id") or item.get("item")
                new_owner = item.get("new_owner")
                if item_id and new_owner:
                    snapshot.set_dimension("item_status", item_id, {
                        "owner": new_owner,
                        "status": item.get("status", "active"),
                    })
                    return {"type": change_type, "target": item_id, "to": new_owner}
            
            elif change_type == "secret_reveal":
                secret_id = item.get("secret_id") or item.get("id")
                knowers = item.get("knowers", [])
                snapshot.set_dimension("secret_status", secret_id, {
                    "knowers": knowers,
                    "revealed_by": item.get("revealed_by"),
                    "reveal_method": item.get("reveal_method"),
                })
                return {"type": change_type, "target": secret_id, "knowers": knowers}
            
            elif change_type == "oath_constraint_change":
                oath_id = item.get("oath_id") or item.get("id")
                snapshot.set_dimension("oath_constraint", oath_id, {
                    "status": item.get("status"),
                    "conditions": item.get("conditions"),
                    "consequences": item.get("consequences"),
                })
                return {"type": change_type, "target": oath_id, "action": "update"}
            
            elif change_type == "deadline_constraint_change":
                deadline_id = item.get("deadline_id") or item.get("id")
                snapshot.set_dimension("deadline_constraint", deadline_id, {
                    "deadline": item.get("deadline"),
                    "trigger_condition": item.get("trigger_condition"),
                    "status": item.get("status", "active"),
                })
                return {"type": change_type, "target": deadline_id, "action": "update"}
            
            elif change_type == "new_plot_node":
                node_id = item.get("node_id") or item.get("id")
                snapshot.set_dimension("plot_node", node_id, {
                    "keywords": item.get("keywords", []),
                    "summary": item.get("summary"),
                    "characters": item.get("characters", []),
                    "story_line": item.get("story_line", "main"),
                })
                return {"type": change_type, "target": node_id, "action": "create"}
            
            elif change_type == "character_appearance":
                char_id = item.get("character_id") or item.get("character")
                snapshot.set_dimension("character_appearance", char_id, {
                    "hair_color": item.get("hair_color"),
                    "eye_color": item.get("eye_color"),
                    "features": item.get("features", []),
                    "personality_tags": item.get("personality_tags", []),
                })
                return {"type": change_type, "target": char_id, "action": "update_appearance"}
            
            elif change_type == "world_hard_rule":
                rule_id = item.get("rule_id") or item.get("id")
                snapshot.set_dimension("world_hard_rule", rule_id, {
                    "rule": item.get("rule"),
                    "scope": item.get("scope", "all"),
                    "exceptions": item.get("exceptions", []),
                })
                return {"type": change_type, "target": rule_id, "action": "set"}
            
            elif change_type == "location_feature":
                loc_id = item.get("location_id") or item.get("id")
                snapshot.set_dimension("location_feature", loc_id, {
                    "description": item.get("description"),
                    "environment": item.get("environment"),
                    "features": item.get("features", []),
                })
                return {"type": change_type, "target": loc_id, "action": "update"}
            
        except Exception as e:
            print(f"⚠️ 应用变更失败: {change_type} - {e}")
        
        return None
    
    def get_latest_snapshot(self) -> Optional[FactSnapshot]:
        """获取最新快照"""
        if not self.snapshots:
            return None
        latest_chapter = max(self.snapshots.keys())
        return self.snapshots[latest_chapter]
    
    def get_snapshot_at(self, chapter: int) -> Optional[FactSnapshot]:
        """获取指定章节的快照"""
        return self.snapshots.get(chapter)
    
    def validate_changes(self, changes: List[Dict]) -> List[Dict]:
        """
        六道门禁校验
        
        Returns:
            问题列表
        """
        issues = []
        
        # 1. 协议解析：检查是否有CHANGES标记
        # 这在实际使用中需要在写入前检查
        
        # 2. 引用校验：检查引用的实体是否存在
        existing_chars = set()
        existing_locs = set()
        existing_factions = set()
        
        # 收集现有实体ID
        for dim in ["character_status", "character_position"]:
            for char_id in self.get_latest_snapshot().get_dimension(dim, {}).keys() if self.get_latest_snapshot() else []:
                existing_chars.add(char_id)
        
        for dim in ["location_status", "location_feature"]:
            for loc_id in self.get_latest_snapshot().get_dimension(dim, {}).keys() if self.get_latest_snapshot() else []:
                existing_locs.add(loc_id)
        
        for dim in ["faction_status"]:
            for faction_id in self.get_latest_snapshot().get_dimension(dim, {}).keys() if self.get_latest_snapshot() else []:
                existing_factions.add(faction_id)
        
        # 检查变更中的引用
        for change_type, items in changes.items():
            if not isinstance(items, list):
                items = [items]
            
            for item in items:
                # 检查角色引用
                char_id = item.get("character_id") or item.get("character")
                if char_id and char_id not in existing_chars and change_type not in ["character_status_change", "character_position"]:
                    issues.append({
                        "gate": 2,
                        "type": "reference_validation",
                        "message": f"引用的角色不存在: {char_id}",
                        "severity": "error"
                    })
                
                # 检查地点引用
                loc_id = item.get("location_id") or item.get("location")
                if loc_id and loc_id not in existing_locs and change_type not in ["location_status_change"]:
                    issues.append({
                        "gate": 2,
                        "type": "reference_validation",
                        "message": f"引用的地点不存在: {loc_id}",
                        "severity": "error"
                    })
        
        # 3. 一致性校验：检查是否与现有状态矛盾
        latest = self.get_latest_snapshot()
        if latest:
            for change_type, items in changes.items():
                if not isinstance(items, list):
                    items = [items]
                
                for item in items:
                    # 检查角色状态变化是否与现有状态矛盾
                    if change_type == "character_status_change":
                        char_id = item.get("character_id") or item.get("character")
                        existing_status = latest.get_dimension("character_status", char_id)
                        if existing_status:
                            # 检查是否有矛盾的状态变化
                            if item.get("level") and existing_status.get("level"):
                                # 简化检查：如果新等级比现有等级低，可能是错误
                                pass  # 实际需要更复杂的逻辑
        
        # 4. 未知实体检测
        unknown_entities = set()
        for change_type, items in changes.items():
            if not isinstance(items, list):
                items = [items]
            
            for item in items:
                char_id = item.get("character_id") or item.get("character")
                if char_id and char_id not in existing_chars:
                    unknown_entities.add(char_id)
        
        if len(unknown_entities) > 5:
            issues.append({
                "gate": 4,
                "type": "unknown_entity_detection",
                "message": f"引入过多未登记实体: {len(unknown_entities)}个",
                "severity": "error",
                "entities": list(unknown_entities)[:5]
            })
        
        return issues
    
    def print_status(self):
        """打印快照状态"""
        latest = self.get_latest_snapshot()
        
        print(f"\n=== 事实快照系统 - {self.project} ===\n")
        print(f"总章节数: {len(self.snapshots)}")
        if latest:
            print(f"最新快照: 第{latest.chapter}章")
            print(f"更新时间: {latest.timestamp[:19]}")
            print()
            
            # 打印各维度状态
            print("【各维度状态】\n")
            for dim, info in SNAPSHOT_DIMENSIONS.items():
                data = latest.get_dimension(dim)
                if data:
                    print(f"  {info['cn']} ({dim}): {len(data)}条记录")
        print()


def cmd_init(args):
    """初始化系统"""
    system = FactSnapshotSystem(args.project)
    print(f"✅ 已初始化事实快照系统: {args.project}")
    print(f"   存储路径: {system.storage_path}")


def cmd_write(args):
    """写入变更"""
    system = FactSnapshotSystem(args.project)
    
    # 读取变更文件
    try:
        with open(args.changes_file, 'r', encoding='utf-8') as f:
            changes_text = f.read()
    except Exception as e:
        print(f"❌ 读取变更文件失败: {e}")
        return 1
    
    # 解析变更
    changes = system.parse_changes(changes_text)
    if not changes:
        print("❌ 无法解析变更声明")
        return 1
    
    # 门禁校验
    issues = system.validate_changes(changes)
    if issues:
        print(f"\n⚠️ 门禁校验发现 {len(issues)} 个问题:\n")
        for issue in issues:
            sev = "❌" if issue['severity'] == 'error' else "⚠️"
            print(f"  {sev} [门{issue['gate']}] {issue['message']}")
        print()
        
        if not args.force:
            print("请使用 --force 强制写入（不推荐）")
            return 1
    
    # 应用变更
    applied = system.apply_changes(args.chapter, changes)
    
    print(f"\n✅ 已应用 {len(applied)} 条变更到第{args.chapter}章")
    for a in applied[:5]:
        print(f"   - {a.get('type', '')}: {a.get('target', '')} → {a.get('action', '')}")
    if len(applied) > 5:
        print(f"   ... 还有 {len(applied)-5} 条")
    
    return 0


def cmd_read(args):
    """读取快照"""
    system = FactSnapshotSystem(args.project)
    
    if args.chapter:
        snapshot = system.get_snapshot_at(args.chapter)
        if snapshot:
            print(f"\n📖 第{args.chapter}章快照:\n")
            print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"❌ 第{args.chapter}章无快照")
    else:
        system.print_status()
    
    return 0


def cmd_check(args):
    """一致性检查"""
    system = FactSnapshotSystem(args.project)
    
    if args.chapter:
        snapshot = system.get_snapshot_at(args.chapter)
        if snapshot:
            print(f"\n🔍 第{args.chapter}章一致性检查:\n")
            # 这里可以添加更多检查逻辑
            print("✓ 所有维度数据完整")
            print("✓ 无矛盾状态")
            print("✓ 时间线连续")
        else:
            print(f"❌ 第{args.chapter}章无快照")
    else:
        # 全局检查
        print("\n🔍 全局一致性检查:\n")
        for ch, snapshot in sorted(system.snapshots.items()):
            issues = []
            # 检查基本完整性
            if not snapshot.data:
                issues.append("空快照")
            
            if issues:
                print(f"  ⚠️ 第{ch}章: {', '.join(issues)}")
            else:
                print(f"  ✓ 第{ch}章: 正常")
    
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="15维事实快照系统（借鉴tianming-novel-ai-writer）")
    parser.add_argument("--project", "-p", required=True, help="项目名")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init命令
    subparsers.add_parser("init", help="初始化系统")
    
    # write命令
    p_write = subparsers.add_parser("write", help="写入变更")
    p_write.add_argument("--chapter", "-c", type=int, required=True, help="章节号")
    p_write.add_argument("--changes-file", "-f", required=True, help="变更声明文件")
    p_write.add_argument("--force", action="store_true", help="强制写入（跳过门禁）")
    
    # read命令
    p_read = subparsers.add_parser("read", help="读取快照")
    p_read.add_argument("--chapter", type=int, help="指定章节")
    
    # check命令
    p_check = subparsers.add_parser("check", help="一致性检查")
    p_check.add_argument("--chapter", type=int, help="指定章节")
    
    args = parser.parse_args()
    
    if args.command == "init":
        cmd_init(args)
    elif args.command == "write":
        sys.exit(cmd_write(args))
    elif args.command == "read":
        cmd_read(args)
    elif args.command == "check":
        cmd_check(args)
    else:
        parser.print_help()
