#!/usr/bin/env python3
"""
narrative-flow.py — 多线叙事流程（借鉴 AbilityKit Flow 模块）

核心设计：
  IFlowNode 节点树：Sequence / Race / Parallel / If / Timeout / Await
  WAKE/PUMP 事件驱动：节点等待外部信号再继续
  FlowContext：作用域内数据传递

小说适配：
  多线叙事：主角线 / 配角线 / 反派线 并行推进
  汇聚点：多条线在某章节交汇
  异步等待：等待某个支线完成后再推进主线
  超时处理：某条线长时间无进展→自动收束

使用：
  python narrative-flow.py add --project my-novel --node hero_line --type parallel --lines hero,side,villain
  python narrative-flow.py advance --project my-novel --node hero_line --line hero --chapter 5
  python narrative-flow.py check --project my-novel --node hero_line
  python narrative-flow.py graph --project my-novel
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve
from collections import defaultdict


class FlowNodeType(Enum):
    SEQUENCE = "sequence"   # 顺序执行
    PARALLEL = "parallel"   # 并行执行
    RACE = "race"           # 竞速（谁先完成谁赢）
    IF = "if"               # 条件分支
    TIMEOUT = "timeout"     # 超时收束
    AWAIT = "await"         # 等待外部信号


@dataclass
class FlowNode:
    """流程节点"""
    id: str
    name: str
    ntype: FlowNodeType
    lines: List[str] = field(default_factory=list)  # 参与并行/竞线的角色线
    timeout_chapters: int = 0  # 超时章节数（0=无限）
    condition: Optional[str] = None  # If条件
    completed_lines: Dict[str, int] = field(default_factory=dict)  # 已完成章节: {line: chapter}
    status: str = "pending"  # pending/running/completed/timeout
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "ntype": self.ntype.value,
            "lines": self.lines,
            "timeout_chapters": self.timeout_chapters,
            "condition": self.condition,
            "completed_lines": self.completed_lines,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'FlowNode':
        data["ntype"] = FlowNodeType(data["ntype"])
        return cls(**data)


class NarrativeFlowManager:
    """多线叙事流程管理器"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = resolve(project_id).flow() / f"{project_id}.json"
        self.nodes: Dict[str, FlowNode] = {}
        self._counter = 0
        self._load()

    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.nodes = {k: FlowNode.from_dict(v) for k, v in data.get("nodes", {}).items()}

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)

    def add(self, name: str, ntype: str, lines: List[str],
            timeout: int = 0, condition: Optional[str] = None) -> str:
        """添加流程节点"""
        self._counter += 1
        node_id = f"FN{self._counter:04d}"
        node = FlowNode(
            id=node_id,
            name=name,
            ntype=FlowNodeType(ntype),
            lines=lines,
            timeout_chapters=timeout,
            condition=condition,
            created_at=datetime.now().isoformat(),
        )
        self.nodes[node_id] = node
        self._save()
        return node_id

    def advance(self, node_id: str, line: str, chapter: int) -> Dict:
        """推进某条线的进度"""
        node = self.nodes.get(node_id)
        if not node:
            return {"status": "error", "error": f"节点 {node_id} 不存在"}

        if node.status == "completed":
            return {"status": "already_completed", "node_id": node_id}

        node.status = "running"
        node.completed_lines[line] = chapter
        self._save()

        # 检查是否完成
        if node.ntype in (FlowNodeType.PARALLEL, FlowNodeType.SEQUENCE):
            if all(l in node.completed_lines for l in node.lines):
                node.status = "completed"
        elif node.ntype == FlowNodeType.RACE:
            # 竞速：第一个完成的线获胜
            if len(node.completed_lines) >= 1:
                winner = min(node.completed_lines.items(), key=lambda x: x[1])
                node.status = "completed"
                return {
                    "status": "race_completed",
                    "node_id": node_id,
                    "winner": winner[0],
                    "winning_chapter": winner[1],
                }

        # 检查超时
        if node.timeout_chapters > 0 and node.lines:
            latest_ch = max(node.completed_lines.values()) if node.completed_lines else 0
            if latest_ch > 0 and len(node.lines) - len(node.completed_lines) > 0:
                remaining = len(node.lines) - len(node.completed_lines)
                if remaining * 1 >= node.timeout_chapters:  # 简化：每条线超时=timeout_chapters
                    node.status = "timeout"
                    return {"status": "timeout", "node_id": node_id}

        self._save()
        return {
            "status": "advanced",
            "node_id": node_id,
            "line": line,
            "chapter": chapter,
            "progress": f"{len(node.completed_lines)}/{len(node.lines)}",
        }

    def check(self, node_id: str) -> Dict:
        """检查节点状态"""
        node = self.nodes.get(node_id)
        if not node:
            return {"error": f"节点 {node_id} 不存在"}
        return {
            "id": node.id,
            "name": node.name,
            "type": node.ntype.value,
            "status": node.status,
            "lines": node.lines,
            "completed": node.completed_lines,
            "progress": f"{len(node.completed_lines)}/{len(node.lines)}",
        }

    def get_graph(self) -> List[Dict]:
        """生成流程图"""
        return [n.to_dict() for n in self.nodes.values()]

    def get_summary(self) -> Dict:
        """总体摘要"""
        status_counts = defaultdict(int)
        for n in self.nodes.values():
            status_counts[n.status] += 1
        return {
            "total_nodes": len(self.nodes),
            "status_dist": dict(status_counts),
            "nodes": [{
                "id": n.id,
                "name": n.name,
                "type": n.ntype.value,
                "status": n.status,
                "progress": f"{len(n.completed_lines)}/{len(n.lines)}",
            } for n in self.nodes.values()],
        }


