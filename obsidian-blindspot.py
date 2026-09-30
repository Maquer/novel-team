#!/usr/bin/env python3
# Version: 0.1.0
"""
认知盲区检测 — 基于知识图谱发现孤立集群、浅涉领域和知识迁移机会。

用法:
    python3 obsidian-blindspot.py --scan        # 全量扫描
    python3 obsidian-blindspot.py --gaps        # 发现浅涉领域
    python3 obsidian-blindspot.py --clusters    # 发现孤立集群
    python3 obsidian-blindspot.py --adjacent    # 相邻可能（推荐探索方向）
    python3 obsidian-blindspot.py --report      # 完整报告
"""

from datetime import datetime
import argparse, os, re, sys, json
from pathlib import Path
from collections import defaultdict, Counter

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
WIKI_RE = re.compile(r'\[\[([^\]]+)\]\]')
TITLE_RE = re.compile(r'^# (.+)')

STOP_WORDS = {
    '和', '的', '了', '在', '是', '我', '有', '与', '不', '也', '都', '但',
    '为', '这', '人', '到', '以', '或', '能', '从', '及', '而', '其',
    '被', '上', '下', '中', '它', '要', '就', '对', '可以', '将', '并',
    '一个', '不是', '这个', '那个', '什么', '已经', '还是', '比较',
    '以及', '通过', '对于', '用于', '使用', '关于', '因为', '所以',
    '如果', '虽然', '然而', '并且', '或者', '而且', '只是', '还是',
    'the', 'and', 'of', 'a', 'is', 'to', 'in', 'for', 'on', 'with',
    'that', 'this', 'are', 'was', 'be', 'have', 'has', 'from', 'or',
    'an', 'at', 'by', 'as', 'not', 'but', 'its', 'your', 'our', 'we',
}


def _find_all_files(root):
    files = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.md') and not fname.startswith('.'):
                rel = os.path.relpath(os.path.join(dirpath, fname), root)
                files[rel] = {"path": rel, "stem": Path(rel).stem, "dir": os.path.dirname(rel)}
    return files


def _extract_keywords(text, min_len=2, max_items=8):
    tokens = re.findall(r'[\u4e00-\u9fff]{2,}', text)
    return [t for t in tokens if t not in STOP_WORDS and len(t) >= min_len][:max_items]


def _build_graph(files):
    """构建引用关系图 + 提取每篇笔记的关键词。"""
    graph = {}
    out_degree = {}
    in_degree = {}

    for rel, info in files.items():
        try:
            content = open(os.path.join(OBSIDIAN_ROOT, rel), 'r', encoding='utf-8', errors='replace').read()
        except:
            continue
        title_m = TITLE_RE.search(content)
        title = title_m.group(1) if title_m else info['stem']

        links = WIKI_RE.findall(content)
        text_upper = content.upper()

        keywords = _extract_keywords(title + ' ' + '\n'.join(content.split('\n')[:5]))

        graph[rel] = {
            "title": title,
            "keywords": keywords,
            "links": [l.split('|')[0].strip() for l in links],
            "text_len": len(content),
        }

        out_degree[rel] = len(links)
        in_degree[rel] = 0

        for link in links:
            target = link.split('|')[0].strip()
            for target_rel in files:
                if files[target_rel]['stem'] == target or target in target_rel:
                    in_degree[rel] = in_degree.get(rel, 0)
                    in_degree[target_rel] = in_degree.get(target_rel, 0) + 1
                    break

    return graph, out_degree, in_degree


def find_isolated_clusters(graph):
    """发现孤立集群——同一目录下互相没有链接的笔记组。"""
    clusters = defaultdict(list)
    for rel, info in graph.items():
        dir_key = info.get('dir', 'root')
        if dir_key:
            clusters[dir_key].append(rel)

    isolated = []
    for dir_key, members in clusters.items():
        if len(members) < 2:
            continue
        # 检查集群内是否有互相链接
        internal_links = 0
        for rel in members:
            for link in graph[rel]['links']:
                link_target = link.split('|')[0].strip()
                for m2 in members:
                    if link_target in m2 or Path(m2).stem == link_target:
                        internal_links += 1
        if internal_links == 0 and len(members) >= 3:
            isolated.append({
                "dir": dir_key, "count": len(members),
                "samples": members[:5],
            })
    return sorted(isolated, key=lambda x: x['count'], reverse=True)[:10]


def find_shallow_areas(graph, files):
    """发现浅涉领域——笔记存在但内容很短或关键词稀少。"""
    shallow = []
    for rel, info in graph.items():
        if info['text_len'] < 500 and len(info['keywords']) <= 2:
            shallow.append({"path": rel, "title": info['title'], "length": info['text_len']})
    return sorted(shallow, key=lambda x: x['length'])[:10]


def find_adjacent_possible(graph):
    """相邻可能——找出关键词交叉多但没有笔记主题的探索方向。"""
    topic_keywords = defaultdict(Counter)
    for rel, info in graph.items():
        for kw in info['keywords']:
            topic_keywords[kw][rel] += 1

    # 高频关键词但对应笔记数少
    candidates = []
    for kw, files_dict in topic_keywords.items():
        if len(files_dict) >= 3:
            candidates.append({"keyword": kw, "file_count": len(files_dict), "files": list(files_dict.keys())[:3]})

    return sorted(candidates, key=lambda x: x['file_count'], reverse=True)[:10]


