#!/usr/bin/env python3
# Version: 0.1.0
"""
知识图谱构建 — 解析 Obsidian 笔记间的 [[wiki-link]] 引用关系，构建知识网络。

用法:
    # 构建完整图谱
    python3 obsidian-graph.py --build

    # 统计图谱信息
    python3 obsidian-graph.py --stats

    # 找孤立笔记（没有任何链接关系）
    python3 obsidian-graph.py --isolated

    # 找中心节点（被引用最多的笔记）
    python3 obsidian-graph.py --hubs

    # 找连接某两个主题的最短路径
    python3 obsidian-graph.py --path --from "水果采购" --to "AI工具"

    # 导出图谱为 Markdown（可放入 Obsidian）
    python3 obsidian-graph.py --export
"""

import argparse
import os
import re
import sys
import json
from collections import defaultdict, deque
from pathlib import Path

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
WIKI_LINK_RE = re.compile(r'\[\[([^\]]+)\]\]')

# ═══════════════════════════════════════════════════

def build_graph() -> dict:
    """构建 wiki-link 图，返回 {node: {outgoing: [...], incoming: [...]}}"""
    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        return {}

    graph = defaultdict(lambda: {"outgoing": set(), "incoming": set()})
    file_map = {}  # node_name -> file_path

    # 收集所有文件
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md'):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            node_name = rel.replace(os.sep, '/').removesuffix('.md')  # 用完整相对路径做节点键（不含 .md）
            file_map[node_name] = rel

    # 解析链接
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md'):
                continue
            full = os.path.join(dirpath, fname)
            try:
                content = open(full, 'r', encoding='utf-8', errors='replace').read()
            except (OSError, PermissionError):
                continue

            source = os.path.relpath(full, root).replace(os.sep, '/').removesuffix('.md')
            links = WIKI_LINK_RE.findall(content)

            for link in links:
                # 处理 [[alias|display]] 格式
                target = link.split('|')[0].strip().removesuffix('.md')
                # 含路径则直接用，否则用文件名
                target_name = target
                if target_name:
                    graph[source]["outgoing"].add(target_name)
                    graph[target_name]["incoming"].add(source)

    # 确保所有文件都在图中（即使是孤立节点）
    for name in file_map:
        if name not in graph:
            graph[name] = {"outgoing": set(), "incoming": set()}

    # 转换 set → list（JSON 序列化）
    result = {}
    for node, edges in graph.items():
        result[node] = {
            "outgoing": sorted(edges["outgoing"]),
            "incoming": sorted(edges["incoming"]),
        }

    return result


def get_stats(graph: dict) -> dict:
    """图谱统计。"""
    total_nodes = len(graph)
    total_edges = sum(len(v["outgoing"]) for v in graph.values())
    isolated = sum(1 for v in graph.values() if not v["outgoing"] and not v["incoming"])
    connected = total_nodes - isolated

    # 平均连接度
    avg_degree = round(total_edges / total_nodes, 1) if total_nodes > 0 else 0

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "isolated": isolated,
        "connected": connected,
        "avg_degree": avg_degree,
        "connectivity": round(connected / total_nodes * 100, 1) if total_nodes > 0 else 0,
    }


def get_isolated(graph: dict) -> list:
    """找孤立笔记。"""
    return [node for node, edges in graph.items()
            if not edges["outgoing"] and not edges["incoming"]]


def get_hubs(graph: dict, top: int = 10) -> list:
    """找中心节点（入度最高的节点 = 被引用最多的）。"""
    scored = []
    for node, edges in graph.items():
        in_degree = len(edges["incoming"])
        out_degree = len(edges["outgoing"])
        if in_degree > 0:
            scored.append({"node": node, "in_degree": in_degree, "out_degree": out_degree,
                           "total": in_degree + out_degree})
    scored.sort(key=lambda x: x["in_degree"], reverse=True)
    return scored[:top]


def find_path(graph: dict, source: str, target: str) -> list:
    """BFS 最短路径。"""
    if source not in graph or target not in graph:
        return []

    visited = {source}
    queue = deque([(source, [source])])

    while queue:
        node, path = queue.popleft()
        for neighbor in graph[node]["outgoing"]:
            if neighbor == target:
                return path + [neighbor]
            if neighbor not in visited and neighbor in graph:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return []


