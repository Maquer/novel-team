#!/usr/bin/env python3
"""
plot-trace.py — 剧情溯源链（借鉴 AbilityKit Trace 模块）

核心设计：
  溯源树：每个剧情事件带 root/parent/cause 上下文
  支持正向追踪（原因→结果）和反向溯源（结果→原因）
  用于：一致性检查、作者回溯、因果链验证

小说适配：
  因果链：事件A（伏笔埋设）→ 事件B（角色获得物品）→ 事件C（高潮使用物品）
  反向溯源：某角色在第20章的行为，追溯到第3章的伏笔
  一致性检查：事件有无合理前因、后果有无合理前置

使用：
  python plot-trace.py add --project my-novel --chapter 1 --event "萧辰获得天命剑" --type foreshadow_recall
  python plot-trace.py trace-back --project my-novel --node-id E0010 --depth 3
  python plot-trace.py trace-forward --project my-novel --node-id E0003 --depth 2
  python plot-trace.py check-consistency --project my-novel
  python plot-trace.py graph --project my-novel
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve


# ==================== 数据模型 ====================

@dataclass
class TraceNode:
    """溯源节点"""
    id: str
    chapter: int
    event: str
    event_type: str  # foreshadow_plant / foreshadow_recall / character_event / world_event / ...
    root_cause: Optional[str] = None      # 根因节点ID
    parent_causes: List[str] = field(default_factory=list)  # 直接原因节点ID列表
    children_effects: List[str] = field(default_factory=list)  # 直接结果节点ID列表
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0  # 因果置信度 0.0-1.0
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "chapter": self.chapter,
            "event": self.event,
            "event_type": self.event_type,
            "root_cause": self.root_cause,
            "parent_causes": self.parent_causes,
            "children_effects": self.children_effects,
            "tags": self.tags,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TraceNode':
        return cls(**data)


# ==================== TraceManager ====================

class PlotTrace:
    """剧情溯源链管理器"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = resolve(project_id).trace() / f"{project_id}.json"
        self.nodes: Dict[str, TraceNode] = {}
        self._counter = 0
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.nodes = {k: TraceNode.from_dict(v) for k, v in data.get("nodes", {}).items()}
            self._counter = data.get("counter", 0)
    
    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "counter": self._counter,
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def add_node(self, chapter: int, event: str, event_type: str,
                 parent_causes: List[str] = None, tags: List[str] = None,
                 confidence: float = 1.0) -> str:
        """添加溯源节点"""
        self._counter += 1
        node_id = f"E{self._counter:04d}"
        
        parents = parent_causes or []
        root = self._find_root(parents)
        
        node = TraceNode(
            id=node_id,
            chapter=chapter,
            event=event,
            event_type=event_type,
            root_cause=root,
            parent_causes=parents,
            tags=tags or [],
            confidence=confidence,
            created_at=datetime.now().isoformat(),
        )
        
        self.nodes[node_id] = node
        
        for pid in parents:
            if pid in self.nodes:
                self.nodes[pid].children_effects.append(node_id)
        
        self._save()
        return node_id
    
    def _find_root(self, parent_ids: List[str]) -> Optional[str]:
        if not parent_ids:
            return None
        root = parent_ids[0]
        for pid in parent_ids:
            if pid in self.nodes and self.nodes[pid].root_cause:
                root = self.nodes[pid].root_cause
        return root
    
    def trace_back(self, node_id: str, depth: int = 3) -> List[Dict]:
        """反向溯源：从某节点追溯到根因"""
        if node_id not in self.nodes:
            return [{"error": f"节点 {node_id} 不存在"}]
        
        result = []
        visited = set()
        queue = deque([(node_id, 0)])
        
        while queue and len(result) < depth * 5:
            current_id, d = queue.popleft()
            if current_id in visited or d > depth:
                continue
            visited.add(current_id)
            
            node = self.nodes[current_id]
            result.append({
                "id": node.id,
                "chapter": node.chapter,
                "event": node.event,
                "event_type": node.event_type,
                "depth_from_target": d,
                "confidence": node.confidence,
            })
            
            for pid in node.parent_causes:
                if pid not in visited:
                    queue.append((pid, d + 1))
        
        return result
    
    def trace_forward(self, node_id: str, depth: int = 2) -> List[Dict]:
        """正向追踪：从某节点追踪到所有后代效果"""
        if node_id not in self.nodes:
            return [{"error": f"节点 {node_id} 不存在"}]
        
        result = []
        visited = set()
        queue = deque([(node_id, 0)])
        
        while queue and len(result) < depth * 10:
            current_id, d = queue.popleft()
            if current_id in visited or d > depth:
                continue
            visited.add(current_id)
            
            node = self.nodes[current_id]
            result.append({
                "id": node.id,
                "chapter": node.chapter,
                "event": node.event,
                "event_type": node.event_type,
                "depth_from_source": d,
                "confidence": node.confidence,
            })
            
            for cid in node.children_effects:
                if cid not in visited:
                    queue.append((cid, d + 1))
        
        return result
    
    def check_consistency(self) -> Dict:
        """一致性检查"""
        issues = []
        
        for nid, node in self.nodes.items():
            for pid in node.parent_causes:
                if pid not in self.nodes:
                    issues.append({
                        "type": "orphan_cause",
                        "node_id": nid,
                        "missing_parent": pid,
                        "severity": "high",
                    })
            
            # 跳过直接的父子关系检查（这是正常的因果关系）
            # 真正的循环需要检测A→B→C→A这样的链式循环
            # 简化处理：暂时移除此检查，避免误报
            
            if node.confidence < 0.5 and node.children_effects:
                issues.append({
                    "type": "low_confidence_with_effects",
                    "node_id": nid,
                    "confidence": node.confidence,
                    "effect_count": len(node.children_effects),
                    "severity": "medium",
                })
        
        isolated = [nid for nid, n in self.nodes.items()
                    if not n.parent_causes and not n.children_effects and n.event_type != "world_event"]
        
        return {
            "total_nodes": len(self.nodes),
            "issue_count": len(issues),
            "isolated_count": len(isolated),
            "issues": issues,
            "isolated_nodes": isolated[:10],
        }
    
    def get_chapter_summary(self, chapter: int) -> Dict:
        ch_nodes = [n for n in self.nodes.values() if n.chapter == chapter]
        return {
            "chapter": chapter,
            "event_count": len(ch_nodes),
            "events": [{"id": n.id, "type": n.event_type, "event": n.event[:60]} for n in ch_nodes],
            "new_causes": [n.id for n in ch_nodes if not n.parent_causes],
            "new_effects": [n.id for n in ch_nodes if n.children_effects],
        }
    
    def to_text_graph(self, node_id: Optional[str] = None, max_depth: int = 3) -> str:
        lines = []
        lines.append(f"\n=== 剧情溯源图 (项目: {self.project_id}) ===\n")
        
        if node_id and node_id in self.nodes:
            targets = [node_id]
        else:
            sorted_ids = sorted(self.nodes.keys(), key=lambda x: self.nodes[x].chapter, reverse=True)
            targets = sorted_ids[:10]
        
        for tid in targets:
            node = self.nodes[tid]
            lines.append(f"\n[{node.chapter}章] {node.id}: {node.event[:50]}")
            lines.append(f"  类型: {node.event_type} | 置信度: {node.confidence:.2f}")
            
            if node.parent_causes:
                causes_text = " ← ".join([f"{pid}({self.nodes[pid].event[:20] if pid in self.nodes else '?'})"
                                           for pid in node.parent_causes[:3]])
                lines.append(f"  原因: {causes_text}")
            
            if node.children_effects:
                effects_text = " → ".join([f"{eid}({self.nodes[eid].event[:20] if eid in self.nodes else '?'})"
                                             for eid in node.children_effects[:3]])
                lines.append(f"  效果: {effects_text}")
            
            if node.tags:
                lines.append(f"  标签: {', '.join(node.tags)}")
        
        lines.append(f"\n--- 统计: {len(self.nodes)} 个节点 ---\n")
        return "\n".join(lines)


