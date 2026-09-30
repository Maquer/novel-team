#!/usr/bin/env python3
# Version: 0.1.0
"""
skill-eval-gate.py — Skill 评测门禁 v5 (Gate-Based Scoring)

v4 → v5 变更：
- Trigger Eval 新增 LLM 模式（--llm / --trigger-eval --llm）
  用 minis-model-use 做语义触发匹配，单次批量调用，支持速率限制自动重试
  LLM 模式召回率 100% vs 确定性模式 60%（ponytail 实测）

用法:
  python3 skill-eval-gate.py run                     # 所有 Skill（含确定性断言）
  python3 skill-eval-gate.py run <name>              # 单个 Skill
  python3 skill-eval-gate.py run --strict            # 严格模式
  python3 skill-eval-gate.py run --meta-skill        # 含三维度质量卡
  python3 skill-eval-gate.py run --trigger-eval      # 含触发评测（确定性）
  python3 skill-eval-gate.py run --trigger-eval --llm  # 含触发评测（LLM语义匹配）
  python3 skill-eval-gate.py trigger-eval            # 所有 Skill 确定性触发评测
  python3 skill-eval-gate.py trigger-eval <name>     # 单个 Skill 确定性触发评测
  python3 skill-eval-gate.py trigger-eval --llm      # 所有 Skill LLM 触发评测
  python3 skill-eval-gate.py trigger-eval <name> --llm # 单个 Skill LLM 触发评测
  python3 skill-eval-gate.py meta-skill              # 三维度质量卡
  python3 skill-eval-gate.py meta-skill <name>       # 单个 Skill 三维度
  python3 skill-eval-gate.py report
  python3 skill-eval-gate.py json
"""

import argparse
import logging

logger = logging.getLogger(__name__)
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SKILLS_DIR = "/var/minis/skills"
REPORT_PATH = "/var/minis/shared/.skill-eval-report.json"

# ─── 09-20 新：能力边界自披露（对齐 avoid-ai-writing PROOF.md 模式） ───
# 每次 run 报告强制打印，明说"这个评分不工作"不藏着
CAPABILITY_BOUNDARY = """
════════════════════════════════════════════════════════════════════════
  ⚠️ 能力边界自披露（对齐 avoid-ai-writing PROOF.md 模式 · 09-20 加）
  ─────────────────────────────────────────────────────────────────────
  本评分是启发式规则匹配，不是真值。已知盲区：
  1. FME/HAB 用中文+英文正则启发式打分，非语义理解
     (archify 实测：FME 2/10 但失败机制编码是全库最强——假阴性)
  2. 断言 A01-A06 是关键词存在性检查，不验证语义正确性
  3. Trigger Eval 确定性匹配 F1 上限约 84%（49 条语料实测）
     剩余 16 skill 无语料、3 缺负例，Precision/Recall 有偏
  4. Meta-skill 打分对英文 skill 有假阴性风险（09-19 已修 FME/HAB）
  → 分数 = 结构合规度下限，不是质量真值。
════════════════════════════════════════════════════════════════════════
"""


def _count_fluff(text):
    patterns = [r'\b建议\b', r'可以考虑', r'灵活把握', r'视情况而定', r'根据情况',
                r'灵活应用', r'灵活处理', r'酌情', r'适当.*考虑', r'酌情考虑']
    count = 0
    for p in patterns:
        count += len(re.findall(p, text))
    return count


# ──────────────────────────────────────────
# Meta-Skill 三维度（SkillLens 论文借鉴）
# 来源：从实测中归纳，判准率 46.4%→73.8%
# 参考：AI渐渐《SkillLens 实现》
# ──────────────────────────────────────────

def _score_failure_mechanism_encoding(text):
    """
    FME: Failure Mechanism Encoding（失败机制编码）
    核心：不只是说"失败了"，而是编码"为什么失败"。
    高质量 FME 特征：
      - 因果链：`因为X所以Y` / `根因`；EN: causes / leads to / results in
      - 具体失败模式：`超时→重试` / `空值→跳过`；EN: if fails then / on error retry
      - 失败模式库：多种失败场景对应处理；EN: failure modes / edge cases / anti-patterns
      - 回退路径：兜底逻辑；EN: fallback / fall back / safety net
    ⚠️ 09-19 修：加英文同义词表（原中文正则对英文 skill 只能命中 fallback 1 词得 1/10，
      archify 假阴性实锤——其失败机制编码是全库最强）
    """
    score = 0
    hits = []
    # 因果链关键词（中文 + 英文）
    causal_cn = len(re.findall(r'(因为|由于|原因是|根因|根源|导致|因此|从而|使得|引发)', text))
    causal_en = len(re.findall(r'\b(causes?|caused by|leads? to|results? in|results? from|due to|because of|thereby|consequently|thus)\b', text, re.IGNORECASE))
    if causal_cn >= 1:
        score += 1
        hits.append(f"因果链 ({causal_cn}处)")
    elif causal_en >= 1:
        score += 1
        hits.append(f"因果链EN ({causal_en}处)")
    if causal_cn >= 2 or causal_en >= 2:
        score += 1
        hits.append("因果链丰富")

    # 具体失败模式（if-fail → then 结构；中文 + 英文）
    fail_then_cn = len(re.findall(r'(如果.*失败.*则|如果.*错误.*则|失败.*时.*应|出错.*时.*应|异常.*时.*应)', text))
    fail_then_en = len(re.findall(r'(if\s+\w*\s*(?:fails?|errors?|times? out).*then|on\s+(?:error|failure|timeout).*\b(?:retry|skip|fallback|abort|halt|stop)\b)', text, re.IGNORECASE))
    fail_then = fail_then_cn + fail_then_en
    if fail_then >= 1:
        score += 1
        hits.append(f"if-fail→then ({fail_then}处)")
    if fail_then >= 2:
        score += 1
        hits.append("if-fail→then 丰富")

    # 失败模式库（多个失败场景；中文 + 英文）
    failure_list_cn = len(re.findall(r'(失败场景|失败模式|错误场景|异常场景)', text))
    failure_list_en = len(re.findall(r'\b(?:failure\s+modes?|failure\s+cases?|error\s+cases?|edge\s+cases?|anti-patterns?|known\s+failures?|common\s+pitfalls?)\b', text, re.IGNORECASE))
    if failure_list_cn >= 1:
        score += 1
        hits.append(f"失败模式库 ({failure_list_cn}处)")
    elif failure_list_en >= 1:
        score += 1
        hits.append(f"失败模式库EN ({failure_list_en}处)")
    if failure_list_cn + failure_list_en >= 2:
        score += 1
        hits.append("失败场景丰富")

    # 回退路径（中文 + 英文）
    fallback_cn = len(re.findall(r'(回退|降级|备选|兜底|容错)', text))
    fallback_en = len(re.findall(r'\b(fallback|falls? back|fall back|degrade|degradation|alternative|safety net|graceful)\b', text, re.IGNORECASE))
    if fallback_cn + fallback_en >= 1:
        score += 1
        hits.append(f"回退路径 ({fallback_cn+fallback_en}处)")
    if fallback_cn + fallback_en >= 2:
        score += 1
        hits.append("回退方案丰富")

    return min(score, 10), hits

def _score_actionable_specificity(text):
    """
    AS: Actionable Specificity（可执行具体性）
    核心：步骤是否引用具体参数/命令/格式/工具，而非泛泛描述。
    高质量 AS 特征：
      - 命令/参数：`--flag` / `path=` / `api-key`
      - 格式/模板：JSON schema、表格模板、output format
      - 具体数字：token数、字符数、行数、大小限制
      - 工具/函数名：引用具体的工具或函数
    """
    score = 0
    hits = []
    # 代码块/内联代码
    code_blocks = len(re.findall(r'```', text)) // 2
    inline_code = len(re.findall(r'`[^`\n]+`', text))
    if code_blocks >= 1:
        score += 1
        hits.append(f"代码块 {code_blocks}处")
    if inline_code >= 5:
        score += 1
        hits.append(f"内联代码 {inline_code}处")
    if inline_code >= 15:
        score += 1
        hits.append("内联代码丰富")
    # 命令参数
    cmd_args = len(re.findall(r'(--[a-zA-Z]|-[a-z]\s|path=|output=|input=|--json|--output)', text))
    if cmd_args >= 3:
        score += 1
        hits.append(f"命令参数 {cmd_args}处")
    if cmd_args >= 10:
        score += 1
        hits.append("命令参数丰富")
    # 格式模板（JSON/YAML/table）
    templates = len(re.findall(r'(\{.*\}|\[.*\]|\|.*\|)', text))
    if templates >= 3:
        score += 1
        hits.append(f"格式模板 {templates}处")
    if templates >= 10:
        score += 1
        hits.append("格式模板丰富")
    # 具体数字约束
    numeric = len(re.findall(r'\b\d{2,}\b', text))
    if numeric >= 5:
        score += 1
        hits.append(f"具体数字 {numeric}处")
    if numeric >= 20:
        score += 1
        hits.append("具体数字丰富")
    return min(score, 10), hits


