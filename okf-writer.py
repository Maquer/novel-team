#!/usr/bin/env python3
# Version: 0.1.0
"""
OKF v0.2 格式输出 — 将 knowledge-store 卡片导出为 Google Open Knowledge Format v0.2 文档集。

每个 knowledge-store 卡片对应一个独立的 .md 文件，包含标准 OKF YAML front matter。
额外生成 knowledge-store/bundle.json（OKF 知识包清单）和 index.md（根索引）。

OKF v0.2 规范: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

用法：
    python3 okf-writer.py                           # 导出到 /var/minis/shared/okf-output/
    python3 okf-writer.py --output /path/to/dir     # 指定输出目录
    python3 okf-writer.py --bundle-only             # 只生成 bundle.json
"""

import hashlib, json, os, re, sys, argparse
from datetime import datetime, timezone
from pathlib import Path

KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
DEFAULT_OUTPUT = "/var/minis/shared/okf-output"

# OKF v0.2 元数据字段映射
TYPE_MAP = {
    "concept": "concept",
    "memory": "concept",
    "tool": "artifact",
    "skill": "artifact",
    "decision": "decision",
    "reference": "reference",
    "insight": "concept",
    "preference": "concept",
    "general": "concept",
}

STATUS_MAP = {
    "draft": "draft",
    "pending": "draft",
    "committed": "active",
    "approved": "active",
    "rejected": "deprecated",
}


def _sanitize_filename(title):
    """将标题转换为安全的文件名。"""
    name = title.lower()
    # 移除特殊字符
    name = re.sub(r'[^\w\u4e00-\u9fff\- ]', '', name)
    name = re.sub(r'\s+', '-', name)
    name = re.sub(r'-+', '-', name)
    name = name.strip('-')
    return name[:50] if name else 'untitled'


def _unique_filename(output_dir, base_name):
    """确保文件名唯一，避免同名卡片覆盖。"""
    path = os.path.join(output_dir, f'{base_name}.md')
    if not os.path.exists(path):
        return path
    counter = 1
    while True:
        path = os.path.join(output_dir, f'{base_name}-{counter}.md')
        if not os.path.exists(path):
            return path
        counter += 1


