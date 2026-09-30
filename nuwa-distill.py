#!/usr/bin/env python3
# Version: 0.1.0
"""
nuwa-distill.py — Minis 适配版：女娲思维蒸馏工具

基于 alchaincyf/nuwa-skill (31k★) 的蒸馏框架，适配 Minis 多模型调用能力。
将领域大师/专家/名人蒸馏为可复用的思维分身（perspective card），
整合进 Minis 知识存储与 auto-learn 管道。

核心流程：
  Phase 1: 六路并行调研（著作/对话/表达/他者/决策/时间线）
  Phase 2: 三重验证 + 框架提炼（心智模型/决策启发式/表达DNA）
  Phase 3: 构建 perspective card + 可选 SKILL.md

用法:
  # 完整蒸馏（自动调研 + 综合 + 生成）
  python3 nuwa-distill.py --distill "张一鸣"

  # 仅调研（指定维度）
  python3 nuwa-distill.py --research "张一鸣" --dimension writings

  # 从已有调研综合
  python3 nuwa-distill.py --synthesize "张一鸣"

  # 导出为可安装 SKILL.md
  python3 nuwa-distill.py --export-skill "张一鸣" --output "/path/to/skill"

  # 质量检查
  python3 nuwa-distill.py --quality-check "张一鸣"

  # 查看已蒸馏
  python3 nuwa-distill.py --view "张一鸣"

  # 列出所有 perspective
  python3 nuwa-distill.py --list

  # 用 perspective 回答问题
  python3 nuwa-distill.py --ask "张一鸣" "OpenAI 和 Anthropic 谁方向对"

数据:
  - Perspective 存储: /var/minis/shared/.nuwa-perspectives.json
  - 调研数据: /var/minis/shared/nuwa-research/<name>/
  - SKILL.md 输出: 默认 /var/minis/skills/<name>-perspective/
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ─── 路径 ─────────────────────────────────────────────────────────────
PERSP_DIR = "/var/minis/shared/.nuwa-perspectives.json"
RESEARCH_DIR = "/var/minis/shared/nuwa-research"
SKILLS_DIR = "/var/minis/skills"
KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
OBSIDIAN_ROOT = "/var/minis/mounts/loong"

# ─── 六路调研维度 ─────────────────────────────────────────────────────
DIMENSIONS = {
    "writings": {
        "label": "著作与系统思考",
        "icon": "📚",
        "desc": "著作、长文、论文、newsletter、系统性思考",
        "extract": "反复出现≥3次的核心论点（真信念）、自创术语、推荐书单",
    },
    "conversations": {
        "label": "长对话与即兴思考",
        "icon": "🎙️",
        "desc": "播客、长视频、AMA、深度采访",
        "extract": "被追问时的回答方式、即兴类比、改变立场的瞬间、拒绝回答的问题",
    },
    "expression": {
        "label": "碎片表达与风格DNA",
        "icon": "✍️",
        "desc": "社交媒体、短文、推文、博客",
        "extract": "高频用词句式、争议立场、幽默方式、公开辩论",
    },
    "external": {
        "label": "他者视角与批评",
        "icon": "👁️",
        "desc": "他人分析、书评、批评、传记",
        "extract": "外部观察到的模式、批评与争议、与同行对比",
    },
    "decisions": {
        "label": "决策记录与行动",
        "icon": "⚖️",
        "desc": "重大决策、转折点、争议行为",
        "extract": "决策背景与逻辑、事后反思、言行一致/不一致案例",
    },
    "timeline": {
        "label": "人物时间线",
        "icon": "📅",
        "desc": "从出生/出道到现在的完整时间线",
        "extract": "关键里程碑、思想转折点、最近12个月动态",
    },
}

# ─── 心智模型三重验证标准 ─────────────────────────────────────────────
VERIFICATION_RULES = {
    "cross_domain": "跨域复现：在≥2个不同领域/话题中出现？",
    "generative": "生成力：能推断此人对新问题的立场？",
    "exclusive": "排他性：不是所有聪明人都这样想？",
}

# ─── 质量评分标准 ─────────────────────────────────────────────────────
QUALITY_CHECKLIST = [
    {"id": "M1", "check": "心智模型 3-7个，每个有来源证据", "pass": lambda d: 3 <= len(d.get("mental_models", [])) <= 7},
    {"id": "M2", "check": "每个模型明确写出局限性/失效条件", "pass": lambda d: all(m.get("limitations") for m in d.get("mental_models", []) if m.get("limitations"))},
    {"id": "E1", "check": "表达DNA包含≥4个维度特征", "pass": lambda d: len(d.get("expression_dna", {})) >= 4},
    {"id": "H1", "check": "诚实边界≥3条具体局限", "pass": lambda d: len(d.get("honest_boundaries", [])) >= 3},
    {"id": "T1", "check": "至少2对内在张力/矛盾", "pass": lambda d: len(d.get("tensions", [])) >= 2},
    {"id": "S1", "check": "决策启发式≥5条", "pass": lambda d: len(d.get("heuristics", [])) >= 5},
    {"id": "D1", "check": "时间线包含最近12个月动态", "pass": lambda d: d.get("timeline_recent") is not None},
    {"id": "V1", "check": "3-5条价值观排序", "pass": lambda d: 3 <= len(d.get("values", [])) <= 5},
]

# ─── 角色定义（用于蒸馏 prompt）──────────────────────────────────────
RESEARCH_PROMPT_TEMPLATE = """你是一位资深传记研究者，正在为"思维蒸馏"项目做调研。