def _score_high_risk_blacklist(text):
    """
    HAB: High-Risk Action Blacklist（高风险动作黑名单）
    核心：不是笼统说"不要这样做"，而是明确禁止具体的有害行为。
    高质量 HAB 特征：
      - 具体禁止项：`不要调用 X` / `禁止写死 Y`；EN: Never / Do not / must not
      - 反例模式：明确列出"反例"或"不要"清单；EN: Anti-pattern / Negative case
      - 边界条件：说明"在什么情况下不能做什么"；EN: When not to use / Not applicable
      - 停止条件：`最多 N 次` / `失败 N 次停止`；EN: retry budget / stop and report / iteration limit
    ⚠️ 09-19 修：加英文同义词（对齐 archify SKILL.md 的英文表达）
    """
    score = 0
    hits = []
    # 反例/黑名单/不要/禁止（中文 + 英文）
    blacklist_cn = len(re.findall(r'(反例|黑名单|不要|禁止|严禁|不得|不应)', text))
    blacklist_en = len(re.findall(r'\b(never|do not|does not|must not|mustn.t|should not|shouldn.t|forbid|prohibit|avoid|refuse)\b', text, re.IGNORECASE))
    blacklist_markers = blacklist_cn + blacklist_en
    if blacklist_markers >= 2:
        score += 1
        hits.append(f"反例/黑名单标记 {blacklist_markers}处")
    if blacklist_markers >= 6:
        score += 1
        hits.append("反例/黑名单丰富")
    # 具体禁止项（"不要"后跟具体行为；中文 + 英文）
    concrete_no_cn = len(re.findall(r'(不要|禁止|不得|不应)\s*(调用|写死|修改|删除|跳过|忽略|硬编码|覆盖|重写|执行|添加依赖)', text))
    concrete_no_en = len(re.findall(r'\b(never|do not|must not|mustn.t|should not|shouldn.t|refuse to)\s+(?:call|invoke|write|modify|delete|skip|ignore|hard.?code|overwrite|rewrite|add (?:dependency|import|require)|run|execute|claim|assert|bypass|halt|abort)\b', text, re.IGNORECASE))
    concrete_no = concrete_no_cn + concrete_no_en
    if concrete_no >= 1:
        score += 1
        hits.append(f"具体禁止项 {concrete_no}处")
    if concrete_no >= 4:
        score += 1
        hits.append("具体禁止项丰富")
    # 反例模式表格（中文 + 英文）
    anti_pattern_cn = len(re.findall(r'(反模式|黑名单)', text))
    anti_pattern_en = len(re.findall(r'\b(anti[- ]?pattern|negative case|negative example|false positive|bad practice|footgun)\b', text, re.IGNORECASE))
    anti_pattern = anti_pattern_cn + anti_pattern_en
    if anti_pattern >= 1:
        score += 1
        hits.append(f"反模式 {anti_pattern}处")
    if anti_pattern >= 3:
        score += 1
        hits.append("反模式丰富")
    # 边界条件（中文 + 英文）
    boundary_cn = len(re.findall(r'(不能|不可|不能直接|不可修改|不能跳过)', text))
    boundary_en = len(re.findall(r'\b(when not to|when to skip|not applicable|outside scope|out of scope|precondition|assumption|constraint|requirement)\b', text, re.IGNORECASE))
    boundary = boundary_cn + boundary_en
    if boundary >= 3:
        score += 1
        hits.append(f"边界条件 {boundary}处")
    if boundary >= 6:
        score += 1
        hits.append("边界条件丰富")
    # 停止条件（中文 + 英文）
    stop_cn = len(re.findall(r'(最多.{0,5}次|不超过.{0,5}次|失败.{0,5}停止|停止.{0,5}次|最多重试|上限)', text))
    stop_en = len(re.findall(r'\b(at most|no more than|max.{0,5}retries?|retry.{0,5}budget|iteration budget|stop and report|falsifiable|give up after|halt after|abort after)\b', text, re.IGNORECASE))
    stop = stop_cn + stop_en
    if stop >= 1:
        score += 1
        hits.append(f"停止条件 {stop}处")

    return min(score, 10), hits

def analyze_meta_skill(text):
    """
    对 Skill 文本做三维度 meta-skill 分析。
    返回三维度分数（0-10）+ 综合 meta-skill score（0-100）+ 命中细节。
    """
    fme_score, fme_hits = _score_failure_mechanism_encoding(text)
    as_score, as_hits = _score_actionable_specificity(text)
    hab_score, hab_hits = _score_high_risk_blacklist(text)
    # 综合：加权平均，FME 权重最高（SkillLens 论文中 Failure Mechanism 是最强预测因子）
    meta_score = round((fme_score * 0.40 + as_score * 0.30 + hab_score * 0.30) * 10, 1)
    return {
        "failure_mechanism_encoding": {
            "score": fme_score, "max": 10, "hits": fme_hits,
            "label": "FME：失败机制编码"
        },
        "actionable_specificity": {
            "score": as_score, "max": 10, "hits": as_hits,
            "label": "AS：可执行具体性"
        },
        "high_risk_blacklist": {
            "score": hab_score, "max": 10, "hits": hab_hits,
            "label": "HAB：高风险黑名单"
        },
        "meta_skill_score": meta_score,
        "meta_skill_label": "meta-skill综合"
    }


def check_success_mode(text):
    """
    成功模式检查（SkillLens 借鉴：成功模式和失败模式应分离提炼）。
    检查 Skill 是否包含正向操作路径（成功模式），而非只有失败处理。
    返回：通过/不通过 + 命中证据。
    """
    hits = []
    # 成功路径关键词
    success_patterns = [
        r'(成功|成功时|成功路径|happy path|正常流程|正向流程)',
        r'(✅|✓|✔)',
        r'(最佳实践|best practice|推荐做法|标准操作)',
    ]
    for pat in success_patterns:
        matches = re.findall(pat, text)
        if matches:
            hits.extend(matches)
    # 成功与失败分离（同时出现"成功"和"失败"且有关联词）
    has_both = re.search(r'(成功|失败)', text) and re.search(r'(成功|失败)', text)
    success_fail_split = bool(re.search(r'(成功.*失败|失败.*成功)', text))
    if success_fail_split:
        hits.append("成功/失败分离")

    passed = len(hits) >= 1
    return {"passed": passed, "hits": hits, "detail": f"命中 {len(hits)} 处成功模式标记"}


def _has_ending_fluff(text):
    endings = [r'灵活应用', r'根据情况判断', r'灵活处理', r'灵活变通',
               r'适当调整', r'根据实际需要', r'视具体情况', r'灵活运用']
    for p in endings:
        if re.search(p + r'[。．，,]?\s*$', text):
            return True
    return False


