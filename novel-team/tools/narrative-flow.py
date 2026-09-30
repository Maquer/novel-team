# Version: 2.1.0
#!/usr/bin/env python3
"""
narrative-flow.py — 多线叙事流程（借鉴 AbilityKit Flow 模块）v2.0

核心设计：
  IFlowNode 节点树：Sequence / Race / Parallel / If / Timeout / Await
  WAKE/PUMP 事件驱动：节点等待外部信号再继续
  FlowContext：作用域内数据传递

小说适配：
  多线叙事：主角线 / 配角线 / 反派线 并行推进
  汇聚点：多条线在某章节交汇 → 自动校验一致性
  异步等待：等待某个支线完成后再推进主线
  超时处理：某条线长时间无进展→自动收束

v2.0 新增：
  - 汇聚点自动检测（convergence detection）
  - 跨线信息不对称检查（information-asymmetry）
  - 叙事线程间隙告警（thread-gap warning）
  - 总编视角输出（orchestrator-report）

使用：
  python narrative-flow.py add --project my-novel --name "三线并行" --type parallel --lines hero,side,villain
  python narrative-flow.py advance --project my-novel --node FN0001 --line hero --chapter 5
  python narrative-flow.py converge-check --project my-novel --node FN0001 --chapter 10
  python narrative-flow.py thread-gap --project my-novel --node FN0001 --threshold 3
  python narrative-flow.py report --project my-novel
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
    convergence_chapters: List[int] = field(default_factory=list)  # 已标记的汇聚章节
    status: str = "pending"  # pending/running/completed/timeout/gap_warning
    info_asymmetry: List[Dict] = field(default_factory=list)  # 信息不对称记录
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
            "convergence_chapters": self.convergence_chapters,
            "info_asymmetry": self.info_asymmetry,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'FlowNode':
        data["ntype"] = FlowNodeType(data["ntype"])
        return cls(**data)


class NarrativeFlowManager:
    """多线叙事流程管理器 v2.0"""

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
                if remaining * 1 >= node.timeout_chapters:
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

    def mark_convergence(self, node_id: str, chapter: int) -> Dict:
        """标记汇聚点（多条线在同一章交汇）"""
        node = self.nodes.get(node_id)
        if not node:
            return {"status": "error", "error": f"节点 {node_id} 不存在"}

        if chapter in node.convergence_chapters:
            return {"status": "already_marked", "node_id": node_id, "chapter": chapter}

        node.convergence_chapters.append(chapter)
        node.convergence_chapters.sort()
        self._save()

        # 检查汇聚时的信息不对称
        asymmetry = self._check_info_asymmetry(node, chapter)

        return {
            "status": "convergence_marked",
            "node_id": node_id,
            "chapter": chapter,
            "asymmetry": asymmetry,
        }

    def _check_info_asymmetry(self, node: FlowNode, chapter: int) -> List[Dict]:
        """检查汇聚时的信息不对称

        规则：如果某条线的最新进展章 < 汇聚章，则该线角色在汇聚时
        无法获得其他线角色的信息（除非有合理的传递路径）
        """
        issues = []
        max_ch = max(node.completed_lines.values()) if node.completed_lines else 0

        for line, ch in node.completed_lines.items():
            if ch < chapter:
                # 这条线的进展落后于汇聚章
                # 需要检查是否有合理的"信息传递"解释
                lag = chapter - ch
                issues.append({
                    "line": line,
                    "latest_chapter": ch,
                    "convergence_chapter": chapter,
                    "lag": lag,
                    "risk": "information_gap",
                    "suggestion": f"考虑在第{ch+1}章到第{chapter}章之间增加信息传递桥段",
                })

        return issues

    def check_thread_gaps(self, node_id: str, threshold: int = 3) -> Dict:
        """检查叙事线程间隙（某条线太久没有进展）

        threshold: 连续无进展章节数超过此值则触发警告
        """
        node = self.nodes.get(node_id)
        if not node:
            return {"status": "error", "error": f"节点 {node_id} 不存在"}

        if not node.completed_lines:
            return {"status": "no_progress", "node_id": node_id}

        # 找到最新的章节号
        max_ch = max(node.completed_lines.values())

        # 对每条线，检查是否有间隙
        gaps = []
        for line in node.lines:
            if line not in node.completed_lines:
                # 这条线从未进展 → 严重警告
                gaps.append({
                    "line": line,
                    "status": "never_advanced",
                    "risk": "high",
                    "suggestion": f"角色 '{line}' 从未推进，考虑删除或合并到其他线",
                })
            else:
                last_ch = node.completed_lines[line]
                # 假设总章节 = max_ch，检查是否有超过 threshold 的空档
                # 这里简化处理：如果最后进展距离最大章节超过 threshold，警告
                if max_ch - last_ch >= threshold:
                    gaps.append({
                        "line": line,
                        "last_chapter": last_ch,
                        "gap_chapters": max_ch - last_ch,
                        "threshold": threshold,
                        "risk": "medium" if max_ch - last_ch < threshold * 2 else "high",
                        "suggestion": f"角色 '{line}' 从第{last_ch}章后无进展，已间隔{max_ch - last_ch}章",
                    })

        # 更新节点状态
        if gaps:
            node.status = "gap_warning"
        else:
            # 没有间隙，恢复原状态
            if node.ntype in (FlowNodeType.PARALLEL, FlowNodeType.SEQUENCE):
                if all(l in node.completed_lines for l in node.lines):
                    node.status = "completed"
                else:
                    node.status = "running"
            elif node.ntype == FlowNodeType.RACE:
                if len(node.completed_lines) >= 1:
                    node.status = "completed"
                else:
                    node.status = "running"
            else:
                node.status = "running"

        self._save()
        return {
            "node_id": node_id,
            "max_chapter": max_ch,
            "gaps": gaps,
            "gap_count": len(gaps),
            "status": node.status,
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
            "convergence_chapters": node.convergence_chapters,
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
                "convergence_count": len(n.convergence_chapters),
            } for n in self.nodes.values()],
        }

    def orchestrator_report(self, node_id: Optional[str] = None) -> Dict:
        """总编视角报告：综合评估所有叙事线的协调性

        输出：
        - 汇聚点有效性（所有线都到场？）
        - 信息不对称风险
        - 线程间隙警告
        - 时序冲突检测
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "project_id": self.project_id,
            "nodes": [],
            "global_issues": [],
        }

        for nid, node in self.nodes.items():
            if node_id and nid != node_id:
                continue

            node_report = {
                "id": nid,
                "name": node.name,
                "type": node.ntype.value,
                "status": node.status,
                "progress": f"{len(node.completed_lines)}/{len(node.lines)}",
                "lines_status": {},
                "issues": [],
            }

            # 逐线状态
            for line in node.lines:
                ch = node.completed_lines.get(line, "NOT_ADVANCED")
                node_report["lines_status"][line] = ch

                # 检查线状态异常
                if ch == "NOT_ADVANCED":
                    node_report["issues"].append({
                        "type": "line_dormant",
                        "severity": "high",
                        "detail": f"线 '{line}' 从未推进",
                    })

            # 汇聚点检查
            for conv_ch in node.convergence_chapters:
                present_lines = [l for l, c in node.completed_lines.items() if c <= conv_ch]
                missing_lines = [l for l in node.lines if l not in present_lines]

                if missing_lines and node.ntype == FlowNodeType.PARALLEL:
                    node_report["issues"].append({
                        "type": "convergence_incomplete",
                        "severity": "medium",
                        "chapter": conv_ch,
                        "detail": f"汇聚章{conv_ch}时，以下线未到场: {missing_lines}",
                    })

                # 信息不对称
                for asym in node.info_asymmetry:
                    if asym.get("convergence_chapter") == conv_ch:
                        node_report["issues"].append({
                            "type": "info_asymmetry",
                            "severity": "low",
                            "chapter": conv_ch,
                            "line": asym["line"],
                            "detail": asym["suggestion"],
                        })

            # 线程间隙
            gap_result = self.check_thread_gaps(nid)
            if gap_result.get("gaps"):
                for g in gap_result["gaps"]:
                    node_report["issues"].append({
                        "type": "thread_gap",
                        "severity": g["risk"],
                        "line": g["line"],
                        "detail": g["suggestion"],
                    })

            report["nodes"].append(node_report)

            # 全局问题累积
            report["global_issues"].extend(node_report["issues"])

        # 排序：高风险在前
        report["global_issues"].sort(
            key=lambda x: {"high": 0, "medium": 1, "low": 2, "info": 3}.get(x.get("severity"), 9)
        )

        return report


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