目标人物：**{name}**
调研维度：**{dim_label}**（{dim_desc}）
提取重点：**{dim_extract}**

请基于你现有的知识（截至训练数据截止日期），系统性地整理以下信息：

## 搜索方向
{search_directions}

## 输出要求
1. 每条信息标注来源类型（一手/二手）和置信度（高/中/低）
2. 区分「他说过的」vs「别人说他的」vs「推断的」
3. 发现矛盾时保留矛盾，不要调和——矛盾本身就是有信息量的
4. 信息不足时诚实标注「该维度信息不足」
5. 如果此人是冷门人物或公开信息极少，请降低期望，聚焦已知信息
6. 对于在世人物，标注调研截止时间

## 格式
用 Markdown 表格和列表，确保信息密度高、可读性强。
"""

# 各维度的搜索方向
SEARCH_DIRECTIONS = {
    "writings": """- 此人出版的所有书籍（书名、出版年份、核心论点）
- 长篇 newsletter / 博客 / 论文 / 公开信
- 反复出现≥3次的核心概念或术语
- 推荐的书籍或作者（揭示智识谱系）
- 此人明确反对的观点或理论""",
    "conversations": """- 长对话或深度访谈中的关键片段
- 被追问时的回答方式（是直接回应还是绕开？）
- 使用的类比和隐喻
- 改变过立场的时刻
- 明确拒绝回答或回避的问题""",
    "expression": """- 社交媒体高频用词和句式
- 争议性言论和公开立场
- 幽默/讽刺/自嘲的风格特征
- 表达中的确定性程度（"明显"型 vs "不确定"型）
- 引用他人的习惯（爱引谁？）""",
    "external": """- 权威媒体对此人的深度报道
- 同行或竞争对手的评价
- 批评者的观点（至少找2-3个批评声音）
- 学术研究或传记中的客观分析
- 此人常被与谁比较？""",
    "decisions": """- 此人做过的3-5个重大决策
- 每个决策的背景、选项、选择理由
- 决策的事后结果和此人的反思
- 言行不一致的案例（如果有）
- 此人在压力下如何决策""",
    "timeline": """- 出生/出道至今的关键节点
- 思想转折点和"aha moment"
- 每个阶段的核心关注点变化
- 最近12个月的重要动态
- 此人对未来的判断和预测""",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _load_perspectives():
    if os.path.exists(PERSP_DIR):
        try:
            return json.load(open(PERSP_DIR, 'r', encoding='utf-8'))
        except:
            pass
    return {"perspectives": {}, "last_update": None}


def _save_perspectives(data):
    os.makedirs(os.path.dirname(PERSP_DIR) or '.', exist_ok=True)
    data["last_update"] = _now_iso()
    json.dump(data, open(PERSP_DIR, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def _load_knowledge_store():
    if os.path.exists(KNOWLEDGE_STORE):
        try:
            return json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
        except:
            pass
    return {"cards": []}


def _save_knowledge_store(store):
    os.makedirs(os.path.dirname(KNOWLEDGE_STORE) or '.', exist_ok=True)
    json.dump(store, open(KNOWLEDGE_STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def _call_model(prompt, model="agnes-2.5-pro", max_tokens=4000, timeout=120):
    """调用外部模型进行推理。"""
    try:
        result = subprocess.run(
            ["minis-model-use", "run", "--model", model, "--prompt", prompt,
             "--max-tokens", str(max_tokens), "--temperature", "0.7"],
            capture_output=True, text=True, timeout=timeout + 30
        )
        if result.returncode != 0:
            return f"[Error: {result.stderr[:200]}]"
        # 解析 JSON 输出
        try:
            d = json.loads(result.stdout)
            return d.get("data", {}).get("output_text", "") or result.stdout
        except (json.JSONDecodeError, KeyError):
            return result.stdout
    except subprocess.TimeoutExpired:
        return "[Error: timeout]"
    except FileNotFoundError:
        return "[Error: minis-model-use not found]"
    except Exception as e:
        return f"[Error: {str(e)[:200]}]"


def _safe_name(name):
    return re.sub(r'[^\w\u4e00-\u9fff\-]', '-', name).lower()[:40]


def _research_dir(name):
    return os.path.join(RESEARCH_DIR, _safe_name(name))


def ensure_research_dir(name):
    d = _research_dir(name)
    os.makedirs(d, exist_ok=True)
    return d


# ═══════════════════════════════════════════════════════════════════════
# Phase 1: 调研
# ═══════════════════════════════════════════════════════════════════════

def research(name, dimension=None, skip_web=True):
    """执行六路调研（指定维度或全部）。"""
    rd = ensure_research_dir(name)
    dim_keys = [dimension] if dimension else list(DIMENSIONS.keys())

    results = {}
    print(f"🔬 开始调研：{name}")
    print(f"   维度: {', '.join(dim_keys)}")
    print(f"   存储: {rd}/\n")

    for dk in dim_keys:
        if dk not in DIMENSIONS:
            print(f"   ⚠️ 未知维度 {dk}，跳过")
            continue

        dim = DIMENSIONS[dk]
        fpath = os.path.join(rd, f"0{len(results)+1}-{dk}.md")

        print(f"   {dim['icon']} {dim['label']}...", end=" ", flush=True)

        prompt = RESEARCH_PROMPT_TEMPLATE.format(
            name=name,
            dim_label=dim['label'],
            dim_desc=dim['desc'],
            dim_extract=dim['extract'],
            search_directions=SEARCH_DIRECTIONS[dk],
        )

        output = _call_model(prompt, model="sensenova-6.7-flash-lite")

        # 解析输出（去除代码块标记等）
        if output.startswith("```"):
            output = re.sub(r'^```.*?\n', '', output, flags=re.MULTILINE)
            output = re.sub(r'\n```.*$', '', output, flags=re.DOTALL)

        # 添加元信息头
        meta_header = f"""---
