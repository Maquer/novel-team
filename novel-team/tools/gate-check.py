#!/usr/bin/env python3
"""门禁 CLI 兼容垫片（v2 Phase 2）。

v1 的 GateChecker（1359 行上帝对象）已拆分：
- 13 个检查 → novelkit/checks/ 插件（进程内调用，无检查子进程）
- 编排/判定/落盘 → novelkit.pipeline.orchestrator.Orchestrator
- 审核状态机 → novelkit.pipeline.review.ReviewStateMachine

本文件只保留：参数解析、输出格式、退出码——与 v1 完全一致。
诊断信息走 stderr，stdout 只输出纯 JSON。

v1 原文件已冻结在基线（~/workspace/novel-assistant-audit/novel-team-fixed/），
此处为兼容垫片。
"""

import json
import sys
import time
from pathlib import Path

# 让 novelkit 可导入（无论从哪个目录调用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novelkit.pipeline.orchestrator import Orchestrator
from novelkit.pipeline.review import ReviewStateMachine


class GateChecker(Orchestrator):
    """v1 兼容别名。

    v1 调用方（tools/test-degradation.py 等）直接 import 本模块并实例化
    GateChecker(project_id)，再调 check(chapter_file, flexible, mode)。
    v2 的 Orchestrator 把 flexible/mode 收进构造器，此处做参数桥接，
    其余行为（generate_fix_order、last_evaluation 等）全部继承。
    """

    def __init__(self, project_id="my-novel"):
        super().__init__(novel_id=project_id)

    def check(self, chapter_file, flexible=False, mode="write"):
        self.flexible = flexible
        self.mode = mode
        return super().check(chapter_file)


def _review_cmd(args):
    """审核状态机子命令：status / trigger / approve / reject / block-status / increment。"""
    import argparse
    cmd = args[0]
    parser = argparse.ArgumentParser()
    parser.add_argument("--novel-id", default="my-novel")
    parser.add_argument("--chapter", required=True, type=int)
    if cmd == "reject":
        parser.add_argument("--reason", required=True, help="驳回原因")
    parsed = parser.parse_args(args[1:])

    sm = ReviewStateMachine(parsed.novel_id)
    if cmd == "status":
        result = sm.get_review_status(parsed.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    elif cmd == "trigger":
        result = sm.trigger_review(parsed.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["success"] else 1)
    elif cmd == "approve":
        result = sm.auto_approve(parsed.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["success"] else 1)
    elif cmd == "reject":
        result = sm.reject_review(parsed.chapter, parsed.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["success"] else 1)
    elif cmd == "block-status":
        result = sm.get_block_status(parsed.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if not result["blocked"] else 1)
    elif cmd == "increment":
        result = sm.increment_no_feedback(parsed.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)


def _check_cmd(args):
    """门禁检查命令（v1 main() 原有命令解析逻辑逐行移植）。"""
    chapter_num = None
    chapter_file = None
    flexible = False
    novel_id = "my-novel"
    mode = "write"  # write（完整）或 modify（修改）
    no_cache = False  # Phase 3：--no-cache 强制重跑，不读/不写缓存

    i = 0
    while i < len(args):
        if args[i] == "--chapter" and i + 1 < len(args):
            chapter_num = args[i + 1]
            i += 2
        elif args[i] == "--novel-id" and i + 1 < len(args):
            # BUG 9 修复（v1）：修前 check 命令完全不解析 --novel-id，
            # 硬编码 GateChecker("my-novel") → 任何项目的门禁都读 my-novel
            # 的账本与事件（多项目隔离在门禁层断裂）
            novel_id = args[i + 1]
            i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            chapter_file = args[i + 1]
            i += 2
        elif args[i] == "--flexible":
            flexible = True
            i += 1
        elif args[i] == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
        elif args[i] == "--no-cache":
            # Phase 3 新增（加法，不破坏 v1 CLI 兼容）
            no_cache = True
            i += 1
        elif args[i] == "--fix-order":
            i += 1
        else:
            i += 1

    if not chapter_file:
        print("Error: --file is required", file=sys.stderr)
        sys.exit(1)

    # 执行检查（进程内插件调用，不再有检查子进程）
    orch = Orchestrator(novel_id=novel_id, flexible=flexible, mode=mode,
                        no_cache=no_cache)
    result = orch.check(chapter_file)

    # D2：--fix-order 模式：输出按优先级排序的修复建议
    if "--fix-order" in args:
        fixes = orch.generate_fix_order(result)
        if fixes:
            print("\n🔧 修复顺序（D2 降级策略）：", file=sys.stderr)
            for i, fix in enumerate(fixes, 1):
                print(f"   {i}. [{fix['level']}] {fix['label']}（gate={fix['gate']}）: {fix['detail'][:80]}", file=sys.stderr)
        else:
            print("\n✅ 无问题，无需修复。", file=sys.stderr)

    # 事件发射：门禁通过 → 触发世界包同步扫描
    # （v1 main() 内联逻辑移植；_emit_gate_event 的 event-bus 发射在 orch._save_result 内）
    if result.get("passed"):
        try:
            _events_dir = Path(__file__).parent.parent / ".events"
            _events_dir.mkdir(parents=True, exist_ok=True)
            _events_file = _events_dir / f"{novel_id}.jsonl"  # BUG 9 配套：事件也按项目分文件
            _ch_num = int(chapter_num) if chapter_num else 1
            _event = {"event": "CHAPTER_GATE_PASSED",
                      "chapter": _ch_num,
                      "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(_events_file, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_event, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 退出码
    sys.exit(0 if result["passed"] else 1)


def main():
    if len(sys.argv) < 3:
        print("Usage: python gate-check.py check --chapter <num> --file <file> [--flexible] [--mode write|modify] [--no-cache]")
        print("       python gate-check.py status --novel-id <id> --chapter <num>")
        print("       python gate-check.py trigger --novel-id <id> --chapter <num>")
        print("       python gate-check.py approve --novel-id <id> --chapter <num>")
        print("       python gate-check.py reject --novel-id <id> --chapter <num> --reason <reason>")
        print("       python gate-check.py block-status --novel-id <id> --chapter <num>")
        sys.exit(1)

    args = sys.argv[1:]

    # 检查是否为新状态机命令
    if args[0] in ("status", "trigger", "approve", "reject", "block-status", "increment"):
        _review_cmd(args)
    else:
        _check_cmd(args)


if __name__ == "__main__":
    main()
