"""novelkit.pipeline.ledger_prefill — 从大纲预填事实账本（Phase 4 新能力）。

把大纲里的世界观/人物/章节钩子抽成事实写入 FactStore，
source="outline"，verified=True（大纲是正源）。幂等：content+category
完全相同的已有事实跳过，跑两次第二次 added=0。

大纲解析：复用 novelkit/outline/loader.py（Phase 4 交付）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from novelkit.core import log as _log
from novelkit.core.config import novel_team_root
from novelkit.core.resolve import resolve
from novelkit.outline.loader import load_outline
from novelkit.stores.fact_store import FactStore

log = _log


@dataclass
class PrefillResult:
    added: int = 0
    skipped_dup: int = 0
    fact_ids: List[str] = field(default_factory=list)
    outline_path: str = ""

    def to_dict(self) -> Dict:
        return {
            "added": self.added,
            "skipped_dup": self.skipped_dup,
            "fact_ids": list(self.fact_ids),
            "outline_path": self.outline_path,
        }


def _locate_outline(novel_id: str, outline_path: Optional[str]) -> Optional[Path]:
    if outline_path:
        p = Path(outline_path)
        return p if p.exists() else None
    candidates = [
        resolve(novel_id).root_dir / "outline.md",
        novel_team_root() / "outline.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def prefill_from_outline(novel_id: str,
                         outline_path: Optional[str] = None,
                         dry_run: bool = False) -> PrefillResult:
    """从大纲预填事实账本。找不到大纲时返回 added=0，不抛异常。"""
    result = PrefillResult()
    path = _locate_outline(novel_id, outline_path)
    if path is None:
        log.warn(f"未找到大纲文件（novel_id={novel_id}），跳过预填")
        return result
    result.outline_path = str(path)

    # L5 修复：删掉未使用的 text 读取（load_outline 内部会再读一次）。
    outline = load_outline(str(path))
    log.info(f"大纲解析完成：世界观{len(outline.world)}行 / "
             f"人物{len(outline.characters)}个 / 章节{len(outline.chapters)}章")

    store = FactStore(novel_id)
    existing = {(f.get("category"), f.get("content")) for f in store.facts.values()}

    def _add(category: str, content: str):
        content = content.strip()
        if not content:
            return
        if (category, content) in existing:
            result.skipped_dup += 1
            return
        if dry_run:
            result.added += 1  # dry-run 只统计
            result.fact_ids.append("(dry-run)")
            return
        fid = store.add_fact(category=category, content=content,
                             source="outline", allow_test=True)
        store.verify_fact(fid)  # 大纲是正源，直接标 verified
        existing.add((category, content))
        result.added += 1
        result.fact_ids.append(fid)

    for w in outline.world:
        _add("world", w)
    for c in outline.characters:
        content = c.name if not c.desc else f"{c.name}：{c.desc}"
        _add("character", content)
    for ch in outline.chapters:
        content = f"第{ch.no}章 {ch.title}".strip()
        if ch.hooks:
            content += f"：钩子：{'；'.join(ch.hooks)}"
        _add("plot", content)

    return result