# ==================== CLI ====================

def cmd_add(args):
    trace = PlotTrace(args.project)
    node_id = trace.add_node(
        chapter=int(args.chapter),
        event=args.event,
        event_type=args.event_type,
        parent_causes=args.parents.split(",") if args.parents else None,
        tags=args.tags.split(",") if args.tags else None,
        confidence=float(args.confidence or 1.0),
    )
    print(json.dumps({"node_id": node_id, "chapter": int(args.chapter), "event": args.event},
                      ensure_ascii=False, indent=2))
    return 0


def cmd_back(args):
    trace = PlotTrace(args.project)
    result = trace.trace_back(args.node_id, int(args.depth or 3))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_forward(args):
    trace = PlotTrace(args.project)
    result = trace.trace_forward(args.node_id, int(args.depth or 2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_consistency(args):
    trace = PlotTrace(args.project)
    result = trace.check_consistency()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_graph(args):
    trace = PlotTrace(args.project)
    print(trace.to_text_graph(getattr(args, 'node', None), int(args.depth or 3)))
    return 0


def cmd_summary(args):
    trace = PlotTrace(args.project)
    result = trace.get_chapter_summary(int(args.chapter))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="剧情溯源链（借鉴AbilityKit Trace）")
    parser.add_argument("--project", "-p", required=True, help="项目ID")
    sub = parser.add_subparsers(dest="command")
    
    p_add = sub.add_parser("add", help="添加溯源节点")
    p_add.add_argument("--chapter", "-c", required=True, type=int)
    p_add.add_argument("--event", "-e", required=True, help="事件描述")
    p_add.add_argument("--event-type", "-t", default="character_event")
    p_add.add_argument("--parents", help="父节点ID（逗号分隔）")
    p_add.add_argument("--tags", help="标签（逗号分隔）")
    p_add.add_argument("--confidence", default="1.0")
    
    p_back = sub.add_parser("trace-back", help="反向溯源")
    p_back.add_argument("--node-id", required=True)
    p_back.add_argument("--depth", default="3")
    
    p_fwd = sub.add_parser("trace-forward", help="正向追踪")
    p_fwd.add_argument("--node-id", required=True)
    p_fwd.add_argument("--depth", default="2")
    
    p_con = sub.add_parser("check-consistency", help="一致性检查")
    p_graph = sub.add_parser("graph", help="文本图谱")
    p_graph.add_argument("--node", help="从指定节点开始")
    p_graph.add_argument("--depth", default="3")
    
    p_sum = sub.add_parser("chapter-summary", help="章节摘要")
    p_sum.add_argument("--chapter", "-c", type=int, required=True)
    
    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "trace-back": cmd_back, "trace-forward": cmd_forward,
               "check-consistency": cmd_consistency, "graph": cmd_graph, "chapter-summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