def _has_concrete_examples(text):
    patterns = [r'`[^`]+`', r'\b\d+px\b', r'\b\d+em\b', r'\b\d+%?\b',
                r'```', r'path=', r'`--', r'\bhttps?://']
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def _load_skill_data(name):
    skill_dir = os.path.join(SKILLS_DIR, name)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    entry = {"name": name, "path": skill_dir, "lines": 0, "components": {},
             "frontmatter_keys": [], "description": "", "desc_length": 0,
             "has_triggers": False, "has_failure_modes": False,
             "has_anti_examples": False, "has_checkpoints": False, "has_steps": False,
             "has_progressive_disclosure": False, "has_compression_strategy": False,
             "has_failure_preservation": False, "text": ""}

    if not os.path.isdir(skill_dir):
        return entry

    for f in os.listdir(skill_dir):
        fp = os.path.join(skill_dir, f)
        if os.path.isfile(fp):
            entry["components"][f] = {"type": "file"}
        elif os.path.isdir(fp):
            entry["components"][f] = {"type": "dir"}

    if not os.path.exists(skill_path):
        return entry

    text = Path(skill_path).read_text(encoding='utf-8')
    entry["text"] = text
    entry["lines"] = len(text.split('\n'))

    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', text, re.DOTALL)
    meta = {}
    if m:
        fm_lines = m.group(1).split('\n')
        i = 0
        while i < len(fm_lines):
            line = fm_lines[i]
            if ':' not in line:
                i += 1
                continue
            k, v = line.split(':', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # YAML 块标量：| > 及其 - / + 折叠变体（漏掉 >- 会让 description 读成字面 ">$-$"）
            if v and v[0] in ('|', '>') and v[1:].rstrip() in ('', '-', '+'):
                continuation = []
                i += 1
                while i < len(fm_lines):
                    nl = fm_lines[i]
                    # 遇到以非空格开头的行或空行，结束多行值
                    if not nl.strip():
                        break
                    if not nl[0].isspace():
                        break
                    continuation.append(nl.lstrip())
                    i += 1
                meta[k] = '\n'.join(continuation)
                continue
            meta[k] = v
            i += 1
        entry["frontmatter_keys"] = list(meta.keys())
        entry["description"] = meta.get("description", "")
        entry["desc_length"] = len(entry["description"])
        entry["has_triggers"] = bool(re.search(r'(触发|trigger|当|when|use when|提到|say|说)', entry["description"], re.IGNORECASE))

    entry["has_failure_modes"] = bool(re.search(r'(失败|error|错误|fallback|异常|如果.*失败|if.*fail)', text, re.IGNORECASE))
    entry["has_anti_examples"] = bool(re.search(r'(不要|反例|黑名单|do not|never|avoid|不应|禁止)', text, re.IGNORECASE))
    entry["has_checkpoints"] = bool(re.search(r'(CHECKPOINT|检查点|STOP|🛑|暂停|确认)', text, re.IGNORECASE))
    entry["has_steps"] = bool(re.search(r'Phase|Step|阶段|步骤|Phase \d|Step \d', text))
    entry["has_progressive_disclosure"] = bool(re.search(r'(progressive|渐进|按需|metadata|元数据)', text, re.IGNORECASE))
    # 09-28 BeataI 上下文工程：压缩策略 + 失败保留
    entry["has_compression_strategy"] = bool(re.search(r'(压缩|compact|摘要|summariz)', text, re.IGNORECASE))
    entry["has_failure_preservation"] = bool(re.search(r'(失败记录|保留失败|失败.*保留|不要洗白|保留.*失败|记录失败|失败原因)', text, re.IGNORECASE))
    return entry


# ═══════════════════════════════════════════════════
# 确定性断言库（AI开发者日常《别凭感觉改 Skill》L3 借鉴）
# 来源：从"文件是否存在也问模型、JSON 是否合法也问模型"
#       反模式提炼——结构化检查必须确定性，不允许 LLM 判断
# ═══════════════════════════════════════════════════

# 安全敏感模式（密钥/凭证/Token 泄露检测）
SECRET_PATTERNS = [
    r'(?i)(api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?token)\s*[:=]\s*[\"\'][^\"\']{8,}',
    r'(?i)(Bearer\s+[A-Za-z0-9\-_]{20,})',
    r'(?i)(sk-[A-Za-z0-9]{20,})',
    r'(?i)(password|passwd|pwd)\s*[:=]\s*[\"\'][^\"\']{6,}',
    r'(?i)(PRIVATE[_-]?KEY|BEGIN RSA PRIVATE KEY|BEGIN PRIVATE KEY)',
    r'(?i)(AKIA[0-9A-Z]{16,})',  # AWS Access Key
]

# 绝对路径模式（不允许在 SKILL.md 中硬编码机器相关的绝对路径）
# 注意：/var/minis/ 是 Minis 沙箱合法路径，不在此列
ABS_PATH_PATTERNS = [
    r'/usr/local/[^\s\"\'\)]+',
    r'/home/[^\s\"\'\)]+',
    r'/Users/[^\s\"\'\)]+',
    r'C:\\[A-Za-z]:\\[^\s\"\'\)]*',
    r'/tmp/[a-zA-Z0-9_\-]+\.py',  # 临时脚本路径不应硬编码
]

# shell=True 检测（安全：subprocess 不应使用 shell=True）
SHELL_TRUE_PATTERN = r'\bshell\s*=\s*True\b'


def assert_no_secrets(text, skill_name):
    """A01: 检测密钥/凭证泄露（一票否决）"""
    hits = []
    for pat in SECRET_PATTERNS:
        matches = re.findall(pat, text)
        for m in matches:
            if isinstance(m, tuple):
                m = m[0] if m[0] else (m[1] if len(m) > 1 else "")
            hits.append(m[:40])
    if hits:
        return False, f"发现 {len(hits)} 处疑似密钥/凭证: {', '.join(hits[:3])}"
    return True, "未检测到密钥/凭证泄露"


def assert_no_absolute_paths(text, skill_name):
    """A02: 检测硬编码绝对路径（一票否决）"""
    hits = []
    for pat in ABS_PATH_PATTERNS:
        matches = re.findall(pat, text)
        hits.extend(matches[:5])
    if hits:
        return False, f"发现硬编码绝对路径: {', '.join(hits[:3])}"
    return True, "未发现硬编码绝对路径"


def assert_no_shell_true(text, skill_name):
    """A03: 检测 shell=True（安全漏洞，一票否决）"""
    if re.search(SHELL_TRUE_PATTERN, text):
        return False, "发现 shell=True，存在命令注入风险"
    return True, "未发现 shell=True"


def assert_meta_json_exists(skill_dir):
    """A04: meta.json 或 skill.meta.json 存在且为合法 JSON（一票否决）"""
    for fname in ("meta.json", "skill.meta.json"):
        meta_path = os.path.join(skill_dir, fname)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return False, f"{fname} 不是合法 JSON: {e}"
            required_fields = ["name", "version"]
            missing = [f for f in required_fields if f not in data]
            if missing:
                return False, f"{fname} 缺字段: {', '.join(missing)}"
            return True, f"{fname} 有效"
    return False, "meta.json 不存在（meta.json 或 skill.meta.json 均可）"


def assert_references_exist(skill_dir, text):
    """A05: SKILL.md 中引用的本地文件/脚本必须存在"""
    refs = set()
    # 反引号中的路径: `scripts/run.py`, `./path/to/file`
    for m in re.findall(r'`((?:\./|scripts/|references/)[^\s`]+)' , text):
        refs.add(m)
    # Markdown 链接中的路径: [text](path/to/file)
    for m in re.findall(r'\]\(((?:\./|scripts/|references/)[^\s\)]+)', text):
        refs.add(m)
    # 圆括号中的路径（非链接）: (scripts/run.py)
    for m in re.findall(r'\(((?:scripts/|references/)[^\s\)]+)\)', text):
        refs.add(m)

    errors = []
    for ref in refs:
        ref_clean = ref.lstrip('./')
        full_path = os.path.join(skill_dir, ref_clean)
        alt_path = os.path.join(skill_dir, ref)
        if not (os.path.exists(full_path) or os.path.exists(alt_path)):
            errors.append(ref)

    if errors:
        return False, f"引用文件不存在: {', '.join(errors[:5])}"
    return True, f"所有引用文件存在 ({len(refs)} 个)" if refs else "无引用文件检查"


def assert_no_duplicate_names(skill_name, all_skills):
    """A06: 检查是否有重名 Skill（一票否决）"""
    duplicates = [s for s in all_skills if s.lower() == skill_name.lower() and s != skill_name]
    if duplicates:
        return False, f"存在重名 Skill: {duplicates}"
    return True, "无重名 Skill"


def run_deterministic_assertions(data, skill_name, all_skills=None):
    """
    运行所有确定性断言，返回 (errors, warnings)。
    errors: 一票否决的结构性错误
    warnings: 建议修复的非致命问题
    """
    errors = []
    warnings = []
    text = data.get("text", "")
    skill_dir = data.get("path", "")

    # A01: 密钥/凭证检测
    passed, detail = assert_no_secrets(text, skill_name)
    if not passed:
        errors.append({"id": "A01", "name": "密钥/凭证泄露", "detail": detail})

    # A02: 硬编码绝对路径
    passed, detail = assert_no_absolute_paths(text, skill_name)
    if not passed:
        errors.append({"id": "A02", "name": "硬编码绝对路径", "detail": detail})

    # A03: shell=True 检测
    passed, detail = assert_no_shell_true(text, skill_name)
    if not passed:
        errors.append({"id": "A03", "name": "shell=True 安全漏洞", "detail": detail})

    # A04: meta.json 存在则必须合法（不存在为警告）
    if os.path.isdir(skill_dir):
        passed, detail = assert_meta_json_exists(skill_dir)
        if not passed:
            if "meta.json 不存在" in detail:
                warnings.append({"id": "A04", "name": "meta.json 不存在", "detail": detail})
            else:
                errors.append({"id": "A04", "name": "meta.json 无效", "detail": detail})

        # A05: 引用文件完整性
        passed, detail = assert_references_exist(skill_dir, text)
        if not passed:
            errors.append({"id": "A05", "name": "引用文件不存在", "detail": detail})

    # A06: 重名检测
    if all_skills:
        passed, detail = assert_no_duplicate_names(skill_name, all_skills)
        if not passed:
            errors.append({"id": "A06", "name": "重名 Skill", "detail": detail})

    return errors, warnings


# ═══════════════════════════════════════════════════
# Trigger Eval（AI开发者日常《别凭感觉改 Skill》L1 借鉴）
# ═══════════════════════════════════════════════════

# 存量 Skill 的触发语料散在 5 种 schema 里，旧版只认 evals/trigger_queries.json，
# 导致明明写了用例的 Skill（nuwa / grill-me / yuwen / apple-reminders …）全部报"无语料"。
# 这里按优先级探测，第一个解析出用例的即用；识别不了的 schema 返回空，绝不猜 should_trigger。
TRIGGER_QUERY_CANDIDATES = (
    ("evals/trigger_queries.json", "native"),
    ("trigger_queries.json", "native"),
    ("evals/trigger_cases.jsonl", "jsonl_expect"),
    ("evals/evals.json", "prompt_expected"),
    ("test-prompts.json", "prompt_expected"),
    ("test-prompts-all.json", "prompt_expected"),
    ("tests/trigger_queries.json", "native"),
    ("tests/README.json", "trigger_lists"),
)


def _mk_query(idv, query, should_trigger, idx, group, schema):
    if not query or not str(query).strip():
        return None
    return {
        "id": idv if idv not in (None, "") else f"{schema}-{idx}",
        "query": str(query).strip(),
        "should_trigger": bool(should_trigger),
        "group": group,
        "schema": schema,
    }


def _normalize_queries(data, schema):
    """归一化触发语料到 [{id, query, should_trigger, group, schema}]。

    支持: native(positive/negative) | jsonl_expect(prompt+expect) |
          prompt_expected(prompt+expected[_output], 全为正例) |
          trigger_lists(explicit/implicit/negative_triggers 字符串数组)
    """
    out = []

    def push(item, default_trigger, group):
        if isinstance(item, str):
            rec = _mk_query(None, item, default_trigger, len(out) + 1, group, schema)
        elif isinstance(item, dict):
            q = item.get("query") or item.get("prompt") or item.get("text") or ""
            st = item.get("should_trigger")
            if st is None:
                exp = item.get("expect") or item.get("expected_trigger")
                if isinstance(exp, str):
                    st = exp.strip().lower() in ("trigger", "true", "yes", "should")
                else:
                    st = default_trigger
            rec = _mk_query(item.get("id"), q, st, len(out) + 1, group, schema)
        else:
            rec = None
        if rec:
            out.append(rec)

    if isinstance(data, list):  # test-prompts.json / jsonl 已解析成 list
        for item in data:
            push(item, True, "positive")
        return out
    if not isinstance(data, dict):
        return out

    if "positive" in data or "negative" in data:
        for group, default in (("positive", True), ("negative", False)):
            for item in data.get(group) or []:
                push(item, default, group)
        return out

    if any(k in data for k in ("explicit_triggers", "implicit_triggers", "negative_triggers")):
        for key, default, group in (("explicit_triggers", True, "positive"),
                                    ("implicit_triggers", True, "positive"),
                                    ("regression", True, "positive"),
                                    ("negative_triggers", False, "negative")):
            for item in data.get(key) or []:
                push(item, default, group)
        return out

    for key in ("evals", "cases", "queries", "tests", "prompts"):
        if isinstance(data.get(key), list):
            for item in data[key]:
                push(item, True, "positive")
            return out
    return out


def load_trigger_queries(skill_dir):
    """加载触发语料，自动适配多种历史 schema。返回 [] 表示确实没有。"""
    for rel, schema in TRIGGER_QUERY_CANDIDATES:
        path = os.path.join(skill_dir, rel)
        if not os.path.exists(path):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
            if path.endswith(".jsonl"):
                data = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
            else:
                data = json.loads(text)
        except Exception:
            continue
        queries = _normalize_queries(data, schema)
        if queries:
            return queries
    return []


def _trigger_tokens(text):
    """中文滑窗 n-gram（2/3 字）+ 英文数字词。

    旧版用 re `{2,3}` 非重叠贪婪切分：连续中文从左每 3 字切一刀、相位取决于
    字符串起点，导致「优化脚本」只切出「优化脚」，「处理文件」切成「处理文/件时触」。
    desc 侧和 query 侧相位不同 → 同一个词永远对不上 → 真实存在的词判为未触发。
    滑窗保证任意位置的字都能组成词。
    """
    lower = text.lower()
    tokens = set(re.findall(r'[a-z0-9]{3,}', lower))
    for seg in re.findall(r'[\u4e00-\u9fff]+', lower):
        for n in (2, 3):
            for i in range(len(seg) - n + 1):
                tokens.add(seg[i:i + n])
    return tokens


def _hit_blocks(query, desc_tokens):
    """命中数按 query 上的不相交区间计数，而不是数 token 个数。

    滑窗 n-gram 会把「处理文件」重复计入 5 次（处理/理文/文件/处理文/理文件），
    而单独一个「优化」只算 1 次——直接数 token 会高估多字词、惩罚精确命中的单词。
    """
    if not query:
        return 0
    flags = [False] * len(query)
    low = query.lower()
    for tok in desc_tokens:
        start = low.find(tok)
        while start != -1:
            for i in range(start, min(start + len(tok), len(flags))):
                flags[i] = True
            start = low.find(tok, start + 1)
    return sum(1 for i, on in enumerate(flags) if on and (i == 0 or not flags[i - 1]))


TRIGGER_HIT_BLOCKS = 1  # 消融实测最优：49 条查询上 F1 83.9%（>=2 时仅 57.1%，>=3 时 40.0%）


def _skill_should_trigger(description, query, full_text=""):
    """
    确定性触发匹配：用 Skill 的 description + 全文关键词判断 query 是否应触发。
    不调用 LLM，纯文本匹配——与 AI开发者日常文章"文件存在别问模型"一致。

    策略：
    1. 提取 description 的关键词（中文 2-gram / 英文词）
    2. 提取 query 的关键词
    3. 计算重叠率，同时考虑 substring 包含关系
    4. 匹配 ≥ 阈值则判定触发
    """
    if not description or not query:
        return False

    # 触发契约只取 description：agent 挑 Skill 时读的就是这个字段。
    # 旧版把整份 SKILL.md 正文也当触发词库（measurement 实测 desc 词集 613 个），
    # 正文里的举例（ nrw"code review" rw"）会变成合法触发源 → 系统性假阳性。
    desc_tokens = _trigger_tokens(description)
    query_tokens = _trigger_tokens(query)
    if not desc_tokens or not query_tokens:
        return False

    hits = query_tokens & desc_tokens
    # 两个独立命中片段才算触发。
    # 旧版阈值 = int(len(desc_tokens) * 0.15)，实测 613×0.15 = 91：
    # 用户一句话只有几个词，数学上不可能达标，且 SKILL.md 越长越难触发（反向激励）。
    return _hit_blocks(query, desc_tokens) >= TRIGGER_HIT_BLOCKS


def _llm_batch_trigger(skill_name, description, queries):
    """
    用 minis-model-use 做 LLM 语义触发匹配（批量调用，单次请求）。

    与确定性匹配的差异：确定性匹配用关键词重叠率，召回率受 description 覆盖面限制；
    LLM 语义匹配理解 query 的意图，能识别 description 未直接覆盖的场景。

    策略：将全部 query 一次性发给 LLM，要求返回 JSON 数组。
    单次调用 vs N 次调用：避免速率限制，减少开销。
    """
    import subprocess

    # 构建 prompt：描述 Skill + 每个 query 的评估
    queries_block = "\n".join(
        '{\"id\": \"%s\", \"query\": \"%s\"}' % (q["id"], q["query"])
        for q in queries
    )

    prompt = (
        "你是一个 Skill 路由判断器。给定一个 Skill 的描述和若干用户 query，"
        "判断每个 query 是否应该触发这个 Skill。\n\n"
        "Skill 名称: %s\n"
        "Skill 描述: %s\n\n"
        "判断标准：query 的意图是否落在这个 Skill 的核心职责范围内。\n"
        "触发意味着用户应该使用这个 Skill 来处理该任务。\n\n"
        "待判断的 queries:\n"
        "[%s]\n\n"
        "请只返回一个 JSON 数组，格式：\n"
        "[{\"pos-01\": true}, {\"neg-01\": false}]\n"
        "每个元素的键是 query 的 id，值是 true（触发）或 false（不触发）。\n"
        "不要返回任何其他文字。"
    ) % (skill_name, description, queries_block)

    cmd = [
        "minis-model-use", "run",
        "--model", "agnes-2.5-pro",
        "--prompt", prompt,
        "--max-tokens", "512",
        "--temperature", "0.0",
        "--endpoint", "auto",
    ]

    try:
        # 带重试的 LLM 调用（应对速率限制）
        result = None
        last_err = ""
        for attempt in range(2):  # 最多 2 次
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                last_err = result.stderr[:200]
                if attempt == 0:
                    import time
                    time.sleep(5)
                    continue
                return None, f"minis-model-use 调用失败: {last_err}"

            output = result.stdout
            try:
                data = json.loads(output)
                text = data.get("data", {}).get("output_text", "").strip()
                if text:
                    break
            except json.JSONDecodeError:
                pass
            last_err = f"LLM 返回空输出 (attempt {attempt+1})"
            if attempt == 0:
                import time
                time.sleep(5)
        else:
            return None, last_err

        # 解析 JSON 数组
        # 尝试多种方式提取
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                decisions = json.loads(match.group())
            except json.JSONDecodeError:
                # 尝试修复：去掉注释等非 JSON 内容
                try:
                    decisions = json.loads(re.sub(r'//.*?\n', '\n', match.group()))
                except json.JSONDecodeError:
                    return None, f"无法解析 LLM 输出: {text[:200]}"

            result_map = {}
            for q in queries:
                qid = q["id"]
                valid_keys = ("should_trigger", "trigger", "triggered", "result", "value")
                if isinstance(decisions, list):
                    result_map[qid] = None
                    for item in decisions:
                        if isinstance(item, dict):
                            # 格式1: [{"id": "pos-01", "should_trigger": true}]
                            if item.get("id") == qid:
                                for k in valid_keys:
                                    if k in item:
                                        result_map[qid] = bool(item[k])
                                        break
                                if result_map[qid] is None:
                                    for k, v in item.items():
                                        if isinstance(v, bool):
                                            result_map[qid] = v
                                            break
                            # 格式2: [{"pos-01": true}]
                            elif qid in item:
                                result_map[qid] = bool(item[qid])
                elif isinstance(decisions, dict):
                    # 格式3: {"pos-01": true}
                    result_map[qid] = bool(decisions.get(qid)) if decisions.get(qid) is not None else False

            return result_map, None
        else:
            return None, f"LLM 输出中未找到 JSON 数组: {text[:200]}"

    except subprocess.TimeoutExpired:
        return None, "LLM 调用超时（60秒）"
    except (json.JSONDecodeError, Exception) as e:
        return None, f"LLM 调用异常: {str(e)[:200]}"


def trigger_eval(skill_name, queries=None, model_call=False):
    """
    运行触发评测，返回 TP/FP/FN/TN + Precision/Recall/F1。

    Args:
        skill_name: Skill 目录名
        queries: 触发查询列表（从 trigger_queries.json 加载或传入）
        model_call: 是否调用 LLM 做触发判断（默认 False，用确定性匹配）

    Returns:
        dict: {tp, fp, fn, tn, precision, recall, f1, records[]}
    """
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    if queries is None:
        queries = load_trigger_queries(skill_dir)

    if not queries:
        return {
            "error": "无 trigger_queries.json，请创建该文件或在 Skill 下创建 evals/trigger_queries.json",
            "tp": 0, "fp": 0, "fn": 0, "tn": 0,
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "records": []
        }

    data = _load_skill_data(skill_name)
    description = data.get("description", "")
    text = data.get("text", "")

    # 决策路径：LLM 模式 vs 确定性模式
    if model_call:
        # LLM 语义触发匹配（单次批量调用）
        result_map, err = _llm_batch_trigger(skill_name, description, queries)
        if err:
            return {
                "error": f"LLM 模式失败: {err}。降级到确定性匹配。",
                "tp": 0, "fp": 0, "fn": 0, "tn": 0,
                "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "records": []
            }
        # 降级检查：如果 LLM 返回了 None，回退到确定性匹配
        fallback = any(result_map.get(q["id"]) is None for q in queries)
        method = "llm" if not fallback else "deterministic"
        if fallback:
            # 部分 LLM 决策缺失，回退到确定性匹配
            pass
    else:
        method = "deterministic"

    tp = fp = fn = tn = 0
    records = []

    for q in queries:
        should = q.get("should_trigger", False)

        if model_call and result_map is not None:
            llm_val = result_map.get(q["id"])
            if llm_val is not None:
                actual = llm_val
            else:
                # LLM 未返回该 query 的决策，回退到确定性
                actual = _skill_should_trigger(description, q["query"], full_text=text)
        else:
            actual = _skill_should_trigger(description, q["query"], full_text=text)

        if should and actual:
            tp += 1
            result_label = "TP"
        elif not should and actual:
            fp += 1
            result_label = "FP"
        elif should and not actual:
            fn += 1
            result_label = "FN"
        else:
            tn += 1
            result_label = "TN"

        records.append({
            "id": q["id"],
            "query": q["query"][:60],
            "should_trigger": should,
            "did_trigger": actual,
            "result": result_label,
        })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "total": len(queries),
        "method": method,
        "records": records,
    }


