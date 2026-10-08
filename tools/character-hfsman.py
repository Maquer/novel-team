#!/usr/bin/env python3
"""
character-hfsman.py — 角色心理状态机（借鉴 AbilityKit HFSM 模块）

核心设计：
  分层状态机：每个状态可嵌套子状态机
  ITriggerable：事件驱动状态转换
  IAction：行为层，返回 Running/Success/Failure
  Decorator AOP：BeforeEnter/AfterEnter/BeforeExit/AfterExit 钩子

小说适配：
  角色心理状态：平静→愤怒→崩溃→觉醒（层次结构）
  触发条件：受到攻击→进入"愤怒"；被背叛→进入"崩溃"
  状态持久化：跨章节保持心理状态，影响后续行为
  用于：角色弧光的一致性保障

使用：
  python character-hfsman.py add-state --project my-novel --char 萧辰 --state calm --sub-states angry,collapsed,awakened
  python character-hfsman.py fire --project my-novel --char 萧辰 --event attacked --chapter 3
  python character-hfsman.py status --project my-novel --char 萧辰
  python character-hfsman.py history --project my-novel --char 萧辰 --limit 10
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class HFSMStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class HFSMTransition:
    """状态转换规则"""
    from_state: str
    event: str
    to_state: str
    guard: Optional[str] = None  # 条件表达式（简化：key=value）
    action: Optional[str] = None  # 转换时执行的动作

    def to_dict(self) -> Dict:
        return {
            "from_state": self.from_state,
            "event": self.event,
            "to_state": self.to_state,
            "guard": self.guard,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'HFSMTransition':
        return cls(**data)


@dataclass
class CharacterHFSM:
    """角色心理状态机"""
    char_name: str
    current_state: str
    sub_states: List[str] = field(default_factory=list)  # 子状态列表
    transitions: Dict[str, List[HFSMTransition]] = field(default_factory=dict)  # event → [transitions]
    history: List[Dict] = field(default_factory=list)  # 状态变化历史
    context: Dict[str, Any] = field(default_factory=dict)  # 运行时上下文
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "char_name": self.char_name,
            "current_state": self.current_state,
            "sub_states": self.sub_states,
            "transitions": {k: [t.to_dict() for t in v] for k, v in self.transitions.items()},
            "history": self.history[-100:],  # 保留最近100条
            "context": self.context,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CharacterHFSM':
        transitions = {}
        for k, v in data.get("transitions", {}).items():
            transitions[k] = [HFSMTransition.from_dict(t) for t in v]
        return cls(
            char_name=data["char_name"],
            current_state=data["current_state"],
            sub_states=data.get("sub_states", []),
            transitions=transitions,
            history=data.get("history", []),
            context=data.get("context", {}),
            created_at=data.get("created_at", ""),
        )


class CharacterHFSMManager:
    """角色心理状态机管理器"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = Path(f"/var/minis/shared/novel-team/.hfsman/{project_id}.json")
        self.characters: Dict[str, CharacterHFSM] = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.characters = {k: CharacterHFSM.from_dict(v) for k, v in data.get("characters", {}).items()}

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)

    def create(self, char_name: str, initial_state: str = "calm",
               sub_states: List[str] = None) -> str:
        """创建角色状态机"""
        hfsman = CharacterHFSM(
            char_name=char_name,
            current_state=initial_state,
            sub_states=sub_states or [],
            created_at=datetime.now().isoformat(),
        )
        self.characters[char_name] = hfsman
        self._save()
        return char_name

    def add_transition(self, char_name: str, from_state: str, event: str,
                       to_state: str, guard: Optional[str] = None,
                       action: Optional[str] = None) -> bool:
        """添加状态转换规则"""
        hfsman = self.characters.get(char_name)
        if not hfsman:
            return False
        if event not in hfsman.transitions:
            hfsman.transitions[event] = []
        hfsman.transitions[event].append(HFSMTransition(
            from_state=from_state, event=event, to_state=to_state,
            guard=guard, action=action,
        ))
        self._save()
        return True

    def fire(self, char_name: str, event: str, chapter: int,
             context: Dict = None) -> Dict:
        """触发事件，执行状态转换"""
        hfsman = self.characters.get(char_name)
        if not hfsman:
            return {"status": "error", "error": f"角色 {char_name} 不存在"}

        # 查找匹配的转换规则
        matching = []
        for t in hfsman.transitions.get(event, []):
            if t.from_state == hfsman.current_state:
                # 检查guard条件
                if t.guard:
                    if not self._evaluate_guard(t.guard, context or {}):
                        continue
                matching.append(t)

        if not matching:
            # 无匹配转换，记录未处理事件
            hfsman.history.append({
                "chapter": chapter,
                "time": datetime.now().isoformat(),
                "event": event,
                "from_state": hfsman.current_state,
                "action": "no_transition",
                "note": f"无匹配转换规则（当前状态={hfsman.current_state}，事件={event}）",
            })
            self._save()
            return {"status": "no_transition", "current_state": hfsman.current_state, "event": event}

        # 执行最高优先级的转换（取最后一条匹配）
        transition = matching[-1]
        old_state = hfsman.current_state
        hfsman.current_state = transition.to_state

        # 记录历史
        hfsman.history.append({
            "chapter": chapter,
            "time": datetime.now().isoformat(),
            "event": event,
            "from_state": old_state,
            "to_state": transition.to_state,
            "action": transition.action or "state_change",
        })

        # 更新上下文
        if context:
            hfsman.context.update(context)

        self._save()
        return {
            "status": "ok",
            "char_name": char_name,
            "from_state": old_state,
            "to_state": transition.to_state,
            "event": event,
            "chapter": chapter,
        }

    def _evaluate_guard(self, guard: str, context: Dict) -> bool:
        """评估guard条件（简化版：key=value 格式）"""
        if "=" not in guard:
            return guard in context
        key, val = guard.split("=", 1)
        return str(context.get(key, "")) == val.strip('"').strip("'")

    def get_status(self, char_name: str) -> Dict:
        """获取角色当前状态"""
        hfsman = self.characters.get(char_name)
        if not hfsman:
            return {"error": f"角色 {char_name} 不存在"}
        return {
            "char_name": char_name,
            "current_state": hfsman.current_state,
            "sub_states": hfsman.sub_states,
            "context": hfsman.context,
            "history_count": len(hfsman.history),
        }

    def get_history(self, char_name: str, limit: int = 10) -> List[Dict]:
        """获取状态变化历史"""
        hfsman = self.characters.get(char_name)
        if not hfsman:
            return []
        return hfsman.history[-limit:]

    def get_summary(self) -> Dict:
        """获取总体摘要"""
        return {
            "total_characters": len(self.characters),
            "characters": [{
                "name": c.char_name,
                "state": c.current_state,
                "history_count": len(c.history),
            } for c in self.characters.values()],
        }