def find_cognitive_gaps(graph):
    """认知差距——发现'提及但从未深挖'的概念。"""
    # 统计所有被提及的链接目标
    all_targets = Counter()
    for rel, info in graph.items():
        for link in info['links']:
            target = link.split('|')[0].strip()
            all_targets[target] += 1

    # 找到被提及多但没有专门笔记的（可能是外部链接或缩写）
    external_refs = []
    for target, count in all_targets.most_common(20):
        found = False
        for rel in graph:
            if Path(rel).stem == target or target in rel:
                found = True
                break
        if not found and len(target) > 2:
            external_refs.append({"target": target, "mentions": count})

    return external_refs[:10]


def generate_report(graph, files):
    clusters = find_isolated_clusters(graph)
    shallow = find_shallow_areas(graph, files)
    adjacent = find_adjacent_possible(graph)
    gaps = find_cognitive_gaps(graph)

    report = []
    report.append("# Obsidian 认知盲区报告")
    report.append(f"> 自动生成于 {datetime.now().isoformat()}")
    report.append("")

    report.append("## 概览")
    report.append(f"- 总笔记: {len(graph)}")
    report.append(f"- 孤立集群: {len(clusters)}")
    report.append(f"- 浅涉笔记: {len(shallow)}")
    report.append(f"- 认知差距: {len(gaps)}")
    report.append("")

    if clusters:
        report.append("## 🏝️ 孤立集群（同目录笔记间无链接）")
        for c in clusters:
            report.append(f"- **{c['dir']}** ({c['count']} 篇)")
            for s in c['samples'][:3]:
                report.append(f"  - {s}")
        report.append("")

    if gaps:
        report.append("## 🔗 认知差距（被频繁提及但无专门笔记）")
        for g in gaps:
            report.append(f"- `{g['target']}` — 被 {g['mentions']} 篇笔记引用，但无专门笔记")
        report.append("")

    if adjacent:
        report.append("## 🧭 相邻可能（推荐探索方向）")
        for a in adjacent:
            report.append(f"- **{a['keyword']}** — {a['file_count']} 篇笔记涉及，可形成专题笔记")
        report.append("")

    return '\n'.join(report)


if __name__ == '__main__':
    from datetime import datetime

    parser = argparse.ArgumentParser(description='认知盲区检测')
    parser.add_argument('--scan', action='store_true', help='全量扫描')
    parser.add_argument('--gaps', action='store_true', help='发现认知差距')
    parser.add_argument('--clusters', action='store_true', help='发现孤立集群')
    parser.add_argument('--adjacent', action='store_true', help='相邻可能')
    parser.add_argument('--report', action='store_true', help='完整报告')
    parser.add_argument('--json', action='store_true', help='JSON 输出')

    args = parser.parse_args()

    root = OBSIDIAN_ROOT
    if not os.path.exists(root):
        print("❌ Obsidian 未挂载")
        sys.exit(1)

    files = _find_all_files(root)
    graph, out_deg, in_deg = _build_graph(files)

    if args.scan:
        clusters = find_isolated_clusters(graph)
        shallow = find_shallow_areas(graph, files)
        adjacent = find_adjacent_possible(graph)
        gaps = find_cognitive_gaps(graph)

        print("══════════════════════════════════════════════")
        print(f"  认知盲区扫描 — {len(graph)} 篇笔记")
        print("══════════════════════════════════════════════")

        print(f"\n🏝️ 孤立集群: {len(clusters)}")
        for c in clusters[:5]:
            print(f"   {c['dir']} ({c['count']} 篇)")

        print(f"\n📉 浅涉笔记: {len(shallow)}")
        for s in shallow[:5]:
            print(f"   {s['title'][:30]} ({s['length']} 字)")

        print(f"\n🔗 认知差距: {len(gaps)}")
        for g in gaps[:5]:
            print(f"   {g['target']} ({g['mentions']} 次引用)")

        print(f"\n🧭 相邻可能: {len(adjacent)}")
        for a in adjacent[:5]:
            print(f"   {a['keyword']} ({a['file_count']} 篇笔记涉及)")
        sys.exit(0)

    if args.gaps:
        gaps = find_cognitive_gaps(graph)
        print(f"🔗 认知差距 ({len(gaps)} 个)\n")
        for g in gaps:
            print(f"  {g['target']} — {g['mentions']} 篇笔记引用，无专门笔记")
        sys.exit(0)

    if args.clusters:
        clusters = find_isolated_clusters(graph)
        print(f"🏝️ 孤立集群 ({len(clusters)} 个)\n")
        for c in clusters:
            print(f"  {c['dir']} ({c['count']} 篇)")
        sys.exit(0)

    if args.adjacent:
        adjacent = find_adjacent_possible(graph)
        print(f"🧭 相邻可能 ({len(adjacent)} 个)\n")
        for a in adjacent:
            print(f"  {a['keyword']} — {a['file_count']} 篇笔记涉及")
        sys.exit(0)

    if args.report:
        report = generate_report(graph, files)
        outpath = "/var/minis/shared/obsidian-blindspot-report.md"
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 报告已导出: {outpath}")
        print(f"\n{report}")
        sys.exit(0)

    parser.print_help()