def run_trigger_eval(names=None, model_call=False):
    """运行触发评测并输出结果"""
    if names is None:
        names = sorted([d for d in os.listdir(SKILLS_DIR)
                        if os.path.isdir(os.path.join(SKILLS_DIR, d))])
    if isinstance(names, str):
        names = [names]

    all_results = {}
    for name in names:
        result = trigger_eval(name, model_call=model_call)
        all_results[name] = result

        if "error" in result:
            print(f"\n{'─' * 50}")
            print(f"  {name}")
            print(f"{'─' * 50}")
            print(f"  ⚠️  {result['error']}")
            continue

        method_label = f" (LLM)" if result.get("method") == "llm" else " (确定性)"
        print(f"\n{'═' * 50}")
        print(f"  {name}  |  Trigger Eval{method_label}")
        print(f"{'═' * 50}")
        print(f"  总查询: {result['total']}")
        print(f"  TP: {result['tp']}  FP: {result['fp']}  FN: {result['fn']}  TN: {result['tn']}")
        bar_p = "█" * int(result["precision"] * 20) + "░" * (20 - int(result["precision"] * 20))
        bar_r = "█" * int(result["recall"] * 20) + "░" * (20 - int(result["recall"] * 20))
        bar_f = "█" * int(result["f1"] * 20) + "░" * (20 - int(result["f1"] * 20))
        print(f"  [{bar_p}] Precision: {result['precision']:.1%}")
        print(f"  [{bar_r}] Recall:    {result['recall']:.1%}")
        print(f"  [{bar_f}] F1:        {result['f1']:.1%}")
        # 显示 FP/FN 详情
        fps = [r for r in result["records"] if r["result"] == "FP"]
        fns = [r for r in result["records"] if r["result"] == "FN"]
        if fps:
            print(f"  ⚠️  FP ({len(fps)}): 不该触发但触发了")
            for r in fps[:3]:
                print(f"      - {r['query'][:50]}")
        if fns:
            print(f"  ⚠️  FN ({len(fns)}): 该触发但没触发")
            for r in fns[:3]:
                print(f"      - {r['query'][:50]}")
        print()
    return all_results


