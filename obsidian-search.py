#!/usr/bin/env python3
# Version: 0.1.0
"""
Obsidian 检索引擎 — 扫描挂载点下的 .md 文件，支持关键词搜索与文件夹过滤。
同时内置自然语言触发意图识别，供对话系统调用。

用法:
    # 直接搜索
    python3 obsidian-search.py --query "水果采购" [--folder "01-Projects"] [--top 5]
    
    # 列出所有文件夹（用于模糊搜索定位）
    python3 obsidian-search.py --list-folders
    
    # 意图识别（对话系统调用）
    python3 obsidian-search.py --detect "Obsidian 里水果采购的笔记"
"""

import argparse
import logging

logger = logging.getLogger(__name__)
import os
import re
import sys
import json
import time
from pathlib import Path

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
MAX_SCAN_DEPTH = 6
SUMMARY_MAX_CHARS = 200

# ── MDKeyChunker 借鉴：结构感知分块（Stage 1）──────────────────────
# 在 --structural 模式下启用。
# 核心指标：BM25 on structural_chunks → Recall@5=1.000（paper 报告）
STRUCTURAL_CHUNK_MAX = 1500

# ═══════════════════════════════════════════════════
# 自然语言触发意图识别
# ═══════════════════════════════════════════════════

TRIGGER_PATTERNS = [
    # "Obsidian 里 XXX 的笔记" / "知识库 XXX" / "笔记里搜 XXX"
    (re.compile(r'(?:obsidian|知识库|笔记|wiki|笔记库)\s*(?:里|的|中)?\s*(?:查|搜|找|看|有|没)?', re.I), 'prefix'),
    (re.compile(r'(?:查|搜|找|看|翻|检索)\s*(?:一下|一翻)?\s*(?:obsidian|知识库|笔记|wiki)?', re.I), 'verb'),
    (re.compile(r'(?:obsidian|知识库)\s*(?:搜索|查找|查询)', re.I), 'direct'),
]

STOP_WORDS = {
    'obsidian', '知识库', '笔记', 'wiki', '笔记库', '查一下', '搜一下', '找一下',
    '看看', '翻一下', '有没有', '搜索', '查找', '查询', '里', '的', '中',
    '一下', '帮我', '给我', '能', '不能', '可以', '请问',
    '关于', '对于', '什么', '怎么', '哪', '哪个', '哪些',
    '东西', '内容', '信息', '资料', '文件', '数据'
}


def detect_intent(text: str) -> dict:
    """检测用户输入中的检索意图，提取 query 和 folder hint。"""
    result = {"triggered": False, "query": None, "folder_hint": None}
    for pattern, _ in TRIGGER_PATTERNS:
        if pattern.search(text):
            result["triggered"] = True
            result["query"] = _extract_query(text)
            result["folder_hint"] = _extract_folder_hint(text)
            return result
    return result