def _generate_content_hash(text):
    """生成内容 SHA256 哈希（用于 OKF 的 content_hash 字段）。"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def _build_frontmatter(card):
    """构建 OKF v0.2 YAML front matter。"""
    okf_type = TYPE_MAP.get(card.get('type', 'general'), 'concept')
    okf_status = STATUS_MAP.get(card.get('status', 'draft'), 'draft')

    fm = [
        '---',
        f'type: {okf_type}',
        f'status: {okf_status}',
        f'title: {card.get("title", "")}',
        f'okf_version: "0.2"',
        f'produced_by: openwiki/minis',
        f'generated:',
        f'  by: minis',
        f'  at: {card.get("created", "")[:19]}Z',
    ]

    # tags
    tags = card.get('tags', [])
    if tags:
        fm.append('tags:')
        for tag in tags[:10]:
            fm.append(f'  - {tag}')

    # claims 作为 sources（evidence 驱动）
    evidence = card.get('evidence', {})
    if evidence and not evidence.get('file_missing'):
        fm.append('sources:')
        fm.append(f'  - type: document')
        fm.append(f'    location: "{evidence.get("source_path", "")}"')
        fm.append(f'    hash: "{evidence.get("source_hash", "")}"')
        fm.append(f'    captured_at: {evidence.get("captured_at", "")}')
        if evidence.get('lines'):
            lines = evidence['lines']
            fm.append(f'    lines: {lines.get("start", "")}-{lines.get("end", "")}')

    # claims 列表
    claims = card.get('claims', [])
    if claims:
        fm.append('claims:')
        for c in claims[:5]:
            fm.append(f'  - {c}')

    # L0/L1 摘要
    if card.get('l0_abstract'):
        fm.append(f'abstract: "{card["l0_abstract"]}"')
    if card.get('l1_overview'):
        fm.append(f'overview: "{card["l1_overview"]}"')

    # 元信息
    score = card.get('score')
    if score is not None:
        fm.append(f'score: {score}')

    # stale_after（OKF lifecycle 字段）
    if evidence and evidence.get('stale'):
        stale_at = evidence.get('stale_at', '')
        fm.append(f'stale_after: {stale_at}')
        fm.append(f'stale_reason: "{evidence.get("stale_reason", "")}"')

    # verified（OKF v0.2）
    if evidence and not evidence.get('stale') and evidence.get('source_hash'):
        fm.append('verified:')
        fm.append(f'  by: minis')
        fm.append(f'  at: {evidence.get("captured_at", "")}')

    fm.append('---')
    return '\n'.join(fm)


def _build_card_body(card):
    """构建卡片正文（Markdown）。"""
    lines = []
    title = card.get('title', '')
    icon = card.get('icon', '')

    lines.append(f'# {icon} {title}')
    lines.append('')

    # L0 摘要
    l0 = card.get('l0_abstract', '')
    if l0:
        lines.append(f'> {l0}')
        lines.append('')

    # L1 概览
    l1 = card.get('l1_overview', '')
    if l1:
        lines.append('## 概览')
        lines.append(l1[:500])
        lines.append('')

    # 主张
    claims = card.get('claims', [])
    if claims:
        lines.append('## 核心主张')
        for c in claims[:10]:
            lines.append(f'- {c}')
        lines.append('')

    # 标签
    tags = card.get('tags', [])
    if tags:
        lines.append(f'**标签：** ' + ', '.join(f'`{t}`' for t in tags[:10]))
        lines.append('')

    # 元数据
    lines.append(f'---')
    lines.append(f'_类型：{card.get("type_label", "")} | 状态：{card.get("status", "")} | 评分：{card.get("score", "")} | 来源：{card.get("source", "")}_')
    lines.append(f'_创建：{card.get("created", "")[:19]}_')

    return '\n'.join(lines)


def export_card(card, output_dir):
    """将单张卡片导出为 OKF 文件。返回文件路径。"""
    filename = _sanitize_filename(card.get('title', ''))
    filepath = _unique_filename(output_dir, filename)

    frontmatter = _build_frontmatter(card)
    body = _build_card_body(card)
    content = f'{frontmatter}\n\n{body}\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return filepath


def build_bundle(cards, output_dir):
    """构建 OKF knowledge bundle（bundle.json）。"""
    now = datetime.now(timezone.utc).isoformat()
    bundle = {
        "okf_version": "0.2",
        "bundle_id": f"minis-knowledge-store-{datetime.now().strftime('%Y%m%d')}",
        "produced_by": "minis/grounded-claims",
        "produced_at": now,
        "card_count": len(cards),
        "type_counts": {},
        "status_counts": {},
        "stale_count": sum(1 for c in cards if c.get('evidence', {}).get('stale')),
        "cards": [],
    }

    for card in cards:
        t = card.get('type', 'general')
        s = card.get('status', 'draft')
        bundle["type_counts"][t] = bundle["type_counts"].get(t, 0) + 1
        bundle["status_counts"][s] = bundle["status_counts"].get(s, 0) + 1
        bundle["cards"].append({
            "id": card.get('id'),
            "title": card.get('title'),
            "type": TYPE_MAP.get(t, 'concept'),
            "status": STATUS_MAP.get(s, 'draft'),
            "evidence_ok": not card.get('evidence', {}).get('stale'),
        })

    bundle_path = os.path.join(output_dir, 'bundle.json')
    with open(bundle_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    return bundle_path


def build_index(cards, output_dir):
    """构建 OKF 根索引 index.md。"""
    lines = [
        '---',
        'okf_version: "0.2"',
        f'generated_at: {datetime.now(timezone.utc).isoformat()}',
        f'card_count: {len(cards)}',
        '---',
        '',
        '# Minis 第二大脑 — 知识库',
        '',
        '> 由 Minis `okf-writer.py` 自动生成（OKF v0.2）',
        f'> 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '',
        '## 知识卡片目录',
        '',
        '| 类型 | 状态 | 标题 |',
        '|------|------|------|',
    ]

    for card in sorted(cards, key=lambda c: (c.get('type', ''), c.get('title', ''))):
        t = card.get('type_label', card.get('type', ''))
        s = STATUS_MAP.get(card.get('status', 'draft'), 'draft')
        title = card.get('title', '')
        stale_marker = ' ⚠️' if card.get('evidence', {}).get('stale') else ''
        lines.append(f'| {t} | {s} | {title}{stale_marker} |')

    index_path = os.path.join(output_dir, 'index.md')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return index_path


def export_all(output_dir=DEFAULT_OUTPUT, bundle_only=False):
    """导出所有知识卡片到 OKF 格式。"""
    if not os.path.exists(KNOWLEDGE_STORE):
        return {"error": "knowledge-store not found"}

    store = json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
    cards = store.get('cards', [])

    os.makedirs(output_dir, exist_ok=True)

    if bundle_only:
        build_bundle(cards, output_dir)
        return {"cards": 0, "bundle": f"{output_dir}/bundle.json", "index": None}

    results = []
    for card in cards:
        filepath = export_card(card, output_dir)
        results.append(filepath)

    bundle_path = build_bundle(cards, output_dir)
    index_path = build_index(cards, output_dir)

    return {
        "cards": len(results),
        "files": results,
        "bundle": bundle_path,
        "index": index_path,
    }


def main():
    parser = argparse.ArgumentParser(description='OKF v0.2 格式导出')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出目录')
    parser.add_argument('--bundle-only', action='store_true', help='只生成 bundle.json')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    result = export_all(output_dir=args.output, bundle_only=args.bundle_only)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if 'error' in result:
        print(f"❌ {result['error']}")
        return

    print(f"📦 OKF v0.2 导出完成")
    print(f"  输出目录: {args.output}")
    print(f"  卡片数: {result.get('cards', 0)}")
    print(f"  索引: {result.get('index', 'N/A')}")
    print(f"  Bundle: {result.get('bundle', 'N/A')}")
    if result.get('files'):
        print(f"  文件列表:")
        for f in result['files']:
            print(f"    📄 {f}")


if __name__ == '__main__':
    main()
