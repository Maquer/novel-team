"""novelkit.outline.loader — 大纲解析器。

支持两种输入：
1. markdown 大纲（示例见 ~/workspace/novel-writing-demo/outline.md）：
     # 《xxx》…          → 作品名
     世界观：/境界：/门派： → 世界观行
     人物： 段落后 "- 名：描述" → 人物
     ## 第N章 标题        → 章节（N 支持中文数字/阿拉伯数字）
       每行非空文本 → 情节 beat；"钩子：" 开头的行 → hooks（同时算 beat）
2. JSON 大纲：{"title":…, "world":[…], "characters":[{name,desc}…],
   "chapters":[{"no":1,"title":…,"beats":[…],"hooks":[…]}…]}

容错优先：任何解析失败都不抛异常，尽量多提取，缺失部分留空。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from novelkit.core import log as _log
from novelkit.core.config import novel_team_root

log = _log

# ------------------------------------------------------------------
# 数据模型
# ------------------------------------------------------------------


@dataclass
class OutlineCharacter:
    name: str   # 人物名
    desc: str   # 描述行


@dataclass
class OutlineChapter:
    no: int                 # 章节号
    title: str              # 章节标题
    beats: List[str] = field(default_factory=list)   # 情节要点（含钩子行原文）
    hooks: List[str] = field(default_factory=list)   # 钩子行（"钩子："后的内容）


@dataclass
class Outline:
    title: str = ""
    world: List[str] = field(default_factory=list)
    characters: List[OutlineCharacter] = field(default_factory=list)
    chapters: List[OutlineChapter] = field(default_factory=list)

    def chapter(self, no: int) -> Optional[OutlineChapter]:
        for c in self.chapters:
            if c.no == no:
                return c
        return None


# ------------------------------------------------------------------
# 中文数字 → int（"二十三"→23，"一百零五"→105）
# ------------------------------------------------------------------

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "两": 2}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(s: str) -> Optional[int]:
    """中文数字转 int；失败返回 None（调用方可回退）。"""
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    # 纯中文数字
    total, cur, has = 0, 0, False
    for ch in s:
        if ch in _CN_DIGITS:
            cur = cur * 10 + _CN_DIGITS[ch] if cur else _CN_DIGITS[ch]
            # 处理"二十三"：'二'后跟'十'，此处先记 2，'十'时再乘
            has = True
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if cur == 0:
                cur = 1  # "十"→10，"百"→100
            total += cur * unit
            cur = 0
            has = True
        else:
            return None
    total += cur
    return total if has else None


_CHAPTER_RE = re.compile(r"^#{1,3}\s*第(.+?)章\s*(.*)$")
_TITLE_RE = re.compile(r"《([^》]+)》")
_WORLD_PREFIXES = ("世界观：", "世界观:", "境界：", "境界:", "门派：", "门派:")
_HOOK_PREFIXES = ("钩子：", "钩子:")
_CHAR_LINE_RE = re.compile(r"^[-*·•]\s*([^：:，,；;、\s]{1,12})\s*[：:]\s*(.+)$")


def _parse_markdown(text: str) -> Outline:
    out = Outline()
    lines = text.split("\n")
    cur: Optional[OutlineChapter] = None
    in_char_block = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            in_char_block = False
            continue

        # 作品名
        if not out.title:
            m = _TITLE_RE.search(line)
            if m and line.startswith("#"):
                out.title = m.group(1).strip()

        # 世界观行
        if line.startswith(_WORLD_PREFIXES):
            out.world.append(line)
            in_char_block = False
            continue

        # 人物段落开始
        if line in ("人物：", "人物:", "主要人物：", "主要人物:"):
            in_char_block = True
            continue

        # 人物行
        if in_char_block:
            m = _CHAR_LINE_RE.match(line)
            if m:
                out.characters.append(
                    OutlineCharacter(name=m.group(1).strip(),
                                     desc=m.group(2).strip()))
                continue
            # 非人物行则结束人物段落（但别吞掉这行，继续走下面流程）
            in_char_block = False

        # 章节标题
        m = _CHAPTER_RE.match(line)
        if m:
            no = cn_to_int(m.group(1))
            if no is None:
                log.warn(f"大纲章节号无法解析，已跳过该节: {line[:40]}")
                cur = None
                continue
            cur = OutlineChapter(no=no, title=m.group(2).strip())
            out.chapters.append(cur)
            continue

        # 章节正文行 → beat；钩子行额外记 hooks
        if cur is not None:
            is_hook = line.startswith(_HOOK_PREFIXES)
            body = line
            if is_hook:
                for p in _HOOK_PREFIXES:
                    if line.startswith(p):
                        body = line[len(p):].strip()
                        break
                cur.hooks.append(body)
            cur.beats.append(body if not is_hook else line)

    out.chapters.sort(key=lambda c: c.no)
    return out


def _parse_json(data: dict) -> Outline:
    out = Outline()
    out.title = str(data.get("title", "") or "")
    world = data.get("world", []) or []
    out.world = [str(x) for x in world if str(x).strip()]
    for c in data.get("characters", []) or []:
        if isinstance(c, dict) and c.get("name"):
            out.characters.append(OutlineCharacter(
                name=str(c["name"]).strip(),
                desc=str(c.get("desc", "") or "").strip()))
        elif isinstance(c, str) and c.strip():
            out.characters.append(OutlineCharacter(name=c.strip(), desc=""))
    for ch in data.get("chapters", []) or []:
        if not isinstance(ch, dict):
            continue
        try:
            no = int(ch.get("no", 0))
        except (TypeError, ValueError):
            continue
        if no <= 0:
            continue
        out.chapters.append(OutlineChapter(
            no=no,
            title=str(ch.get("title", "") or "").strip(),
            beats=[str(b) for b in (ch.get("beats", []) or []) if str(b).strip()],
            hooks=[str(h) for h in (ch.get("hooks", []) or []) if str(h).strip()],
        ))
    out.chapters.sort(key=lambda c: c.no)
    return out


def load_outline(path: Union[str, Path]) -> Outline:
    """加载大纲文件（markdown 或 JSON）。容错：失败返回空 Outline，不抛异常。"""
    p = Path(path).expanduser()
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        log.warn(f"大纲文件读取失败: {p}: {e}")
        return Outline()
    stripped = text.lstrip()
    if p.suffix.lower() == ".json" or stripped.startswith("{"):
        try:
            return _parse_json(json.loads(text))
        except (ValueError, AttributeError) as e:
            log.warn(f"大纲 JSON 解析失败，回退 markdown 解析: {e}")
    try:
        return _parse_markdown(text)
    except Exception as e:  # 容错优先：绝不让解析器崩掉调用方
        log.warn(f"大纲 markdown 解析异常（返回已提取部分）: {e}")
        return Outline()


def find_outline(project_dir: Union[str, Path]) -> Optional[Path]:
    """按序查找大纲文件：project_dir/outline.md → 上级/outline.md →
    NOVEL_TEAM_ROOT/outline.md（.md/.json 均可）。找不到返回 None。"""
    base = Path(project_dir).expanduser()
    candidates = [
        base / "outline.md",
        base / "outline.json",
        base.parent / "outline.md",
        base.parent / "outline.json",
        novel_team_root() / "outline.md",
        novel_team_root() / "outline.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None
