"""stores 包：账本/世界包/债务的访问层。不再裸操作 JSON（问题 #7）。

Stores 束：Context 携带的统一数据访问入口，插件需要文件 IO 时走
ctx.stores，不自己拼路径（契约第 2 条）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from novelkit.stores.fact_store import FactStore

if TYPE_CHECKING:  # 避免循环 import；运行时按需导入
    from novelkit.stores.debt_store import DebtStore
    from novelkit.stores.world_store import WorldStore


@dataclass
class Stores:
    """插件可用的数据访问束。

    fact: 事实账本（FactStore，novel 级）
    debt: 质量债务账本（DebtStore，novel 级）
    world: 世界包（WorldStore，全局，与 novel_id 无关）
    """

    fact: FactStore
    debt: "DebtStore" = field(default=None)  # type: ignore[assignment]
    world: "WorldStore" = field(default=None)  # type: ignore[assignment]

    @classmethod
    def for_novel(cls, novel_id: str) -> "Stores":
        """为指定作品构造完整的 stores 束（惰性导入，避免循环依赖）。"""
        from novelkit.stores.debt_store import DebtStore
        from novelkit.stores.world_store import WorldStore

        return cls(
            fact=FactStore(novel_id),
            debt=DebtStore(novel_id),
            world=WorldStore(),
        )
