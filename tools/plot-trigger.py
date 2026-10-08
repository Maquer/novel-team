#!/usr/bin/env python3
"""
plot-trigger.py — 剧情触发器系统（借鉴 AbilityKit Triggering 模块）

核心设计：
  EventBus + TriggerRunner + TriggerPlan
  事件进入 → 条件评估 → 排序 → 执行Action
  继承 decide-trigger.py 的决策点识别，扩展到全量剧情事件

小说适配：
  事件类型：chapter_start / scene_change / character_enter / conflict_escalate / foreshadow_recall / dialogue_key / death / birth / 等
  条件：角色状态、剧情进度、时间线位置
  Action：写事实账本、推演下一情节、提示决策点、更新状态修正器

使用：
  python plot-trigger.py register --event-type chapter_start --condition "chapter>=1" --action write_fact
  python plot-trigger.py fire --project my-novel --event chapter_start --payload '{"chapter":1}'
  python plot-trigger.py list --project my-novel
  python plot-trigger.py history --project my-novel --limit 20
"""

import sys
import json
import time
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ==================== 事件与触发器定义 ====================

class EventType(Enum):
    # 章节级
    CHAPTER_START = "chapter_start"
    CHAPTER_END = "chapter_end"
    CHAPTER_COMPLETE = "chapter_complete"
    
    # 场景级
    SCENE_CHANGE = "scene_change"
    SCENE_ENTER = "scene_enter"
    SCENE_EXIT = "scene_exit"
    
    # 角色级
    CHARACTER_ENTER = "character_enter"
    CHARACTER_EXIT = "character_exit"
    CHARACTER_STATE_CHANGE = "character_state_change"
    CHARACTER_DEATH = "character_death"
    CHARACTER_BIRTH = "character_birth"
    
    # 剧情级
    CONFLICT_ESCALATE = "conflict_escalate"
    CONFLICT_RESOLVE = "conflict_resolve"
    FORESHADOW_PLANT = "foreshadow_plant"
    FORESHADOW_RECALL = "foreshadow_recall"
    REVEAL = "reveal"
    DECISION_POINT = "decision_point"
    
    # 对话级
    DIALOGUE_KEY = "dialogue_key"
    DIALOGUE_CONFLICT = "dialogue_conflict"
    
    # 世界级
    WORLD_STATE_CHANGE = "world_state_change"
    FACTION_CHANGE = "faction_change"
    
    # 特殊
    PLOT_TWIST = "plot_twist"
    CLIMAX_APPROACH = "climax_approach"


@dataclass
class TriggerRule:
    """单条触发规则"""
    id: str
    event_type: EventType
    condition: str  # 条件表达式（简化版：key=value 或 key>value）
    action: str  # 执行的动作名称
    priority: int = 0  # 优先级，越高越先执行
    action_params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "condition": self.condition,
            "priority": self.priority,
            "action": self.action,
            "action_params": self.action_params,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TriggerRule':
        return cls(
            id=data["id"],
            event_type=EventType(data["event_type"]),
            condition=data["condition"],
            priority=data.get("priority", 0),
            action=data["action"],
            action_params=data.get("action_params", {}),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", ""),
        )


@dataclass
class FireRecord:
    """触发记录"""
    id: str
    rule_id: str
    event_type: str
    payload: Dict
    action_result: Optional[Dict] = None
    fired_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "action_result": self.action_result,
            "fired_at": self.fired_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FireRecord':
        return cls(**data)


# ==================== 条件评估器 ====================

class ConditionEvaluator:
    """条件表达式评估器（简化版）"""
    
    # 支持的比较操作符
    OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
           ">": lambda a, b: a > b, "<": lambda a, b: a < b,
           "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
    
    @classmethod
    def evaluate(cls, condition: str, payload: Dict) -> bool:
        """评估条件，payload 是事件载荷"""
        if not condition:
            return True  # 无条件 = 总是触发
        
        # 解析条件：支持 "key op value" 格式
        for op_str, op_fn in cls.OPS.items():
            if op_str in condition:
                parts = condition.split(op_str, 1)
                if len(parts) == 2:
                    key, val_str = parts[0].strip(), parts[1].strip()
                    try:
                        payload_val = payload.get(key)
                        expected = float(val_str) if val_str.replace('.','',1).isdigit() else val_str
                        return op_fn(payload_val, expected)
                    except (ValueError, TypeError):
                        continue
        
        # 简单 key 存在性检查
        if condition in payload:
            return True
        
        return False


