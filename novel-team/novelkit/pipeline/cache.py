"""novelkit.pipeline.cache — 按文件 hash 的检查缓存（Phase 3）。

iSH 性能：章节内容未变更时跳过检查，直接返回上次结果。

缓存键 = sha256(章节原文 + 模式 + 柔性标志 + novel_id + 配置 JSON
              + novelkit 版本)，取前 16 位 hex。
缓存文件：<project_dir>/.novel/cache/gate-<key>.json（纯 JSON，可人工查看）。

命中时返回缓存的整套门禁结果 dict；不重做报告落盘/账本同步/事件发射
等副作用——与「未变更章节跳过」的语义一致。调用方如需强制重跑，
传 use_cache=False 或 CLI --no-cache。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import novelkit
from novelkit.core import log as _log

log = _log

CACHE_VERSION = 1  # 缓存格式版本；payload 结构变化时递增


class CheckCache:
    """门禁结果缓存。"""

    def __init__(self, project_dir: Path):
        self.dir = Path(project_dir) / ".novel" / "cache"

    def key(self, chapter_raw: str, novel_id: str, mode: str,
            flexible: bool, config_dict: Dict[str, Any],
            tool_hashes: str = "") -> str:
        h = hashlib.sha256()
        h.update(chapter_raw.encode("utf-8"))
        h.update(novel_id.encode("utf-8"))
        h.update(mode.encode("utf-8"))
        h.update(b"1" if flexible else b"0")
        h.update(json.dumps(config_dict, sort_keys=True,
                            ensure_ascii=False).encode("utf-8"))
        h.update(novelkit.__version__.encode("utf-8"))
        h.update(str(CACHE_VERSION).encode("utf-8"))
        # L1：检查插件经 importlib 加载 tools/*.py（novel-humanizer.py、
        # logic-review.py、anti-ai-12.py），改了这些文件缓存必须失效。
        h.update(tool_hashes.encode("utf-8"))
        return h.hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self.dir / f"gate-{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning(f"缓存读取失败（视为未命中）: {p}: {e}")
            return None

    def put(self, key: str, payload: Dict[str, Any]) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            p = self._path(key)
            fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                os.replace(tmp, p)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        except OSError as e:
            # 缓存写失败不阻断门禁
            log.warning(f"缓存写入失败（忽略）: {e}")

    def invalidate(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError:
            pass
