#!/usr/bin/env python3
# Version: 0.1.0
"""
L0/L1/L2 三层内容处理 — 借鉴 OpenViking 的分层加载架构。

每次笔记/卡片写入时自动生成三层：
  L0 Abstract   — 一句话摘要 (~50 tokens)，用于快速相关性判断
  L1 Overview   — 核心要点概览 (~200 tokens)，用于规划级检索
  L2 Details    — 完整原始内容，按需加载

每个层级独立存储，搜索时可指定层级，按深度递增加载。

用法:
    # 生成三层摘要
    python3 tiering.py --text "内容..." [--title "标题"]
    
    # 从文件生成
    python3 tiering.py --file /path/to/note.md
    
    # 批量处理 knowledge-store 中的卡片
    python3 tiering.py --backfill

    # 为 Obsidian 笔记添加 frontmatter 层级（就地修改）
    python3 tiering.py --annotate --file /path/to/note.md
"""

import argparse, json, os, re, sys
from pathlib import Path
from datetime import datetime

# ── 句子拆分 ──
_SENT_SPLIT_RE = re.compile(r'([。！？；\n])')

# ── 知识性句子特征 ──
_KNOW_PATTERNS = [
    # 定义型
    re.compile(r'(?:是|即|指|定义为|表示)[^。！？；]{3,}'),
    # 关系型
    re.compile(r'(?:包含|包括|涵盖|涉及|关联|连接|依赖|基于|通过|使用|采用)[^。！？；]{4,}'),
    # 功能型
    re.compile(r'(?:提供|支持|实现|完成|允许|使.*能够|用于|服务于)[^。！？；]{4,}'),
    # 特征型
    re.compile(r'(?:核心|关键|主要|重要|独特|创新|特色|亮点)[^。！？；]{4,}'),
    # 结论型
    re.compile(r'(?:结论|总结|最终|因此|所以|综上)[^。！？；]{4,}'),
    # 推荐型
    re.compile(r'(?:推荐|建议|应该|必须|需要|最佳)[^。！？；]{4,}'),
]

# 标题/关键行
_TITLE_RE = re.compile(r'^#{1,3}\s+(.{3,80})')
_BOLD_RE = re.compile(r'\*\*(.{3,80})\*\*')


def _clean_sentence(s):
    """清洗句子：去掉 Markdown 标记、行首编号/符号。"""
    # 去掉行首的 # 标题标记
    s = re.sub(r'^#{1,6}\s+', '', s)
    # 去掉行首的列表符号 - * +
    s = re.sub(r'^[-*+]\s+', '', s)
    # 去掉行首的编号 1. 2. (1) 等
    s = re.sub(r'^[\d]+[.)、]\s*', '', s)
    s = re.sub(r'^[（(]\d+[)）]\s*', '', s)
    # 去掉行首/尾多余空白
    s = s.strip()
    return s


def _split_sentences(text):
    """按句号等拆分句子，保留分隔符，清洗 Markdown 标记。"""
    parts = _SENT_SPLIT_RE.split(text)
    sentences = []
    buf = ''
    for p in parts:
        if p in '。！？；\n':
            if buf.strip():
                cleaned = _clean_sentence(buf)
                if len(cleaned) >= 4:
                    sentences.append(cleaned)
            buf = ''
        else:
            buf += p
    if buf.strip():
        cleaned = _clean_sentence(buf)
        if len(cleaned) >= 4:
            sentences.append(cleaned)
    return sentences


def _is_knowledge_sentence(s):
    """判断是否为知识性句子（含定义/关系/功能/结论等）。"""
    for pat in _KNOW_PATTERNS:
        if pat.search(s):
            return True
    return False


