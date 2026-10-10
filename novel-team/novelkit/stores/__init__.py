"""stores 包：账本/世界包/债务的访问层。不再裸操作 JSON（问题 #7）。

Stores 束：Context 携带的统一数据访问入口，插件需要文件 IO 时走
ctx.stores，不自己拼路径（契约第 2 条）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from novelkit.stores.fact_store import FactStore

if TYPE_CHECKING:  # 避免循环 import；运行时按需导入
    from novelkit.stores.debt_store import DebtStore
    from novelkit.stores.world_store import WorldStore


@dataclass
class Stores:
    """插件可用的数据访问束。

    fact: 事实账本（FactStore，novel 级）
    debt: 质量债务账本（DebtStore，novel 级，惰性构造）
    world: 世界包（WorldStore，全局，与 novel_id 无关，惰性构造）
    """

    fact: FactStore
    _novel_id: str = ""
    _debt: Optional["DebtStore"] = None
    _world: Optional["WorldStore"] = None

    @property
    def debt(self) -> "DebtStore":
        # L10：惰性构造。门禁检查目前只用 fact；DebtStore/WorldStore
        # 按需加载，避免 WorldStore.__init__ 每次 importlib exec
        # world-pack.py 的浪费，以及 world-pack import 期报错连带拖死门禁。
        if self._debt is None:
            from novelkit.stores.debt_store import DebtStore
            self._debt = DebtStore(self._novel_id)
        return self._debt

    @property
    def world(self) -> "WorldStore":
        if self._world is None:
            from novelkit.stores.world_store import WorldStore
            self._world = WorldStore()
        return self._world

    @classmethod
    def for_novel(cls, novel_id: str) -> "Stores":
        """为指定作品构造 stores 束（fact 立即构造，debt/world 惰性）。"""
        return cls(fact=FactStore(novel_id), _novel_id=novel_id)