def eval_skill(name, strict=False, all_skills=None):
    data = _load_skill_data(name)
    text = data.get("text", "")
    errors = []
    warnings = []
    infos = []

    # ===== Error: 一票否决 =====
    if not os.path.exists(os.path.join(data.get("path", ""), "SKILL.md")):
        errors.append({"id": "R01", "name": "SKILL.md 不存在", "detail": "必需文件缺失"})
    meta_keys = data.get("frontmatter_keys", [])
    if "name" not in meta_keys:
        errors.append({"id": "R02", "name": "frontmatter 缺 name", "detail": "SKILL.md 必须包含 name 字段"})
    if "description" not in meta_keys:
        errors.append({"id": "R03", "name": "frontmatter 缺 description", "detail": "SKILL.md 必须包含 description 字段"})
    elif data.get("desc_length", 0) == 0:
        errors.append({"id": "R04", "name": "description 为空", "detail": "description 字段不能为空"})

    # ===== 确定性断言（一票否决） =====
    # 来源：AI开发者日常《别凭感觉改 Skill》L3 — 文件存在/结构完整/安全必须确定性检查
    det_errors, det_warnings = run_deterministic_assertions(data, name, all_skills)
    errors.extend(det_errors)
    warnings.extend(det_warnings)

    # ===== Warning: 建议修复 =====
    if data.get("desc_length", 0) > 1024:
        warnings.append({"id": "R05", "name": "description 过长", "detail": f"{data['desc_length']} 字符 > 1024"})
    if not data.get("has_triggers", False):
        warnings.append({"id": "Q01", "name": "缺少触发条件", "detail": "description 应包含明确的触发场景"})
    if not data.get("has_failure_modes", False):
        warnings.append({"id": "Q02", "name": "缺少失败模式", "detail": "应编码 '如果 X 失败 → Y' 分支"})
    # 09-28 BeataI 上下文工程借鉴：故障分类法（污染/干扰/混淆/冲突）诊断入口
    if not data.get("has_compression_strategy", False):
        warnings.append({"id": "CE01", "name": "缺少压缩策略", "detail": "建议明确压缩触发阈值（70-85%）和保留/丢弃清单，对齐 BeataI 上下文工程"})
    if not data.get("has_failure_preservation", False):
        warnings.append({"id": "CE02", "name": "失败记录可能被洗白", "detail": "压缩时须保留'尝试X→失败，因为Y'，抹除证据=恶性循环（BeataI 反直觉规则）"})
    # CE03 混淆：工具定义过多且无筛选策略（对应 BeataI 混淆故障：40个工具只用了3个）
    tool_mentions = len(re.findall(r'(?:工具|tool|`[^`]+`)', text, re.IGNORECASE))
    has_tool_filter = bool(re.search(r'(只|仅|minimal|only|精简|最小|specific|按需)', text, re.IGNORECASE))
    if tool_mentions > 20 and not has_tool_filter:
        warnings.append({"id": "CE03", "name": "工具定义多但无筛选策略", "detail": f"引用 {tool_mentions} 个工具/术语，未声明最小工具集（BeataI 混淆故障：40个工具只用了3个反而伤害）"})
    # CE04 冲突：版本/时间敏感内容 ≥3 处但无来源优先级声明（BeataI 冲突故障：旧需求vs新需求无原则性选择）
    ver_count = len(re.findall(r'(?:版本|version|v\d|日期|date|时间戳|timestamp)', text, re.IGNORECASE))
    has_source_priority = bool(re.search(r'(优先级|优先|precedence|wins|以.*为准|权威|source.?of.?truth|最新|最旧)', text, re.IGNORECASE))
    if ver_count >= 4 and not has_source_priority:
        warnings.append({"id": "CE04", "name": "版本/时间敏感但无来源优先级", "detail": "内容含版本/日期引用，未声明冲突时以哪个来源为准（BeataI 冲突故障：旧需求vs新需求无原则性选择）"})
    if not data.get("has_anti_examples", False):
        warnings.append({"id": "Q03", "name": "缺少反例/黑名单", "detail": "应包含 '不要做什么' 清单"})
    if not data.get("has_checkpoints", False):
        warnings.append({"id": "Q04", "name": "缺少检查点", "detail": "关键决策前应有显式确认点"})
    if not data.get("has_steps", False):
        warnings.append({"id": "Q05", "name": "缺少步骤结构", "detail": "应有明确的 Phase/Step 流程"})
    fluff_count = _count_fluff(text)
    if fluff_count >= 3:
        warnings.append({"id": "N01", "name": "AI 腔软化措辞", "detail": f"发现 {fluff_count} 处软化措辞"})
    if _has_ending_fluff(text):
        warnings.append({"id": "N02", "name": "结尾空话", "detail": "结尾不应有空话尾巴"})

    # ===== Info: 参考项 =====
    if not data.get("has_progressive_disclosure", False):
        infos.append({"id": "Q06", "name": "未体现进度式披露", "detail": "建议遵循 metadata→SKILL→resources 三层"})
    if not _has_concrete_examples(text):
        infos.append({"id": "N03", "name": "缺少具体参数/示例", "detail": "建议补充可执行的具体参数或格式示例"})
    for comp in ["tests", "skill.meta.json", "CHANGELOG.md"]:
        if comp not in data.get("components", {}):
            infos.append({"id": f"C01", "name": f"缺少 {comp}", "detail": "推荐生产结构组件"})

    # 门禁评分
    passed = len(errors) == 0
    score = max(0, 100 - len(warnings) * 10 - len(infos) * 3)

    return {
        "name": name, "passed": passed, "score": score,
        "errors": errors, "warnings": warnings, "infos": infos,
        "error_count": len(errors), "warning_count": len(warnings), "info_count": len(infos),
    }


