#!/usr/bin/env python3
"""
outline-grill-bridge.py — grill-me 与大纲创作的衔接工具

功能：
  1. 启动 grill-me 追问大纲结构（五卷/章节数/爽点节奏/关键转折）
  2. 将追问结果落地为 vol-001-brief.yaml ~ vol-005-brief.yaml
  3. 与 world-logic-builder.py 形成完整衔接链

使用：
  # 启动大纲追问
  python3 tools/outline-grill-bridge.py start --project helper-creator

  # 落地大纲文件
  python3 tools/outline-grill-bridge.py build --project helper-creator

  # 一步到位
  python3 tools/outline-grill-bridge.py run --project helper-creator

  # 查看当前大纲状态
  python3 tools/outline-grill-bridge.py status --project helper-creator
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


BASE_DIR = Path("/var/minis/shared/novel-team")
WORKSPACE_DIR = Path("/var/minis/workspace")
TOOLS_DIR = BASE_DIR / "tools"
TEMPLATES_DIR = BASE_DIR / "templates"


def get_project_dirs(project_id: str) -> Dict[str, Path]:
    """解析项目路径"""
    new_path = BASE_DIR / "novel-team" / "projects" / project_id
    old_path = BASE_DIR / "projects" / project_id

    if new_path.exists():
        return {
            "root": new_path,
            "world": new_path / "world",
            "outline": new_path / "outline",
            "chapters": new_path / "chapters",
        }
    elif old_path.exists():
        return {
            "root": old_path,
            "world": old_path / "world",
            "outline": old_path / "outline",
            "chapters": old_path / "chapters",
        }
    else:
        print(f"❌ 项目 '{project_id}' 不存在", file=sys.stderr)
        sys.exit(1)


# ============================================================
# 大纲追问问题库
# ============================================================

OUTLINE_QUESTION_BANK = [
    {
        "id": "OQ01",
        "domain": "五卷结构",
        "question": "《辅助之道》为什么要分五卷？每卷的核心冲突是什么？为什么是这个顺序？",
        "follow_up": [
            "如果只有四卷，哪一卷会被合并或删除？为什么？",
            "如果要有六卷，多出来的那一卷会在哪里插入？讲什么？",
            "五卷的标题（初露锋芒/天机崛起/大陆争锋/巅峰之路/问道永恒）是怎么想的？每个标题对应什么情节？",
        ],
        "expected_output": {
            "vol_count": "五卷（必须回答为什么不是四卷或六卷）",
            "vol_titles": ["卷一标题", "卷二标题", ...],
            "vol_conflicts": ["卷一核心冲突", "卷二核心冲突", ...],
            "vol_order_reason": "为什么是这个顺序而不是其他顺序",
        },
    },
    {
        "id": "OQ02",
        "domain": "章节数分配",
        "question": "第一卷为什么是30章？20章够吗？50章会怎样？",
        "follow_up": [
            "每卷的章节数是怎么计算的？是按字数算的还是按情节密度算的？",
            "第一卷30章中，多少章是铺垫？多少章是高潮？多少章是过渡？",
            "如果第一卷只写20章，剩下的10章内容会去哪一卷？",
            "最后一卷400章，这个数量是怎么想的？会不会太拖沓？",
        ],
        "expected_output": {
            "chapters_per_volume": "待用户回答后填充",
            "chapter_type_distribution": "待用户回答后填充",
            "total_chapters": "待用户回答后填充",
        },
    },
    {
        "id": "OQ03",
        "domain": "爽点节奏",
        "question": "L1/L2/L3/L4的分布是否合理？哪里该压抑？哪里该爆发？",
        "follow_up": [
            "前3章为什么必须有L2+爽点？没有会怎样？",
            "连续3章没有正反馈，读者会流失吗？为什么？",
            "L4（卷末大高潮）和L3（中期高潮）的区别是什么？怎么区分？",
            "压抑章的目的是什么？没有压抑直接高潮会怎样？",
        ],
        "expected_output": {
            "thrill_schedule": {
                "vol_1": [{"ch_range": "1-3", "level": "L2", "design": "破冰"}, ...],
                "vol_2": [...],
            },
            "depress_chapters": [10, 25, 50, ...],  # 压抑章位置
        },
    },
    {
        "id": "OQ04",
        "domain": "关键转折点",
        "question": "Ch10/Ch30/Ch100/Ch200/Ch300这些节点为什么重要？删掉会怎样？",
        "follow_up": [
            "每个关键转折点对应什么具体事件？（不能是虚词）",
            "转折点是主角主动选择的还是被动发生的？",
            "转折点之后，主角获得了什么？失去了什么？",
            "如果没有这个转折点，后续剧情还能成立吗？",
        ],
        "expected_output": {
            "key_turning_points": [
                {"chapter": 1, "event": "炼丹首秀", "change": "被发现异常"},
                {"chapter": 10, "event": "阵法入门", "change": "解锁新能力"},
                ...
            ],
        },
    },
    {
        "id": "OQ05",
        "domain": "伏笔分布",
        "question": "哪些伏笔需要提前埋？哪些伏笔该提前收？伏笔太多会怎样？",
        "follow_up": [
            "鉴灵匣的秘密分几层揭示？每层对应哪一章？",
            "天机阁的暗线伏笔有哪些？什么时候收？",
            "伏笔埋得太早会剧透，埋得太晚会遗忘，怎么平衡？",
            "有没有伏笔埋了但忘记收了的情况？怎么预防？",
        ],
        "expected_output": {
            "foreshadowing_plan": [
                {"chapter": 1, "hint": "匣身纹路亮了一下", "reveal": "Ch30阁主观察"},
                {"chapter": 5, "hint": "老赵的异常态度", "reveal": "Ch50身份揭露"},
                ...
            ],
        },
    },
]


def load_decision_tree(project_dirs: Dict) -> Optional[Dict]:
    """加载已有的决策树"""
    tree_path = project_dirs["root"] / "DECISION-TREE.md"
    if not tree_path.exists():
        return None

    content = tree_path.read_text(encoding="utf-8")
    sections = content.split("## ")[1:]
    tree = {}
    for section in sections:
        lines = section.strip().split("\n")
        if lines:
            title = lines[0].strip()
            content_lines = "\n".join(lines[1:]).strip()
            tree[title] = content_lines

    return tree


def extract_outline_answers(decision_tree: Dict) -> Dict:
    """从决策树中提取大纲相关答案"""
    answers = {}
    for section_title, content in decision_tree.items():
        # 匹配 OQ01~OQ05
        for oq in OUTLINE_QUESTION_BANK:
            if oq["id"] in section_title or oq["domain"] in section_title:
                answers[oq["id"]] = {
                    "domain": oq["domain"],
                    "question": oq["question"],
                    "answer": content,
                }
    return answers


def generate_volume_brief(volume_num: int, answers: Dict, project_dirs: Dict) -> str:
    """生成单卷细纲文件"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 从 answers 提取数据
    vol_conflict = answers.get("OQ01", {}).get("answer", "待定")
    chapters_range = answers.get("OQ02", {}).get("answer", f"待确认")
    thrill_schedule = answers.get("OQ03", {}).get("answer", "待设计")
    key_turning_points = answers.get("OQ04", {}).get("answer", "待定义")
    foreshadowing = answers.get("OQ05", {}).get("answer", "待规划")

    # 生成 YAML
    brief = f"""# 第{volume_num}卷细纲

> 生成日期：{today}
> 来源：grill-me 追问 + 世界核心逻辑
> 状态：draft（待创作验证）

## 卷基本信息
- **卷号**：第{volume_num}卷
- **章节范围**：待确认（基于 OQ02 答案）
- **核心冲突**：{vol_conflict}
- **目标字数**：待计算（章节数 × 2500字）

## 爽点节奏
{thrill_schedule}

## 关键转折点
{key_turning_points}

## 伏笔规划
{foreshadowing}

## 创作约束
- 不得违反 world/core-logic.md 中的铁律
- 每章必须有明确的爽点层级（L1-L4）
- 场景切换必须有过渡桥段
- 金手指鉴灵匣始终隐藏，不得提前暴露

## 与上下卷的衔接
- **上一卷结尾钩子**：待填充
- **本卷开头承接**：待填充
- **本卷结尾钩子**：待填充
- **下一卷开头承接**：待填充

---
*此文件由 outline-grill-bridge.py 生成，基于 grill-me 追问结果。*
*创作过程中如发现逻辑矛盾，需回退到 Phase 1 重新追问。*
"""
    return brief


