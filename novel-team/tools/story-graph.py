#!/usr/bin/env python3
"""
知识图谱构建器 — 借鉴 Novel-Creator-Skill

节点类型：character, location, faction, item, event, foreshadow, worldrule, power_system
边类型：ally, enemy, mentor, subordinate, romantic, belongs_to, located_at, triggers, foreshadows, owns
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

# 数据目录
LEDGER_DIR = Path("/var/minis/shared/novel-team/ledger")
GRAPH_FILE = LEDGER_DIR / "story_graph.json"

# 节点类型白名单
NODE_TYPES: Set[str] = {
    "character", "location", "faction", "item",
    "event", "foreshadow", "worldrule", "power_system",
}

# 边类型白名单
EDGE_TYPES: Set[str] = {
    "ally", "enemy", "mentor", "subordinate", "romantic",
    "belongs_to", "located_at", "triggers", "foreshadows", "owns",
}


def now():
    from datetime import timezone, timedelta
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz)


def load_graph() -> Dict:
    if not GRAPH_FILE.exists():
        return {"version": "1.0", "nodes": [], "edges": [], "timeline": []}
    return json.loads(GRAPH_FILE.read_text(encoding='utf-8'))


def save_graph(graph: Dict) -> None:
    tmp = GRAPH_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(GRAPH_FILE)


def make_node_id(node_type: str, name: str) -> str:
    return f"{node_type}_{name.replace(' ', '_')}"


def make_edge_id(edge_type: str, source: str, target: str) -> str:
    return f"{edge_type}_{source}_{target}"


def cmd_add_node(args):
    graph = load_graph()
    
    if args.type not in NODE_TYPES:
        print(f"❌ 非法节点类型: {args.type}")
        print(f"可用类型: {', '.join(NODE_TYPES)}")
        return 1
    
    node_id = make_node_id(args.type, args.name)
    
    # 检查是否已存在
    for node in graph["nodes"]:
        if node["id"] == node_id:
            print(f"⚠️  节点已存在: {node_id}")
            print(f"   将更新现有节点")
            node.update({
                "name": args.name,
                "updated_at": now().isoformat(),
                "attributes": json.loads(args.attrs) if args.attrs else {}
            })
            save_graph(graph)
            print(f"✅ 节点已更新")
            return 0
    
    # 创建新节点
    node = {
        "id": node_id,
        "type": args.type,
        "name": args.name,
        "created_at": now().isoformat(),
        "updated_at": now().isoformat(),
        "attributes": json.loads(args.attrs) if args.attrs else {}
    }
    
    graph["nodes"].append(node)
    save_graph(graph)
    
    print(f"✅ 已添加节点")
    print(f"   ID: {node_id}")
    print(f"   类型: {args.type}")
    print(f"   名称: {args.name}")
    if args.chapter:
        print(f"   章节: 第{args.chapter}章")
    
    return 0


def cmd_add_edge(args):
    graph = load_graph()
    
    if args.type not in EDGE_TYPES:
        print(f"❌ 非法边类型: {args.type}")
        print(f"可用类型: {', '.join(EDGE_TYPES)}")
        return 1
    
    edge_id = make_edge_id(args.type, args.source, args.target)
    
    # 检查源节点和目标节点是否存在
    source_exists = any(n["id"] == args.source or n["name"] == args.source for n in graph["nodes"])
    target_exists = any(n["id"] == args.target or n["name"] == args.target for n in graph["nodes"])
    
    if not source_exists:
        print(f"⚠️  源节点不存在: {args.source}，将自动创建")
        graph["nodes"].append({
            "id": make_node_id("character", args.source),
            "type": "character",
            "name": args.source,
            "created_at": now().isoformat(),
            "updated_at": now().isoformat(),
            "attributes": {}
        })
        source_exists = True
    
    if not target_exists:
        print(f"⚠️  目标节点不存在: {args.target}，将自动创建")
        graph["nodes"].append({
            "id": make_node_id("character", args.target),
            "type": "character",
            "name": args.target,
            "created_at": now().isoformat(),
            "updated_at": now().isoformat(),
            "attributes": {}
        })
        target_exists = True
    
    # 检查边是否已存在
    for edge in graph["edges"]:
        if edge["id"] == edge_id:
            print(f"⚠️  边已存在: {edge_id}")
            print(f"   将更新现有边")
            edge["strength"] = args.strength
            edge["updated_at"] = now().isoformat()
            if args.chapter:
                edge["chapter"] = args.chapter
            save_graph(graph)
            print(f"✅ 边已更新")
            return 0
    
    # 创建新边
    edge = {
        "id": edge_id,
        "type": args.type,
        "source": args.source,
        "target": args.target,
        "strength": args.strength,
        "created_at": now().isoformat(),
        "updated_at": now().isoformat()
    }
    if args.chapter:
        edge["chapter"] = args.chapter
    
    graph["edges"].append(edge)
    save_graph(graph)
    
    print(f"✅ 已添加边")
    print(f"   {args.source} --[{args.type}]--> {args.target}")
    print(f"   强度: {args.strength}")
    
    return 0


def cmd_list_nodes(args):
    graph = load_graph()
    nodes = graph.get("nodes", [])
    
    if not nodes:
        print("图谱为空")
        return
    
    if args.type:
        nodes = [n for n in nodes if n.get("type") == args.type]
    
    print(f"\n{'ID':<30} {'类型':<12} {'名称':<20} {'更新时间'}")
    print("-" * 80)
    for n in sorted(nodes, key=lambda x: x.get("name", "")):
        updated = n.get("updated_at", "")[:10]
        print(f"{n['id']:<30} {n.get('type', ''):<12} {n.get('name', ''):<20} {updated}")
    print(f"\n总计 {len(nodes)} 个节点")


def cmd_list_edges(args):
    graph = load_graph()
    edges = graph.get("edges", [])
    
    if not edges:
        print("图谱中无边")
        return
    
    if args.type:
        edges = [e for e in edges if e.get("type") == args.type]
    
    print(f"\n{'源':<20} {'关系':<12} {'目标':<20} {'强度':<6}")
    print("-" * 60)
    for e in sorted(edges, key=lambda x: (x.get("source", ""), x.get("target", ""))):
        print(f"{e.get('source', ''):<20} {e.get('type', ''):<12} {e.get('target', ''):<20} {e.get('strength', '1.0'):<6}")
    print(f"\n总计 {len(edges)} 条边")


def cmd_export(args):
    graph = load_graph()
    
    if args.format == "mermaid":
        print("```mermaid")
        print("graph LR")
        
        # 节点
        for node in graph.get("nodes", []):
            node_id = node["id"].replace(" ", "_")
            label = f"{node['name']}({node['type']})"
            print(f"    {node_id}[\"{label}\"]")
        
        # 边
        for edge in graph.get("edges", []):
            source_id = edge["source"].replace(" ", "_")
            target_id = edge["target"].replace(" ", "_")
            print(f"    {source_id} -->|{edge['type']}| {target_id}")
        
        print("```")
    
    elif args.format == "json":
        print(json.dumps(graph, ensure_ascii=False, indent=2))
    
    elif args.format == "csv":
        print("id,type,name,created_at,updated_at")
        for node in graph.get("nodes", []):
            print(f"{node['id']},{node['type']},{node['name']},{node.get('created_at', '')},{node.get('updated_at', '')}")
    
    return 0


def cmd_validate(args):
    graph = load_graph()
    errors = []
    
    # 检查节点类型
    for node in graph.get("nodes", []):
        if node.get("type") not in NODE_TYPES:
            errors.append(f"非法节点类型: {node['id']} ({node.get('type')})")
    
    # 检查边类型
    for edge in graph.get("edges", []):
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"非法边类型: {edge['id']} ({edge.get('type')})")
        
        # 检查源节点和目标节点是否存在
        source_exists = any(n["id"] == edge["source"] or n["name"] == edge["source"] for n in graph["nodes"])
        target_exists = any(n["id"] == edge["target"] or n["name"] == edge["target"] for n in graph["nodes"])
        
        if not source_exists:
            errors.append(f"边引用不存在的源节点: {edge['source']}")
        if not target_exists:
            errors.append(f"边引用不存在的目标节点: {edge['target']}")
    
    if errors:
        print("❌ 图谱校验失败:")
        for err in errors:
            print(f"   - {err}")
        return 1
    else:
        print("✅ 图谱校验通过")
        print(f"   节点: {len(graph.get('nodes', []))} 个")
        print(f"   边: {len(graph.get('edges', []))} 条")
        return 0


def cmd_report(args):
    graph = load_graph()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    
    # 统计
    by_type = {}
    for n in nodes:
        t = n.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    
    # 入度出度统计
    in_degree = {}
    out_degree = {}
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        out_degree[src] = out_degree.get(src, 0) + 1
        in_degree[tgt] = in_degree.get(tgt, 0) + 1
    
    print("\n" + "=" * 60)
    print("📊 知识图谱统计报告")
    print("=" * 60)
    print(f"报告时间: {now().strftime('%Y-%m-%d %H:%M')}")
    print()
    print("【节点统计】")
    print(f"  总节点数: {len(nodes)}")
    for t, count in sorted(by_type.items()):
        print(f"  {t}: {count}个")
    print()
    print("【边统计】")
    print(f"  总边数: {len(edges)}")
    edge_types = {}
    for e in edges:
        t = e.get("type", "unknown")
        edge_types[t] = edge_types.get(t, 0) + 1
    for t, count in sorted(edge_types.items()):
        print(f"  {t}: {count}条")
    print()
    print("【核心角色（按连接数排序）】")
    all_entities = set(list(in_degree.keys()) + list(out_degree.keys()))
    entity_degree = {}
    for e in all_entities:
        entity_degree[e] = in_degree.get(e, 0) + out_degree.get(e, 0)
    for name, degree in sorted(entity_degree.items(), key=lambda x: -x[1])[:10]:
        print(f"  {name}: {degree}个连接")
    print()
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="知识图谱构建器")
    subparsers = parser.add_subparsers(dest="command")
    
    # add-node
    p_add = subparsers.add_parser("add-node", help="添加节点")
    p_add.add_argument("--type", required=True, help="节点类型")
    p_add.add_argument("--name", required=True, help="节点名称")
    p_add.add_argument("--attrs", help="属性JSON")
    p_add.add_argument("--chapter", type=int, help="来源章节")
    
    # add-edge
    p_edge = subparsers.add_parser("add-edge", help="添加边")
    p_edge.add_argument("--type", required=True, help="边类型")
    p_edge.add_argument("--source", required=True, help="源节点")
    p_edge.add_argument("--target", required=True, help="目标节点")
    p_edge.add_argument("--strength", type=float, default=1.0, help="关系强度（0-1）")
    p_edge.add_argument("--chapter", type=int, help="来源章节")
    
    # list-nodes
    p_list = subparsers.add_parser("list-nodes", help="列出节点")
    p_list.add_argument("--type", help="过滤类型")
    
    # list-edges
    p_list_edge = subparsers.add_parser("list-edges", help="列出边")
    p_list_edge.add_argument("--type", help="过滤类型")
    
    # export
    p_export = subparsers.add_parser("export", help="导出图谱")
    p_export.add_argument("--format", choices=["mermaid", "json", "csv"], default="mermaid")
    
    # validate
    subparsers.add_parser("validate", help="校验图谱")
    
    # report
    subparsers.add_parser("report", help="生成报告")
    
    args = parser.parse_args()
    
    if args.command == "add-node":
        sys.exit(cmd_add_node(args) or 0)
    elif args.command == "add-edge":
        sys.exit(cmd_add_edge(args) or 0)
    elif args.command == "list-nodes":
        cmd_list_nodes(args)
    elif args.command == "list-edges":
        cmd_list_edges(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "validate":
        sys.exit(cmd_validate(args) or 0)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()