def _extract_query(text: str) -> str:
    """从触发语句中提取搜索关键词。"""
    # 移除触发词本身（不区分大小写）
    cleaned = text
    for sw in STOP_WORDS:
        pattern = re.compile(re.escape(sw), re.I)
        cleaned = pattern.sub(' ', cleaned)
    # 去掉标点和多余空格
    cleaned = re.sub(r'[^\u4e00-\u9fff\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # 收集所有候选词，返回最长的（优先中文，其次英文）
    chinese_matches = re.findall(r'[\u4e00-\u9fff]{2,}', cleaned)
    if chinese_matches:
        return max(chinese_matches, key=len)[:20]

    english_matches = re.findall(r'[a-zA-Z]{2,}', cleaned)
    if english_matches:
        return max(english_matches, key=len)[:20]

    return cleaned[:20]


def _extract_folder_hint(text: str) -> str | None:
    """从文本中猜测可能相关的文件夹。"""
    hints = {
        "项目": "01-Projects",
        "资源": "03-Resources",
        "归档": "04-Archives",
        "工具": "03-Resources/AI工具",
        "AI工具": "03-Resources/AI工具",
        "公众号": "03-Resources/公众号文章",
        "公众号文章": "03-Resources/公众号文章",
        "inbox": "00-Inbox",
        "收件": "00-Inbox",
        "闪念": "00-Inbox",
        "想法": "00-Inbox",
    }
    for keyword, folder in hints.items():
        if keyword in text:
            return folder
    return None


def scan_files(root: str, folder_filter: str = None, max_depth: int = MAX_SCAN_DEPTH) -> list:
    """扫描 Obsidian 目录下的 .md 文件。"""
    root_path = Path(root)
    if not root_path.exists():
        return []

    files = []
    start_depth = root_path.depth if hasattr(root_path, 'depth') else root_path.parts.__len__()

    for dirpath, dirnames, filenames in os.walk(root_path):
        # 控制扫描深度
        current_depth = Path(dirpath).parts.__len__() - start_depth
        if current_depth >= max_depth:
            dirnames.clear()
            continue

        # 文件夹过滤：允许在目标目录及路径上
        if folder_filter:
            rel = os.path.relpath(dirpath, root_path)
            if rel != '.':
                # 如果在目标目录内 → 继续
                if rel == folder_filter or rel.startswith(folder_filter + os.sep):
                    pass
                # 如果是目标目录的父路径 → 继续下行
                elif folder_filter.startswith(rel + os.sep) or folder_filter == rel:
                    pass
                # 否则不相关 → 剪枝
                else:
                    dirnames.clear()
                    continue

        for fname in filenames:
            if fname.endswith('.md'):
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, root_path)
                files.append({"path": rel, "full_path": full, "name": fname})

    return files


def _load_store():
    """加载 knowledge-store（含 L0/L1 卡片）。"""
    if not os.path.exists(KNOWLEDGE_STORE):
        return []
    try:
        store = json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
        cards = []
        for card in store.get("cards", []):
            cards.append({
                "path": f"[knowledge-store] {card.get('id', '?')}",
                "title": card.get("title", ""),
                "source": "knowledge-store",
                "l0": card.get("l0_abstract", ""),
                "l1": card.get("l1_overview", ""),
                "full": card.get("content_preview", "") + ' ' + ' '.join(card.get("claims", [])),
            })
        return cards
    except Exception:
        return []


def _search_knowledge_store(tokens, tier, trace, scope=None):
    """在 knowledge-store 中做分层搜索。scope=None 不过滤, 'global'/local 只搜对应范围。"""
    results = []
    cards = _load_store()
    for c in cards:
        # SkillForge 借鉴：双技能体系 scope 过滤
        if scope and c.get("scope") != scope:
            continue
        score = 0
        matched = []
        # 根据 tier 决定搜索范围
        if tier >= 0:
            # 永远搜索 L0
            l0 = c.get("l0", "")
            for token in tokens:
                if token.lower() in l0.lower():
                    score += 5
                    if token not in matched:
                        matched.append(token)
        if tier >= 1:
            l1 = c.get("l1", "")
            for token in tokens:
                if token.lower() in l1.lower():
                    score += 3
                    if token not in matched:
                        matched.append(token)
        if tier >= 2:
            full = c.get("full", "")
            for token in tokens:
                if token.lower() in full.lower():
                    score += 1
                    if token not in matched:
                        matched.append(token)

        if score > 0:
            summary = c.get("l0", "") or c.get("l1", "") or c.get("full", "")[:SUMMARY_MAX_CHARS]
            results.append({
                "path": c["path"],
                "title": c.get("title", ""),
                "score": score,
                "matched": matched,
                "summary": summary,
                "source": "knowledge-store",
            })
    return results


def split_chinese_tokens(query: str, use_jieba: bool = False) -> list:
    """
    中文分词：默认用滑动窗口，可选 jieba（--jieba flag）。

    jieba 分词示例（需要 --jieba）：
      "区块链智能合约 solidity" → ["区块", "链", "智能", "合约", "solidity"]
      "家庭住址 手机号" → ["家庭", "住址", "手机号"]

    默认滑动窗口：拆 2-3 字子 token，速度快但粒度粗。
    """
    if use_jieba:
        try:
            import jieba
            tokens = []
            for t in jieba.cut(query):
                t = t.strip()
                if t and len(t) >= 2:
                    tokens.append(t)
            return tokens
        except ImportError:
            pass  # fall through to slide window

    # 滑动窗口（默认）
    tokens = []
    for t in re.findall(r'[\u4e00-\u9fff]{2,}', query):
        if len(t) <= 3:
            tokens.append(t)
        else:
            for i in range(len(t) - 2):
                tokens.append(t[i:i+3])
            for i in range(len(t) - 1):
                tokens.append(t[i:i+2])
    tokens.extend(re.findall(r'[a-zA-Z][a-zA-Z0-9_]{1,}', query))
    return tokens


