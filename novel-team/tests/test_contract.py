#!/usr/bin/env python3
"""v2 契约测试（设计文档 §7 输出契约 / §10 回归要求）。

锁定的契约：
1. novelkit.core.config.novel_team_root() 与 tools/project_guard.BASE_DIR 同源
2. CheckResult / GateReport 的 to_dict() 字段名锁定、可 JSON 序列化
3. Chapter.path 恒为绝对路径（相对路径/cwd 类 bug 从结构上消失）
4. 统一配置默认值（10-01 决策）：soft_min=2000、hard_min=1500、warn_above=5500、target=2500
5. CLI 的 stdout 为纯 JSON（无警告行混入）
6. config/novelkit.json 为合法 JSON 且被实际加载（H1 回归）
7. P0 WARNING 不阻断（与 check() 口径一致），FAIL/ERROR 才阻断（M1 回归）
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from novelkit.core.chapter import Chapter
from novelkit.core.config import Config, get_config, novel_team_root
from novelkit.core.results import CheckResult, GateReport, Severity, CheckStatus

PASS, FAIL = "✅", "❌"
failures = []


def check(name, cond, extra=""):
    print(f"{PASS if cond else FAIL} {name}" + ("" if cond else f" — {extra}"))
    if not cond:
        failures.append(name)


# 1. 路径同源
os.environ["NOVEL_TEAM_ROOT"] = "/tmp/contract-test-root"
import importlib
import project_guard
importlib.reload(project_guard)
check("NOVEL_TEAM_ROOT 设置时 novel_team_root()==BASE_DIR",
      novel_team_root() == project_guard.BASE_DIR,
      f"{novel_team_root()} vs {project_guard.BASE_DIR}")
del os.environ["NOVEL_TEAM_ROOT"]
importlib.reload(project_guard)
check("默认 novel_team_root()==BASE_DIR",
      novel_team_root() == project_guard.BASE_DIR)

# 2. 结果模型契约
r = CheckResult(check="ai_tone", status=CheckStatus.FAIL, severity=Severity.BLOCK,
                score=18.5, details=["d1"], suggestions=["s1"])
d = r.to_dict()
check("CheckResult 字段锁定",
      set(d.keys()) == {"check", "status", "severity", "score", "details", "suggestions", "raw"},
      str(set(d.keys())))
json.dumps(d)
check("CheckResult 可 JSON 序列化", True)

rep = GateReport(passed=False, will_block=True, p0_failures=[r],
                 chapter_file="/x.md", tier_1a_score=18.5)
rd = rep.to_dict()
check("GateReport 字段锁定",
      set(rd.keys()) == {"passed", "will_block", "chapter_file", "tier_1a_score",
                         "p0_failures", "p1_warnings", "p2_suggestions", "errors"})
json.dumps(rd)

# 3. Chapter.path 绝对
tmp = Path("/tmp/contract-chapter.md")
tmp.write_text("---\ntitle: t\n---\n正文内容\n", encoding="utf-8")
c = Chapter.load(str(tmp), novel_id="n")
check("Chapter.path 为绝对路径", c.path.is_absolute(), str(c.path))
check("Chapter.meta 解析", c.meta.get("title") == "t", str(c.meta))
check("Chapter.body 剥离 frontmatter", c.body == "正文内容", repr(c.body))
check("Chapter.char_count 口径", c.char_count() == 4, str(c.char_count()))

# 相对路径传入也 resolve
cwd = os.getcwd()
os.chdir("/tmp")
c2 = Chapter.load("contract-chapter.md", novel_id="n")
check("相对路径传入仍得绝对路径", c2.path.is_absolute() and c2.path == tmp)
os.chdir(cwd)

# 4. 配置默认值（novel-team：2026-10-01 评审决策，字数下限升级 2000，新增 hard_min=1500）
cfg = Config()
check("soft_min=2000（10-01 决策）", cfg.get("word_count", "soft_min") == 2000)
check("hard_min=1500（10-01 决策）", cfg.get("word_count", "hard_min") == 1500)
check("warn_above=5500", cfg.get("word_count", "warn_above") == 5500)
check("target=2500", cfg.get("word_count", "target") == 2500)
check("ai_tone.threshold=15.0", cfg.get("ai_tone", "threshold") == 15.0)
check("ai_tone.block_at=16.0", cfg.get("ai_tone", "block_at") == 16.0)

# 5. stdout 纯 JSON
p = subprocess.run([sys.executable, str(REPO / "tools/wordcount-check.py"),
                    str(tmp), "--json"],
                   capture_output=True, text=True, cwd=str(REPO))
try:
    json.loads(p.stdout)
    pure = True
except Exception:
    pure = False
check("wordcount-check --json 的 stdout 为纯 JSON", pure, p.stdout[:120])
check("退出码语义（4字<2000 → fail → 1）", p.returncode == 1, str(p.returncode))

# 6. 配置文件可解析且被实际加载（H1 回归：文件曾不是合法 JSON，
#    解析失败被静默吞掉，Config 永远回退默认值）
cfg_path = REPO / "config" / "novelkit.json"
try:
    file_data = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg_valid = isinstance(file_data, dict)
except Exception as e:
    cfg_valid = False
    file_data = {}
    print(f"  配置文件解析异常: {e}")
check("config/novelkit.json 为合法 JSON", cfg_valid)
cfg_loaded = Config()
check("配置文件被实际加载（source 指向文件）",
      cfg_loaded.source == str(cfg_path), cfg_loaded.source)
if cfg_valid:
    check("配置文件值生效（非静默回退默认值）",
          cfg_loaded.get("word_count", "soft_min") == file_data["word_count"]["soft_min"]
          and cfg_loaded.get("ai_tone", "block_at") == file_data["ai_tone"]["block_at"])

# 7. M1 回归：P0 warning 不阻断（与 check()/_evaluate_results 口径一致），但保持可见
from novelkit.pipeline.orchestrator import Orchestrator
_warn_r = CheckResult(check="ai_tone", status=CheckStatus.WARNING,
                     severity=Severity.BLOCK, details=["接近阈值"])
_fail_r = CheckResult(check="protocol", status=CheckStatus.FAIL,
                     severity=Severity.BLOCK, details=["x"])
_err_r = CheckResult(check="protocol", status=CheckStatus.ERROR,
                    severity=Severity.BLOCK, details=["y"])
check("P0 WARNING 不计入阻断", Orchestrator._p0_blocking([_warn_r]) == [])
check("P0 FAIL 计入阻断", len(Orchestrator._p0_blocking([_fail_r])) == 1)
check("P0 ERROR 计入阻断", len(Orchestrator._p0_blocking([_err_r])) == 1)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("全部通过")
