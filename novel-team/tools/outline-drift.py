#!/usr/bin/env python3
"""大纲偏离检测 CLI（v2 Phase 4 新能力）。

把章节正文与大纲该章 beats 做关键词覆盖检查，输出偏离 findings。
只读检查，不写任何文件。

用法：
    python tools/outline-drift.py --novel-id my-novel --dir <章节目录> [--outline path]

stdout 纯 JSON；诊断走 stderr。
退出码：0=完成（有 finding 也不阻断，偏离属 P2 建议）；2=出错。
"""

import argparse
import json
import sys
from pathlib import Path

# 让 novelkit 可导入（无论从哪个目录调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novelkit.core import log as _log  # noqa: E402
from novelkit.core.resolve import resolve  # noqa: E402
from novelkit.outline import find_outline, load_outline  # noqa: E402
from novelkit.pipeline.outline_drift import check_drift  # noqa: E402

log = _log


def main() -> int:
    ap = argparse.ArgumentParser(description="大纲偏离检测（只读）")
    ap.add_argument("--novel-id", default="my-novel")
    ap.add_argument("--dir", default=None, help="章节目录，缺省为 <project>/current/chapters")
    ap.add_argument("--outline", default=None, help="大纲文件路径（缺省自动查找）")
    ap.add_argument("--json", action="store_true", help="兼容标志：输出恒为 JSON")
    args = ap.parse_args()

    try:
        project_dir = resolve(args.novel_id).root_dir
        ch_dir = Path(args.dir).expanduser() if args.dir else project_dir / "chapters"
        if not ch_dir.is_dir():
            log.error(f"章节目录不存在: {ch_dir}")
            return 2

        o_path = Path(args.outline).expanduser() if args.outline else find_outline(project_dir)
        if o_path is None:
            log.error("找不到大纲文件（--outline 指定或按约定查找）")
            return 2
        log.info(f"大纲: {o_path}")
        outline = load_outline(o_path)
        if not outline.chapters:
            log.error(f"大纲中没有解析出任何章节: {o_path}")
            return 2

        files = sorted(str(p) for p in ch_dir.glob("*.md"))
        if not files:
            log.warn(f"章节目录为空: {ch_dir}")
        log.info(f"待检查章节: {len(files)} 个")

        report = check_drift(args.novel_id, files, outline)
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        log.error(f"偏离检测失败: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