def cmd_add(args):
    mgr = NarrativeFlowManager(args.project)
    node_id = mgr.add(
        name=args.name,
        ntype=args.type,
        lines=args.lines.split(","),
        timeout=int(args.timeout or 0),
        condition=args.condition,
    )
    print(json.dumps({"node_id": node_id, "name": args.name, "type": args.type,
                       "lines": args.lines.split(",")}, ensure_ascii=False, indent=2))
    return 0


def cmd_advance(args):
    mgr = NarrativeFlowManager(args.project)
    result = mgr.advance(args.node_id, args.line, int(args.chapter))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_check(args):
    mgr = NarrativeFlowManager(args.project)
    print(json.dumps(mgr.check(args.node_id), ensure_ascii=False, indent=2))
    return 0


def cmd_graph(args):
    mgr = NarrativeFlowManager(args.project)
    print(json.dumps(mgr.get_graph(), ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args):
    mgr = NarrativeFlowManager(args.project)
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多线叙事流程（借鉴AbilityKit Flow）")
    parser.add_argument("--project", "-p", required=True)
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="添加流程节点")
    p_add.add_argument("--name", "-n", required=True)
    p_add.add_argument("--type", "-t", required=True,
                        choices=["sequence", "parallel", "race", "if", "timeout", "await"])
    p_add.add_argument("--lines", "-l", required=True, help="角色线（逗号分隔）")
    p_add.add_argument("--timeout", help="超时章节数")
    p_add.add_argument("--condition", help="条件表达式（If类型用）")

    p_adv = sub.add_parser("advance", help="推进进度")
    p_adv.add_argument("--node-id", required=True)
    p_adv.add_argument("--line", required=True)
    p_adv.add_argument("--chapter", "-c", required=True, type=int)

    p_chk = sub.add_parser("check", help="检查状态")
    p_chk.add_argument("--node-id", required=True)

    p_graph = sub.add_parser("graph", help="流程图")
    p_sum = sub.add_parser("summary", help="总体摘要")

    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "advance": cmd_advance, "check": cmd_check,
               "graph": cmd_graph, "summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