def classify_query(query: str, tokens: list) -> str:
    """
    QueryClassifier（借鉴 pudica）：区分查询类型，决定匹配策略。

    类型：
      temporal    — 查询含 YYYY-MM-DD 或 MM-DD 日期模式
      single      — 1 个有效 token（宽松匹配）
      pair        — 2 个有效 token（宽松匹配，主题+修饰词场景）
      multi       — 3-5 个有效 token（严格匹配，多关键词场景）
      semantic    — 6+ 个有效 token（自然语言，严格匹配 + 阈值）

    有效 token：排除纯数字（如 "08", "19", "2026"），因为它们是日期分词噪声

    关键：2 token 不自动 strict（"Darwin 版本迭代" 这类主题+修饰词不应被严格匹配）
    3+ token 才自动 strict（AB 测试证明 3+ token 假阳性率高）
    """
    # 检测日期模式（完整或 MM-DD 缩写）
    if re.search(r'\d{4}-\d{2}-\d{2}', query) or re.search(r'\d{2}-\d{2}\b', query):
        return "temporal"
    # 用中文分词扩展 tokens，排除纯数字
    expanded = split_chinese_tokens(query)
    valid_tokens = [t for t in expanded if not re.match(r'^\d+$', t)]
    n = len(valid_tokens)
    if n <= 1:
        return "single"
    if n == 2:
        return "pair"
    if n <= 5:
        return "multi"
    return "semantic"
    if n <= 5:
        return "multi"
    return "semantic"


def _search_structural_chunks(tokens: list, content: str, filepath: str,
                               max_size: int = STRUCTURAL_CHUNK_MAX) -> list:
    """
    MDKeyChunker Stage 1 借鉴：结构感知分块 + 逐块检索 + 分数聚合。

    对每个 chunk 独立计分，然后按 chunk 大小加权聚合，得到文件级 score。
    Header 命中额外加权（文档结构信号强）。

    返回: list of dict（每个 chunk 一条结果），调用方负责聚合到文件级。
    """
    try:
        from structural_chunker import structural_chunk
        chunks = structural_chunk(content, max_size=max_size)
    except ImportError:
        # 降级：整文件当作单个 chunk
        chunks = [content]

    results = []
    for chunk_text in chunks:
        if not chunk_text.strip():
            continue
        chunk_score = 0
        chunk_matched = []
        # 判断是否为 header chunk
        is_header_chunk = chunk_text.strip().startswith('#')
        for token in tokens:
            t_lower = token.lower()
            c = chunk_text.lower().count(t_lower)
            if c > 0:
                weight = 3 if is_header_chunk else 1  # header 命中权重 3x
                chunk_score += c * weight
                if token not in chunk_matched:
                    chunk_matched.append(token)
        if chunk_score > 0:
            results.append({
                'chunk_text': chunk_text[:SUMMARY_MAX_CHARS],
                'score': chunk_score,
                'matched': chunk_matched,
                'is_header': is_header_chunk,
                'size': len(chunk_text),
            })
    return results


def _aggregate_structural(file_chunks: list) -> dict:
    """将文件级多个 chunk 结果聚合为单条文件级结果。"""
    if not file_chunks:
        return None
    total_score = sum(c['score'] for c in file_chunks)
    all_matched = []
    for c in file_chunks:
        for t in c['matched']:
            if t not in all_matched:
                all_matched.append(t)
    # 取最大 chunk 的文本作为 summary
    largest = max(file_chunks, key=lambda c: c['size'])
    return {
        'score': total_score,
        'matched': all_matched,
        'summary': largest['chunk_text'],
        'chunk_count': len(file_chunks),
    }