def export_markdown(graph: dict) -> str:
    """导出图谱为 Obsidian 可读的 Markdown。"""
    hubs = get_hubs(graph, 15)
    isolated = get_isolated(graph)
    stats = get_stats(graph)

    lines = [
        "# 知识图谱分析",
        f"> 自动生成于 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 概览",
        f"- **总节点：** {stats['total_nodes']} 篇笔记",
        f"- **总链接：** {stats['total_edges']} 条 wiki-link",
        f"- **已连接：** {stats['connected']} 篇（{stats['connectivity']}%）",
        f"- **孤立：** {stats['isolated']} 篇",
        f"- **平均连接度：** {stats['avg_degree']}",
        "",
        "## 🏛️ 中心节点（被引用最多）",
    ]

    for h in hubs:
        lines.append(f"- **{h['node']}** ← 被 {h['in_degree']} 篇笔记引用，链接出去 {h['out_degree']} 篇")

    lines.append("")
    lines.append("## 🏝️ 孤立笔记（建议添加链接）")

    if isolated:
        for node in isolated[:30]:
            lines.append(f"- {node}")
    else:
        lines.append("（无孤立笔记，知识网络很健康 ✅）")

    lines.append("")
    lines.append("---")
    lines.append("*图谱基于 `[[wiki-link]]` 语法构建，仅统计 Obsidian 内部的链接关系。*")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Obsidian 知识图谱构建')
    parser.add_argument('--build', '-b', action='store_true', help='构建图谱（默认操作）')
    parser.add_argument('--stats', '-s', action='store_true', help='显示统计')
    parser.add_argument('--isolated', '-i', action='store_true', help='显示孤立笔记')
    parser.add_argument('--hubs', action='store_true', help='显示中心节点')
    parser.add_argument('--path', action='store_true', help='找路径')
    parser.add_argument('--from', dest='from_node', help='起点（配合 --path）')
    parser.add_argument('--to', dest='to_node', help='终点（配合 --path）')
    parser.add_argument('--export', '-e', action='store_true', help='导出为 Markdown')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')

    args = parser.parse_args()

    graph = build_graph()

    if not graph:
        print("❌ 无法构建图谱（Obsidian 未挂载或无笔记）")
        sys.exit(1)

    if args.stats:
        stats = get_stats(graph)
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
        else:
            print("📊 知识图谱统计")
            for k, v in stats.items():
                label = {"total_nodes": "总节点", "total_edges": "总链接",
                         "isolated": "孤立笔记", "connected": "已连接",
                         "avg_degree": "平均连接度", "connectivity": "连通率"}[k]
                print(f"  {label}: {v}")
        sys.exit(0)

    if args.isolated:
        isolated = get_isolated(graph)
        if args.json:
            print(json.dumps(isolated, ensure_ascii=False, indent=2))
        else:
            print(f"🏝️ 孤立笔记（{len(isolated)} 篇）\n")
            for node in isolated[:30]:
                print(f"  {node}")
            if len(isolated) > 30:
                print(f"  ... 还有 {len(isolated) - 30} 篇")
        sys.exit(0)

    if args.hubs:
        hubs = get_hubs(graph)
        if args.json:
            print(json.dumps(hubs, ensure_ascii=False, indent=2))
        else:
            print("🏛️ 中心节点（被引用最多）\n")
            for h in hubs:
                print(f"  {h['in_degree']:3d}← {h['node']} →{h['out_degree']}")
        sys.exit(0)

    if args.path:
        if not args.from_node or not args.to_node:
            print("❌ --path 需要 --from 和 --to 参数")
            sys.exit(1)
        path = find_path(graph, args.from_node, args.to_node)
        if path:
            print(f"🔗 最短路径: {' → '.join(path)}")
        else:
            print(f"❌ 未找到 {args.from_node} 到 {args.to_node} 的路径")
        sys.exit(0)

    if args.export:
        md = export_markdown(graph)
        out_path = "/var/minis/shared/obsidian-knowledge-graph.md"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"✅ 图谱已导出: {out_path}")
        sys.exit(0)

    # 默认：构建并显示统计
    stats = get_stats(graph)
    hubs = get_hubs(graph, 5)
    isolated_count = len(get_isolated(graph))

    print("📊 知识图谱概览\n")
    print(f"  节点: {stats['total_nodes']} 篇笔记")
    print(f"  链接: {stats['total_edges']} 条 wiki-link")
    print(f"  连通率: {stats['connectivity']}%（{stats['isolated']} 篇孤立）")
    print(f"\n  🏛️ 中心节点:")
    for h in hubs:
        print(f"    {h['in_degree']:3d}← {h['node']} →{h['out_degree']}")


if __name__ == '__main__':
    main()