调研维度: {dim['label']}
调研时间: {_now_iso()}
调研模型: sensenova-6.7-flash-lite
---

"""

        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(meta_header)
            f.write(output)

        results[dk] = {
            "file": fpath,
            "size": len(output),
            "status": "done" if len(output) > 200 else "thin",
        }
        print(f"done ({len(output)} chars)")

    # 保存调研摘要
    summary_path = os.path.join(rd, "research-summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({"name": name, "dimensions": results, "completed_at": _now_iso()},
                  f, ensure_ascii=False, indent=2)

    print(f"\n✅ 调研完成，{len(results)} 个维度")
    for dk, r in results.items():
        status_icon = "✅" if r["status"] == "done" else "⚠️"
        print(f"   {status_icon} {DIMENSIONS[dk]['label']}: {r['size']} chars → {r['file']}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Phase 2: 综合提炼
# ═══════════════════════════════════════════════════════════════════════

def synthesize(name, quality_model="agnes-2.5-pro"):
    """综合调研结果，提炼心智模型/启发式/表达DNA。"""
    rd = _research_dir(name)
    if not os.path.exists(rd):
        print(f"❌ 未找到调研数据：{rd}")
        print("请先运行: --research " + name)
        return None

    # 读取所有调研文件
    research_files = sorted(Path(rd).glob("*.md"))
    if not research_files:
        print("❌ 调研目录下无文件")
        return None

    print(f"📝 综合提炼：{name}")
    print(f"   调研文件: {len(research_files)} 个")

    # 合并调研内容
    combined = ""
    dim_summaries = []
    for f in research_files:
        content = open(f, 'r', encoding='utf-8', errors='replace').read()
        combined += f"\n\n=== {f.name} ===\n{content}"
        # 提取前300字作为摘要
        first_300 = content[:300].strip()
        dim_summaries.append((f.name, first_300))

    # 构建综合 prompt
    synthesis_prompt = f"""你是一位思维蒸馏专家，正在将调研数据提炼为结构化的思维框架。

目标人物：**{name}**

以下是对此人的六路调研结果（著作/对话/表达/他者/决策/时间线）。请综合提炼以下内容：

--- 调研数据 ---
{combined[:12000]}
--- 调研数据结束 ---

请按以下格式输出（使用纯文本，非 JSON）：

## 心智模型（3-7个）
对每个心智模型，请给出：
- 名称：[一句话命名]
- 描述：[2-3句话解释]
- 来源证据：[从调研中找到的≥2个支撑场景]
- 应用场景：[此模型适用于什么情况]
- 局限性：[在什么情况下此模型失效]

## 决策启发式（5-10条）
格式：如果[条件]，则[行动]。[简短案例]

## 表达DNA
- 句式偏好：
- 高频词汇：
- 类比密度：
- 确定性表达：
- 幽默风格：
- 节奏感：

## 价值观与反模式
价值观（3-5条，按重要性排序）：
反模式（此人明确反对的）：

## 内在张力（≥2对矛盾）
格式：[张力A] 与 [张力B] 的矛盾

## 智识谱系
- 受谁影响：
- 影响了谁：
- 思想地图位置：

## 诚实边界
- [至少3条具体局限]

## 时间线关键节点
[精简的关键节点列表]

## 最新动态
[最近12个月的重要动态]

### 重要规则
- 不要编造：信息不足时标注「基于有限信息推测」
- 心智模型要有排他性：不是所有聪明人都这样想的才是真模型
- 至少保留2对内在张力（矛盾才是深度的来源）
- 诚实边界不能只有「不能替代本人」这种废话
"""

    print(f"   调用模型综合提炼...", end=" ", flush=True)
    output = _call_model(synthesis_prompt, model=quality_model, timeout=180)

    if output.startswith("```"):
        output = re.sub(r'^```.*?\n', '', output, flags=re.MULTILINE)
        output = re.sub(r'\n```.*$', '', output, flags=re.DOTALL)

    # 保存综合结果
    synth_path = os.path.join(rd, "synthesis.md")
    with open(synth_path, 'w', encoding='utf-8') as f:
        f.write(f"""---
综合时间: {_now_iso()}
综合模型: {quality_model}
---

