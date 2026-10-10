"""novelkit.core.resolve — 项目根目录解析。

v1 对应物：tools/project_guard.py 的 resolve()（代际 manifest 机制）。
v2 精简版：门禁/插件只需要「当前代际可写目录」，
路径约定与 v1 完全一致：<root>/projects/<novel_id>/current，
其中 <root> = novel_team_root()（NOVEL_TEAM_ROOT 环境变量，
默认 /var/minis/shared/novel-team）。

代际归档等管理操作仍保留在 tools/project_guard.py（CLI 兼容垫片），
不迁入 novelkit。
"""

from dataclasses import dataclass
from pathlib import Path

from novelkit.core.config import novel_team_root


@dataclass
class ProjectRoot:
    project_id: str
    root_dir: Path


def resolve(novel_id: str) -> ProjectRoot:
    """解析项目根目录（当前代际）。目录惰性创建：只在写入时建。"""
    # FIX 2026-09-30（v1 project_guard 同款）：project_id 不做格式强校验，宽松接受
    root_dir = novel_team_root() / "projects" / novel_id / "current"
    return ProjectRoot(project_id=novel_id, root_dir=root_dir)


def ensure_dir(path: Path) -> Path:
    """确保目录存在（写入时调用）。"""
    path.mkdir(parents=True, exist_ok=True)
    return path