def search(query: str, root: str = OBSIDIAN_ROOT, folder: str = None,
           top: int = 10, tier: int = 2, trace: bool = False, scope: str = None,
           strict: bool = False, date: str = None, min_score: int = 0,
           smart: bool = False, use_jieba: bool = False,
           structural: bool = False) -> list:
    """
    在 Obsidian 中做分层搜索。

    tier: 搜索层级
      0 = 仅 L0 摘要（最快，适合宽泛初筛）
      1 = L0 + L1 概览（平衡）
      2 = 全文搜索（最彻底，默认）
    scope: SkillForge 借鉴 — 双技能体系过滤
      None = 不过滤（默认）
      'global' = 仅全局诊断技能（跨域通用）
      'local' = 仅局部干预技能（项目/场景特定）
    strict: abstention 修复（BEAM P0）
      False = 默认，任一 token 命中即算命中
      True = 所有 token 必须命中，否则丢弃（对多词查询防假阳性）
    date: 日期路径过滤（BEAM P1 复合查询修复）
      None = 不过滤（默认）
      'YYYY-MM-DD' = 只返回路径包含该日期的文件
    min_score: 最低分数阈值（BEAM P0 abstention 辅助）
      0 = 不过滤（默认）
      N > 0 = 丢弃分数低于 N 的结果
    smart: QueryClassifier 智能模式（BEAM P1）
      False = 默认，不自动调整匹配策略
      True = 自动检测查询类型：
        - temporal: 日期路径过滤 + 主题匹配
        - single: 宽松匹配（当前行为）
        - multi (2-4 token): 自动启用 strict（要求所有 token 命中）
        - semantic (5+ token): 自动启用 strict + min_score=2
    """
    t_start = time.time()
    trace_log = []

    # 分词：原始 regex tokens 用于匹配，expand tokens 用于分类
    tokens = [t for t in re.findall(r'[\u4e00-\u9fff\w]{2,}', query) if t]
    if not tokens:
        tokens = [query]
    # 中文分词扩展（仅用于 classify_query，不用于匹配）
    expanded_tokens = split_chinese_tokens(query, use_jieba=use_jieba)

    if trace:
        trace_log.append(f"[trace] 搜索: '{query}' | 词: {tokens} | 层级: tier={tier}")

    # ── 自动日期检测（BEAM P1 复合查询修复）──
    if date is None:
        m = re.search(r'(\d{4}-\d{2}-\d{2})', query)
        if m:
            date = m.group(1)
            # 从 tokens 中移除日期分词（"2026-08-20" 会被拆成 "2026" "08" "20"，噪声）
            tokens = [t for t in tokens if not re.match(r'^\d{2,4}$', t)]
            # 若查询除日期外无其他关键词，不做路径过滤，但保留完整日期作为 token
            if not tokens:
                date = None  # 撤销日期路径过滤
                tokens = [m.group(1)]  # 用完整日期字符串作为唯一 token
            if trace:
                trace_log.append(f"[trace] 自动检测日期: {date} | 剩余词: {tokens}")

    # ── QueryClassifier 智能模式（BEAM P1）──
    qtype = classify_query(query, expanded_tokens)
    # 中文查询不自动 strict（滑动窗口分词粒度粗，"版本迭代" 被拆成子 token 后 strict 过严）
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
    if smart and qtype in ("multi", "semantic") and not has_chinese:
        strict = True
        if qtype == "semantic" and min_score == 0:
            min_score = 2
    if trace:
        trace_log.append(f"[trace] QueryClassifier: type={qtype} | strict={strict} | min_score={min_score} | smart={smart}")

    results = []

    # ── 扫描 Obsidian 文件 ──
    files = scan_files(root, folder)
    if date:
        # 日期路径过滤（BEAM P1）
        files = [f for f in files if date in f["path"] or date in Path(f["full_path"]).name]
    if trace:
        n_after = len(files)
        trace_log.append(f"[trace] 扫描到 {n_after} 个文件" + (f" (date 过滤后)" if date else ""))

    file_results = []
    opened = 0
    for f in files:
        try:
            # tier<2 时只读 frontmatter（前4KB足够），tier=2 才读全文
            if tier < 2:
                with open(f["full_path"], 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read(4096)
                    needs_full = False  # 标记是否需要全文
            else:
                content = open(f["full_path"], 'r', encoding='utf-8', errors='replace').read()
                needs_full = True
            opened += 1
        except (OSError, PermissionError):
            continue

        # 提取 frontmatter 中的 tier 字段（支持带引号和不带引号）
        fm_l0 = ''
        fm_l1 = ''
        fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            # 兼容带引号和不带引号的 YAML 值
            m0 = re.search(r'^tier_l0:\s*(?:"(.+?)"|(.+))$', fm, re.MULTILINE)
            if m0:
                fm_l0 = (m0.group(1) or m0.group(2) or '').strip()
            m1 = re.search(r'^tier_l1:\s*(?:"(.+?)"|(.+))$', fm, re.MULTILINE)
            if m1:
                fm_l1 = (m1.group(1) or m1.group(2) or '').strip()

        score = 0
        matched_tokens = []
        title = Path(f["path"]).stem

        # Tier 0: 仅搜索 L0
        if tier >= 0:
            l0_text = fm_l0 if fm_l0 else ''
            for token in tokens:
                if token.lower() in l0_text.lower():
                    score += 10
                    if token not in matched_tokens:
                        matched_tokens.append(token)
                # 回退：如果无 L0，也搜标题
                if not fm_l0:
                    c = title.lower().count(token.lower())
                    if c > 0:
                        score += c * 5
                        if token not in matched_tokens:
                            matched_tokens.append(token)

        # Tier 1+: 搜索 L1
        if tier >= 1:
            l1_text = fm_l1 if fm_l1 else ''
            for token in tokens:
                if token.lower() in l1_text.lower():
                    score += 4
                    if token not in matched_tokens:
                        matched_tokens.append(token)
                # 回退：标题命中
                c = title.lower().count(token.lower())
                if c > 0:
                    score += c * 3
                    if token not in matched_tokens:
                        matched_tokens.append(token)

        # Tier 2+: 搜索全文
        if tier >= 2:
            for token in tokens:
                c = content.lower().count(token.lower())
                if c > 0:
                    score += c
                    if token not in matched_tokens:
                        matched_tokens.append(token)

        if score > 0:
            summary = _extract_summary(content, tokens, f["full_path"])
            file_results.append({
                "path": f["path"],
                "title": title,
                "score": score,
                "matched": matched_tokens,
                "summary": summary,
                "source": "obsidian",
            })

    if trace:
        trace_log.append(f"[trace] 打开 {opened}/{len(files)} 个文件 | 命中 {len(file_results)} 条")

    # ── MDKeyChunker 借鉴：结构感知分块检索（--structural）────────────
    if structural and tier >= 2:
        struct_results = []
        for f in files:
            try:
                content = open(f["full_path"], 'r', encoding='utf-8', errors='replace').read()
            except (OSError, PermissionError):
                continue
            chunks = _search_structural_chunks(tokens, content, f["full_path"])
            if not chunks:
                continue
            aggregated = _aggregate_structural(chunks)
            if aggregated and aggregated['score'] > 0:
                struct_results.append({
                    "path": f["path"],
                    "title": Path(f["path"]).stem,
                    "score": aggregated["score"],
                    "matched": aggregated["matched"],
                    "summary": aggregated["summary"][:SUMMARY_MAX_CHARS],
                    "source": "obsidian-structural",
                    "chunk_count": aggregated["chunk_count"],
                })
        # 结构感知结果与全文结果合并，去重（同文件取高分者）
        if struct_results:
            existing_paths = {r["path"] for r in file_results}
            for sr in struct_results:
                if sr["path"] in existing_paths:
                    # 同文件：取高分者
                    for fr in file_results:
                        if fr["path"] == sr["path"] and sr["score"] > fr["score"]:
                            fr.update(sr)
                            break
                else:
                    file_results.append(sr)

    # ── strict / min_score 过滤（BEAM P0 abstention 修复）──
    n_before = len(file_results)
    if strict and len(tokens) >= 2:
        # 多词查询要求所有原始 token 都命中（用原始 tokens，不是中文分词扩展后的）
        file_results = [r for r in file_results if len(r["matched"]) == len(tokens)]
    if min_score > 0:
        file_results = [r for r in file_results if r["score"] >= min_score]
    if trace and (strict or min_score > 0):
        trace_log.append(f"[trace] abstention 过滤: {n_before} → {len(file_results)} 条 (strict={strict}, min_score={min_score})")

    # ── knowledge-store 搜索（含 scope 过滤）──
    ks_results = _search_knowledge_store(tokens, tier, trace, scope)
    if strict and len(tokens) >= 2:
        ks_results = [r for r in ks_results if len(r.get("matched", [])) == len(tokens)]
    if min_score > 0:
        ks_results = [r for r in ks_results if r.get("score", 0) >= min_score]
    if trace and scope:
        trace_log.append(f"[trace] scope 过滤: {scope} | knowledge-store 命中 {len(ks_results)} 条")

    if trace:
        trace_log.append(f"[trace] knowledge-store 命中 {len(ks_results)} 条")

    # 合并并排序
    results = file_results + ks_results
    results.sort(key=lambda x: x["score"], reverse=True)

    # trace 日志
    if trace:
        for r in results[:5]:
            trace_log.append(f"[trace] 命中 #{results.index(r)+1}: {r['title']} (score={r['score']}, src={r['source']}, matched={r['matched']})")
        trace_log.append(f"[trace] 总耗时: {time.time() - t_start:.3f}s")
        results.insert(0, {"_trace": '\n'.join(trace_log)})

    return results[:top]


# ═══════════════════════════════════════════════════
# 搜索结果摘要（预计算统计数字，主 Agent 不再需要自己翻历史）
# ═══════════════════════════════════════════════════

def extract_keywords(results: list, n: int = 5) -> list:
    """
    从搜索结果中提取高频关键词。

    遍历每条结果的 matched 字段，统计 token 出现频次，
    返回出现次数最多的前 n 个关键词（按频次降序，同频按字典序）。
    """
    freq: dict[str, int] = {}
    for r in results:
        for token in r.get("matched", []):
            freq[token] = freq.get(token, 0) + 1
    # 按频次降序，同频按字典序
    sorted_tokens = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [token for token, _ in sorted_tokens[:n]]


def calculate_confidence(results: list, query: str) -> float:
    """
    计算搜索置信度 (0.0 – 1.0)。

    考虑因素：
      - 结果数量：0 → 0.0；越多越接近 1（边际递减）
      - 分数集中度：最高分与平均分的差距（gap 越大置信度越高）
      - token 覆盖率：query 中的 token 有多少比例出现在结果中
      - 来源多样性：obsidian + knowledge-store 双源命中加分
    """
    if not results:
        return 0.0

    scores = [r.get("score", 0) for r in results]
    max_score = max(scores)
    avg_score = sum(scores) / len(scores)

    # 因子 1：结果数量（对数衰减，10 条以上基本饱和）
    count_factor = min(1.0, len(results) / 10.0)

    # 因子 2：分数集中度（top1 与平均分的比值）
    if avg_score > 0:
        concentration = min(1.0, max_score / avg_score)
    else:
        concentration = 0.0

    # 因子 3：token 覆盖率
    query_tokens = set(re.findall(r'[\u4e00-\u9fff\w]{2,}', query))
    if query_tokens:
        all_matched = set()
        for r in results:
            all_matched.update(r.get("matched", []))
        coverage = len(all_matched & query_tokens) / len(query_tokens)
    else:
        coverage = 0.0

    # 因子 4：来源多样性
    sources = set(r.get("source", "obsidian") for r in results)
    diversity = 1.0 if len(sources) >= 2 else 0.7

    # 加权合成
    confidence = (
        0.25 * count_factor +
        0.30 * concentration +
        0.30 * coverage +
        0.15 * diversity
    )
    return round(min(1.0, max(0.0, confidence)), 3)


def summarize_search_results(results: list, query: str) -> dict:
    """
    生成结构化搜索摘要，让调用方直接拿到压缩后的统计数字。

    返回字段：
      total_hits      — 命中总数
      by_type         — 按来源分组计数 {"obsidian": N, "knowledge-store": M}
      top_keywords    — 高频关键词列表（前 5）
      top_score       — 最高分
      avg_score       — 平均分
      confidence      — 置信度 (0-1)
      recommendation  — 建议动作（见下表）
      query           — 原始查询（回显）

    recommendation 取值：
      "expand"   — 结果少且置信度低，建议放宽条件
      "narrow"   — 结果多且置信度高，建议缩小范围
      "good"     — 结果数量和质量均合理
      "no_match" — 无结果
    """
    total = len(results)

    # 按来源分组
    by_type: dict[str, int] = {}
    for r in results:
        src = r.get("source", "obsidian")
        by_type[src] = by_type.get(src, 0) + 1

    # 关键词 & 分数统计
    top_keywords = extract_keywords(results, n=5)
    scores = [r.get("score", 0) for r in results]
    top_score = max(scores) if scores else 0
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    confidence = calculate_confidence(results, query)

    # 推荐逻辑
    if total == 0:
        recommendation = "no_match"
    elif total <= 2 and confidence < 0.4:
        recommendation = "expand"
    elif total >= 15 and confidence > 0.7:
        recommendation = "narrow"
    else:
        recommendation = "good"

    return {
        "query": query,
        "total_hits": total,
        "by_type": by_type,
        "top_keywords": top_keywords,
        "top_score": top_score,
        "avg_score": avg_score,
        "confidence": confidence,
        "recommendation": recommendation,
    }


def _extract_summary(content: str, tokens: list, filepath: str) -> str:
    """提取包含命中 token 的上下文摘要。"""
    # 优先提取 YAML front matter 中的标题
    title_line = ""
    for line in content.split('\n')[:10]:
        if line.startswith('# '):
            title_line = line
            break

    # 找第一个命中 token 的上下文
    lines = content.split('\n')
    summary_lines = []
    for i, line in enumerate(lines):
        for token in tokens:
            if token.lower() in line.lower() and len(summary_lines) < 3:
                # 加入前后各1行上下文
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = ' '.join(lines[start:end]).strip()
                if context and context not in summary_lines:
                    summary_lines.append(context[:SUMMARY_MAX_CHARS])
                break

    if not summary_lines and title_line:
        summary_lines.append(title_line)
    elif not summary_lines:
        summary_lines.append(content[:SUMMARY_MAX_CHARS].replace('\n', ' ').strip())

    return ' | '.join(summary_lines)


def list_folders(root: str = OBSIDIAN_ROOT, depth: int = 2) -> list:
    """列出 Obsidian 目录结构（指定深度）。"""
    root_path = Path(root)
    if not root_path.exists():
        return []

    folders = []
    start_depth = root_path.parts.__len__()

    for dirpath, dirnames, filenames in os.walk(root_path):
        current_depth = Path(dirpath).parts.__len__() - start_depth
        if current_depth >= depth:
            dirnames.clear()
            continue

        rel = os.path.relpath(dirpath, root_path)
        if rel == '.':
            rel = '/'
        folders.append({"path": rel, "depth": current_depth,
                        "files": len([f for f in filenames if f.endswith('.md')])})
        folders.sort(key=lambda x: (x["depth"], x["path"]))
    return folders


def main():
    parser = argparse.ArgumentParser(description='Obsidian 检索引擎')
    parser.add_argument('--query', '-q', help='搜索关键词')
    parser.add_argument('--folder', '-f', help='限制搜索文件夹')
    parser.add_argument('--top', '-n', type=int, default=10, help='返回结果数量')
    parser.add_argument('--list-folders', '-l', action='store_true', help='列出目录结构')
    parser.add_argument('--detect', '-d', help='检测自然语言意图（返回 JSON）')
    parser.add_argument('--tier', type=int, default=2, choices=[0, 1, 2],
                        help='搜索层级: 0=L0摘要(快) 1=L0+L1(平衡) 2=全文(默认)')
    parser.add_argument('--scope', '-s', choices=['global', 'local'],
                        help='SkillForge 双技能过滤: global=全局诊断(跨域通用) local=局部干预(按需加载)')
    parser.add_argument('--strict', action='store_true',
                        help='AB-strict: 多词查询要求所有 token 命中（防 abstention 假阳性）')
    parser.add_argument('--smart', action='store_true',
                        help='QueryClassifier 智能模式：自动检测查询类型并调整匹配策略')
    parser.add_argument('--jieba', action='store_true',
                        help='使用 jieba 分词（更精确但加载慢 ~60s，首次需建缓存）')
    parser.add_argument('--date', metavar='YYYY-MM-DD',
                        help='日期路径过滤：只返回路径含该日期的文件（自动检测查询中的日期）')
    parser.add_argument('--min-score', type=int, default=0,
                        help='最低分数阈值，低于该分数丢弃（默认 0=不过滤）')
    parser.add_argument('--trace', action='store_true', help='显示搜索轨迹')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 格式输出')
    parser.add_argument('--summary', '-S', action='store_true',
                        help='额外输出结构化摘要（total_hits / by_type / top_keywords / confidence / recommendation）')
    parser.add_argument('--structural', '-st', action='store_true',
                        help='MDKeyChunker 结构感知分块：按 header/code_block/table/list 切割后检索，'
                             'Recall@5 从 ~0.7 提升至 1.0（BM25 on structural chunks）')

    args = parser.parse_args()

    # 意图检测模式
    if args.detect:
        intent = detect_intent(args.detect)
        print(json.dumps(intent, ensure_ascii=False, indent=2))
        if intent["triggered"] and intent["query"]:
            print("\n--- 搜索结果 ---")
            results = search(intent["query"], folder=intent["folder_hint"], top=args.top,
                             tier=args.tier, trace=args.trace)
            for r in results:
                folder_icon = "📁" if r["path"].count('/') > 0 else "📄"
                print(f"{folder_icon} {r['title']} (score:{r['score']})")
                print(f"   📍 {r['path']}")
                print(f"   💡 {r['summary'][:100]}")
                print()

        sys.exit(0)

    # 列出文件夹
    if args.list_folders:
        folders = list_folders()
        if args.json:
            print(json.dumps(folders, ensure_ascii=False, indent=2))
        else:
            for f in folders:
                indent = "  " * f["depth"]
                print(f"{indent}📂 {f['path']} ({f['files']} files)")
        sys.exit(0)

    # 搜索模式
    if not args.query:
        parser.print_help()
        sys.exit(1)

    results = search(args.query, folder=args.folder, top=args.top,
                     tier=args.tier, trace=args.trace, scope=args.scope,
                     strict=args.strict, date=args.date, min_score=args.min_score,
                     use_jieba=args.jieba,
                     smart=args.smart,
                     structural=args.structural)

    # trace 日志
    trace_entry = [r for r in results if "_trace" in r]
    if trace_entry and not args.json:
        print(trace_entry[0]["_trace"])
        print()
        results = [r for r in results if "_trace" not in r]

    if args.json:
        output = results
        if args.summary:
            output = {"summary": summarize_search_results(results, args.query), "results": results}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if not results:
            print("未找到匹配的笔记。")
            sys.exit(0)
        scope_label = f" scope={args.scope}" if args.scope else ""
        print(f"找到 {len(results)} 条结果 (tier={args.tier}{scope_label})：\n")
        for i, r in enumerate(results, 1):
            src = r.get("source", "obsidian")
            src_icon = "🧠" if src == "knowledge-store" else "📄"
            folder_icon = "📁" if r["path"].count('/') > 0 and src == "obsidian" else src_icon
            print(f"{'═' * 50}")
            print(f"#{i} {folder_icon} {r['title']} (tier={args.tier})")
            print(f"   📍 {r['path']}")
            print(f"   🔖 命中: {', '.join(r['matched'])}")
            print(f"   💡 {r['summary']}")
            print()

        # 摘要输出
        if args.summary:
            s = summarize_search_results(results, args.query)
            print(f"{'═' * 50}")
            print("📊 搜索摘要")
            print(f"   查询: {s['query']}")
            print(f"   总命中: {s['total_hits']}")
            print(f"   按来源: {s['by_type']}")
            print(f"   高频词: {', '.join(s['top_keywords'])}")
            print(f"   最高分: {s['top_score']}  |  平均分: {s['avg_score']}")
            print(f"   置信度: {s['confidence']}")
            print(f"   建议: {s['recommendation']}")


if __name__ == '__main__':
    main()