#!/usr/bin/env python3
# Version: 0.1.0
"""
知识蒸馏管道 — 将对话/原始笔记自动转化为结构化知识卡片，
并关联已有知识网络，可选生成 Skill 骨架。

用法:
    # 从文本蒸馏知识卡片
    python3 obsidian-distill.py --distill "对话内容或笔记内容"

    # 从文件蒸馏
    python3 obsidian-distill.py --distill-file "01-Projects/水果采购/水果采购.md"

    # 批量蒸馏（Inbox 扫描）
    python3 obsidian-distill.py --batch

    # 查看待蒸馏列表
    python3 obsidian-distill.py --pending

    # 导出知识卡片为 Obsidian Markdown
    python3 obsidian-distill.py --export

    # 生成 Skill 骨架（基于知识卡片）
    python3 obsidian-distill.py --skill-from "知识卡片名称"
"""

import argparse
import logging

logger = logging.getLogger(__name__)
import os
import re
import json
import sys
from pathlib import Path
from datetime import datetime

# ── 引入分层模块 ──
import importlib.util
_tiering_spec = importlib.util.spec_from_file_location('tiering', '/var/minis/shared/tiering.py')
_tiering_mod = importlib.util.module_from_spec(_tiering_spec)
_tiering_spec.loader.exec_module(_tiering_mod)

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
OBSIDIAN_INBOX = os.path.join(OBSIDIAN_ROOT, "00-Inbox")
KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"

# 知识类型
KNOWLEDGE_TYPES = {
    "concept": {"label": "概念", "icon": "🧠", "suffix": "概念"},
    "tool": {"label": "工具", "icon": "🔧", "suffix": "工具"},
    "method": {"label": "方法", "icon": "📐", "suffix": "方法"},
    "principle": {"label": "原理", "icon": "⚡", "suffix": "原理"},
    "example": {"label": "案例", "icon": "📋", "suffix": "案例"},
    "framework": {"label": "框架", "icon": "🏗️", "suffix": "框架"},
}

WIKI_RE = re.compile(r'\[\[([^\]]+)\]\]')
# 知识句式：涵盖定义/关系/功能/对比/流程/推荐/事实/列表
CLAIM_RE = re.compile(r'(?:核心|主张|定义|原理|关键|方法论|原则|策略|重点|本质|结论|总结|发现|认为|指出|提出)[：:]((?:[^。]{5,50}。?)?)')
# 列表项
# 列表项
ITEM_RE = re.compile(r'^[\s]*[-*]\s+([^\n]{6,})$')
# 编号项
NUM_RE = re.compile(r'^[\s]*(?:\d+\.|[（\(]\d+[）\)])\s+([^\n]{6,})$')
# 标题行
TITLE_RE = re.compile(r'^#{1,3}\s+(.{2,60})')
# 加粗语句
BOLD_RE = re.compile(r'\*\*(.{3,80})\*\*')


def _load_store():
    if os.path.exists(KNOWLEDGE_STORE):
        try:
            return json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
        except:
            return {"cards": [], "pending": []}
    return {"cards": [], "pending": []}


