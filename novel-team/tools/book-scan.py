#!/usr/bin/env python3
"""全书扫描 CLI（v2 Phase 4 新能力）。

对指定目录（或项目章节目录）下的全部章节逐个跑门禁，输出书级报告。
stdout 纯 JSON；诊断走 stderr。

退出码：全部通过 → 0；有失败章节 → 1；出错 → 2。
"""

import argparse
import json
import sys
from pathlib import Path

# 让 novelkit 可导入（无论从哪个目录调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novelkit.core import log
from novelkit.core.resolve import resolve
from novelkit.pipeline.book_scan import scan_book


def main() -> int:
    ap = argparse.ArgumentParser(description="全书扫描：逐章门禁 + 书级汇总")
    ap.add_argument("--novel-id", default="my-novel")
    ap.add_argument("--dir", default=None,
                    help="章节目录（默认 <project>/current/chapters，不存在则报错）")
    ap.add_argument("--mode", default="write", choices=["write", "modify"])
    ap.add_argument("--no-cache", action="store_true",
                    help="强制重跑，不读/不写 hash 缓存")
    args = ap.parse_args()

    if args.dir:
        chapter_dir = Path(args.dir)
    else:
        chapter_dir = resolve(args.novel_id).root_dir / "chapters"

    if not chapter_dir.is_dir():
        log.error(f"章节目录不存在: {chapter_dir}")
        print(json.dumps({"error": f"章节目录不存在: {chapter_dir}"},
                         ensure_ascii=False))
        return 2

    files = sorted(str(p) for p in chapter_dir.glob("*.md"))
    if not files:
        log.error(f"章节目录为空: {chapter_dir}")
        print(json.dumps({"error": f"章节目录为空: {chapter_dir}"},
                         ensure_ascii=False))
        return 2

    try:
        report = scan_book(args.novel_id, files, mode=args.mode,
                           use_cache=not args.no_cache)
    except Exception as e:
        log.error(f"全书扫描失败: {e}")
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2

    d = report.to_dict()
    print(json.dumps(d, ensure_ascii=False, indent=2))
    return 0 if report.failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