def cmd_create(args):
    mgr = CharacterHFSMManager(args.project)
    mgr.create(args.char, args.initial or "calm", args.subs.split(",") if args.subs else None)
    print(f"✅ 已创建角色状态机: {args.char}（初始状态: {args.initial or 'calm'}）")
    return 0


def cmd_transition(args):
    mgr = CharacterHFSMManager(args.project)
    ok = mgr.add_transition(args.char, args.from_state, args.event, args.to_state,
                            args.guard, args.action)
    print(f"{'✅' if ok else '❌'} 转换规则 {'已添加' if ok else '失败'}: {args.from_state} --[{args.event}]--> {args.to_state}")
    return 0 if ok else 1


def cmd_fire(args):
    mgr = CharacterHFSMManager(args.project)
    ctx = json.loads(args.context) if args.context else None
    result = mgr.fire(args.char, args.event, int(args.chapter), ctx)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args):
    mgr = CharacterHFSMManager(args.project)
    print(json.dumps(mgr.get_status(args.char), ensure_ascii=False, indent=2))
    return 0


def cmd_history(args):
    mgr = CharacterHFSMManager(args.project)
    history = mgr.get_history(args.char, int(args.limit or 10))
    print(json.dumps(history, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args):
    mgr = CharacterHFSMManager(args.project)
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="角色心理状态机（借鉴AbilityKit HFSM）")
    parser.add_argument("--project", "-p", required=True)
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="创建角色状态机")
    p_create.add_argument("--char", "-c", required=True)
    p_create.add_argument("--initial", help="初始状态（默认calm）")
    p_create.add_argument("--subs", help="子状态列表（逗号分隔）")

    p_trans = sub.add_parser("transition", help="添加状态转换规则")
    p_trans.add_argument("--char", required=True)
    p_trans.add_argument("--from-state", required=True)
    p_trans.add_argument("--event", required=True)
    p_trans.add_argument("--to-state", required=True)
    p_trans.add_argument("--guard", help="条件表达式（key=value）")
    p_trans.add_argument("--action", help="转换时动作")

    p_fire = sub.add_parser("fire", help="触发事件")
    p_fire.add_argument("--char", required=True)
    p_fire.add_argument("--event", required=True)
    p_fire.add_argument("--chapter", "-c", required=True, type=int)
    p_fire.add_argument("--context", help="上下文JSON")

    p_status = sub.add_parser("status", help="查看状态")
    p_status.add_argument("--char", required=True)

    p_hist = sub.add_parser("history", help="查看历史")
    p_hist.add_argument("--char", required=True)
    p_hist.add_argument("--limit", default="10")

    p_sum = sub.add_parser("summary", help="总体摘要")

    args = parser.parse_args()
    cmd_map = {"create": cmd_create, "transition": cmd_transition, "fire": cmd_fire,
               "status": cmd_status, "history": cmd_history, "summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
