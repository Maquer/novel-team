#!/usr/bin/env python3
# Version: 0.1.0
"""
Grounded Claims — 证据版本追踪与过期检测（P0）

借鉴 OpenWiki 的 Grounded Claims 机制：每张知识卡片记录其来源证据
（文件路径 + SHA256 哈希 + 时间戳），定期或触发式检查证据是否变更，
变更时自动标记卡片为 stale。

架构：
    card.evidence → {source_path, source_hash, captured_at, lines, stale, stale_at, stale_reason}

用法：
    python3 grounded-claims.py                          # 检查所有卡片证据
    python3 grounded-claims.py --fix                    # 修复 stale 卡片（重新读取源文件）
    python3 grounded-claims.py --json                   # JSON 输出
"""

import hashlib, json, os, sys, argparse
from datetime import datetime, timezone

KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
MEMORY_DIR = "/var/minis/memory"
OBSIDIAN_ROOT = "/var/minis/mounts/loong"

# ── 核心函数 ─────────────────────────────────────────────


def _sha256_file(path):
    """计算文件的 SHA256 哈希（分块读取，支持大文件）。"""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return None


def _resolve_source_path(source):
    """将 card.source 字段解析为实际文件系统路径。

    支持的 source 格式：
    - daily-log/YYYY-MM-DD        → /var/minis/memory/YYYY-MM-DD.md
    - 03-Resources/xxx/xxx.md     → /var/minis/mounts/loong/03-Resources/xxx/xxx.md
    - /var/minis/xxx/xxx.md       → 绝对路径（原样返回）
    - 对话 / 自定义               → 返回 None（不可追溯）
    """
    if not source:
        return None
    if source.startswith('/'):
        return source
    if source.startswith('daily-log/'):
        return os.path.join(MEMORY_DIR, f"{source.replace('daily-log/', '')}.md")
    if source.startswith('03-Resources/') or source.startswith('01-') or source.startswith('02-') or source.startswith('00-'):
        return os.path.join(OBSIDIAN_ROOT, source)
    return None


def _extract_lines(text, title=None, max_lines=5):
    """从文本中提取与卡片相关的内容行号范围（简化版）。
    
    策略：按 ## 标题分割，找到包含 card.title 的段落行号范围。
    如果找不到，返回全文行号范围。
    """
    if not title:
        return None
    lines = text.split('\n')
    sections = []
    current_title = None
    current_start = 0
    for i, line in enumerate(lines):
        if line.startswith('## '):
            if current_title:
                sections.append((current_start, i, current_title))
            current_title = line.strip()
            current_start = i
    if current_title:
        sections.append((current_start, len(lines), current_title))

    # 模糊匹配：标题词在 section 标题中
    for start, end, sec_title in sections:
        if title.lower() in sec_title.lower():
            return {"start": start + 1, "end": min(end, start + max_lines), "section": sec_title}

    # 找不到精确段落，返回全文前 5 行
    return {"start": 1, "end": min(max_lines, len(lines)), "section": None}


def capture_evidence(card):
    """为卡片捕获来源证据。返回 evidence 字典。

    证据结构：
    {
        "source_path": 实际文件路径,
        "source_hash": SHA256 哈希,
        "captured_at":  ISO 时间戳,
        "lines": {start, end, section},  // 可选
        "file_size": 文件大小（字节）
    }
    """
    source = card.get('source', '')
    path = _resolve_source_path(source)
    if not path or not os.path.exists(path):
        return {
            "source_path": path,
            "source_hash": None,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "file_missing": True,
        }

    h = _sha256_file(path)
    stat = os.stat(path)

    # 提取行号范围
    lines = None
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        lines = _extract_lines(text, card.get('title'))
    except Exception:
        pass

    return {
        "source_path": path,
        "source_hash": h,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "lines": lines,
        "file_size": stat.st_size,
        "file_mtime": stat.st_mtime,
    }


def attach_evidence(card, evidence=None):
    """将 evidence 附加到卡片。如果 card 已有 evidence，更新 captured_at。"""
    if evidence is None:
        evidence = capture_evidence(card)
    card['evidence'] = evidence
    return card


