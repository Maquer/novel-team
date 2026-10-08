#!/usr/bin/env python3
"""
plot-explain.py — 剧情解释器（借鉴 AbilityKit Ability.Explain 模块）

核心设计：
  森林树+导航协议：将复杂执行链路可视化
  用于调试：某效果为什么生效/没生效

小说适配：
  剧情逻辑可解释：某章为什么这样写？追溯到大纲→触发器→Phase 执行路径
  用于审稿：快速定位逻辑断层
  输出：可读的决策树/执行路径报告

使用：
  python plot-explain.py explain --project my-novel --chapter 5 --reason "萧辰为何突然觉醒"
  python plot-explain.py chain --project my-novel --node E0002 --depth 3
  python plot-explain.py report --project my-novel --chapter 5
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExplainNode:
    """解释节点"""
    id: str
    chapter: int
    event: str
    cause_chain: List[str] = field(default_factory=list)  # 原因链节点ID
    effect_chain: List[str] = field(default_factory=list)  # 结果链节点ID
    explanation: str = ""  # 解释文本
    confidence: float = 1.0
    source: str = ""  # 来源：outline/trigger/trace/fact

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "chapter": self.chapter,
            "event": self.event,
            "cause_chain": self.cause_chain,
            "effect_chain": self.effect_chain,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ExplainNode':
        return cls(**data)


class PlotExplainManager:
    """剧情解释器管理器"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = Path(f"/var/minis/shared/novel-team/.explain/{project_id}.json")
        self.nodes: Dict[str, ExplainNode] = {}
        self._counter = 0
        self._load()

    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.nodes = {k: ExplainNode.from_dict(v) for k, v in data.get("nodes", {}).items()}

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)

    def add_node(self, chapter: int, event: str, explanation: str,
                 cause_chain: List[str] = None, source: str = "manual") -> str:
        """添加解释节点"""
        self._counter += 1
        node_id = f"EX{self._counter:04d}"
        node = ExplainNode(
            id=node_id,
            chapter=chapter,
            event=event,
            cause_chain=cause_chain or [],
            explanation=explanation,
            source=source,
        )
        self.nodes[node_id] = node
        self._save()
        return node_id

    def link_cause(self, node_id: str, cause_id: str):
        """链接因果"""
        node = self.nodes.get(node_id)
        cause = self.nodes.get(cause_id)
        if node and cause:
            if cause_id not in node.cause_chain:
                node.cause_chain.append(cause_id)
            if node_id not in cause.effect_chain:
                cause.effect_chain.append(node_id)
            self._save()

    def explain(self, chapter: int, keyword: str = "") -> List[Dict]:
        """生成某章节的解释报告"""
        ch_nodes = [n for n in self.nodes.values() if n.chapter == chapter]
        if keyword:
            ch_nodes = [n for n in ch_nodes if keyword in n.event or keyword in n.explanation]

        results = []
        for node in ch_nodes:
            results.append({
                "id": node.id,
                "chapter": node.chapter,
                "event": node.event,
                "explanation": node.explanation[:200],
                "cause_chain": node.cause_chain,
                "effect_chain": node.effect_chain,
                "confidence": node.confidence,
                "source": node.source,
            })
        return results

    def chain(self, node_id: str, depth: int = 3) -> List[Dict]:
        """追溯因果链"""
        if node_id not in self.nodes:
            return [{"error": f"节点 {node_id} 不存在"}]

        result = []
        visited = {node_id}
        queue = [(node_id, 0)]

        while queue and len(result) < depth * 5:
            current_id, d = queue.pop(0)
            node = self.nodes[current_id]
            result.append({
                "id": current_id,
                "chapter": node.chapter,
                "event": node.event,
                "explanation": node.explanation[:100],
                "depth": d,
                "direction": "root" if d == 0 else ("cause" if current_id in self.nodes[node_id].cause_chain else "effect"),
            })

            # 向原因和结果双向追溯
            if d < depth:
                for cid in node.cause_chain:
                    if cid not in visited:
                        visited.add(cid)
                        queue.append((cid, d + 1))
                for eid in node.effect_chain:
                    if eid not in visited:
                        visited.add(eid)
                        queue.append((eid, d + 1))

        return result

    def report(self, chapter: int) -> Dict:
        """生成章节报告"""
        nodes = [n for n in self.nodes.values() if n.chapter == chapter]
        if not nodes:
            return {"chapter": chapter, "message": "该章节暂无解释节点"}

        # 统计
        by_source = {}
        total_confidence = 0.0
        for n in nodes:
            by_source[n.source] = by_source.get(n.source, 0) + 1
            total_confidence += n.confidence

        return {
            "chapter": chapter,
            "node_count": len(nodes),
            "by_source": by_source,
            "avg_confidence": total_confidence / len(nodes) if nodes else 0,
            "nodes": [n.to_dict() for n in nodes],
        }

    def get_summary(self) -> Dict:
        """总体摘要"""
        return {
            "total_nodes": len(self.nodes),
            "chapters_covered": len(set(n.chapter for n in self.nodes.values())),
            "by_source": dict(defaultdict(int, {
                s: sum(1 for n in self.nodes.values() if n.source == s)
                for s in set(n.source for n in self.nodes.values())
            })),
        }