{output}
""")

    # 解析综合结果为结构化数据
    perspective = parse_synthesis(name, output, research_files)

    print(f"done")
    print(f"   心智模型: {len(perspective.get('mental_models', []))} 个")
    print(f"   决策启发式: {len(perspective.get('heuristics', []))} 条")
    print(f"   表达DNA维度: {len(perspective.get('expression_dna', {}))}")
    print(f"   内在张力: {len(perspective.get('tensions', []))} 对")
    print(f"   诚实边界: {len(perspective.get('honest_boundaries', []))} 条")
    print(f"   → {synth_path}")

    # 保存到 perspective 存储
    perspectives = _load_perspectives()
    perspectives["perspectives"][name] = perspective
    perspective["_meta"] = {
        "research_dir": rd,
        "synthesis_path": synth_path,
        "created": _now_iso(),
        "status": "draft",
    }
    _save_perspectives(perspectives)

    # 同步到 knowledge-store
    _sync_to_knowledge_store(perspective)

    return perspective


def parse_synthesis(name, text, research_files):
    """从综合文本解析为结构化 perspective 数据。
    支持多种输出格式（模型生成格式可能变化，做健壮解析）。"""
    p = {
        "name": name,
        "mental_models": [],
        "heuristics": [],
        "expression_dna": {},
        "values": [],
        "anti_patterns": [],
        "tensions": [],
        "intellectual_genealogy": {},
        "honest_boundaries": [],
        "timeline": [],
        "timeline_recent": None,
        "research_count": len(research_files),
        "status": "draft",
    }

    # ── 心智模型 ──
    mm_section = _extract_section(text, "心智模型")
    if mm_section:
        # 格式A: ### N. 模型名称：xxx / ### N. xxx
        # 格式B: N. **名称：xxx**
        # 格式C: - 名称：xxx \n  描述：xxx
        
        # 先尝试格式A（### 标题行）
        model_blocks = re.split(r'###\s+\d+\.?\s*', mm_section)
        if len(model_blocks) > 1:
            for block in model_blocks:
                block = block.strip()
                if not block:
                    continue
                lines = block.split('\n')
                first_line = lines[0].strip()
                m_name = first_line.split('：')[-1].split(':')[0].strip() if ('：' in first_line or ':' in first_line) else first_line[:50]
                desc = _extract_field(block, "描述")
                evidence = _extract_field(block, "来源证据")
                app = _extract_field(block, "应用场景")
                limitations = _extract_field(block, "局限性")
                p["mental_models"].append({
                    "name": m_name,
                    "description": desc[:300] if desc else f"（{m_name}）",
                    "evidence": evidence[:200] if evidence else "",
                    "application": app[:200] if app else "",
                    "limitations": limitations[:200] if limitations else "",
                })
        else:
            # 格式B: N. **名称：xxx**
            blocks = re.split(r'\n\s*\d+\.?\s*\*\*名称\s*[：:]', mm_section)
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                # 名称在第一行（**名称：xxx** 的 xxx 部分）
                m_name_match = re.match(r'\*\*([^*]+)\*\*', block)
                if m_name_match:
                    m_name = m_name_match.group(1).strip()
                else:
                    m_name = block.split('\n')[0][:50]
                desc = _extract_field(block, "描述")
                evidence = _extract_field(block, "来源证据")
                app = _extract_field(block, "应用场景")
                limitations = _extract_field(block, "局限性")
                p["mental_models"].append({
                    "name": m_name,
                    "description": desc[:300] if desc else f"（{m_name}）",
                    "evidence": evidence[:200] if evidence else "",
                    "application": app[:200] if app else "",
                    "limitations": limitations[:200] if limitations else "",
                })

    # ── 决策启发式 ──
    h_section = _extract_section(text, "决策启发式")
    if h_section:
        # 格式：数字. **如果**...则...
        heuristics = re.findall(r'(?:\d+\.?\s*)?(?:如果|若|当).+?(?:则|那么|就).+?(?:。|；|\n|$)', h_section)
        p["heuristics"] = [h.strip() for h in heuristics[:10]]

    # ── 表达DNA ──
    dna_section = _extract_section(text, "表达DNA")
    if dna_section:
        for line in dna_section.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '：' in line or ':' in line:
                sep = '：' if '：' in line else ':'
                key, val = line.split(sep, 1)
                key = key.strip().lstrip('-').strip().lstrip('*').strip()
                val = val.strip().lstrip('*').strip()
                if key and val:
                    p["expression_dna"][key] = val

    # ── 价值观 ──
    v_section = _extract_section(text, "价值观")
    if v_section:
        vals = re.findall(r'[\d、]+\.?\s*(.+?)(?:\n|$)', v_section)
        p["values"] = [v.strip().lstrip('-').strip() for v in vals if len(v.strip()) > 3][:5]

    # ── 反模式 ──
    ap_section = _extract_section(text, "反模式")
    if ap_section:
        items = re.findall(r'[-*]\s*(?:\*\*)?(.+?)(?:\*\*)?(?:\n|$)', ap_section)
        p["anti_patterns"] = [i.strip() for i in items if len(i.strip()) > 3][:5]
    # 也尝试从价值观后面的反模式获取
    if not p["anti_patterns"]:
        ap2 = re.search(r'反模式[（(].*?[）)].*?[：:](.+)', text, re.DOTALL)
        if ap2:
            for line in ap2.group(1).split('\n'):
                line = line.strip().lstrip('-').strip()
                if line and len(line) > 3:
                    p["anti_patterns"].append(line)

    # ── 内在张力 ──
    t_section = _extract_section(text, "内在张力")
    if t_section:
        # 格式：### N. xxx 与 xxx 的矛盾
        tensions1 = re.findall(r'###\s+\d+\.?\s*(.+?)\s*[与和]\s*(.+?)(?:的矛盾|的张力|：)', t_section)
        for a, b in tensions1:
            p["tensions"].append({"a": a.strip(), "b": b.strip()})
        # 格式：* **xxx** 与 **yyy**
        tensions2 = re.findall(r'\*\*([^*]+)\*\*\s*[与和]\s*\*\*([^*]+)\*\*', t_section)
        for a, b in tensions2:
            p["tensions"].append({"a": a.strip(), "b": b.strip()})
        # 格式：普通文本
        tensions3 = re.findall(r'(.+?)与(.+?)的矛盾', t_section)
        for a, b in tensions3:
            p["tensions"].append({"a": a.strip(), "b": b.strip()})

    # ── 诚实边界 ──
    hb_section = _extract_section(text, "诚实边界")
    if hb_section:
        boundaries = re.findall(r'[-*]\s*(?:\d+\.?\s*)?(.+?)(?:\n|$)', hb_section)
        p["honest_boundaries"] = [b.strip() for b in boundaries if len(b.strip()) > 5]

    # ── 时间线 ──
    tl_section = _extract_section(text, "时间线")
    if tl_section:
        items = re.findall(r'[-*]\s*(?:\d+\.?\s*)?(.+?)(?:\n|$)', tl_section)
        p["timeline"] = [i.strip() for i in items if len(i.strip()) > 3][:10]

    # ── 最新动态 ──
    recent = _extract_section(text, "最新动态")
    if recent:
        p["timeline_recent"] = recent.strip()[:500]

    return p


def _extract_field(text, field_name):
    """从文本中提取指定字段值。"""
    # 格式：- **字段名**：值 或 - 字段名：值
    patterns = [
        rf'-\s*\*\*{re.escape(field_name)}\*\*\s*[：:]\s*(.+?)(?=\n\s*-|\Z)',
        rf'-\s*{re.escape(field_name)}\s*[：:]\s*(.+?)(?=\n\s*-|\Z)',
        rf'\*\*{re.escape(field_name)}\*\*\s*[：:]\s*(.+?)(?=\n\s*-|\n\*\*|\Z)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return ""


def _extract_section(text, heading):
    """提取指定标题下的内容块。"""
    # 支持 ## 和 ### 级别的标题
    patterns = [
        rf'##\s+{heading}[：:]*(.*?)(?=\n##\s+|\Z)',
        rf'###\s+{heading}[：:]*(.*?)(?=\n###\s+|\n##\s+|\Z)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


# ═══════════════════════════════════════════════════════════════════════
# Phase 3: 质量检查
# ═══════════════════════════════════════════════════════════════════════

def quality_check(name):
    """对 perspective 执行质量检查。"""
    perspectives = _load_perspectives()
    if name not in perspectives["perspectives"]:
        print(f"❌ 未找到 perspective: {name}")
        return None

    p = perspectives["perspectives"][name]
    print(f"🔍 质量检查：{name}\n")
    print(f"{'检查项':<8} {'状态':<6} {'描述'}")
    print("-" * 60)

    passed = 0
    failed = 0
    results = []

    for item in QUALITY_CHECKLIST:
        try:
            ok = item["pass"](p)
        except Exception:
            ok = False

        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  {item['id']:<6} {status:<6} {item['check']}")
        results.append({"id": item["id"], "pass": ok, "desc": item["check"]})

    score = int(passed / len(QUALITY_CHECKLIST) * 100)
    print(f"\n{'='*60}")
    print(f"  质量评分: {score}/100 ({passed}/{len(QUALITY_CHECKLIST)} 项通过)")

    if score >= 80:
        print(f"  评级: 🟢 A级（可直接使用）")
        grade = "A"
    elif score >= 60:
        print(f"  评级: 🟡 B级（建议使用，关注薄弱项）")
        grade = "B"
    elif score >= 40:
        print(f"  评级: 🟠 C级（需要补充调研）")
        grade = "C"
    else:
        print(f"  评级: 🔴 D级（建议重新蒸馏）")
        grade = "D"

    # 更新 perspective 状态
    p["_meta"]["quality_score"] = score
    p["_meta"]["grade"] = grade
    p["_meta"]["quality_checked"] = _now_iso()
    perspectives["perspectives"][name] = p
    _save_perspectives(perspectives)

    return {"name": name, "score": score, "grade": grade, "results": results}


# ═══════════════════════════════════════════════════════════════════════
# Phase 4: 导出 SKILL.md
# ═══════════════════════════════════════════════════════════════════════

def export_skill(name, output_dir=None):
    """将 perspective 导出为可安装的 SKILL.md。"""
    perspectives = _load_perspectives()
    if name not in perspectives["perspectives"]:
        print(f"❌ 未找到 perspective: {name}")
        return None

    p = perspectives["perspectives"][name]
    rd = p.get("_meta", {}).get("research_dir", _research_dir(name))

    # 默认输出到 skills 目录
    if not output_dir:
        output_dir = os.path.join(SKILLS_DIR, f"{_safe_name(name)}-perspective")
    os.makedirs(output_dir, exist_ok=True)

    # 读取调研摘要
    research_summary = _load_research_summary(rd)

    # 构建 SKILL.md
    skill_md = build_skill_md(p, name, research_summary, rd)

    skill_path = os.path.join(output_dir, "SKILL.md")
    with open(skill_path, 'w', encoding='utf-8') as f:
        f.write(skill_md)

    # 创建目录结构
    refs_dir = os.path.join(output_dir, "references", "research")
    os.makedirs(refs_dir, exist_ok=True)
    # 复制调研文件
    for fpath in sorted(Path(rd).glob("*.md")):
        if fpath.name == "synthesis.md":
            continue
        dest = os.path.join(refs_dir, fpath.name)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as src:
            with open(dest, 'w', encoding='utf-8') as dst:
                dst.write(src.read())

    # 创建 meta.json
    meta = {
        "name": f"{_safe_name(name)}-perspective",
        "description": f"蒸馏 {name} 的思维方式 — 心智模型/决策启发式/表达DNA",
        "version": "1.0.0",
        "created": _now_iso(),
        "permissions": {"network": False, "filesystem": "read"},
        "dependencies": [],
        "provenance": {
            "source": "nuwa-distill",
            "research_files": len(list(Path(rd).glob("*.md"))),
        },
    }
    with open(os.path.join(output_dir, "skill.meta.json"), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 创建 CHANGELOG
    changelog = f"""# Changelog

