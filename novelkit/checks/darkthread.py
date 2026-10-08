"""暗线追踪检查插件（v2 Phase 2：由 tools/gate-check.py _check_darkthread 移植）。

检查伏笔是否推进：读取 dark-threads/ 下最新的 ch*_snapshot.yaml，
统计活跃伏笔在本章被提及的数量。纯 Python，逐行移植。

注意：v1 通过 `import yaml` 解析快照（PyYAML 非标准库）；缺失时走 except 分支
→ status=pass + details 说明检查失败。此处保留相同语义（v1 行为保真），
不引入新的 YAML 解析器。
"""

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core import log
from novelkit.core.results import CheckResult, CheckStatus, Severity


@register
class DarkthreadCheck:
    """暗线追踪检查（P2；v1 _classify_gate：非 p0/p1 即 P2）。"""

    name = "darkthread"
    default_severity = Severity.ADVICE

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        raw = {"status": "pass", "details": [], "foreshadowing_pushed": 0}
        try:
            darkthreads_dir = ctx.project_dir / "dark-threads"
            if not darkthreads_dir.exists():
                return self._to_result(raw)

            # 找到最新的快照
            snapshots = list(darkthreads_dir.glob("ch*_snapshot.yaml"))
            if not snapshots:
                return self._to_result(raw)

            latest = max(snapshots, key=lambda p: p.stat().st_mtime)

            # 读取当前章节内容（v1 读文件原文；chapter.raw 即文件原文）
            content = chapter.raw

            # 检查是否提及了活跃的伏笔
            import yaml
            snapshot = yaml.safe_load(latest.read_text())
            active_foreshadowing = snapshot.get("foreshadowing_active", [])

            pushed = 0
            for foreshadow in active_foreshadowing:
                if foreshadow[:10] in content or foreshadow[:5] in content:
                    pushed += 1

            raw["foreshadowing_pushed"] = pushed
            if pushed == 0 and len(active_foreshadowing) > 0:
                raw["status"] = "warning"
                raw["details"].append(f"未推进任何伏笔（活跃{len(active_foreshadowing)}条）")
        except Exception as e:
            # v1 语义：异常（含 yaml 缺失）→ pass + details 说明检查失败。
            raw["status"] = "pass"
            raw["details"].append(f"暗线追踪检查失败: {e}")
            log.warn(f"darkthread 执行异常：{e}")

        return self._to_result(raw)

    def _to_result(self, raw: dict) -> CheckResult:
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}.get(raw["status"], CheckStatus.ERROR)
        return CheckResult(
            check=self.name,
            status=status,
            severity=self.default_severity,
            details=list(raw.get("details", [])),
            raw=raw,
        )