from collections import defaultdict


def cmd_add(args):
    mgr = PlotExplainManager(args.project)
    node_id = mgr.add_node(
        chapter=int(args.chapter),
        event=args.event,
        explanation=args.explanation or "",
        cause_chain=args.cause.split(",") if args.cause else None,
        source=args.source or "manual",
    )
    print(json.dumps({"node_id": node_id, "chapter": int(args.chapter), "event": args.event},
                      ensure_ascii=False, indent=2))
    return 0


def cmd_link(args):
    mgr = PlotExplainManager(args.project)
    mgr.link_cause(args.node_id, args.cause_id)
    print(f"✅ 因果链接: {args.node_id} ← {args.cause_id}")
    return 0


def cmd_explain(args):
    mgr = PlotExplainManager(args.project)
    results = mgr.explain(int(args.chapter), args.keyword or "")
    print(json.dumps({"chapter": int(args.chapter), "keyword": args.keyword,
                       "count": len(results), "nodes": results}, ensure_ascii=False, indent=2))
    return 0


def cmd_chain(args):
    mgr = PlotExplainManager(args.project)
    result = mgr.chain(args.node_id, int(args.depth or 3))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_report(args):
    mgr = PlotExplainManager(args.project)
    print(json.dumps(mgr.report(int(args.chapter)), ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args):
    mgr = PlotExplainManager(args.project)
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="剧情解释器（借鉴AbilityKit Ability.Explain）")
    parser.add_argument("--project", "-p", required=True)
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="添加解释节点")
    p_add.add_argument("--chapter", "-c", required=True, type=int)
    p_add.add_argument("--event", "-e", required=True)
    p_add.add_argument("--explanation", help="解释文本")
    p_add.add_argument("--cause", help="原因节点ID（逗号分隔）")
    p_add.add_argument("--source", default="manual", help="来源（outline/trigger/trace/fact/manual）")

    p_link = sub.add_parser("link", help="链接因果")
    p_link.add_argument("--node-id", required=True)
    p_link.add_argument("--cause-id", required=True)

    p_exp = sub.add_parser("explain", help="章节解释查询")
    p_exp.add_argument("--chapter", "-c", required=True, type=int)
    p_exp.add_argument("--keyword", help="关键词过滤")

    p_chain = sub.add_parser("chain", help="因果链追溯")
    p_chain.add_argument("--node-id", required=True)
    p_chain.add_argument("--depth", default="3")

    p_rep = sub.add_parser("report", help="章节报告")
    p_rep.add_argument("--chapter", "-c", required=True, type=int)

    p_sum = sub.add_parser("summary", help="总体摘要")

    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "link": cmd_link, "explain": cmd_explain,
               "chain": cmd_chain, "report": cmd_report, "summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
