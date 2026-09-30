#!/usr/bin/env python3
"""
continuous-state.py — 持续状态系统（借鉴 AbilityKit Continuous 模块）

核心设计：
  条件驱动的激活/阻止/暂停/恢复/移除
  Tag 规则控制：特定 GameplayTag 存在时激活，不存在时阻止
  保留 explain 结果：每轮 Tick 记录为什么继续/停止

小说适配：
  持续性剧情状态："追杀中"、"逃亡中"、"热恋中"——跨章节持续
  激活条件：某个事件发生后进入该状态
  终止条件：完成某个目标或触发某个事件
  暂停/恢复：暂时中断追杀但后续恢复

使用：
  python continuous-state.py add --project my-novel --name 追杀中 --tags 追杀,威胁 --activate-chapter 5 --trigger "萧辰发现父亲遗言"
  python continuous-state.py tick --project my-novel --chapter 6
  python continuous-state.py list --project my-novel
  python continuous-state.py resolve --project my-novel --name 追杀中 --reason "萧辰逃脱"
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ContinuousStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    RESOLVED = "resolved"


@dataclass
class ContinuousState:
    """持续状态"""
    id: str
    name: str
    tags: List[str]
    status: ContinuousStatus
    activate_chapter: int
    trigger_event: str  # 激活触发事件描述
    expire_chapter: Optional[int] = None  # 到期章节（None=永久）
    pause_reason: Optional[str] = None  # 暂停原因
    resolve_reason: Optional[str] = None  # 解决原因
    tick_log: List[Dict] = field(default_factory=list)  # 每轮Tick记录
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "tags": self.tags,
            "status": self.status.value,
            "activate_chapter": self.activate_chapter,
            "trigger_event": self.trigger_event,
            "expire_chapter": self.expire_chapter,
            "pause_reason": self.pause_reason,
            "resolve_reason": self.resolve_reason,
            "tick_log": self.tick_log,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ContinuousState':
        data["status"] = ContinuousStatus(data["status"])
        return cls(**data)


class ContinuousStateManager:
    """持续状态管理器"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = Path(f"/var/minis/shared/novel-team/.continuous/{project_id}.json")
        self.states: Dict[str, ContinuousState] = {}
        self._counter = 0
        self._load()

    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.states = {k: ContinuousState.from_dict(v) for k, v in data.get("states", {}).items()}
            self._counter = data.get("counter", 0)

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "states": {k: v.to_dict() for k, v in self.states.items()},
            "counter": self._counter,
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)

    def add(self, name: str, tags: List[str], activate_chapter: int,
            trigger_event: str, expire_chapter: Optional[int] = None) -> str:
        """添加持续状态"""
        self._counter += 1
        state_id = f"C{self._counter:04d}"
        state = ContinuousState(
            id=state_id,
            name=name,
            tags=tags,
            status=ContinuousStatus.ACTIVE,
            activate_chapter=activate_chapter,
            trigger_event=trigger_event,
            expire_chapter=expire_chapter,
            created_at=datetime.now().isoformat(),
        )
        self.states[state_id] = state
        self._save()
        return state_id

    def tick(self, current_chapter: int) -> List[Dict]:
        """执行一轮Tick，检查所有持续状态"""
        results = []
        for sid, state in self.states.items():
            if state.status not in (ContinuousStatus.ACTIVE, ContinuousStatus.PAUSED):
                continue

            # 检查是否到期
            if state.expire_chapter and current_chapter >= state.expire_chapter:
                state.status = ContinuousStatus.RESOLVED
                state.resolve_reason = f"到期（第{state.expire_chapter}章）"
                results.append({"id": sid, "action": "expired", "reason": state.resolve_reason})
                continue

            # 检查暂停状态
            if state.status == ContinuousStatus.PAUSED:
                results.append({"id": sid, "action": "paused", "reason": state.pause_reason})
                continue

            # 主动状态：记录Tick
            state.tick_log.append({
                "chapter": current_chapter,
                "time": datetime.now().isoformat(),
                "status": "active",
                "note": f"第{current_chapter}章持续中",
            })
            results.append({"id": sid, "action": "ticked", "chapter": current_chapter})

        self._save()
        return results

    def pause(self, state_id: str, reason: str) -> bool:
        """暂停持续状态"""
        state = self.states.get(state_id)
        if not state or state.status != ContinuousStatus.ACTIVE:
            return False
        state.status = ContinuousStatus.PAUSED
        state.pause_reason = reason
        self._save()
        return True

    def resume(self, state_id: str) -> bool:
        """恢复持续状态"""
        state = self.states.get(state_id)
        if not state or state.status != ContinuousStatus.PAUSED:
            return False
        state.status = ContinuousStatus.ACTIVE
        state.pause_reason = None
        self._save()
        return True

    def resolve(self, state_id: str, reason: str) -> bool:
        """解决持续状态"""
        state = self.states.get(state_id)
        if not state:
            return False
        state.status = ContinuousStatus.RESOLVED
        state.resolve_reason = reason
        self._save()
        return True

    def list_states(self, status: Optional[str] = None) -> List[Dict]:
        """列出持续状态"""
        result = []
        for sid, state in self.states.items():
            if status and state.status.value != status:
                continue
            result.append({
                "id": sid,
                "name": state.name,
                "status": state.status.value,
                "tags": state.tags,
                "activate_chapter": state.activate_chapter,
                "expire_chapter": state.expire_chapter,
                "tick_count": len(state.tick_log),
            })
        return result

    def get_tag_states(self, tag: str) -> List[str]:
        """按标签查询"""
        return [sid for sid, s in self.states.items() if tag in s.tags and s.status == ContinuousStatus.ACTIVE]

    def get_summary(self) -> Dict:
        """获取摘要"""
        active = len([s for s in self.states.values() if s.status == ContinuousStatus.ACTIVE])
        paused = len([s for s in self.states.values() if s.status == ContinuousStatus.PAUSED])
        resolved = len([s for s in self.states.values() if s.status == ContinuousStatus.RESOLVED])
        return {
            "total": len(self.states),
            "active": active,
            "paused": paused,
            "resolved": resolved,
            "all_tags": list(set(t for s in self.states.values() for t in s.tags)),
        }


