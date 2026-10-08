"""Chapter — 章节统一模型。

替代原来散落在各工具里的"读文件 + 解析 frontmatter"代码
（gate-check._load_chapter、quality-gate 的 frontmatter 解析、
wordcount-check.extract_content_from_chapter 等）。

语义：
- raw: 文件全文
- meta: frontmatter 字典（--- ... --- 之间，key: value）
- body: 剥离 frontmatter 后的正文（gate-check 的语义；humanizer 扫描用的也是这个）

注意（v1 行为保留说明）：
- wordcount-check 另有一套"跳过 #第X章 标题"的提取逻辑且不剥 frontmatter，
  迁移时原样保留（见 tools/wordcount-check.py 注释），此处不收编——
  口径统一是 Phase 3/4 的决策，本阶段只求行为一致。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


def _split_frontmatter(raw: str):
    """拆 frontmatter。well-formed 输入与 v1 gate-check._load_chapter 语义一致。

    v1 边缘差异（已修正，未保留）：原文以 --- 开头但没有闭合 --- 时，
    v1 会取 raw[4:]（find 返回 -1 + 5 的意外行为）；此处视为无 frontmatter。
    """
    meta: Dict[str, str] = {}
    if raw.startswith("---"):
        closing = raw.find("\n---\n")
        if closing != -1:
            for line in raw.split("\n")[1:]:
                if line == "---":
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            return meta, raw[closing + 5:].strip()
    return meta, raw


@dataclass
class Chapter:
    path: Path            # 绝对路径（构造时即 resolve，从结构上消灭相对路径/cwd 类 bug）
    novel_id: str
    raw: str              # 全文
    meta: Dict[str, str]  # frontmatter
    body: str             # 剥离 frontmatter 后的正文

    @classmethod
    def load(cls, path, novel_id: str = "") -> "Chapter":
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"章节文件不存在: {p}")
        raw = p.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(raw)
        return cls(path=p, novel_id=novel_id, raw=raw, meta=meta, body=body)

    def char_count(self) -> int:
        """门禁口径：全部非空白字符（含标点，不含空白）。唯一字数口径。"""
        return len(re.sub(r"\s+", "", self.body))

    def chinese_count(self) -> int:
        """纯汉字口径（旧选项 --chinese-only 用）。"""
        text = self.body
        for pat, rep in [(r"#{1,6}\s*", ""), (r"\*\*(.*?)\*\*", r"\1"),
                         (r"\*(.*?)\*", r"\1"), (r"~~(.*?)~~", r"\1"),
                         (r"`(.*?)`", r"\1")]:
            text = re.sub(pat, rep, text)
        return len(re.findall(r"[\u4e00-\u9fff]", text))

    def save(self) -> None:
        """写回（保留 frontmatter）。"""
        if self.meta:
            fm = "---\n" + "".join(f"{k}: {v}\n" for k, v in self.meta.items()) + "---\n"
            self.raw = fm + self.body
        else:
            self.raw = self.body
        self.path.write_text(self.raw, encoding="utf-8")