# ==================== Action 注册表 ====================

class ActionRegistry:
    """Action 注册表"""
    
    def __init__(self):
        self._actions: Dict[str, Callable] = {}
        self._register_builtins()
    
    def _register_builtins(self):
        """注册内置 Actions"""
        self.register("log", self._action_log)
        self.register("write_fact", self._action_write_fact)
        self.register("add_trigger", self._action_add_trigger)
        self.register("notify_decision", self._action_notify_decision)
        self.register("update_context", self._action_update_context)
        self.register("fire_another", self._action_fire_another)
    
    def register(self, name: str, fn: Callable):
        self._actions[name] = fn
    
    def execute(self, name: str, params: Dict, context: Dict) -> Dict:
        fn = self._actions.get(name)
        if not fn:
            return {"status": "error", "error": f"Unknown action: {name}"}
        return fn(params, context)
    
    def _action_log(self, params: Dict, context: Dict) -> Dict:
        msg = params.get("message", params.get("text", "无消息"))
        print(f"  [TRIGGER LOG] {msg}")
        return {"status": "ok", "logged": msg}
    
    def _action_write_fact(self, params: Dict, context: Dict) -> Dict:
        """写一条事实到账本"""
        content = params.get("content", "")
        category = params.get("category", "general")
        if not content:
            return {"status": "error", "error": "write_fact 需要 content 参数"}
        # 这里只记录，实际写入由外部 fact-ledger 处理
        print(f"  [FACT] 待写入: [{category}] {content[:80]}...")
        return {"status": "ok", "fact": content, "category": category}
    
    def _action_add_trigger(self, params: Dict, context: Dict) -> Dict:
        """动态添加新触发规则"""
        print(f"  [TRIGGER] 动态添加规则: {params.get('event_type', '?')} → {params.get('action', '?')}")
        return {"status": "ok", "new_rule": params}
    
    def _action_notify_decision(self, params: Dict, context: Dict) -> Dict:
        """通知用户需要决策"""
        title = params.get("title", "需要决策")
        situation = params.get("situation", "")
        print(f"  [DECISION] {title}: {situation[:60]}...")
        return {"status": "ok", "decision_requested": title}
    
    def _action_update_context(self, params: Dict, context: Dict) -> Dict:
        """更新共享上下文"""
        for k, v in params.get("updates", {}).items():
            context[k] = v
        return {"status": "ok", "updated": list(params.get("updates", {}).keys())}
    
    def _action_fire_another(self, params: Dict, context: Dict) -> Dict:
        """级联触发另一个事件"""
        print(f"  [CASCADE] 级联触发: {params.get('event_type', '?')}")
        return {"status": "ok", "cascaded_to": params.get("event_type")}


# ==================== TriggerManager ====================