def _save_store(store):
    os.makedirs(os.path.dirname(KNOWLEDGE_STORE) or '.', exist_ok=True)
    json.dump(store, open(KNOWLEDGE_STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


# ── 状态机强制校验（借鉴 Edict kanban_update.py 的 _VALID_TRANSITIONS）──
# 合法跳转表：draft→approved→committed，非合法跳转一律拒绝并写入审计日志
# 状态由其他工具（session-commit.py）设置时，本脚本不介入——但 approved→committed 是合法方向
_VALID_TRANSITIONS = {
    "draft":     {"approved"},
    "approved":  {"committed"},
    "committed": set(),
}
_TERMINAL_STATES = {"committed"}

def _transition(card, new_status, store=None):
    """合法性校验 + 状态推进 + 审计日志。非法跳转 raise ValueError 并记录。

    store: 调用方传入的 store 对象。若为 None 则内部加载/保存（可能造成覆盖，
           强烈建议调用方显式传入已加载的 store，避免 _log_audit 的独立
           save 覆盖调用方随后的 card 修改。
    """
    cur = card.get("status", "draft")
    card_id = card.get("id", "?")
    title = card.get("title", "")[:40]

    # 幂等：目标态 = 当前态，直接返回，不算非法
    if new_status == cur:
        return card

    allowed = _VALID_TRANSITIONS.get(cur, set())
    if store is None:
        store = _load_store()
    if new_status not in allowed:
        _log_audit(card_id, cur, new_status, rejected=True, note=title, store=store)
        _save_store(store)  # 非法跳转：只落审计日志，不改 card
        raise ValueError(f"非法状态跳转: {cur}→{new_status} (card={card_id} '{title}')"
                         f" | 允许: {sorted(allowed) or '无 (终态)'}. 非法跳转已写入审计日志。")
    _log_audit(card_id, cur, new_status, rejected=False, note=title, store=store)
    card["status"] = new_status
    return card

def _log_audit(card_id, frm, to, rejected, note="", store=None):
    """追加状态流转审计日志（JSON store 内的 audit_log 数组）。

    只 append 到内存 store，不 save——save 由 _transition / 调用方负责，
    避免嵌套 save 覆盖调用方对 store 的其他修改。
    """
    try:
        if store is None:
            store = _load_store()
        store.setdefault("audit_log", []).append({
            "ts": datetime.now().isoformat(),
            "card_id": card_id, "from": frm, "to": to,
            "rejected": bool(rejected), "note": note,
        })
    except Exception:
        pass  # 审计失败不阻塞业务流程


# 句子拆分：按。！？；拆分，保留分割符
_SENT_SPLIT_RE = re.compile(r'([。！？；])')

# 知识性句子特征：包含定义/关系/功能/事实词汇
_KNOW_WORDS = re.compile(r'(?:是|有|包含|包括|基于|通过|使用|依赖|提供|支持|需要|应该|必须|用于|属于|采用|提供|涵盖|针对|面向)')

# 信息密度检查：至少2个4字以上中文词组或5个汉字
_DENSITY_RE = re.compile(r'[\u4e00-\u9fff]{4,}')


def extract_claims(content):
    """提取关键主张。"""
    claims = []

    # 1. 标题（最高优先级）
    for line in content.split('\n'):
        m = TITLE_RE.match(line.strip())
        if m:
            claims.insert(0, m.group(1).strip())

    # 2. 按句子拆分后逐句匹配
    sentences = _SENT_SPLIT_RE.split(content)
    for s in sentences:
        s = s.strip()
        if len(s) < 8:
            continue

        # 核心句式（核心方法论：/关键原则是/...）
        m = CLAIM_RE.search(s)
        if m:
            val = m.group(1).strip()
            if val:
                claims.append(val)
                continue

        # 知识性语句
        if _KNOW_WORDS.search(s):
            # 信息密度检查：至少1个4字以上中文词组
            if _DENSITY_RE.search(s):
                claims.append(s)
                continue

        # 列表项
        m = ITEM_RE.match(s)
        if m:
            claims.append(m.group(1).strip())
            continue
        m = NUM_RE.match(s)
        if m:
            claims.append(m.group(1).strip())
            continue

        # 加粗语句
        for bm in BOLD_RE.finditer(s):
            val = bm.group(1).strip()
            if len(val) >= 4:
                claims.append(val)

    # 去重保序
    seen = set()
    deduped = []
    for c in claims:
        if c not in seen and len(c) >= 5:
            seen.add(c)
            deduped.append(c)
    return deduped[:8]


def _score_card(title, claims, text, link_count):
    """卡片质量评分（0-100）。"""
    score = 0
    score += min(len(claims) * 8, 30)
    score += min(len(text) // 20, 20)
    score += min(link_count * 5, 20)
    score += min(len(set(re.findall(r'[\u4e00-\u9fff]{2,4}', title))) * 2, 10)
    score += 20
    return min(score, 100)


def classify_type(claims, title):
    """分类知识类型。"""
    text = ' '.join(claims + [title]).lower()
    tool_kw = ['工具', '软件', 'api', 'sdk', 'cli', 'platform', 'service', '框架', 'library', '包', 'npm', 'pip', 'mcp']
    method_kw = ['方法', '策略', '流程', '步骤', 'pipeline', '工作流', 'sop', '步骤', '方法']
    framework_kw = ['框架', '架构', '体系', '模型', '模式', 'paradigm', 'architecture', 'system']
    principle_kw = ['原理', '原则', '理论', '定律', '公式', '原理']
    example_kw = ['案例', '例子', '实例', '场景', '应用', '实践', 'demo', 'use case']

    scores = {"tool": 0, "method": 0, "framework": 0, "principle": 0, "example": 0, "concept": 0}
    for kw in tool_kw:
        if kw in text:
            scores["tool"] += 1
    for kw in method_kw:
        if kw in text:
            scores["method"] += 1
    for kw in framework_kw:
        if kw in text:
            scores["framework"] += 1
    for kw in principle_kw:
        if kw in text:
            scores["principle"] += 1
    for kw in example_kw:
        if kw in text:
            scores["example"] += 1

    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return "concept"


# ═══════════════════════════════════════════════════
# SkillForge 借鉴：双技能体系 — 全局诊断 vs 局部干预
# ═══════════════════════════════════════════════════

def classify_scope(title, claims, text, source):
    """
    判断知识的适用范围 — global（跨域通用，JIT 全量加载）还是 local（项目/场景特定，按需注入）
    对应 SkillForge 的 global-diagnostic-skills / local-intervention-skills 分离
    """
    combined = (title + ' ' + ' '.join(claims) + ' ' + text[:500]).lower()
    source_lower = (source or '').lower()

    local_signals = [
        '项目', '场景', '案例', '实例', '这次', '本次', '这个', '那个',
        '当前', '我的', '我们的', '公司', '团队', '客户',
        'synthesis', 'local-intervention', 'instance',
        'daily-log', 'session-commit',
    ]
    global_signals = [
        '原理', '原则', '方法', '模式', '通用', '跨域', '跨语言',
        '方法论', '框架', '范式', '规律', '经验', '全局',
        'global', 'global-diagnostic', 'meta',
        'benchmark', 'baseline', 'universal',
        'skillforge', 'darwin', 'veriskill', 'swe-bench',
    ]

    local_score = sum(1 for kw in local_signals if kw in combined) + sum(1 for kw in local_signals if kw in source_lower)
    global_score = sum(1 for kw in global_signals if kw in combined) + sum(1 for kw in global_signals if kw in source_lower)

    if global_score > local_score + 1:
        return "global"
    if local_score > global_score + 1:
        return "local"

    if source and ('daily-log' in source_lower or 'session' in source_lower):
        return "local"
    return "global"


def distill(text, source_file=None):
    """从文本蒸馏知识卡片。"""
    text = text.strip()
    if not text:
        print("⚠️ 输入为空，跳过蒸馏")
        return None, None
    claims = extract_claims(text)
    title_m = TITLE_RE.search(text)
    if title_m:
        title = title_m.group(1)
    elif source_file:
        title = Path(source_file).stem
    else:
        # 用第一句前20字作为标题
        first_line = text.split('\n')[0].strip()
        title = first_line[:20] if first_line else "未命名知识"

    ktype = classify_type(claims, title)
    type_info = KNOWLEDGE_TYPES.get(ktype, KNOWLEDGE_TYPES["concept"])

    # 提取 wiki-link 作为相关笔记
    links = WIKI_RE.findall(text)

    # 从内容中提取标签
    tags = set()
    for tag in re.findall(r'#([\w\-/··]+)', text):
        tags.add(tag)
    # 标题关键词作为标签
    for word in re.findall(r'[\u4e00-\u9fff]{2,4}', title):
        tags.add(word)

    # 评分
    card_score = _score_card(title, claims, text, len(links))

    # ── SkillForge 借鉴：双技能体系（全局诊断 vs 局部干预）──
    scope = classify_scope(title, claims, text, source_file or "对话")
    scope_info = {
        "global": {"label": "全局诊断", "icon": "🌐", "desc": "跨域通用，所有场景适用"},
        "local": {"label": "局部干预", "icon": "📍", "desc": "项目/场景特定，按需加载"},
    }

    card = {
        "id": f"KD-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}",
        "title": title,
        "type": ktype,
        "type_label": type_info["label"],
        "icon": type_info["icon"],
        "claims": claims,
        "links": links[:10],
        "tags": sorted(tags)[:10],
        "source": source_file or "对话",
        "scope": scope,
        "scope_label": scope_info[scope]["label"],
        "scope_icon": scope_info[scope]["icon"],
        "created": datetime.now().isoformat(),
        "status": "draft",
        "score": card_score,
        "content_preview": text[:200],
    }

    # ── 自动生成 L0/L1 三层（OpenViking 模式）──
    try:
        tiers = _tiering_mod.generate_tiers(text[:2000], title)
        card["l0_abstract"] = tiers["l0_abstract"]
        card["l1_overview"] = tiers["l1_overview"]
        card["l0_tokens"] = tiers["l0_tokens"]
        card["l1_tokens"] = tiers["l1_tokens"]
    except Exception:
        card["l0_abstract"] = title[:50] if title else text[:50]
        card["l1_overview"] = text[:200]

    # ── Grounded Claims: 捕获来源证据 ──
    try:
        from grounded_claims import capture_evidence
        evidence = capture_evidence(card)
        card["evidence"] = evidence
    except Exception:
        pass  # 证据捕获失败不阻塞卡片创建

    # 生成 Markdown
    card_md = generate_card_markdown(card)
    card["content_md"] = card_md

    return card, card_md


def generate_card_markdown(card):
    """生成 Obsidian 知识卡片 Markdown。"""
    lines = [
        f"# {card['icon']} {card['title']} — {card['type_label']}",
        "",
        f"> **类型：** {card['type_label']} ({card['type']})",
        f"> **来源：** {card['source']}",
        f"> **创建：** {card['created'][:10]}",
        f"> **状态：** {card['status']}",
        "",
        "---",
        "",
        "## 核心主张",
    ]
    for c in card['claims']:
        lines.append(f"- {c}")
    lines.append("")

    if card['tags']:
        lines.append("## 标签")
        lines.append(f"> {' '.join('#' + t for t in card['tags'])}")
        lines.append("")

    if card['links']:
        lines.append("## 相关笔记")
        for link in card['links']:
            lines.append(f"- [[{link}]]")
        lines.append("")

    lines.append("---")
    lines.append("*由知识蒸馏管道自动生成，状态: draft，请审核*")

    return '\n'.join(lines)


def save_card(card, card_md):
    """保存知识卡片到 Obsidian Inbox。"""
    store = _load_store()
    store["cards"].append(card)

    if card_md:
        safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', card['title'])[:40]
        filename = f"{card['id']}-{safe_title}.md"
        filepath = os.path.join(OBSIDIAN_INBOX, filename)

        os.makedirs(OBSIDIAN_INBOX, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(card_md)

        card["file"] = filepath

    _save_store(store)
    return card


def batch_distill():
    """扫描 Inbox 中未处理文件，自动蒸馏。"""
    store = _load_store()
    pending = []

    if not os.path.exists(OBSIDIAN_INBOX):
        return pending

    for fname in os.listdir(OBSIDIAN_INBOX):
        if not fname.endswith('.md') or fname.startswith('.'):
            continue
        # 检查是否已蒸馏
        fpath = os.path.join(OBSIDIAN_INBOX, fname)
        try:
            content = open(fpath, 'r', encoding='utf-8', errors='replace').read()
        except:
            continue

        # 已蒸馏的文件含有 KD- 前缀
        if 'KD-' in content[:50]:
            continue
        # 跳过过短的文件
        if len(content) < 50:
            continue

        rel = os.path.relpath(fpath, OBSIDIAN_ROOT)
        pending.append(rel)

    return pending


def generate_skill_skeleton(card):
    """从知识卡片生成 Skill 骨架。"""
    title = card['title']
    safe_name = re.sub(r'[^\w\-]', '-', title).lower()[:30]

    skill_dir = f"/var/minis/skills/{safe_name}"
    os.makedirs(skill_dir, exist_ok=True)

    skill_md = f"""# {title}

> 从知识卡片蒸馏生成的 Skill 骨架
> 类型：{card['type_label']} | 来源：{card['source']}

## 简介

{card['claims'][0] if card['claims'] else '待填写'}

## 核心主张

"""
    for c in card['claims']:
        skill_md += f"- {c}\n"

    skill_md += f"""
## 用法

- 触发条件：[待定义]
- 输入：[待定义]
- 输出：[待定义]

## 关联笔记

"""
    for link in card['links'][:5]:
        skill_md += f"- [[{link}]]\n"

    skill_md += f"""
## 知识卡片

- 来源卡片：{card['id']}
- 标签：{', '.join(card['tags'])}
"""

    with open(os.path.join(skill_dir, "SKILL.md"), 'w', encoding='utf-8') as f:
        f.write(skill_md)

    return skill_dir


# ═══════════════════════════════════════════════════
# SkillForge 借鉴：主动合成 (Active Trajectory Synthesis)
# ═══════════════════════════════════════════════════

def synthesize(topic, n_variants=3, model="agnes-2.5-pro"):
    """
    主动合成对抗案例，蒸馏成功/失败模式。
    SkillForge 核心机制：synthesize → distill → 双向学习。

    流程：
    1. 从 seed topic 生成变体（正向案例 + 对抗案例）
    2. 对比每个变体的处理路径
    3. 蒸馏成功模式（success_pattern）和失败模式（failure_pattern）
    4. 生成双向卡片

    用法：
        python3 obsidian-distill.py --synthesize "Agent 如何决定何时使用 MCP"
    """
    import subprocess

    # Step 1: 用 LLM 生成变体
    prompt = f"""你是一个知识工程专家。请基于以下主题，生成 {n_variants} 个变体案例，用于经验蒸馏。

主题：{topic}

对每个变体，请提供：
1. 【正向案例】{n_variants} 个：描述一个成功的处理场景，包含上下文、操作、结果
2. 【对抗案例】{n_variants} 个：描述一个容易出错的边界场景，包含陷阱、症状、根因

格式（严格 JSON 数组）：
```json
[
  {{"variant": 1, "type": "positive", "context": "...", "action": "...", "result": "...", "lesson": "成功的关键要素"}},
  ...
  {{"variant": 1, "type": "adversarial", "context": "...", "trap": "...", "symptom": "...", "root_cause": "...", "lesson": "避免此错误的教训"}}
]
```"""

    try:
        result = subprocess.run(
            ["python3", "/var/minis/shared/minis-cli", "model", "run",
             "--model", model, "--prompt", prompt],
            capture_output=True, text=True, timeout=120
        )
        variants_text = result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"⚠️ 无法调用 LLM 生成变体: {e}")
        print("   使用内置启发式生成")
        variants_text = _synthesize_heuristic(topic, n_variants)

    # Step 2: 解析变体 JSON
    import re as _re
    json_match = _re.search(r'```json\s*(.*?)\s*```', variants_text, _re.DOTALL)
    if json_match:
        try:
            variants = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            variants = []
    else:
        variants = []

    if not variants:
        print(f"⚠️ 未解析到有效变体，使用基础模式")
        variants = _synthesize_heuristic(topic, n_variants)

    # Step 3: 蒸馏双向卡片
    store = _load_store()
    cards_created = {"success": [], "failure": []}

    for v in variants:
        vtype = v.get("type", "adversarial")
        if vtype == "positive":
            card = _make_pattern_card(v, topic, "success")
            store["cards"].append(card)
            cards_created["success"].append(card["title"])
        else:
            card = _make_pattern_card(v, topic, "failure")
            store["cards"].append(card)
            cards_created["failure"].append(card["title"])

    _save_store(store)

    # 报告
    print(f"🧪 主动合成完成（SkillForge 借鉴）")
    print(f"   主题: {topic}")
    print(f"   成功模式: {len(cards_created['success'])} 张")
    for t in cards_created['success']:
        print(f"      ✅ {t}")
    print(f"   失败模式: {len(cards_created['failure'])} 张")
    for t in cards_created['failure']:
        print(f"      ❌ {t}")
    return cards_created


def _synthesize_heuristic(topic, n_variants):
    """内置启发式生成变体（当 LLM 不可用时）。"""
    variants = []
    for i in range(n_variants):
        variants.append({
            "variant": i+1, "type": "positive",
            "context": f"常规场景 #{i+1}：{topic}",
            "action": "按标准流程处理",
            "result": "成功完成",
            "lesson": f"在常规场景下，{topic} 的标准流程有效"
        })
    for i in range(n_variants):
        variants.append({
            "variant": i+1, "type": "adversarial",
            "context": f"边界场景 #{i+1}：{topic} 的异常输入",
            "trap": "输入偏离常规假设",
            "symptom": "处理结果不符合预期",
            "root_cause": f"未考虑到 {topic} 的边界条件",
            "lesson": f"处理 {topic} 时需要验证边界条件"
        })
    return variants


def _make_pattern_card(v, topic, mode):
    """从变体创建成功/失败模式卡片。"""
    icon = "✅" if mode == "success" else "❌"
    title = f"{icon} {topic} — {mode}模式 #{v.get('variant','?')}"
    scope = "global" if mode == "success" else "local"  # 成功模式偏全局，失败模式偏局部

    if mode == "success":
        claims = [
            f"场景: {v.get('context', '')}",
            f"操作: {v.get('action', '')}",
            f"结果: {v.get('result', '')}",
            f"关键要素: {v.get('lesson', '')}",
        ]
    else:
        claims = [
            f"陷阱: {v.get('trap', '')}",
            f"症状: {v.get('symptom', '')}",
            f"根因: {v.get('root_cause', '')}",
            f"教训: {v.get('lesson', '')}",
        ]

    card = {
        "id": f"SYN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}",
        "title": title,
        "type": "pattern",
        "type_label": "模式",
        "icon": icon,
        "claims": claims,
        "tags": [mode, "synthesize", topic[:10]],
        "source": f"synthesize/{topic[:30]}",
        "scope": scope,
        "scope_label": "全局诊断" if scope == "global" else "局部干预",
        "scope_icon": "🌐" if scope == "global" else "📍",
        "created": datetime.now().isoformat(),
        "status": "draft",
        "score": 70,
        "content_preview": ' '.join(claims[:2])[:200],
    }
    return card


def main():
    parser = argparse.ArgumentParser(description='知识蒸馏管道')
    parser.add_argument('--distill', '-d', help='蒸馏文本内容')
    parser.add_argument('--distill-file', '-f', help='蒸馏文件')
    parser.add_argument('--batch', '-b', action='store_true', help='批量蒸馏 Inbox')
    parser.add_argument('--pending', '-p', action='store_true', help='查看待蒸馏列表')
    parser.add_argument('--review', '-r', action='store_true', help='审核待确认的知识卡片')
    parser.add_argument('--approve', metavar='ID', help='批准指定知识卡片并归档')
    parser.add_argument('--archive-to', metavar='DIR', default='00-Inbox', help='归档目标目录（配合 --approve）')
    parser.add_argument('--export', '-e', action='store_true', help='导出所有知识卡片')
    parser.add_argument('--skill-from', help='从知识卡片生成 Skill 骨架')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    parser.add_argument('--synthesize', '-S', metavar='TOPIC',
                        help='SkillForge 借鉴：主动合成对抗案例 → 蒸馏成功/失败模式')
    parser.add_argument('--variants', '-V', type=int, default=3,
                        help='合成变体数量（配合 --synthesize，默认3）')
    parser.add_argument('--model', '-M', default='agnes-2.5-pro',
                        help='合成使用的模型（配合 --synthesize）')

    args = parser.parse_args()

    if args.distill is not None:
        card, card_md = distill(args.distill)
        if card is None:
            sys.exit(0)
        save_card(card, card_md)
        if args.json:
            print(json.dumps(card, ensure_ascii=False, indent=2))
        else:
            print(f"🧠 知识卡片已生成")
            print(f"   标题: {card['title']}")
            print(f"   类型: {card['icon']} {card['type_label']}")
            print(f"   主张: {len(card['claims'])} 条")
            print(f"   标签: {', '.join(card['tags'][:5])}")
            print(f"\n{card_md}")
        sys.exit(0)

    if args.distill_file:
        filepath = args.distill_file
        if not os.path.isabs(filepath):
            filepath = os.path.join(OBSIDIAN_ROOT, filepath)
        try:
            content = open(filepath, 'r', encoding='utf-8', errors='replace').read()
        except (OSError, PermissionError) as e:
            print(f"❌ {e}")
            sys.exit(1)
        card, card_md = distill(content, source_file=os.path.relpath(filepath, OBSIDIAN_ROOT))
        save_card(card, card_md)
        if args.json:
            print(json.dumps(card, ensure_ascii=False, indent=2))
        else:
            print(f"🧠 从 {filepath} 蒸馏完成")
            print(f"   标题: {card['title']}")
            print(f"   类型: {card['icon']} {card['type_label']}")
            print(f"   主张: {len(card['claims'])} 条")
            print(f"\n{card_md}")
        sys.exit(0)

    if args.batch:
        pending = batch_distill()
        if pending:
            print(f"📋 Inbox 中有 {len(pending)} 个文件可蒸馏")
            for p in pending[:10]:
                print(f"   📄 {p}")
        else:
            print("✅ Inbox 无待处理文件")
        sys.exit(0)

    if args.pending:
        store = _load_store()
        pending = [c for c in store.get("cards", []) if c.get("status") == "draft"]
        print(f"📋 待审核知识卡片: {len(pending)} 张")
        for c in pending[-10:]:
            print(f"   {c['icon']} {c['title']} [{c['type_label']}] — {c['source']}")
        sys.exit(0)

    if args.export:
        store = _load_store()
        cards = store.get("cards", [])
        print(f"📦 知识卡片存储: {len(cards)} 张")
        if cards:
            for c in cards[-20:]:
                status_icon = "📝" if c.get("status") == "draft" else "✅"
                print(f"   {status_icon} {c['icon']} {c['title']} [{c['type_label']}] — {c.get('created', '?')[:10]}")
        sys.exit(0)

    # 审核：列出待确认卡片，显示摘要
    if args.review:
        store = _load_store()
        pending = [c for c in store.get("cards", []) if c.get("status") == "draft"]
        if not pending:
            print("✅ 无待审核知识卡片")
            sys.exit(0)

        print(f"📋 待审核知识卡片: {len(pending)} 张\n")
        for i, c in enumerate(pending):
            print(f"  [{i}] {c['icon']} {c['title']} [{c['type_label']}]")
            print(f"       来源: {c.get('source', '?')}")
            print(f"       主张: {'; '.join(c.get('claims', [])[:2])}")
            print(f"       命令: --approve {c['id']}")
            print()

        print("批准命令示例:")
        print('  python3 obsidian-distill.py --approve CARD_ID')
        print('  python3 obsidian-distill.py --approve CARD_ID --archive-to "03-Resources/AI工具"')
        sys.exit(0)

    # 批准并归档
    if args.approve:
        store = _load_store()
        card = None
        for c in store.get("cards", []):
            if c["id"] == args.approve:
                card = c
                break
        if not card:
            print(f"❌ 未找到知识卡片: {args.approve}")
            sys.exit(1)

        # 确定归档目标
        archive_dir = args.archive_to or card.get("target_dir", "00-Inbox")
        if not archive_dir or archive_dir == "00-Inbox":
            # 自动推断目录
            title_tags = card.get("title", "") + ' '.join(card.get("tags", []))
            hints = [
                ("AI", "03-Resources/AI工具"),
                ("Agent", "03-Resources/AI工具"),
                ("公众号", "03-Resources/公众号文章"),
                ("MCP", "03-Resources/AI工具"),
                ("工具", "03-Resources/AI工具"),
                ("编程", "03-Resources/AI工具"),
                ("Obsidian", "03-Resources/AI工具"),
                ("大脑", "02-Areas/认知思考"),
                ("认知", "02-Areas/认知思考"),
                ("框架", "02-Areas/认知思考"),
                ("方法", "02-Areas/认知思考"),
                ("Agent", "03-Resources/AI工具"),
                ("Pi", "03-Resources/AI工具"),
            ]
            for kw, folder in hints:
                if kw in title_tags:
                    archive_dir = folder
                    break

        # 移动卡片文件
        card_file = card.get("file", "")
        if card_file and os.path.exists(card_file):
            target_path = os.path.join(OBSIDIAN_ROOT, archive_dir, os.path.basename(card_file))
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            os.rename(card_file, target_path)
            card["file"] = target_path
            card["archived"] = archive_dir

        # 状态机校验（draft→approved 合法，重复批准幂等，非法跳转拒绝）
        _transition(card, "approved", store=store)
        card["archived"] = archive_dir
        card["approved_at"] = datetime.now().isoformat()
        _save_store(store)

        print(f"✅ 已批准并归档")
        print(f"   {card['icon']} {card['title']}")
        print(f"   归档至: {archive_dir}/")
        print(f"   文件: {card.get('file', '?')}")
        sys.exit(0)

    if args.skill_from:
        store = _load_store()
        target = None
        for c in store.get("cards", []):
            if args.skill_from in c['title']:
                target = c
                break
        if not target:
            print(f"❌ 未找到知识卡片: {args.skill_from}")
            sys.exit(1)
        skill_dir = generate_skill_skeleton(target)
        print(f"✅ Skill 骨架已生成: {skill_dir}")
        print(f"   请编辑 {skill_dir}/SKILL.md 完成配置")
        sys.exit(0)

    # SkillForge 借鉴：主动合成对抗案例
    if args.synthesize:
        print(f"🧪 主动合成: {args.synthesize}（{args.variants} 组变体）")
        cards = synthesize(args.synthesize, n_variants=args.variants, model=args.model)
        if args.json:
            print(json.dumps(cards, ensure_ascii=False, indent=2))
        sys.exit(0)

    parser.print_help()


if __name__ == '__main__':
    main()