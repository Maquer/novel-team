#!/usr/bin/env python3
"""大纲预填事实账本 CLI（v2 Phase 4 新能力）。

从大纲（outline.md）抽取世界观/人物/章节钩子，写入事实账本，
source="outline"，verified=True。幂等。
stdout 纯 JSON；诊断走 stderr。

退出码：恒 0（预填不阻断）；出错 → 2。
"""

import argparse
import json
import sys
from pathlib import Path

# 让 novelkit 可导入（无论从哪个目录调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novelkit.core import log
from novelkit.pipeline.ledger_prefill import prefill_from_outline


def main() -> int:
    ap = argparse.ArgumentParser(description="从大纲预填事实账本")
    ap.add_argument("--novel-id", default="my-novel")
    ap.add_argument("--outline", default=None, help="大纲文件路径")
    ap.add_argument("--dry-run", action="store_true",
                    help="只统计不写入")
    args = ap.parse_args()

    try:
        result = prefill_from_outline(args.novel_id,
                                      outline_path=args.outline,
                                      dry_run=args.dry_run)
    except Exception as e:
        log.error(f"预填失败: {e}")
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
