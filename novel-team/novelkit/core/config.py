"""统一配置：唯一阈值来源。

设计文档 §8。`config/novelkit.json` 为唯一阈值/开关来源；
`NOVEL_TEAM_ROOT` 等环境变量继续有效。任何新增阈值必须进这个文件，
不允许散落在检查代码里（code review 红线）。

v1 → v2 阈值迁移（评审决策 2026-09-30：取严，不保留双轨）：
- word_count.soft_min = 1500（原 wordcount-check fail 线 1350 与
  gate soft_min 1500 分裂，统一取严；下限不再打 flexible_range 折扣）
- word_count.warn_above = 5500（原两处一致）
- word_count.target = 2500（写作目标，非门禁）
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULTS: Dict[str, Any] = {
    "word_count": {
        "target": 2500,       # 写作目标（非门禁）
        "soft_min": 1500,     # 下限：低于此为 fail/P1（取严，见模块 docstring）
        "warn_above": 5500,   # 超长警告线：高于此为 warning（与 v1 行为一致）
    },
    "ai_tone": {
        "threshold": 15.0,    # humanizer 默认阈值
        "block_at": 16.0,     # tier_1a 阻断线（P0）：tier_1a >= 16 → fail
        "warn_at": 13,        # 接近阈值预警线：13 <= tier_1a <= 15 → warning
    },
}

CONFIG_FILENAME = "novelkit.json"


def _config_path() -> Path:
    # novelkit/core/config.py -> parents[2] = 仓库根 -> config/novelkit.json
    return Path(__file__).resolve().parents[2] / "config" / CONFIG_FILENAME


def novel_team_root() -> Path:
    """项目根目录。与 tools/project_guard.BASE_DIR 同源（环境变量 NOVEL_TEAM_ROOT）。

    两处默认值用 contract 测试锁定一致（tests/test_contract.py），
    避免"看起来一样其实两套"的分裂重演。
    """
    return Path(os.environ.get("NOVEL_TEAM_ROOT", "/var/minis/shared/novel-team"))


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


class Config:
    """统一配置对象。"""

    def __init__(self, overrides: Optional[Dict[str, Any]] = None):
        data = _deep_merge(DEFAULTS, {})
        path = _config_path()
        if path.exists():
            try:
                file_data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(file_data, dict):
                    data = _deep_merge(data, file_data)
            except Exception as e:
                # H1 修复：配置文件损坏时必须可见，不能静默吞错
                # （否则阈值修改不生效且无声无息）。回退默认值，不阻断。
                print(f"novelkit: 配置文件解析失败 {path}: {e}，已回退默认值",
                      file=sys.stderr)
        if overrides:
            data = _deep_merge(data, overrides)
        self._data = data
        self.source = str(path) if path.exists() else "<defaults>"

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    @property
    def word_count(self) -> Dict[str, Any]:
        return self._data["word_count"]

    @property
    def ai_tone(self) -> Dict[str, Any]:
        return self._data["ai_tone"]

    def to_dict(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self._data))


_config: Optional[Config] = None


def get_config() -> Config:
    """进程内单例。测试可用 Config(overrides={...}) 构造独立实例。"""
    global _config
    if _config is None:
        _config = Config()
    return _config