def cmd_add(args):
    mgr = ContinuousStateManager(args.project)
    state_id = mgr.add(
        name=args.name,
        tags=args.tags.split(",") if args.tags else [],
        activate_chapter=int(args.chapter),
        trigger_event=args.trigger or "",
        expire_chapter=int(args.expire) if args.expire else None,
    )
    print(json.dumps({"state_id": state_id, "name": args.name, "chapter": int(args.chapter)},
                      ensure_ascii=False, indent=2))
    return 0


def cmd_tick(args):
    mgr = ContinuousStateManager(args.project)
    results = mgr.tick(int(args.chapter))
    print(json.dumps({"chapter": int(args.chapter), "results": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args):
    mgr = ContinuousStateManager(args.project)
    states = mgr.list_states(args.status)
    print(json.dumps({"count": len(states), "states": states}, ensure_ascii=False, indent=2))
    return 0


def cmd_pause(args):
    mgr = ContinuousStateManager(args.project)
    ok = mgr.pause(args.state_id, args.reason or "用户暂停")
    print(f"{'✅' if ok else '❌'} 状态 {'已暂停' if ok else '不存在或无法暂停'}: {args.state_id}")
    return 0 if ok else 1


def cmd_resume(args):
    mgr = ContinuousStateManager(args.project)
    ok = mgr.resume(args.state_id)
    print(f"{'✅' if ok else '❌'} 状态 {'已恢复' if ok else '不存在或无法恢复'}: {args.state_id}")
    return 0 if ok else 1


def cmd_resolve(args):
    mgr = ContinuousStateManager(args.project)
    ok = mgr.resolve(args.state_id, args.reason or "用户解决")
    print(f"{'✅' if ok else '❌'} 状态 {'已解决' if ok else '不存在'}: {args.state_id}")
    return 0 if ok else 1


def cmd_tags(args):
    mgr = ContinuousStateManager(args.project)
    states = mgr.get_tag_states(args.tag)
    print(json.dumps({"tag": args.tag, "active_states": states}, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args):
    mgr = ContinuousStateManager(args.project)
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="持续状态系统（借鉴AbilityKit Continuous）")
    parser.add_argument("--project", "-p", required=True)
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="添加持续状态")
    p_add.add_argument("--name", "-n", required=True)
    p_add.add_argument("--tags", help="标签（逗号分隔）")
    p_add.add_argument("--chapter", "-c", required=True, type=int)
    p_add.add_argument("--trigger", help="激活触发事件描述")
    p_add.add_argument("--expire", help="到期章节号")

    p_tick = sub.add_parser("tick", help="执行一轮Tick")
    p_tick.add_argument("--chapter", "-c", required=True, type=int)

    p_list = sub.add_parser("list", help="列出状态")
    p_list.add_argument("--status", help="按状态过滤（active/paused/resolved）")

    p_pause = sub.add_parser("pause", help="暂停状态")
    p_pause.add_argument("--state-id", required=True)
    p_pause.add_argument("--reason", default="用户暂停")

    p_resume = sub.add_parser("resume", help="恢复状态")
    p_resume.add_argument("--state-id", required=True)

    p_resolve = sub.add_parser("resolve", help="解决状态")
    p_resolve.add_argument("--state-id", required=True)
    p_resolve.add_argument("--reason", default="用户解决")

    p_tags = sub.add_parser("tags", help="按标签查询")
    p_tags.add_argument("--tag", required=True)

    p_sum = sub.add_parser("summary", help="总体摘要")

    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "tick": cmd_tick, "list": cmd_list,
               "pause": cmd_pause, "resume": cmd_resume, "resolve": cmd_resolve,
               "tags": cmd_tags, "summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
