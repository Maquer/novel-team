"""novelkit.pipeline.outline_drift — 大纲偏离检测（Phase 4 新能力）。

把章节正文与大纲中该章的 beats 做关键词覆盖检查：
beat 里出现的大纲人物名、"引号"标出的关键词、钩子要点，
在正文里找不到 → 记一条偏离 finding。

方法局限（启发式，属 P2 建议性质，不阻断）：
- 只做子串匹配；同义词、代称（"他/那少年"）、意象化改写会误报
- 关键词提取只覆盖人物名与引号词，自由文本 beat 的覆盖是近似的
- 大纲与正文的章节号靠文件名数字映射，映射失败时按文件顺序配对

只读：不写任何文件。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from novelkit.core import log as _log
from novelkit.core.chapter import Chapter
from novelkit.outline.loader import Outline

log = _log

# 引号词："…" "…" "..."（2~12 字，太长多为整句引用，不算关键词）
_QUOTED_RE = re.compile(r'[“"「]([^"」]{2,12})[""」]')
# 文件名章节号：ch1 / chapter-009 / 第3章 / 其他含数字
_FILENAME_NOS = [
    re.compile(r"[cC][hH](\d+)"),
    re.compile(r"[cC]hapter[-_ ]?(\d+)"),
    re.compile(r"第(\d+)章"),
    re.compile(r"(\d+)"),
]
_HOOK_PREFIXES = ("钩子：", "钩子:")
_HOOK_SPLIT_RE = re.compile(r"[+＋，、；;]")
_PUNCT_STRIP = "。，、；；：：「」『』（）()…—─ \t\"“”''"


def chapter_no_from_filename(path: str) -> Optional[int]:
    """从文件名提取章节号；提不到返回 None（调用方回退顺序配对）。"""
    stem = Path(path).stem
    for pat in _FILENAME_NOS:
        m = pat.search(stem)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _strip_hook_prefix(beat: str) -> str:
    s = beat.strip()
    for p in _HOOK_PREFIXES:
        if s.startswith(p):
            return s[len(p):].strip()
    return s


def _phrase_forms(phrase: str) -> List[str]:
    """短语 → 候选形态（任一命中即视为覆盖）。

    如"剑胎的指向"→["剑胎的指向","剑胎"]，"幻象真相"→["幻象真相","幻象"]。
    去"的XX"尾巴；4 字以上短语再加前 2 字（中文偏正短语多为"概念+修饰"）。
    """
    forms: List[str] = []
    if len(phrase) >= 2:
        forms.append(phrase)
    m = re.match(r"^(.{2,}?)的.{1,4}$", phrase)
    if m and m.group(1) not in forms:
        forms.append(m.group(1))
    cjk = re.sub(r"[^\u4e00-\u9fff]", "", phrase)
    if len(cjk) >= 4 and cjk[:2] not in forms:
        forms.append(cjk[:2])
    return [f for f in forms if len(f) >= 2]


def _beat_keywords(beat: str, outline: Outline,
                   ) -> Tuple[List[str], List[List[str]], bool]:
    """beat → (原子关键词, 短语候选组, 是否钩子行)。

    原子关键词：引号词 + beat 中出现的大纲人物名（逐个检查，缺一记一）。
    短语候选组：钩子行中切分出的短语，每组多种形态，组内任一命中即覆盖；
    若短语包含已提取的原子关键词则丢弃该短语（避免"王海话里有话"这类
    字面短语在"王海"已覆盖时仍误报）。
    """
    stripped = beat.strip()
    is_hook = stripped.startswith(_HOOK_PREFIXES)

    atomic: List[str] = []
    for q in _QUOTED_RE.findall(beat):
        q = q.strip()
        if len(q) >= 2 and q not in atomic:
            atomic.append(q)
    for c in outline.characters:
        if c.name and c.name in beat and c.name not in atomic:
            atomic.append(c.name)

    phrases: List[List[str]] = []
    if is_hook:
        for seg in _HOOK_SPLIT_RE.split(_strip_hook_prefix(beat)):
            seg = seg.strip(_PUNCT_STRIP)
            if len(seg) < 2:
                continue
            if any(a in seg for a in atomic):
                continue  # 已有更短的原子关键词覆盖，不再按字面查
            forms = _phrase_forms(seg)
            if forms:
                phrases.append(forms)
    return atomic, phrases, is_hook


@dataclass
class DriftFinding:
    chapter_no: int
    chapter_title: str
    kind: str        # missing_beat | missing_character | missing_hook
    detail: str      # 缺失的 beat/人物/钩子原文（截断 60 字），附缺失关键词

    def to_dict(self) -> Dict:
        return {
            "chapter_no": self.chapter_no,
            "chapter_title": self.chapter_title,
            "kind": self.kind,
            "detail": self.detail,
        }


@dataclass
class DriftReport:
    novel_id: str
    checked: int = 0
    findings: List[DriftFinding] = field(default_factory=list)

    def to_dict(self) -> Dict:
        by_kind: Dict[str, int] = {}
        for f in self.findings:
            by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        return {
            "novel_id": self.novel_id,
            "checked": self.checked,
            "summary": {
                "total": len(self.findings),
                "by_kind": by_kind,
            },
            "findings": [f.to_dict() for f in self.findings],
        }


def check_drift(novel_id: str, chapter_files: List[str],
               outline: Outline) -> DriftReport:
    """对 chapter_files 逐章做偏离检测。返回 DriftReport（只读，不写文件）。"""
    report = DriftReport(novel_id=novel_id)
    files = sorted(chapter_files)

    # 章节号映射：文件名数字优先；提不到数字的文件按顺序取最小未用号。
    # L11 修复：此前 fallback_iter 从头取号，与已被文件名认领的章节号
    # 无关（如 ch1.md→1，draft.md→fallback 又分到 1），导致同章被查
    # 两次、有章被跳过。现跟踪已用号，fallback 只取未用号。
    ordered_nos = sorted(c.no for c in outline.chapters)
    used = set()
    file_nos: List[Tuple[str, Optional[int]]] = []
    for f in files:
        no = chapter_no_from_filename(f)
        if no is None:
            no = next((n for n in ordered_nos if n not in used), None)
        if no is not None:
            used.add(no)
        file_nos.append((f, no))

    for f, no in file_nos:
        if no is None:
            log.warn(f"无法确定章节号，已跳过: {f}")
            continue
        och = outline.chapter(no)
        if och is None:
            log.warn(f"大纲中无第 {no} 章，已跳过: {f}")
            continue
        try:
            chapter = Chapter.load(f, novel_id)
        except (OSError, FileNotFoundError) as e:
            log.warn(f"章节读取失败，已跳过: {f}: {e}")
            continue
        report.checked += 1
        body = chapter.body

        for beat in och.beats:
            atomic, phrases, is_hook = _beat_keywords(beat, outline)
            missing_atomic = [k for k in atomic if k not in body]
            missing_phrases = [forms for forms in phrases
                               if not any(f in body for f in forms)]
            if not missing_atomic and not missing_phrases:
                continue
            # kind 按"最严重"的缺失定：hook > character > beat
            if is_hook:
                kind = "missing_hook"
            elif any(any(c.name == k for c in outline.characters)
                     for k in missing_atomic):
                kind = "missing_character"
            else:
                kind = "missing_beat"
            missing_desc = [f"「{k}」" for k in missing_atomic]
            missing_desc += [f"「{'/'.join(forms)}」" for forms in missing_phrases]
            beat_txt = beat.strip()
            if len(beat_txt) > 60:
                beat_txt = beat_txt[:60] + "…"
            report.findings.append(DriftFinding(
                chapter_no=no,
                chapter_title=och.title,
                kind=kind,
                detail=f"缺失{'；'.join(missing_desc)}｜{beat_txt}",
            ))

    return report
