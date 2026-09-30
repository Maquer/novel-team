#!/usr/bin/env python3
"""交付索引器 — 把项目产物列成带 minis:// 链接的清单。

存在理由：SOP 定义了「交付物」但没有任何一步要求把文件回给用户，
导致文件落盘 = 交付完成，用户看不到任何东西。本脚本把
「记得贴链接」这个依赖主动想起的规则，降级成「跑一条命令，贴输出」。

用法:
  python3 tools/deliver-index.py --project helper-creator
  python3 tools/deliver-index.py --project helper-creator --json
  python3 tools/deliver-index.py --project helper-creator --check   # 只判定，不打印清单

退出码: 0 有产物 / 1 项目不存在或零产物（禁止静默成功）
"""
import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(os.environ.get("NOVEL_TEAM_ROOT", "/var/minis/shared/novel-team"))
MINIS_BASE = "minis://shared/novel-team"

# 阶段 -> (相对子目录/文件名, 类型标签, 是否必须)。顺序即阅读顺序。
STAGES = [
    ("① 决策与大纲", [
        ("DECISION-TREE.md", "决策树", False),
        ("outline/outline-v2.md", "大纲 v2", False),
        ("outline/outline-v1.md", "大纲 v1", False),
        ("outline/DECISION-TREE-outline.md", "大纲决策记录", False),
        ("outline/vol-001-brief.yaml", "卷细纲", False),
    ]),
    ("② 世界包", [
        ("world/core-concept.md", "核心概念", False),
        ("world/core-logic.md", "世界逻辑", True),
        ("world/iron-laws.md", "铁律(对接门禁)", True),
        ("world/world-bible.md", "世界圣经", False),
        ("world/world-pack.json", "世界数据包", False),
    ]),
    ("③ 角色", [
        ("characters/protagonist.json", "主角", True),
    ]),
    ("④ 章节正文", []),          # 动态扫描
    ("⑤ 细纲", []),              # 动态扫描
    ("⑥ 报告与账本", [
        ("docs/progress-report.md", "进度报告", False),
        ("../ledger/{pid}/facts.json", "事实账本", False),
    ]),
]
REQUIRED_TOTAL = 0  # 硬性必须项按下面运行时统计


def link(p: Path) -> str:
    """相对 novel-team 根 -> minis:// 链接。"""
    try:
        rel = p.resolve().relative_to(BASE_DIR.resolve())
    except ValueError:
        return str(p.resolve())
    return f"{MINIS_BASE}/{rel}"


def size(p: Path) -> str:
    n = p.stat().st_size
    return f"{n}B" if n < 1024 else f"{n // 1024}KB"


def chars(p: Path) -> int:
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    body = txt.split("---", 2)[-1] if txt.startswith("---") else txt
    return len([c for c in body if not c.isspace()])


def collect(pid: str, root: Path):
    """返回 [(阶段, 标签, Path, 字数)]，按 STAGES 顺序。"""
    cur = root / "projects" / pid / "current"
    if not cur.is_dir():
        return cur, []
    out, seen = [], set()

    for stage, fixed in STAGES:
        for sub, label, req in fixed:
            f = (cur / sub.replace("{pid}", pid)).resolve()
            if f.is_file() and f not in seen:
                seen.add(f)
                out.append((stage, label + ("  ⚠️必须" if req else ""), f, chars(f)))
        if stage.startswith("④"):
            d = cur / "chapters"
            for f in sorted(d.glob("ch*.md")) if d.is_dir() else []:
                if f not in seen:
                    seen.add(f)
                    out.append((stage, f.stem, f, chars(f)))
        if stage.startswith("⑤"):
            d = cur / "outline"
            for f in sorted(d.glob("ch-*-brief.md")) if d.is_dir() else []:
                if f not in seen:
                    seen.add(f)
                    out.append((stage, f.stem, f, chars(f)))
    return cur, out


def stray_copies(pid: str):
    """检出 project_guard 规范路径之外的同名项目目录（相对路径 bug 产物）。"""
    hits = []
    for p in BASE_DIR.rglob(pid):
        if p.is_dir() and (p / "chapters").is_dir() or (p.is_dir() and (p / "world").is_dir()):
            canon = (BASE_DIR / "projects" / pid / "current").resolve()
            try:
                p.resolve().relative_to(canon)
                continue          # 在规范路径下，正常
            except ValueError:
                pass
            n = sum(1 for _ in p.rglob("*.md"))
            if n:
                hits.append((p, n))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true", help="只判定有无产物，不打印清单")
    a = ap.parse_args()

    cur, items = collect(a.project, BASE_DIR)
    stray = stray_copies(a.project)

    if not items:
        print(f"ERROR: 项目 '{a.project}' 在 {cur} 下无任何交付物", file=sys.stderr)
        return 1

    if a.json:
        print(json.dumps({
            "project": a.project, "root": str(cur), "count": len(items),
            "total_chars": sum(c for *_, c in items),
            "stray_copies": [str(p) for p, _ in stray],
            "items": [{"stage": s, "label": l, "path": str(f), "url": link(f), "chars": c}
                      for s, l, f, c in items],
        }, ensure_ascii=False, indent=2))
        return 0

    if a.check:
        print(f"OK {a.project}: {len(items)} 个交付需要同步给用户")
        return 0

    total = sum(c for *_, c in items)
    print(f"## 「{a.project}」交付清单 — {len(items)} 个文件 / 正文累计 {total} 字\n")
    last = None
    for stage, label, f, c in items:
        if stage != last:
            print(f"\n### {stage}")
            last = stage
        note = f"（{c} 字）" if c > 200 else ""
        print(f"- [{label}]({link(f)}) {size(f)}{note}")
    if stray:
        print("\n### ⚠️ 游离副本（不在 project_guard 规范路径下）")
        for p, n in stray:
            print(f"- `{p}` — {n} 个 md，可能是工具相对路径 bug 产生，"
                  f"其中的大纲/决策树可能尚未归位到 `projects/{a.project}/current/`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
