"""novelkit.checks.base — 检查插件协议与注册表。

插件契约（设计文档 §6）：
1. @register 装饰器注册，不改编排器即插即用
2. 输入只收 (Chapter, Context)；文件 IO 走 ctx.stores，不自己拼路径
3. 输出 CheckResult（raw 字段携带 v1 形状 dict，供门禁 CLI 兼容）
4. run() 内自行捕获异常并映射为 warning/fail（"检查没跑"必须可见，
   不静默为 pass；编排器 _run_check 另有最后兜底→ warning）
   （M2 修正：原"run() 内不捕获异常——抛给编排器统一记 error"与全部
   13 个插件的实现脱节，已按实际规范改写）
5. 不 print；日志走 novelkit.core.log（→ stderr）
6. 类属性声明 severity：P0 阻断 / P1 警告 / P2 建议
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Protocol, Type

from novelkit.core.chapter import Chapter
from novelkit.core.config import Config
from novelkit.core.results import CheckResult, CheckStatus

if TYPE_CHECKING:
    from novelkit.stores import Stores


@dataclass
class Context:
    """检查运行上下文。"""
    config: Config
    novel_id: str
    chapter: Chapter
    project_dir: Path          # resolve(novel_id).root_dir（v1 GateChecker.project_dir）
    repo_root: Path            # novelkit 所在仓库根（tools/ 的父目录）
    flexible: bool = False     # 柔性模式
    mode: str = "write"        # write（完整）/ modify（修改）
    stores: Optional["Stores"] = None  # Phase 3：fact/world/debt 数据访问束


class Check(Protocol):
    """检查插件协议。"""
    name: str
    default_severity: str

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        ...


_REGISTRY: Dict[str, Type[Check]] = {}


def register(cls: Type[Check]) -> Type[Check]:
    """插件注册装饰器。"""
    if not getattr(cls, "name", None):
        raise ValueError(f"Check {cls.__name__} 缺少 name 属性")
    _REGISTRY[cls.name] = cls
    return cls


def get_check(name: str) -> Optional[Type[Check]]:
    return _REGISTRY.get(name)


def all_checks() -> Dict[str, Type[Check]]:
    return dict(_REGISTRY)


def skipped_result(name: str, severity: str, reason: str) -> CheckResult:
    """modify 模式跳过项：v1 语义（status=skipped，不参与判定；raw 与 v1 形状一致）。"""
    raw = {"status": "skipped", "reason": reason, "details": []}
    return CheckResult(check=name, status=CheckStatus.SKIPPED,
                       severity=severity, details=[], raw=raw)