def cmd_start(args):
    """启动大纲追问"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print("🍳 大纲追问启动器")
    print("=" * 60)
    print()
    print(f"项目：{args.project}")
    print(f"工作区：{WORKSPACE_DIR}")
    print()

    # 检查是否已有决策树
    workspace_tree = WORKSPACE_DIR / "DECISION-TREE.md"
    project_tree = project_dirs["root"] / "DECISION-TREE.md"

    if workspace_tree.exists():
        print(f"⚠️ 发现已有决策树: {workspace_tree}")
        confirm = input("继续追问会追加新答案，覆盖已有？(y/N): ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return

    print()
    print("即将启动 grill-me 大纲追问模式。")
    print()
    print("追问领域：")
    for oq in OUTLINE_QUESTION_BANK:
        print(f"  {oq['id']}: {oq['domain']}")
        print(f"    Q: {oq['question'][:50]}...")
    print()
    print("追问完成后，运行：")
    print(f"  python3 {TOOLS_DIR / 'outline-grill-bridge.py'} build --project {args.project}")
    print()
    print("💡 提示：在对话中说 'grill me' 激活追问模式")


def cmd_build(args):
    """落地大纲文件"""
    project_dirs = get_project_dirs(args.project)
    workspace_tree = WORKSPACE_DIR / "DECISION-TREE.md"
    project_tree = project_dirs["root"] / "DECISION-TREE.md"

    print("=" * 60)
    print("🔨 大纲文件落地")
    print("=" * 60)
    print()

    # 检查决策树
    if not workspace_tree.exists():
        print("❌ 未找到 DECISION-TREE.md")
        print(f"   预期位置: {workspace_tree}")
        print()
        print("请先运行追问：")
        print(f"  python3 {TOOLS_DIR / 'outline-grill-bridge.py'} start --project {args.project}")
        sys.exit(1)

    print(f"✅ 找到决策树: {workspace_tree}")
    print()

    # 复制到项目目录
    project_tree.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(workspace_tree, project_tree)
    print(f"✅ 已复制到项目目录: {project_tree}")
    print()

    # 加载决策树
    decision_tree = load_decision_tree(project_dirs)
    if not decision_tree:
        print("❌ 无法解析决策树")
        sys.exit(1)

    # 提取大纲答案
    answers = extract_outline_answers(decision_tree)
    print(f"✅ 提取到 {len(answers)} 个大纲相关问题答案")
    print()

    # 生成各卷细纲
    outline_dir = project_dirs["outline"]
    outline_dir.mkdir(parents=True, exist_ok=True)

    # 假设五卷（可根据实际调整）
    for vol_num in range(1, 6):
        brief = generate_volume_brief(vol_num, answers, project_dirs)
        brief_path = outline_dir / f"vol-{vol_num:03d}-brief.yaml"
        brief_path.write_text(brief, encoding="utf-8")
        print(f"✅ 已生成: {brief_path.name}")

    print()
    print("=" * 60)
    print("✅ 大纲落地完成")
    print("=" * 60)
    print()
    print("下一步：")
    print(f"  1. 审阅 {outline_dir}/vol-001-brief.yaml")
    print(f"  2. 基于细纲生成单章写作指令")
    print(f"     python3 tools/chapter-brief-generator.py --project {args.project} --volume 1 --batch")


def cmd_status(args):
    """查看当前大纲状态"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print(f"📋 项目 '{args.project}' 大纲状态")
    print("=" * 60)
    print()

    # 检查决策树
    workspace_tree = WORKSPACE_DIR / "DECISION-TREE.md"
    project_tree = project_dirs["root"] / "DECISION-TREE.md"

    if workspace_tree.exists():
        size = workspace_tree.stat().st_size
        print(f"  ✅ workspace/DECISION-TREE.md: {size:,} bytes")
    else:
        print(f"  ⏳ workspace/DECISION-TREE.md: 不存在")

    if project_tree.exists():
        size = project_tree.stat().st_size
        print(f"  ✅ projects/<id>/DECISION-TREE.md: {size:,} bytes")
    else:
        print(f"  ⏳ projects/<id>/DECISION-TREE.md: 不存在")

    print()

    # 检查卷细纲
    outline_dir = project_dirs["outline"]
    if outline_dir.exists():
        vol_briefs = list(outline_dir.glob("vol-*-brief.yaml"))
        print(f"  📄 卷细纲文件: {len(vol_briefs)} 个")
        for vb in sorted(vol_briefs):
            size = vb.stat().st_size
            print(f"     - {vb.name}: {size:,} bytes")
    else:
        print(f"  ⏳ 大纲目录: 不存在")

    print()

    # 检查单章细纲
    ch_briefs = list(outline_dir.glob("ch-*-brief.md")) if outline_dir.exists() else []
    print(f"  📝 单章细纲: {len(ch_briefs)} 章")

    print()

    # 检查已有正文
    chapters_dir = project_dirs["chapters"]
    if chapters_dir.exists():
        ch_files = list(chapters_dir.glob("ch*.md"))
        print(f"  ✍️ 已写章节: {len(ch_files)} 章")
    else:
        print(f"  ⏳ 章节目录: 不存在")


def main():
    parser = argparse.ArgumentParser(
        description="grill-me 与大纲创作的衔接工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 启动大纲追问
  python3 tools/outline-grill-bridge.py start --project helper-creator

  # 落地大纲文件
  python3 tools/outline-grill-bridge.py build --project helper-creator

  # 一步到位
  python3 tools/outline-grill-bridge.py run --project helper-creator

  # 查看当前大纲状态
  python3 tools/outline-grill-bridge.py status --project helper-creator
        """
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    p_start = sub.add_parser("start", help="启动 grill-me 大纲追问")
    p_start.add_argument("--project", "-p", required=True, help="项目 ID")

    p_build = sub.add_parser("build", help="落地大纲文件")
    p_build.add_argument("--project", "-p", required=True, help="项目 ID")

    p_status = sub.add_parser("status", help="查看当前大纲状态")
    p_status.add_argument("--project", "-p", required=True, help="项目 ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "start":
        cmd_start(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