def check_stale(card):
    """检查单张卡片的证据是否过期。

    返回 (is_stale, reason)：
    - (True, "file_missing") — 源文件已删除
    - (True, "content_changed") — 源文件内容变更（哈希不同）
    - (False, None) — 证据有效
    """
    evidence = card.get('evidence', {})
    if not evidence:
        return (True, "no_evidence")

    path = evidence.get('source_path')
    if not path or not os.path.exists(path):
        return (True, "file_missing")

    current_hash = _sha256_file(path)
    original_hash = evidence.get('source_hash')
    if current_hash != original_hash:
        return (True, "content_changed")

    return (False, None)


def fix_stale(card):
    """修复 stale 卡片：重新捕获证据并清除 stale 标记。

    返回 (fixed, new_evidence) 元组。
    """
    evidence = card.get('evidence', {})
    old_hash = evidence.get('source_hash') if evidence else None
    path = evidence.get('source_path') if evidence else None

    new_evidence = capture_evidence(card)

    # 如果源文件不存在或哈希变化，不自动修复证据（只更新 metadata）
    if new_evidence.get('file_missing'):
        return (False, new_evidence)

    if old_hash and old_hash != new_evidence.get('source_hash'):
        # 内容变了，只更新证据，不更新卡片内容（需要人工审核）
        card['evidence'] = new_evidence
        card['evidence']['stale'] = None  # 清除过期标记
        return (True, new_evidence)

    return (False, new_evidence)


# ── 批量操作 ─────────────────────────────────────────────


def check_all(dry_run=False, fix=False):
    """批量检查所有卡片的证据状态。

    返回统计信息。
    """
    if not os.path.exists(KNOWLEDGE_STORE):
        return {"error": "knowledge-store not found"}

    store = json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
    cards = store.get('cards', [])

    stats = {
        "total": len(cards),
        "with_evidence": 0,
        "without_evidence": 0,
        "stale": 0,
        "valid": 0,
        "file_missing": 0,
        "content_changed": 0,
        "fixed": 0,
        "results": [],
    }

    for card in cards:
        result = {"id": card.get('id', '')[:16], "title": card.get('title', '')[:40]}

        # 如果卡片没有 evidence，先捕获
        if 'evidence' not in card:
            evidence = capture_evidence(card)
            attach_evidence(card, evidence)
            result['evidence'] = 'captured'
            stats['without_evidence'] += 1
            result['status'] = 'ok'
        else:
            stats['with_evidence'] += 1
            is_stale, reason = check_stale(card)
            result['status'] = 'stale' if is_stale else 'ok'
            result['reason'] = reason

            if is_stale:
                stats['stale'] += 1
                if reason == 'file_missing':
                    stats['file_missing'] += 1
                    result['action'] = 'file_missing'
                elif reason == 'content_changed':
                    stats['content_changed'] += 1
                    result['action'] = 'content_changed'

                    if fix and not dry_run:
                        fixed, new_ev = fix_stale(card)
                        if fixed:
                            stats['fixed'] += 1
                            result['action'] = 'fixed'
                card['evidence']['stale'] = is_stale
                card['evidence']['stale_at'] = datetime.now(timezone.utc).isoformat()
                card['evidence']['stale_reason'] = reason
            else:
                stats['valid'] += 1
                # 检查通过则清除过期标记
                if 'evidence' in card:
                    card['evidence']['stale'] = False
                    card['evidence']['stale_reason'] = None

        stats['results'].append(result)

    if not dry_run:
        json.dump(store, open(KNOWLEDGE_STORE, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)

    return stats


# ── CLI ──────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description='Grounded Claims — 证据版本追踪')
    parser.add_argument('--fix', action='store_true', help='修复 stale 卡片（重新捕获证据）')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    stats = check_all(fix=args.fix)

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    s = stats
    print(f"📊 Grounded Claims 检查结果")
    print(f"  总卡片: {s['total']}")
    print(f"  已有证据: {s['with_evidence']} | 新捕获: {s['without_evidence']}")
    print(f"  有效: {s['valid']} | 过期: {s['stale']}")
    if s['stale']:
        print(f"    文件丢失: {s['file_missing']} | 内容变更: {s['content_changed']}")
    if s['fixed']:
        print(f"  ✅ 已修复: {s['fixed']}")
    if s['stale'] > s['fixed']:
        print(f"  ⚠️ 仍有 {s['stale'] - s['fixed']} 张卡片需要人工审核")

    # 显示 stale 卡片详情
    for r in s.get('results', []):
        if r['status'] == 'stale':
            print(f"    🔴 {r['id']} | {r['title']} → {r.get('reason', 'unknown')}")


if __name__ == '__main__':
    main()