def run_all(strict=False):
    if not os.path.isdir(SKILLS_DIR):
        return {"error": f"Skills directory not found: {SKILLS_DIR}"}
    all_skills = sorted([d for d in os.listdir(SKILLS_DIR)
                         if os.path.isdir(os.path.join(SKILLS_DIR, d))])
    results = {}
    for name in all_skills:
        results[name] = eval_skill(name, strict, all_skills=all_skills)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": 5,
        "strict": strict,
        "skills": results,
        "summary": _summarize(results),
    }
    os.makedirs(os.path.dirname(REPORT_PATH) or '.', exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def _summarize(results):
    total = len(results)
    passed = sum(1 for r in results.values() if r["passed"])
    scores = [r["score"] for r in results.values()]
    return {
        "total": total, "passed": passed, "failed": total - passed,
        "total_errors": sum(r["error_count"] for r in results.values()),
        "total_warnings": sum(r["warning_count"] for r in results.values()),
        "total_infos": sum(r["info_count"] for r in results.values()),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
    }


def get_report():
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"error": "No report. Run 'run' first."}


def run_meta_skill(names=None):
    """运行三维度 meta-skill 质量卡"""
    if names is None:
        names = sorted([d for d in os.listdir(SKILLS_DIR)
                        if os.path.isdir(os.path.join(SKILLS_DIR, d))])
    if isinstance(names, str):
        names = [names]

    results = {}
    for name in names:
        data = _load_skill_data(name)
        if not data.get("text"):
            results[name] = {"error": "SKILL.md 不存在或为空"}
            continue
        meta = analyze_meta_skill(data["text"])
        sm = check_success_mode(data["text"])
        meta["success_mode"] = sm
        results[name] = meta

    # 打印
    for name, meta in results.items():
        if "error" in meta:
            print(f"  🔴 {name}: {meta['error']}")
            continue
        print(f"\n{'═' * 60}")
        print(f"  {name}  |  Meta-Skill: {meta['meta_skill_score']}/100")
        print(f"{'═' * 60}")
        for dim in ["failure_mechanism_encoding", "actionable_specificity", "high_risk_blacklist"]:
            d = meta[dim]
            bar = "█" * d["score"] + "░" * (10 - d["score"])
            print(f"  [{bar}] {d['label']:20s} {d['score']}/10")
            if d["hits"]:
                print(f"        └ {', '.join(d['hits'])}")
        sm = meta.get("success_mode", {})
        sm_icon = "✅" if sm.get("passed") else "⚠️"
        print(f"  {sm_icon} 成功模式分离: {sm.get('detail', '')}")
    print()
    return results


# ═══════════════════════════════════════════════════
# SkillForge 借鉴：评测泄漏过滤
# ═══════════════════════════════════════════════════

