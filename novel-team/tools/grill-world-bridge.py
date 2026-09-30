#!/usr/bin/env python3
"""
grill-world-bridge.py — grill-me 与 world-logic-builder 的衔接层

功能：
  1. 启动 grill-me 追问模式（在当前会话）
  2. 追问完成后，自动将 DECISION-TREE.md 复制到项目目录
  3. 可选：自动触发 Phase 3 落地

使用：
  # 启动追问（推荐）
  python3 tools/grill-world-bridge.py start --project helper-creator

  # 追问完成后，落地逻辑
  python3 tools/grill-world-bridge.py build --project helper-creator

  # 一步到位（启动追问 + 落地）
  python3 tools/grill-world-bridge.py run --project helper-creator
"""

import argparse
import shutil
import sys
from pathlib import Path

# 路径定义
BASE_DIR = Path("/var/minis/shared/novel-team")
WORKSPACE_DIR = Path("/var/minis/workspace")
TOOLS_DIR = BASE_DIR / "tools"


def get_project_dirs(project_id: str) -> dict:
    """解析项目路径"""
    new_path = BASE_DIR / "novel-team" / "projects" / project_id
    old_path = BASE_DIR / "projects" / project_id

    if new_path.exists():
        return {
            "root": new_path,
            "world": new_path / "world",
            "outline": new_path / "outline",
            "characters": new_path / "characters",
            "chapters": new_path / "chapters",
        }
    elif old_path.exists():
        return {
            "root": old_path,
            "world": old_path / "world",
            "outline": old_path / "outline",
            "characters": old_path / "characters",
            "chapters": old_path / "chapters",
        }
    else:
        print(f"❌ 项目 '{project_id}' 不存在", file=sys.stderr)
        sys.exit(1)


def cmd_start(args):
    """Phase 1：启动 grill-me 追问"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print("🍳 世界包追问启动器")
    print("=" * 60)
    print()
    print(f"项目：{args.project}")
    print(f"工作区：{WORKSPACE_DIR}")
    print(f"项目目录：{project_dirs['root']}")
    print()

    # 检查是否有已有决策树
    workspace_tree = WORKSPACE_DIR / "DECISION-TREE.md"
    project_tree = project_dirs["root"] / "DECISION-TREE.md"

    if workspace_tree.exists():
        print(f"⚠️ 发现已有决策树: {workspace_tree}")
        print(f"   大小: {workspace_tree.stat().st_size} bytes")
        confirm = input("覆盖已有决策树？(y/N): ").strip().lower()
        if confirm != "y":
            print("已取消。请手动删除或重命名已有决策树后重试。")
            return

    if project_tree.exists():
        print(f"⚠️ 项目目录已有决策树: {project_tree}")
        print(f"   将被覆盖。")

    print()
    print("即将启动 grill-me 追问模式。")
    print()
    print("追问领域：")
    print("  Q01: 力量体系的代价")
    print("  Q02: 社会结构的根源")
    print("  Q03: 核心矛盾的发动机")
    print("  Q04: 主角的特殊性")
    print("  Q05: 第一卷具体任务")
    print()
    print("追问完成后，运行：")
    print(f"  python3 {TOOLS_DIR / 'grill-world-bridge.py'} build --project {args.project}")
    print()
    print("或直接一步到位：")
    print(f"  python3 {TOOLS_DIR / 'grill-world-bridge.py'} run --project {args.project}")
    print()
    print("💡 提示：在对话中说 'grill me' 或 '先追问我' 激活追问模式")


def cmd_build(args):
    """Phase 2+3：复制决策树并落地"""
    project_dirs = get_project_dirs(args.project)
    workspace_tree = WORKSPACE_DIR / "DECISION-TREE.md"
    project_tree = project_dirs["root"] / "DECISION-TREE.md"

    print("=" * 60)
    print("🔨 世界包逻辑落地")
    print("=" * 60)
    print()

    # Step 1: 检查决策树
    if not workspace_tree.exists():
        print("❌ 未找到 DECISION-TREE.md")
        print(f"   预期位置: {workspace_tree}")
        print()
        print("请先运行追问：")
        print(f"  python3 {TOOLS_DIR / 'grill-world-bridge.py'} start --project {args.project}")
        print()
        print("然后在对话中说 'grill me' 启动追问。")
        sys.exit(1)

    print(f"✅ 找到决策树: {workspace_tree}")
    print(f"   大小: {workspace_tree.stat().st_size} bytes")
    print()

    # Step 2: 复制到项目目录
    project_tree.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(workspace_tree, project_tree)
    print(f"✅ 已复制到项目目录: {project_tree}")
    print()

    # Step 3: 运行 world-logic-builder build
    print("正在落地逻辑文件...")
    print()

    import subprocess
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "world-logic-builder.py"),
         "build", "--project", args.project],
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"❌ 落地失败（退出码 {result.returncode}）")
        sys.exit(1)

    print()
    print("=" * 60)
    print("✅ 逻辑落地完成")
    print("=" * 60)
    print()
    print("产出文件：")
    print(f"  - {project_dirs['world'] / 'core-logic.md'}")
    print(f"  - {project_dirs['world'] / 'iron-laws.md'}")
    print()
    print("下一步：生成第一卷细纲")
    print(f"  python3 {TOOLS_DIR / 'chapter-brief-generator.py'} --project {args.project} --volume 1 --batch")


def cmd_run(args):
    """一步到位：启动追问 + 落地"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print("🚀 世界包构建全流程")
    print("=" * 60)
    print()
    print(f"项目：{args.project}")
    print()
    print("流程：")
    print("  1. 启动 grill-me 追问（5个领域）")
    print("  2. 追问完成后，自动复制决策树到项目目录")
    print("  3. 自动落地为 core-logic.md + iron-laws.md")
    print()
    print("⚠️  注意：追问需要你在对话中主动说 'grill me'")
    print("    本脚本只会启动追问模式，不会自动执行追问。")
    print()

    confirm = input("确认启动？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消。")
        return

    print()
    print("Step 1: 启动追问模式")
    print("-" * 40)
    cmd_start(args)

    print()
    print("Step 2: 请在对话中说 'grill me' 或 '先追问我'")
    print("        完成 5 个领域的追问。")
    print()
    print("Step 3: 追问完成后，运行以下命令落地：")
    print(f"  python3 {TOOLS_DIR / 'grill-world-bridge.py'} build --project {args.project}")
    print()
    print("或者使用一步到位命令：")
    print(f"  python3 {TOOLS_DIR / 'grill-world-bridge.py'} run --project {args.project}")


def main():
    parser = argparse.ArgumentParser(
        description="grill-me 与 world-logic-builder 的衔接层",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 启动追问
  python3 tools/grill-world-bridge.py start --project helper-creator

  # 追问完成后落地
  python3 tools/grill-world-bridge.py build --project helper-creator

  # 一步到位（启动+落地）
  python3 tools/grill-world-bridge.py run --project helper-creator
        """
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    p_start = sub.add_parser("start", help="启动 grill-me 追问模式")
    p_start.add_argument("--project", "-p", required=True, help="项目 ID")

    p_build = sub.add_parser("build", help="复制决策树并落地逻辑文件")
    p_build.add_argument("--project", "-p", required=True, help="项目 ID")

    p_run = sub.add_parser("run", help="一步到位：启动追问 + 落地")
    p_run.add_argument("--project", "-p", required=True, help="项目 ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "start":
        cmd_start(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "run":
        cmd_run(args)


if __name__ == "__main__":
    main()
