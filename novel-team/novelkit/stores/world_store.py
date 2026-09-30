"""WorldStore — 世界包读取层。

从 tools/world-pack.py 的 WorldPack 迁移而来的读取 API，语义原样保留
（含 2026-09-30 全量修复：add_relation 必写 to 键、历史缺 to 关系报 warning）。

与 v1 不同的地方（有意为之，已评审）：
1. 路径：v1 world-pack.py 把 WORLD_DIR 硬编码为 /var/minis/shared/novel-team/.world-packs，
   且在 import 时就 mkdir（D3 同类 bug）。此处改走 novelkit.core.config.novel_team_root()
   （NOVEL_TEAM_ROOT 环境变量，默认 /var/minis/shared/novel-team），目录惰性创建。
   在 OpenMinis 生产环境（NOVEL_TEAM_ROOT 未设置）行为与 v1 完全一致。
2. 只读为主：entries / check_consistency / stats 做薄封装；写操作（add_entry、
   add_relation、add_source）直接通过 get_pack() 返回的底层 WorldPack 对象调用，
   不另包一层（保持 v1 写入语义逐字一致）。

注意：世界包是跨项目的全局包，与 novel_id 无关——这是 v1 的设计，保持。
"""

import importlib.util
from pathlib import Path
from typing import Dict, List, Optional

from novelkit.core import log
from novelkit.core.config import novel_team_root

_WORLD_PACK_MOD = None  # 进程内只加载一次


def _load_world_pack_module():
    """importlib 加载 tools/world-pack.py（连字符文件名，非合法模块名）。"""
    global _WORLD_PACK_MOD
    if _WORLD_PACK_MOD is not None:
        return _WORLD_PACK_MOD
    path = Path(__file__).resolve().parents[2] / "tools" / "world-pack.py"
    spec = importlib.util.spec_from_file_location("world_pack", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _WORLD_PACK_MOD = mod
    return mod


class WorldStore:
    """世界包读取层（跨项目全局）。"""

    def __init__(self):
        mod = _load_world_pack_module()
        self._WorldPack = mod.WorldPack
        # 与修补后的 world-pack.py._world_dir() 同源（NOVEL_TEAM_ROOT）
        self.dir = novel_team_root() / ".world-packs"

    # --- 包 ---

    def list_packs(self) -> List[str]:
        """列出所有世界包名。目录不存在时返回空列表，不报错。"""
        if not self.dir.exists():
            return []
        return sorted(p.stem for p in self.dir.glob("*.json"))

    def get_pack(self, name: str) -> Optional[object]:
        """返回底层的 WorldPack 对象（写操作直接调它的方法）。

        包不存在或读取失败时返回 None，不抛异常。
        """
        if not (self.dir / f"{name}.json").exists():
            return None
        try:
            return self._WorldPack(name)
        except Exception as e:
            log.warn(f"WorldStore.get_pack: 读取世界包 {name} 失败: {e}")
            return None

    # --- 只读 API（v1 WorldPack 语义原样） ---

    def entries(self, name: str, kind: str = None,
                status: str = None) -> List[Dict]:
        """返回世界包条目（dict 列表），可按 kind/status 过滤。"""
        pack = self.get_pack(name)
        if pack is None:
            return []
        out = []
        for entry in pack.entries.values():
            if kind and entry.kind != kind:
                continue
            if status and entry.status != status:
                continue
            out.append(entry.to_dict())
        return out

    def check_consistency(self, name: str) -> List[Dict]:
        """v1 WorldPack.check_consistency 原样（21 条规则，问题带指纹）。"""
        pack = self.get_pack(name)
        if pack is None:
            return []
        return pack.check_consistency()

    def stats(self, name: str) -> Dict:
        """v1 WorldPack.get_stats 原样。包不存在时返回空 dict。"""
        pack = self.get_pack(name)
        if pack is None:
            return {}
        return pack.get_stats()