def detect_leakage(skill_name, test_cases_path=None):
    """
    检测 Skill 内容是否包含评测数据泄漏。
    SkillForge 的 leakage_filter.py 思路：确保蒸馏出的技能不泄漏评测实例。

    检测维度：
    1. 测试用例名/路径出现在 SKILL.md 中
    2. 具体测试场景描述与评测集高度重合
    3. 特定的评测实例 ID 出现在 Skill 中

    Args:
        skill_name: Skill 目录名
        test_cases_path: 评测实例 JSONL/JSON 路径（可选，自动扫描）

    Returns:
        dict: {passed, leakage_score, leaks[], summary}
    """
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_path):
        return {"passed": False, "leakage_score": 100, "leaks": ["SKILL.md 不存在"], "summary": "无法检查"}

    text = open(skill_path, 'r', encoding='utf-8').read()

    # 自动扫描评测集：skill 目录下 tests/
    test_dir = os.path.join(skill_dir, "tests")
    test_files = []
    if os.path.isdir(test_dir):
        for f in os.listdir(test_dir):
            test_files.append(os.path.join(test_dir, f))
    if test_cases_path and os.path.exists(test_cases_path):
        test_files.append(test_cases_path)

    leaks = []
    score = 0

    # 维度1: 测试文件路径泄漏
    test_path_patterns = set()
    for tf in test_files:
        # 提取文件名和路径作为可疑模式
        test_path_patterns.add(os.path.basename(tf))
        test_path_patterns.add(os.path.relpath(tf, skill_dir))
        # 提取可能的测试函数名（test_xxx）
        if tf.endswith('.py'):
            content = open(tf, 'r', encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'def (test_\w+)', content):
                test_path_patterns.add(m.group(1))
            # 提取 test case 数据片段（前100字符作为指纹）
            for m in re.finditer(r'"([^"]{10,80})"', content):
                snippet = m.group(1)
                if any(c in snippet for c in ['def test', 'test_', 'testcase', 'case_id']):
                    test_path_patterns.add(snippet)

    for pattern in test_path_patterns:
        if pattern in text:
            leaks.append({
                "type": "test_path_leakage",
                "pattern": pattern[:100],
                "severity": "error" if len(pattern) > 20 else "warning"
            })
            score += 20 if len(pattern) > 20 else 10

    # 维度2: 评测实例 ID 泄漏（如 swebench instance_id, benchmark_id）
    instance_ids = set()
    for tf in test_files:
        if tf.endswith(('.jsonl', '.json')):
            try:
                content = open(tf, 'r', encoding='utf-8', errors='replace').read()
                for m in re.finditer(r'"(instance_id|case_id|benchmark_id|id)"\s*:\s*"([^"]+)"', content):
                    instance_ids.add(m.group(2))
            except:
                pass
    for iid in instance_ids:
        if iid in text:
            leaks.append({
                "type": "instance_id_leakage",
                "pattern": iid[:80],
                "severity": "error"
            })
            score += 30

    # 维度3: 评测特定字段名（swebench, eval 等上下文）
    eval_contexts = ['swebench', 'instance_id', 'base_commit', 'patch', 'test_patch', 'gold_patch']
    eval_count = sum(1 for ctx in eval_contexts if ctx in text.lower())
    if eval_count >= 3:
        leaks.append({
            "type": "eval_context_overlap",
            "pattern": f"含 {eval_count} 个评测上下文关键词",
            "severity": "warning"
        })
        score += 10

    passed = score < 30  # 30分以下认为安全
    return {
        "passed": passed,
        "leakage_score": min(score, 100),
        "leaks": leaks,
        "summary": f"{'✅ 安全' if passed else '🔴 可能泄漏'} — 泄漏分 {score}/100，{len(leaks)} 处可疑"
    }


# ─── 09-20 新：Self-Scan（对齐 avoid-ai-writing PROOF.md） ───

def print_capability_boundary():
    """打印能力边界自披露段（每次 run 报告强制打印）。"""
    print(CAPABILITY_BOUNDARY)


def _is_exempt_position(text, line_no, col, source_lines):
    """判断 (line_no, col) 是否落在豁免位置（注释/字符串字面量/三引号块）。"""
    if not source_lines or line_no < 1 or line_no > len(source_lines):
        return False
    line = source_lines[line_no - 1]
    # 三引号块内（粗略：整行没 # 但有 """ 边界）
    triple_count = line.count('"""') + line.count("'''")
    # 判断 col 是否在 # 之后
    if '#' in line:
        hash_col = line.index('#')
        # 检查 # 之前是否有引号未闭合
        prefix = line[:hash_col]
        if prefix.count('"') % 2 == 0 and prefix.count("'") % 2 == 0:
            if col > hash_col:
                return True
    # 判断 col 是否在引号内
    before = line[:col]
    quote_in = False
    for i, ch in enumerate(before):
        if ch in ('"', "'") and (i == 0 or before[i-1] != '\\'):
            quote_in = not quote_in
    return quote_in


def self_scan():
    """对 skill-eval-gate.py 自身跑自审（对齐 avoid-ai-writing PROOF.md 模式）。

    返回：
      raw    : 全部命中数（不豁免）
      exempt : 在注释/字符串里的命中（不算真正问题）
      net    : raw - exempt = 未豁免的诚实信号
      checks : 结构性检查（tests/CHANGELOG/meta.json）
      top_unexempted : Top 3 未豁免命中（对齐 PROOF.md "坏消息写在正中间"）
    """
    self_path = os.path.abspath(__file__)
    with open(self_path, "r", encoding="utf-8") as f:
        source = f.read()
    source_lines = source.split('\n')

    # 结构性检查（对齐 eval_skill 的 Q01/Q02/Q03 但针对工具自身）
    checks = {}
    script_dir = os.path.dirname(self_path)
    checks["tests_dir"] = "tests" in os.listdir(script_dir) or "test" in os.listdir(script_dir)
    checks["changelog"] = os.path.exists(os.path.join(script_dir, "CHANGELOG.md"))
    checks["meta_json"] = os.path.exists(os.path.join(script_dir, "meta.json"))

    # 计数：工具里"讨论要抓的模式"的引用数（Raw）
    # 这些是元模式——工具代码里必然引用这些词，但引用 ≠ 自身违反
    meta_patterns = {
        "failure_keywords": r'(失败|回退|停止条件|错误|异常|超时|降级|重试)',
        "assertion_keywords": r'(assert|断言|检查|验证)',
        "boundary_keywords": r'(边界|范围|条件|前提|假设)',
    }
    hits = []
    for pat_name, pattern in meta_patterns.items():
        for m in re.finditer(pattern, source):
            line_no = source.count('\n', 0, m.start()) + 1
            col = m.start() - (source.rfind('\n', 0, m.start()) + 1)
            exempt = _is_exempt_position(source, line_no, col, source_lines)
            hits.append({
                "pattern": pat_name,
                "line": line_no,
                "col": col,
                "match": m.group(),
                "exempt": exempt,
            })

    raw = len(hits)
    exempt_count = sum(1 for h in hits if h["exempt"])
    net = raw - exempt_count
    unexempted = [h for h in hits if not h["exempt"]]

    # Top 3 未豁免（按行号升序，前 3 条）
    top_unexempted = unexempted[:3]

    return {
        "raw": raw,
        "exempt": exempt_count,
        "net": net,
        "checks": checks,
        "hits": hits,
        "top_unexempted": top_unexempted,
    }


def print_self_scan(scan_result):
    """打印 self-scan 报告（对齐 PROOF.md Raw+Exempt 双列）。"""
    raw = scan_result["raw"]
    exempt = scan_result["exempt"]
    net = scan_result["net"]
    checks = scan_result["checks"]
    top = scan_result["top_unexempted"]

    print()
    print("─" * 60)
    print("  Self-Scan（skill-eval-gate.py 自审，对齐 PROOF.md）")
    print("─" * 60)
    print(f"  Raw    : {raw:4d} 处触发规则命中")
    print(f"  Exempt : {exempt:4d} 处（代码注释 / 字符串字面量 / 自引用）")
    print(f"  Net    : {net:4d} 处（未豁免的诚实信号）")
    print()
    print("  结构性检查（对齐 eval_skill Q01/Q02/Q03）：")
    for k, v in checks.items():
        icon = "✅" if v else "❌"
        print(f"    {icon} {k}: {'存在' if v else '缺失'}")
    print()
    if top:
        print("  ⚠️ 未豁免 Top 3：")
        for h in top:
            print(f"    - line {h['line']:4d} [{h['pattern']}] \"{h['match']}\"")
    else:
        print("  ✅ 全部命中都在豁免位置（注释/字符串/自引用）")
    print()
    print("  → 我们评测 skill 的规则，自己也没满足（tests/CHANGELOG/meta.json）。")
    print("     这是 PROOF.md 模式的价值：不藏着、双列都公布、坏消息写在正中间。")
    print()