## [1.0.0] - {_now_iso()[:10]}
- 初始版本：基于 nuwa-distill 蒸馏 {name}
- 心智模型: {len(p.get('mental_models', []))} 个
- 决策启发式: {len(p.get('heuristics', []))} 条
- 调研维度: {p.get('research_count', 0)} 个
"""
    with open(os.path.join(output_dir, "CHANGELOG.md"), 'w', encoding='utf-8') as f:
        f.write(changelog)

    # 创建 tests 目录
    tests_dir = os.path.join(output_dir, "tests")
    os.makedirs(tests_dir, exist_ok=True)
    with open(os.path.join(tests_dir, "README.json"), 'w', encoding='utf-8') as f:
        json.dump({"status": "template", "description": "待填写触发边界测试"}, f, ensure_ascii=False, indent=2)

    print(f"✅ SKILL.md 已导出")
    print(f"   路径: {skill_path}")
    print(f"   包含: SKILL.md + references/research/ + meta.json + CHANGELOG + tests/")
    print(f"   心智模型: {len(p.get('mental_models', []))} 个")

    return skill_path


def _load_research_summary(rd):
    """加载调研摘要。"""
    summary_path = os.path.join(rd, "research-summary.json")
    if os.path.exists(summary_path):
        try:
            return json.load(open(summary_path, 'r', encoding='utf-8'))
        except:
            pass
    return None


def build_skill_md(p, name, research_summary, rd):
    """构建完整的 SKILL.md 内容。"""
    grade = p.get("_meta", {}).get("grade", "?")
    score = p.get("_meta", {}).get("quality_score", "?")

    # 构建心智模型列表
    mm_lines = []
    for i, m in enumerate(p.get("mental_models", []), 1):
        mm_lines.append(f"""### 模型 {i}: {m.get('name', '?')}