def cmd_converge(args):
    """标记汇聚点"""
    mgr = NarrativeFlowManager(args.project)
    result = mgr.mark_convergence(args.node_id, int(args.chapter))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_gap(args):
    """检查线程间隙"""
    mgr = NarrativeFlowManager(args.project)
    threshold = int(args.threshold or 3)
    result = mgr.check_thread_gaps(args.node_id, threshold)
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


def cmd_report(args):
    """总编视角综合报告"""
    mgr = NarrativeFlowManager(args.project)
    node_id = args.node_id if hasattr(args, 'node_id') and args.node_id else None
    result = mgr.orchestrator_report(node_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多线叙事流程（借鉴AbilityKit Flow）v2.0")
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

    p_conv = sub.add_parser("converge", help="标记汇聚点（多条线交汇章）")
    p_conv.add_argument("--node-id", required=True)
    p_conv.add_argument("--chapter", "-c", required=True, type=int)

    p_gap = sub.add_parser("gap", help="检查线程间隙")
    p_gap.add_argument("--node-id", required=True)
    p_gap.add_argument("--threshold", default="3", help="触发警告的间隙章节数（默认3）")

    p_chk = sub.add_parser("check", help="检查状态")
    p_chk.add_argument("--node-id", required=True)

    p_graph = sub.add_parser("graph", help="流程图")
    p_sum = sub.add_parser("summary", help="总体摘要")
    p_rep = sub.add_parser("report", help="总编视角综合报告")
    p_rep.add_argument("--node-id", help="指定节点（可选，默认全部）")

    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "advance": cmd_advance, "converge": cmd_converge,
               "gap": cmd_gap, "check": cmd_check, "graph": cmd_graph,
               "summary": cmd_summary, "report": cmd_report}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