def main():
    parser = argparse.ArgumentParser(description="Skill Eval Gate v3")
    sub = parser.add_subparsers(dest="command")
    run_p = sub.add_parser("run")
    run_p.add_argument("name", nargs="?", help="指定 Skill")
    run_p.add_argument("--strict", action="store_true")
    run_p.add_argument("--meta-skill", action="store_true",
                        help="运行后附加三维度 meta-skill 质量卡")
    run_p.add_argument("--trigger-eval", action="store_true",
                        help="AI开发者日常借鉴：附加 Trigger Eval（TP/FP/FN/TN）")
    run_p.add_argument("--leakage-check", action="store_true",
                        help="SkillForge 借鉴：评测泄漏检测")
    run_p.add_argument("--test-cases", help="评测实例路径（配合 --leakage-check）")
    run_p.add_argument("--self-scan", action="store_true",
                        help="附加 self-scan：对本工具自身跑一遍自审（对齐 avoid-ai-writing PROOF.md）")
    sub.add_parser("self-scan", help="独立运行 self-scan（不跑全量 skill 评测）")
    ms_p = sub.add_parser("meta-skill", help="仅输出三维度 meta-skill 质量卡")
    ms_p.add_argument("name", nargs="?", help="指定 Skill")
    te_p = sub.add_parser("trigger-eval", help="AI开发者日常借鉴：触发评测（TP/FP/FN/TN）")
    te_p.add_argument("name", nargs="?", help="指定 Skill（省略则全部）")
    te_p.add_argument("--llm", action="store_true",
                        help="用 LLM 语义匹配（minis-model-use）替代确定性匹配")
    run_p_trigger = run_p.add_argument("--llm", action="store_true",
                                        help="Trigger Eval 用 LLM 语义匹配（minis-model-use）")
    sub.add_parser("report")
    sub.add_parser("json")
    args = parser.parse_args()

    if args.command == "run":
        # 09-20 新：每次 run 报告强制打印能力边界自披露（对齐 avoid-ai-writing PROOF.md）
        print_capability_boundary()
        if args.name:
            r = eval_skill(args.name, args.strict)
            print(f"\n{'═' * 60}")
            print(f"  {r['name']}  |  {r['score']}/100  |  {'✅ PASS' if r['passed'] else '🔴 FAIL'}")
            print(f"{'═' * 60}")
            for grp, label in [("errors", "🔴 Error"), ("warnings", "⚠️ Warning"), ("infos", "ℹ️ Info")]:
                if r[grp]:
                    print(f"\n  {label} ({len(r[grp])}):")
                    for e in r[grp]:
                        print(f"    [{e['id']}] {e['name']}: {e['detail']}")
            if args.meta_skill:
                data = _load_skill_data(args.name)
                if data.get("text"):
                    meta = analyze_meta_skill(data["text"])
                    sm = check_success_mode(data["text"])
                    meta["success_mode"] = sm
                    print(f"\n  {'─' * 40}")
                    print(f"  Meta-Skill 三维度质量卡（SkillLens 借鉴）")
                    print(f"  {'─' * 40}")
                    print(f"  综合: {meta['meta_skill_score']}/100")
                    for dim in ["failure_mechanism_encoding", "actionable_specificity", "high_risk_blacklist"]:
                        d = meta[dim]
                        bar = "█" * d["score"] + "░" * (10 - d["score"])
                        print(f"  [{bar}] {d['label']:20s} {d['score']}/10")
                    sm_icon = "✅" if sm.get("passed") else "⚠️"
                    print(f"  {sm_icon} 成功模式分离: {sm.get('detail', '')}")
            if args.trigger_eval:
                te = trigger_eval(args.name, model_call=args.llm)
                if "error" in te:
                    print(f"\n  {'─' * 40}")
                    print(f"  Trigger Eval")
                    print(f"  {'─' * 40}")
                    print(f"  ⚠️  {te['error']}")
                else:
                    method_label = " (LLM)" if te.get("method") == "llm" else " (确定性)"
                    print(f"\n  {'─' * 40}")
                    print(f"  Trigger Eval{method_label}（AI开发者日常借鉴）")
                    print(f"  {'─' * 40}")
                    print(f"  总查询: {te['total']}")
                    print(f"  TP: {te['tp']}  FP: {te['fp']}  FN: {te['fn']}  TN: {te['tn']}")
                    print(f"  Precision: {te['precision']:.1%}  Recall: {te['recall']:.1%}  F1: {te['f1']:.1%}")
                    fps = [r for r in te["records"] if r["result"] == "FP"]
                    fns = [r for r in te["records"] if r["result"] == "FN"]
                    if fps:
                        print(f"  ⚠️  FP ({len(fps)}): 不该触发但触发了")
                        for r in fps[:3]:
                            print(f"      - {r['query'][:50]}")
                    if fns:
                        print(f"  ⚠️  FN ({len(fns)}): 该触发但没触发")
                        for r in fns[:3]:
                            print(f"      - {r['query'][:50]}")
            if args.leakage_check:
                l = detect_leakage(args.name, args.test_cases)
                print(f"\n  {'─' * 40}")
                print(f"  泄漏检测（SkillForge 借鉴）")
                print(f"  {'─' * 40}")
                print(f"  {l['summary']}")
                if l["leaks"]:
                    for leak in l["leaks"]:
                        sev_icon = "🔴" if leak["severity"] == "error" else "⚠️"
                        print(f"  {sev_icon} [{leak['type']}] {leak['pattern'][:60]}")
                else:
                    print(f"  ✅ 未检测到泄漏")
        else:
            report = run_all(args.strict)
            s = report["summary"]
            print(f"\n{'═' * 60}")
            print(f"  Eval Report v{report['version']} — {report['timestamp'][:16]}")
            print(f"{'═' * 60}")
            print(f"  ✅ 通过 {s['passed']}/{s['total']}  🔴 未通过 {s['failed']}")
            print(f"  Avg {s['avg_score']} (min {s['min_score']}, max {s['max_score']})")
            print(f"  Error {s['total_errors']}  Warning {s['total_warnings']}  Info {s['total_infos']}")
            print(f"{'═' * 60}\n")
            for name in sorted(report["skills"].keys()):
                r = report["skills"][name]
                icon = "✅" if r["passed"] else "🔴"
                detail = f" ({r['error_count']}🔴{r['warning_count']}⚠️{r['info_count']}ℹ️)"
                print(f"  {icon} {name:<24} {r['score']:>3}/100{detail}")
            print()
            if args.meta_skill:
                run_meta_skill()
        # 09-20 新：run 结束附加 self-scan（对齐 avoid-ai-writing PROOF.md）
        if args.self_scan:
            print_self_scan(self_scan())
    elif args.command == "self-scan":
        # 独立子命令：只跑 self-scan，不跑全量 skill 评测
        print_capability_boundary()
        print_self_scan(self_scan())
    elif args.command == "meta-skill":
        run_meta_skill(args.name)
    elif args.command == "trigger-eval":
        if args.llm:
            # 逐个 Skill 输出
            names = sorted([d for d in os.listdir(SKILLS_DIR)
                            if os.path.isdir(os.path.join(SKILLS_DIR, d))])
            for name in names:
                te = trigger_eval(name, model_call=True)
                if "error" in te:
                    print(f"  🔴 {name}: {te['error']}")
                else:
                    print(f"\n{'═' * 50}")
                    print(f"  {name}  |  Trigger Eval (LLM)")
                    print(f"{'═' * 50}")
                    print(f"  总查询: {te['total']}  方法: {te['method']}")
                    print(f"  TP: {te['tp']}  FP: {te['fp']}  FN: {te['fn']}  TN: {te['tn']}")
                    print(f"  Precision: {te['precision']:.1%}  Recall: {te['recall']:.1%}  F1: {te['f1']:.1%}")
        else:
            run_trigger_eval(args.name)
    elif args.command in ("report", "json"):
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()