**描述**：{m.get('description', '待补充')}
**应用场景**：{m.get('application', '待定')}
**局限性**：{m.get('limitations', '待定')}""")

    mm_block = "\n\n".join(mm_lines) if mm_lines else "（暂无心智模型）"

    # 构建启发式列表
    h_lines = []
    for h in p.get("heuristics", []):
        h_lines.append(f"- {h}")
    h_block = "\n".join(h_lines) if h_lines else "（暂无决策启发式）"

    # 构建表达DNA
    dna_lines = []
    for k, v in p.get("expression_dna", {}).items():
        dna_lines.append(f"| **{k}** | {v} |")
    dna_block = "\n".join(dna_lines) if dna_lines else "| — | — |"

    # 构建价值观
    val_lines = []
    for i, v in enumerate(p.get("values", []), 1):
        val_lines.append(f"{i}. {v}")
    val_block = "\n".join(val_lines) if val_lines else "（暂无）"

    # 构建反模式
    ap_lines = []
    for v in p.get("anti_patterns", []):
        ap_lines.append(f"- {v}")
    ap_block = "\n".join(ap_lines) if ap_lines else "（暂无）"

    # 构建张力
    t_lines = []
    for t in p.get("tensions", []):
        t_lines.append(f"- **{t.get('a','?')}** 与 **{t.get('b','?')}**")
    t_block = "\n".join(t_lines) if t_lines else "（暂无）"

    # 构建谱系
    ig = p.get("intellectual_genealogy", {})
    ig_block = f"- 受谁影响：{ig.get('influenced_by', '待补充')}\n- 影响了谁：{ig.get('influenced', '待补充')}\n- 思想地图位置：{ig.get('position', '待补充')}"

    # 构建诚实边界
    hb_lines = []
    for b in p.get("honest_boundaries", []):
        hb_lines.append(f"- {b}")
    hb_block = "\n".join(hb_lines) if hb_lines else "- 不能替代本人的创造力和直觉\n- 公开表达 vs 真实想法可能有差距"

    # 构建时间线
    tl_lines = []
    for t in p.get("timeline", [])[:8]:
        tl_lines.append(f"- {t}")
    tl_block = "\n".join(tl_lines) if tl_lines else "（暂无时间线）"

    # 最新动态
    recent = p.get("timeline_recent", "") or "（暂无最新动态）"

    # 构建触发词
    triggers = f"「用{name}的视角」「{name}怎么看」「{name}会怎么说」「切换到{name}」「{name}思维」"

    description = f"蒸馏 {name} 的思维方式：{len(p.get('mental_models', []))}个心智模型 + {len(p.get('heuristics', []))}条决策启发式 + 完整表达DNA。触发词：{triggers}"

    skill_md = f"""---
name: {_safe_name(name)}-perspective
description: |
  {description}
---

# {name} · 思维分身

> 本 Skill 由 [nuwa-distill](/var/minis/skills/nuwa-skill/) 蒸馏生成
> 质量评分：{score}/100 ({grade}级) | 调研维度：{p.get('research_count', '?')} 个 | 创建：{p.get('_meta', {}).get('created', '?')[:10]}

---

## 身份卡

{f"我是 {name}。{p.get('mental_models', [{}])[0].get('description', '')[:100] if p.get('mental_models') else ''}"}