class PlotTrigger:
    """剧情触发器管理器"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = Path(f"/var/minis/shared/novel-team/.triggers/{project_id}.json")
        self.rules: Dict[str, TriggerRule] = {}
        self.fire_records: List[FireRecord] = []
        self.context: Dict[str, Any] = {}
        self.action_registry = ActionRegistry()
        self._counter = 0
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.rules = {k: TriggerRule.from_dict(v) for k, v in data.get("rules", {}).items()}
            self.fire_records = [FireRecord.from_dict(r) for r in data.get("fire_records", [])]
            self.context = data.get("context", {})
            self._counter = data.get("counter", 0)
    
    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": {k: v.to_dict() for k, v in self.rules.items()},
            "fire_records": [r.to_dict() for r in self.fire_records[-500:]],  # 保留最近500条
            "context": self.context,
            "counter": self._counter,
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def register_rule(self, event_type: str, condition: str, action: str,
                      priority: int = 0, action_params: Dict = None) -> str:
        """注册触发规则"""
        self._counter += 1
        rule_id = f"T{self._counter:04d}"
        rule = TriggerRule(
            id=rule_id,
            event_type=EventType(event_type),
            condition=condition,
            priority=priority,
            action=action,
            action_params=action_params or {},
            created_at=datetime.now().isoformat(),
        )
        self.rules[rule_id] = rule
        self._save()
        return rule_id
    
    def fire(self, event_type: str, payload: Dict = None) -> List[Dict]:
        """触发事件，返回所有执行的 Action 结果"""
        payload = payload or {}
        etype = EventType(event_type) if isinstance(event_type, str) else event_type
        fired_results = []
        
        # 收集匹配的规则
        matching = []
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            if rule.event_type != etype:
                continue
            if ConditionEvaluator.evaluate(rule.condition, payload):
                matching.append(rule)
        
        # 按优先级排序
        matching.sort(key=lambda r: r.priority, reverse=True)
        
        # 执行
        for rule in matching:
            result = self.action_registry.execute(rule.action, rule.action_params, self.context)
            self._counter += 1
            record = FireRecord(
                id=f"F{self._counter:04d}",
                rule_id=rule.id,
                event_type=etype.value,
                payload=payload,
                action_result=result,
                fired_at=datetime.now().isoformat(),
            )
            self.fire_records.append(record)
            fired_results.append({
                "record_id": record.id,
                "rule_id": rule.id,
                "action": rule.action,
                "result": result,
            })
        
        self._save()
        return fired_results
    
    def list_rules(self) -> List[Dict]:
        return [r.to_dict() for r in self.rules.values()]
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        return [r.to_dict() for r in self.fire_records[-limit:]]
    
    def disable_rule(self, rule_id: str):
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            self._save()
    
    def enable_rule(self, rule_id: str):
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            self._save()


# ==================== CLI ====================

def cmd_register(args):
    trigger = PlotTrigger(args.project)
    rule_id = trigger.register_rule(args.event_type, args.condition or "", args.action,
                                     int(args.priority or 0),
                                     json.loads(args.params) if args.params else None)
    print(json.dumps({"rule_id": rule_id, "event_type": args.event_type, "action": args.action},
                      ensure_ascii=False, indent=2))
    return 0


def cmd_fire(args):
    trigger = PlotTrigger(args.project)
    payload = json.loads(args.payload) if args.payload else {}
    results = trigger.fire(args.event_type, payload)
    print(json.dumps({"fired_count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args):
    trigger = PlotTrigger(args.project)
    rules = trigger.list_rules()
    print(json.dumps({"total": len(rules), "rules": rules}, ensure_ascii=False, indent=2))
    return 0


def cmd_history(args):
    trigger = PlotTrigger(args.project)
    records = trigger.get_history(int(args.limit or 20))
    print(json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2))
    return 0


def cmd_enable(args):
    trigger = PlotTrigger(args.project)
    trigger.enable_rule(args.rule_id)
    print(f"✅ 规则 {args.rule_id} 已启用")
    return 0


def cmd_disable(args):
    trigger = PlotTrigger(args.project)
    trigger.disable_rule(args.rule_id)
    print(f"⏸️ 规则 {args.rule_id} 已禁用")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="剧情触发器系统（借鉴AbilityKit Triggering）")
    parser.add_argument("--project", "-p", required=True, help="项目ID")
    sub = parser.add_subparsers(dest="command")
    
    p_reg = sub.add_parser("register", help="注册触发规则")
    p_reg.add_argument("--event-type", "-e", required=True, help="事件类型")
    p_reg.add_argument("--condition", "-c", help="条件表达式（key op value）")
    p_reg.add_argument("--action", "-a", required=True, help="执行动作")
    p_reg.add_argument("--priority", "-pr", default="0", help="优先级")
    p_reg.add_argument("--params", help="动作参数JSON")
    
    p_fire = sub.add_parser("fire", help="触发事件")
    p_fire.add_argument("--event-type", "-e", required=True)
    p_fire.add_argument("--payload", help="事件载荷JSON")
    
    p_list = sub.add_parser("list", help="列出规则")
    
    p_hist = sub.add_parser("history", help="触发历史")
    p_hist.add_argument("--limit", default="20")
    
    p_en = sub.add_parser("enable", help="启用规则")
    p_en.add_argument("--rule-id", required=True)
    
    p_dis = sub.add_parser("disable", help="禁用规则")
    p_dis.add_argument("--rule-id", required=True)
    
    args = parser.parse_args()
    cmd_map = {"register": cmd_register, "fire": cmd_fire, "list": cmd_list,
               "history": cmd_history, "enable": cmd_enable, "disable": cmd_disable}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
