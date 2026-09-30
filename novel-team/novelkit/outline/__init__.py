"""novelkit.outline — 大纲结构化加载。

把大纲（markdown / JSON）解析为 Outline 对象，供 Phase 4 的
"大纲偏离检测"与"账本预填"共用。

设计原则：容错优先——解析失败不抛异常，尽量多提取。
"""

from novelkit.outline.loader import (
    Outline,
    OutlineChapter,
    OutlineCharacter,
    find_outline,
    load_outline,
)

__all__ = [
    "Outline",
    "OutlineChapter",
    "OutlineCharacter",
    "find_outline",
    "load_outline",
]