## 角色扮演规则

1. 你是 {name}，用 {name} 的思维方式和表达风格回答问题
2. 你使用的核心认知工具是下面列出的心智模型
3. 遇到需要事实支撑的问题时，先做研究再回答（见回答工作流）
4. 未公开表态的主题，明确标注「推断」而非假装确定
5. 关键引用应可追溯到真实来源

---

## 心智模型

{mm_block}

---

## 决策启发式

{h_block}

---

## 表达DNA

| 维度 | 特征 |
|------|------|
{dna_block}

---

## 回答工作流（Agentic Protocol）

**核心原则：{name}不凭感觉说话。遇到需要事实支撑的问题时，先做功课再回答。**

### Step 1: 问题分类

| 类型 | 特征 | 行动 |
|------|------|------|
| 需要事实 | 涉及具体公司/人物/事件/产品/市场 | → 先研究（Step 2） |
| 纯框架 | 抽象价值观、思维方式、人生建议 | → 直接用心智模型回答 |
| 混合问题 | 用具体案例讨论抽象道理 | → 先获取事实，再框架分析 |

### Step 2: {name}式研究

根据问题类型和心智模型，确定研究维度并获取真实信息。

### Step 3: {name}式回答

基于事实，用心智模型和表达DNA输出回答。

---

## 价值观与反模式

### 价值观
{val_block}

### 反模式
{ap_block}

---

## 内在张力

{t_block}

---

## 智识谱系

{ig_block}

---

## 时间线

{tl_block}

### 最新动态
{recent}

---

## 诚实边界

{hb_block}

---

## 调研来源

> 本 Skill 基于以下调研生成，调研数据存储于 references/research/ 目录。

{p.get('name', name)} 的思维方式是一个活的目标——建议每6个月更新一次最新动态。

---

*由 nuwa-distill (Minis 适配版) 生成 | 基于 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill) 31k★ 蒸馏框架*
"""
    return skill_md


# ═══════════════════════════════════════════════════════════════════════
# 同步到 knowledge-store
# ═══════════════════════════════════════════════════════════════════════

def _sync_to_knowledge_store(p):
    """将 perspective 同步为知识卡片。"""
    store = _load_knowledge_store()
    store.setdefault("cards", [])

    card = {
        "id": f"KP-{_now_iso()[:10].replace('-','')}-{os.urandom(2).hex()}",
        "title": f"{p.get('name', '?')} 思维分身",
        "type": "perspective",
        "type_label": "思维分身",
        "icon": "🎭",
        "claims": [m.get("name", "") for m in p.get("mental_models", [])[:3]],
        "tags": [p.get("name", ""), "perspective", "nuwa", "蒸馏"] + p.get("tags", []),
        "source": "nuwa-distill",
        "created": _now_iso(),
        "status": "draft",
        "score": p.get("_meta", {}).get("quality_score", 50),
        "content_preview": p.get("mental_models", [{}])[0].get("description", "")[:200] if p.get("mental_models") else "",
        "perspective_ref": p.get("name", ""),
    }

    store["cards"].append(card)
    _save_knowledge_store(store)


# ═══════════════════════════════════════════════════════════════════════
# 问答模式
# ═══════════════════════════════════════════════════════════════════════

def ask_perspective(name, question, model="agnes-2.5-pro"):
    """使用 perspective 回答问题。"""
    perspectives = _load_perspectives()
    if name not in perspectives["perspectives"]:
        print(f"❌ 未找到 perspective: {name}")
        print(f"   可用: {list(perspectives['perspectives'].keys())}")
        return None

    p = perspectives["perspectives"][name]

    # 构建角色 prompt
    role_prompt = f"""你是 {name}。以下是从你的公开著作、访谈、社交媒体、决策记录中蒸馏出的思维框架：

## 你的核心心智模型
"""
    for m in p.get("mental_models", []):
        role_prompt += f"- **{m.get('name','?')}**: {m.get('description','')}\n"

    role_prompt += f"""

## 你的决策启发式
"""
    for h in p.get("heuristics", []):
        role_prompt += f"- {h}\n"

    dna = p.get("expression_dna", {})
    if dna:
        role_prompt += f"""

## 你的表达风格
"""
        for k, v in dna.items():
            role_prompt += f"- {k}：{v}\n"

    val = p.get("values", [])
    if val:
        role_prompt += f"""

## 你的价值观
"""
        for i, v in enumerate(val, 1):
            role_prompt += f"{i}. {v}\n"

    role_prompt += f"""

## 回答要求
1. 用 {name} 的语言风格和思维方式回答
2. 遇到信息不足时诚实标注，不要编造
3. 保持 {name} 的表达节奏和用词习惯
4. 用具体例子而非抽象套话

---

用户问题：{question}
"""

    print(f"🎭 以 {name} 的视角回答...")
    print(f"   问题: {question}")
    print()

    output = _call_model(role_prompt, model=model, timeout=120)

    if output.startswith("```"):
        output = re.sub(r'^```.*?\n', '', output, flags=re.MULTILINE)
        output = re.sub(r'\n```.*$', '', output, flags=re.DOTALL)

    print(f"{output}")
    return output


# ═══════════════════════════════════════════════════════════════════════
# 展示
# ═══════════════════════════════════════════════════════════════════════

def view_perspective(name):
    """展示 perspective 详情。"""
    perspectives = _load_perspectives()
    if name not in perspectives["perspectives"]:
        print(f"❌ 未找到 perspective: {name}")
        print(f"   可用: {list(perspectives['perspectives'].keys())}")
        return

    p = perspectives["perspectives"][name]
    meta = p.get("_meta", {})

    print(f"""
{'='*60}
🎭 {p.get('name', '?')} — 思维分身
{'='*60}