def _score_sentence(s):
    """句子重要性评分：标题>加粗>知识句>普通。"""
    score = 1
    if _TITLE_RE.match(s):
        score += 10
    if _BOLD_RE.search(s):
        score += 6
    if _is_knowledge_sentence(s):
        score += 3
    if s.startswith('- ') or s.startswith('* '):
        score += 2
    score += min(len(s) // 20, 2)
    return score


def _token_count(text):
    """估算 token 数（中文按字符计，英文/数字按词计）。"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z0-9]+', text))
    return chinese_chars + english_words


def generate_l0(text, title=None):
    """
    生成 L0 Abstract — 一句话摘要。
    策略：优先取标题+首句关键信息，控制在 50 字以内。
    """
    if not text.strip():
        return ''

    # 1. 提取标题
    title_text = ''
    if title:
        title_text = title.strip()
    else:
        m = _TITLE_RE.search(text)
        if m:
            title_text = m.group(1).strip()

    # 2. 拆分并评分句子
    sentences = _split_sentences(text)
    scored = [(s, _score_sentence(s)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)

    # 3. 取最高分句子（去重标题）
    best = ''
    for s, sc in scored:
        if s != title_text:
            best = s
            break
    if not best:
        best = scored[0][0] if scored else ''

    # 4. 组合
    if title_text and best and best != title_text:
        # 标题 + 首句核心
        combined = f"{title_text}：{best}"
        if len(combined) > 60:
            combined = combined[:59] + '…'
        return combined
    elif title_text:
        return title_text
    elif best:
        if len(best) > 60:
            return best[:59] + '…'
        return best
    return ''


def generate_l1(text, title=None, max_tokens=300):
    """
    生成 L1 Overview — 核心要点概览。
    策略：取标题 + Top-N 知识性句子，控制在 200-300 tokens 以内。
    """
    if not text.strip():
        return ''

    lines = []

    # 标题行
    title_text = ''
    if title:
        title_text = title.strip()
    else:
        m = _TITLE_RE.search(text)
        if m:
            title_text = m.group(1).strip()
    if title_text:
        lines.append(title_text)

    # 拆分并评分
    sentences = _split_sentences(text)
    scored = [(s, _score_sentence(s)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)

    # 取 Top-N 去重句子（O(1) 累加，非 O(n²)）
    seen = set([title_text])
    cumulative_tokens = _token_count(title_text) if title_text else 0
    for s, sc in scored:
        if s in seen or len(s) < 8:
            continue
        seen.add(s)
        s_tokens = _token_count(s)
        if cumulative_tokens + s_tokens > max_tokens and lines:
            break
        lines.append(s)
        cumulative_tokens += s_tokens

    # 列表项
    bullet_lines = re.findall(r'^\s*[-*]\s+(.{4,})$', text, re.MULTILINE)
    for bl in bullet_lines[:5]:
        stripped = bl.strip()
        if stripped not in seen and _token_count('\n'.join(lines + [stripped])) < max_tokens:
            seen.add(stripped)
            lines.append(stripped)

    result = '\n'.join(lines[:10])
    if _token_count(result) > max_tokens:
        result = result[:int(max_tokens * 1.5)]
    return result


def generate_l2(text):
    """L2 Details — 完整原始内容（去首尾空白）。"""
    return text.strip()


def generate_tiers(text, title=None):
    """生成完整的 L0/L1/L2 三层。返回 dict。"""
    l0 = generate_l0(text, title)
    l1 = generate_l1(text, title)
    l2 = generate_l2(text)
    return {
        "l0_abstract": l0,
        "l0_tokens": _token_count(l0),
        "l1_overview": l1,
        "l1_tokens": _token_count(l1),
        "l2_details": l2,
        "l2_tokens": _token_count(l2),
        "generated_at": datetime.now().isoformat(),
    }


def annotate_file(filepath, title=None):
    """
    为笔记文件添加 L0/L1 frontmatter 层级标注。
    就地修改文件，在 YAML frontmatter 中插入 tier 字段。
    返回 (l0, l1, l2_tokens)。
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    tiers = generate_tiers(text, title)

    # 检查是否已有 frontmatter
    if text.startswith('---'):
        # 已有 frontmatter，在第二行 --- 前插入
        lines = text.split('\n')
        insert_idx = 1  # 第一行是 ---
        for i in range(1, min(len(lines), 20)):
            if lines[i].strip() == '---':
                insert_idx = i
                break
        # 在 closing --- 前插入 tier 字段（值不加引号，已清理特殊字符）
        l0_clean = tiers["l0_abstract"].replace('"', '').replace('\n', ' ').strip()
        l1_clean = tiers["l1_overview"].replace('"', '').replace('\n', ' ').strip()
        tier_lines = [
            f'tier_l0: {l0_clean}',
            f'tier_l1: {l1_clean}',
            f'tier_l2_tokens: {tiers["l2_tokens"]}',
            f'tier_updated: "{tiers["generated_at"]}"',
        ]
        # 替换 closing ---
        lines[insert_idx] = '\n'.join(tier_lines) + '\n' + lines[insert_idx]
        text = '\n'.join(lines)
    else:
        # 无 frontmatter，添加
        l0_clean = tiers["l0_abstract"].replace('"', '').replace('\n', ' ').strip()
        l1_clean = tiers["l1_overview"].replace('"', '').replace('\n', ' ').strip()
        tier_lines = [
            '---',
            f'tier_l0: {l0_clean}',
            f'tier_l1: {l1_clean}',
            f'tier_l2_tokens: {tiers["l2_tokens"]}',
            f'tier_updated: "{tiers["generated_at"]}"',
            '---',
        ]
        text = '\n'.join(tier_lines) + '\n\n' + text

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    return tiers


def backfill_knowledge_store():
    """为 knowledge-store.json 中所有卡片补充 L0/L1。"""
    store_path = "/var/minis/shared/.knowledge-store.json"
    if not os.path.exists(store_path):
        print("⚠️ knowledge-store.json 不存在")
        return 0

    with open(store_path, 'r', encoding='utf-8') as f:
        store = json.load(f)

    count = 0
    for card in store.get("cards", []):
        preview = card.get("content_preview", "")
        title = card.get("title", "")
        if not preview:
            # 尝试从 claims 拼接
            claims = card.get("claims", [])
            if claims:
                preview = ' '.join(claims[:3])
            else:
                continue

        tiers = generate_tiers(preview, title)
        card["l0_abstract"] = tiers["l0_abstract"]
        card["l1_overview"] = tiers["l1_overview"]
        card["tier_tokens"] = tiers["l2_tokens"]
        count += 1

    with open(store_path, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

    print(f"✅ 已为 {count} 张卡片补充 L0/L1 层级")
    return count


def main():
    parser = argparse.ArgumentParser(description='L0/L1/L2 三层内容处理')
    parser.add_argument('--text', '-t', help='输入文本')
    parser.add_argument('--file', '-f', help='输入文件')
    parser.add_argument('--title', help='标题（可选）')
    parser.add_argument('--annotate', '-a', action='store_true', help='为文件添加 frontmatter 层级')
    parser.add_argument('--backfill', '-b', action='store_true', help='批量为 knowledge-store 补充层级')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')

    args = parser.parse_args()

    if args.backfill:
        backfill_knowledge_store()
        sys.exit(0)

    if args.annotate:
        if not args.file:
            parser.error("--annotate 需要 --file")
        tiers = annotate_file(args.file, args.title)
        print(f"  L0 ({tiers['l0_tokens']}t): {tiers['l0_abstract']}")
        print(f"  L1 ({tiers['l1_tokens']}t): {tiers['l1_overview'][:80]}...")
        print(f"  L2 ({tiers['l2_tokens']}t): {len(tiers['l2_details'])} chars")
        sys.exit(0)

    if not args.text and not args.file:
        parser.print_help()
        sys.exit(1)

    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 文件不存在: {args.file}")
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    else:
        text = args.text

    tiers = generate_tiers(text, args.title)

    if args.json:
        print(json.dumps(tiers, ensure_ascii=False, indent=2))
    else:
        print(f"L0 Abstract ({tiers['l0_tokens']} tokens):")
        print(f"  {tiers['l0_abstract']}")
        print()
        print(f"L1 Overview ({tiers['l1_tokens']} tokens):")
        print(f"  {tiers['l1_overview']}")
        print()
        print(f"L2 Details ({tiers['l2_tokens']} tokens):")
        print(f"  {tiers['l2_details'][:200]}...")


if __name__ == '__main__':
    main()