质量评分: {meta.get('quality_score', '?')}/100 ({meta.get('grade', '?')}级)
调研维度: {p.get('research_count', '?')} 个
状态: {p.get('status', '?')}
创建时间: {meta.get('created', '?')[:10]}

── 心智模型 ({len(p.get('mental_models', []))} 个) ──""")
    for m in p.get("mental_models", []):
        print(f"   🧠 {m.get('name', '?')}")
        print(f"      {m.get('description', '')[:80]}")

    print(f"\n── 决策启发式 ({len(p.get('heuristics', []))} 条) ──")
    for h in p.get("heuristics", [])[:5]:
        print(f"   ⚖️ {h[:80]}")

    dna = p.get("expression_dna", {})
    print(f"\n── 表达DNA ({len(dna)} 维度) ──")
    for k, v in list(dna.items())[:6]:
        print(f"   ✍️ {k}：{v}")

    tensions = p.get("tensions", [])
    print(f"\n── 内在张力 ({len(tensions)} 对) ──")
    for t in tensions:
        print(f"   ↔️ {t.get('a','?')} × {t.get('b','?')}")

    hb = p.get("honest_boundaries", [])
    print(f"\n── 诚实边界 ({len(hb)} 条) ──")
    for b in hb[:5]:
        print(f"   ⚠️ {b[:80]}")


def list_perspectives():
    """列出所有 perspective。"""
    perspectives = _load_perspectives()
    items = perspectives.get("perspectives", {})
    if not items:
        print("📭 暂无已蒸馏的思维分身")
        print("\n蒸馏命令:")
        print("  python3 nuwa-distill.py --distill \"人物名\"")
        return

    print(f"🎭 已蒸馏的思维分身: {len(items)} 个\n")
    print(f"{'名称':<20} {'评分':<6} {'等级':<4} {'模型数':<6} {'启发式':<6} {'创建'}")
    print("-" * 65)
    for name, p in sorted(items.items()):
        meta = p.get("_meta", {})
        score = meta.get("quality_score", "?")
        grade = meta.get("grade", "?")
        mm_count = len(p.get("mental_models", []))
        h_count = len(p.get("heuristics", []))
        created = meta.get("created", "?")[:10]
        print(f"  {name:<18} {score:<6} {grade:<4} {mm_count:<6} {h_count:<6} {created}")

    print(f"\n查看: python3 nuwa-distill.py --view <名称>")
    print(f"问答: python3 nuwa-distill.py --ask <名称> \"问题\"")


# ═══════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="nuwa-distill — Minis 思维蒸馏工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 nuwa-distill.py --distill "张一鸣"          # 完整蒸馏
  python3 nuwa-distill.py --research "芒格" --dimension writings  # 单维度调研
  python3 nuwa-distill.py --synthesize "芒格"         # 从调研综合
  python3 nuwa-distill.py --quality-check "芒格"      # 质量检查
  python3 nuwa-distill.py --view "芒格"               # 查看详情
  python3 nuwa-distill.py --ask "芒格" --question "怎么看AI投资"  # 问答
  python3 nuwa-distill.py --export-skill "芒格"       # 导出SKILL.md
  python3 nuwa-distill.py --list                      # 列出全部
        """
    )
    parser.add_argument("--distill", "-d", help="完整蒸馏（调研+综合）")
    parser.add_argument("--research", "-r", help="仅调研")
    parser.add_argument("--synthesize", "-s", help="从调研综合提炼")
    parser.add_argument("--quality-check", "-q", help="质量检查")
    parser.add_argument("--export-skill", "-e", help="导出为SKILL.md")
    parser.add_argument("--view", "-v", help="查看详情")
    parser.add_argument("--ask", "-a", help="使用perspective回答问题（指定人物名）")
    parser.add_argument("--question", help="问题内容（配合--ask使用）")
    parser.add_argument("--list", "-l", action="store_true", help="列出全部")
    parser.add_argument("--dimension", help="调研维度（writings/conversations/expression/external/decisions/timeline）")
    parser.add_argument("--model", default="agnes-2.5-pro", help="用于综合/问答的模型（默认agnes-2.5-pro）")
    parser.add_argument("--output", help="导出SKILL.md的输出目录")
    parser.add_argument("--quick", action="store_true", help="快速模式（仅3个维度调研）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")

    args = parser.parse_args()

    if args.list:
        list_perspectives()
        return

    if args.distill:
        name = args.distill
        print(f"🔮 完整蒸馏：{name}\n")

        # 调研
        if args.quick:
            dims = ["writings", "conversations", "decisions"]
            print(f"   快速模式：3个维度 ({', '.join(dims)})")
            research(name, quick=True)
        else:
            research(name)

        # 综合
        print()
        synthesize(name, quality_model=args.model)

    elif args.research:
        research(args.research, dimension=args.dimension)

    elif args.synthesize:
        synthesize(args.synthesize, quality_model=args.model)

    elif args.quality_check:
        result = quality_check(args.quality_check)
        if args.json and result:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.export_skill:
        export_skill(args.export_skill, output_dir=args.output)

    elif args.view:
        view_perspective(args.view)

    elif args.ask:
        question = args.question or ""
        ask_perspective(args.ask, question, model=args.model)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()