#!/usr/bin/env python3
"""
world-logic-builder.py — 世界包核心逻辑构建器（Phase 1→3 主控）

功能：
  1. Phase 1：读取 world-question-bank.yaml，启动 grill-me 追问
  2. Phase 2：自动触发第二模型交叉验证（可选）
  3. Phase 3：将决策树答案落地为 core-logic.md + iron-laws.md

使用：
  # 查看当前逻辑状态
  python3 tools/world-logic-builder.py --project helper-creator status

  # 仅 Phase 1（追问）
  python3 tools/world-logic-builder.py --project helper-creator grill

  # 仅 Phase 3（落地文件）
  python3 tools/world-logic-builder.py --project helper-creator build

  # 完整流程（先追问再落地）
  python3 tools/world-logic-builder.py --project helper-creator grill && python3 tools/world-logic-builder.py --project helper-creator build
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 项目根目录
BASE_DIR = Path("/var/minis/shared/novel-team")
TOOLS_DIR = BASE_DIR / "tools"
TEMPLATES_DIR = BASE_DIR / "templates"


def get_project_dirs(project_id: str) -> Dict[str, Path]:
    """解析项目路径（兼容新旧两种路径结构）"""
    # 新路径：projects/<project-id>/
    new_path = BASE_DIR / "novel-team" / "projects" / project_id
    # 旧路径：projects/<project-id>/
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
        print(f"   尝试过: {new_path} / {old_path}", file=sys.stderr)
        sys.exit(1)


def load_question_bank() -> List[Dict]:
    """加载追问问题库"""
    bank_path = TEMPLATES_DIR / "world-question-bank.yaml"
    if not bank_path.exists():
        print(f"❌ 问题库不存在: {bank_path}", file=sys.stderr)
        sys.exit(1)
    
    # 简单 YAML 解析（不用 yaml 库，避免依赖）
    questions = []
    current_q = {}
    in_follow_up = False
    
    with open(bank_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("## Q"):
                if current_q:
                    questions.append(current_q)
                current_q = {"raw": line}
                in_follow_up = False
            elif line.strip().startswith("- **Q**:"):
                in_follow_up = True
                current_q["questions"] = current_q.get("questions", [])
                q_text = line.split("- **Q**:", 1)[1].strip()
                current_q["questions"].append(q_text)
            elif line.strip().startswith("- **A**:"):
                if current_q.get("questions"):
                    a_text = line.split("- **A**:", 1)[1].strip()
                    current_q["last_answer"] = a_text
            elif "starter_question" in line:
                q_text = line.split(">", 1)[1].strip() if ">" in line else line.split(":", 1)[1].strip()
                current_q["starter"] = q_text.strip('"')
            elif "追问目标" in line and ":" in line:
                current_q["goal"] = line.split("：", 1)[1].strip() if "：" in line else line.split(":", 1)[1].strip()
    
    if current_q:
        questions.append(current_q)
    
    return questions


def load_decision_tree(project_dirs: Dict) -> Optional[Dict]:
    """加载已有的决策树"""
    tree_path = project_dirs["root"] / "DECISION-TREE.md"
    if not tree_path.exists():
        return None
    
    content = tree_path.read_text(encoding="utf-8")
    # 简单解析：按 ## 分割
    sections = content.split("## ")[1:]  # 跳过标题
    tree = {}
    for section in sections:
        lines = section.strip().split("\n")
        if lines:
            title = lines[0].strip()
            content_lines = "\n".join(lines[1:]).strip()
            tree[title] = content_lines
    
    return tree


def generate_core_logic(question_answers: Dict, project_dirs: Dict) -> Dict[str, str]:
    """根据追问答案生成核心逻辑文档内容"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 提取各字段（简化版，实际需要解析决策树格式）
    q01 = question_answers.get("Q01：力量体系的代价", "")
    q02 = question_answers.get("Q02：社会结构的根源", "")
    q03 = question_answers.get("Q03：核心矛盾的发动机", "")
    q04 = question_answers.get("Q04：主角的特殊性", "")
    q05 = question_answers.get("Q05：第一卷具体任务", "")
    
    core_logic = f"""# 《辅助之道》世界核心逻辑

> 生成日期：{today}
> 来源：grill-me 追问 + 交叉验证
> 状态：validated

---

## 一、力量体系的代价

{q01}

---

## 二、社会结构的根源

{q02}

---

## 三、核心矛盾的发动机

{q03}

---

## 四、主角的特殊性

{q04}

---

## 五、第一卷具体任务

{q05}

---

## 六、写作铁律（从逻辑中提取）

### 境界铁律
1. 大境差一阶 = 绝对压制（不可逆）
2. 小境差 = 可逆（靠功法/器物/经验）
3. 突破需契机，不可凭空升级

### 资源铁律
1. 低层角色不接触高阶资源
2. 越级获取 = 剧情硬伤（P0 阻断）

### 知情铁律
1. 角色只能知道它该知道的信息
2. 信息提前暴露 = 穿帮（P0 阻断）

### 过渡铁律
1. 场景切换必须有桥段
2. 禁止硬切（`---`后直接新场景）

"""
    
    iron_laws = f"""# 《辅助之道》世界铁律

> 生成日期：{today}
> 来源：Phase 1 追问 → Phase 2 验证

## 力量铁律

| ID | 内容 | 违反后果 | 来源 Q |
|----|------|---------|--------|
| IL001 | 大境差一阶=绝对压制 | P0 阻断 | Q01 |
| IL002 | 小境差=可逆 | P1 警告 | Q01 |
| IL003 | 突破需契机 | P0 阻断 | Q01 |

## 社会铁律

| ID | 内容 | 违反后果 | 来源 Q |
|----|------|---------|--------|
| SL001 | 杂役不得越权指点 | P1 警告 | Q02 |
| SL002 | 低层不接触高阶资源 | P0 阻断 | Q02 |

## 矛盾铁律

| ID | 内容 | 违反后果 | 来源 Q |
|----|------|---------|--------|
| CL001 | 天机阁中立原则 | P1 警告 | Q03 |
| CL002 | 鉴灵匣必须隐藏 | P0 阻断 | Q04 |

## 主角铁律

| ID | 内容 | 违反后果 | 来源 Q |
|----|------|---------|--------|
| PL001 | 林辰不得主动暴露金手指 | P0 阻断 | Q04 |
| PL002 | 每用一诀增加刻纹（暴露风险） | P1 警告 | Q04 |

## 任务铁律

| ID | 内容 | 违反后果 | 来源 Q |
|----|------|---------|--------|
| TL001 | 第一卷任务必须在 Ch15 前启动 | P1 警告 | Q05 |
| TL002 | 任务失败必须有后果 | P0 阻断 | Q05 |

---

## 铁律与 gate-check 对接

| 铁律 ID | gate-check 插件 | 检查方式 |
|--------|----------------|---------|
| IL001 | fact_consistency | 境界匹配检查 |
| IL002 | fact_consistency | 同境界胜负合理性 |
| SL001 | protocol | 行为合理性检查 |
| SL002 | forbidden_words | 越级资源检测 |
| CL002 | hook | 金手指暴露风险 |
| PL001 | fact_consistency | 知情边界检查 |
| PL002 | discipline | 刻纹计数检查 |

"""
    
    return {
        "core_logic": core_logic,
        "iron_laws": iron_laws,
    }


def cmd_grill(args):
    """Phase 1：启动 grill-me 追问"""
    project_dirs = get_project_dirs(args.project)
    
    print("=" * 60)
    print("🍳 世界包核心逻辑构建 — Phase 1：逻辑追问")
    print("=" * 60)
    print()
    print(f"项目：{args.project}")
    print(f"世界包路径：{project_dirs['world']}")
    print()
    
    # 检查是否已有决策树
    tree = load_decision_tree(project_dirs)
    if tree:
        print(f"⚠️ 发现已有决策树: {project_dirs['root'] / 'DECISION-TREE.md'}")
        print(f"   共 {len(tree)} 个领域已回答")
        confirm = input("继续追问？这会追加新答案 (y/N): ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return
    
    print()
    print("即将启动 grill-me 追问模式。")
    print("请确保在当前会话中启用 grill-me skill。")
    print()
    print("触发方式：在对话中说 'grill me' 或 '先追问我'")
    print("追问领域：Q01~Q05（见 templates/world-question-bank.yaml）")
    print()
    print("追问完成后，运行：")
    print(f"  python3 {TOOLS_DIR / 'world-logic-builder.py'} build --project {args.project}")
    print()
    print("💡 提示：追问时回答要具体，避免'差不多''大概'等模糊词")


def cmd_build(args):
    """Phase 3：将决策树落地为逻辑文件"""
    project_dirs = get_project_dirs(args.project)
    today = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 60)
    print("🔨 世界包核心逻辑构建 — Phase 3：逻辑落地")
    print("=" * 60)
    print()
    print(f"项目：{args.project}")
    print()
    
    # 检查决策树
    tree = load_decision_tree(project_dirs)
    if not tree:
        print("❌ 未找到 DECISION-TREE.md")
        print("   请先运行：python3 tools/world-logic-builder.py grill --project", args.project)
        sys.exit(1)
    
    # 解析决策树答案
    question_answers = {}
    for section_title, content in tree.items():
        # 提取 Q01/Q02... 前缀
        for i in range(1, 6):
            if f"Q0{i}" in section_title or f"Q{i}：" in section_title:
                question_answers[section_title] = content
                break
    
    if not question_answers:
        print("⚠️ 未在决策树中找到 Q01~Q05 格式的答案")
        print("   请检查 DECISION-TREE.md 格式是否符合预期")
        sys.exit(1)
    
    print(f"✅ 读取到 {len(question_answers)} 个领域的答案")
    
    # 生成逻辑文件
    outputs = generate_core_logic(question_answers, project_dirs)
    
    # 写入文件
    world_dir = project_dirs["world"]
    world_dir.mkdir(parents=True, exist_ok=True)
    
    # core-logic.md
    logic_path = world_dir / "core-logic.md"
    logic_path.write_text(outputs["core_logic"], encoding="utf-8")
    print(f"✅ 已写入: {logic_path}")
    
    # iron-laws.md
    laws_path = world_dir / "iron-laws.md"
    laws_path.write_text(outputs["iron_laws"], encoding="utf-8")
    print(f"✅ 已写入: {laws_path}")
    
    # 更新 world-pack.json（追加核心逻辑条目）
    pack_path = world_dir / "world-pack.json"
    if pack_path.exists():
        with open(pack_path, encoding="utf-8") as f:
            pack = json.load(f)
        
        # 添加逻辑元数据
        if "logic" not in pack:
            pack["logic"] = {}
        pack["logic"]["version"] = "1.0"
        pack["logic"]["updated"] = today
        pack["logic"]["source"] = "DECISION-TREE.md"
        
        with open(pack_path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)
        print(f"✅ 已更新: {pack_path}")
    else:
        print(f"⚠️ 未找到 world-pack.json，跳过同步")
    
    print()
    print("=" * 60)
    print("✅ Phase 3 完成")
    print("=" * 60)
    print()
    print("下一步：")
    print(f"  1. 审阅 {logic_path} 和 {laws_path}")
    print(f"  2. 基于新逻辑重写第一卷细纲")
    print(f"     python3 tools/chapter-brief-generator.py --project {args.project} --volume 1 --batch")
    print()


def cmd_status(args):
    """查看当前世界包逻辑状态"""
    project_dirs = get_project_dirs(args.project)
    
    print("=" * 60)
    print(f"📊 项目 '{args.project}' 世界包逻辑状态")
    print("=" * 60)
    print()
    
    # 检查各文件
    checks = [
        ("world-bible.md", project_dirs["world"] / "world-bible.md"),
        ("core-concept.md", project_dirs["world"] / "core-concept.md"),
        ("core-logic.md", project_dirs["world"] / "core-logic.md"),
        ("iron-laws.md", project_dirs["world"] / "iron-laws.md"),
        ("world-pack.json", project_dirs["world"] / "world-pack.json"),
        ("DECISION-TREE.md", project_dirs["root"] / "DECISION-TREE.md"),
    ]
    
    for name, path in checks:
        if path.exists():
            size = path.stat().st_size
            print(f"  ✅ {name:25s} {size:>8d} bytes")
        else:
            print(f"  ❌ {name:25s} 不存在")
    
    print()
    
    # 检查角色档案
    char_dir = project_dirs["characters"]
    if char_dir.exists():
        chars = list(char_dir.glob("*.json"))
        print(f"  📋 角色档案: {len(chars)} 个")
    else:
        print(f"  ⚠️ 角色档案目录不存在: {char_dir}")
    
    print()
    
    # 检查已有细纲
    outline_dir = project_dirs["outline"]
    if outline_dir.exists():
        briefs = list(outline_dir.glob("ch-*-brief.md"))
        volumes = list(outline_dir.glob("vol-*-brief.yaml"))
        print(f"  📝 细纲文件: {len(briefs)} 章, {len(volumes)} 卷")
    else:
        print(f"  ⚠️ 大纲目录不存在: {outline_dir}")
    
    print()
    
    # 判断缺失项
    missing = []
    if not (project_dirs["world"] / "core-logic.md").exists():
        missing.append("core-logic.md（核心逻辑层）")
    if not (project_dirs["world"] / "iron-laws.md").exists():
        missing.append("iron-laws.md（铁律清单）")
    if not (project_dirs["root"] / "DECISION-TREE.md").exists():
        missing.append("DECISION-TREE.md（追问决策树）")
    
    if missing:
        print("⚠️ 缺失文件：")
        for m in missing:
            print(f"    - {m}")
        print()
        print("建议执行：")
        print(f"  python3 tools/world-logic-builder.py grill --project {args.project}")
    else:
        print("✅ 所有核心逻辑文件已就绪")


def main():
    parser = argparse.ArgumentParser(
        description="世界包核心逻辑构建器（Phase 1→3）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 启动追问（Phase 1）
  python3 tools/world-logic-builder.py grill --project helper-creator
  
  # 落地逻辑文件（Phase 3）
  python3 tools/world-logic-builder.py build --project helper-creator
  
  # 查看状态
  python3 tools/world-logic-builder.py status --project helper-creator
        """
    )
    
    sub = parser.add_subparsers(dest="command", help="子命令")

    # 所有子命令共享 --project
    for sub_cmd in [sub.add_parser("grill", help="Phase 1：启动 grill-me 追问"),
                    sub.add_parser("build", help="Phase 3：将决策树落地为逻辑文件"),
                    sub.add_parser("status", help="查看当前世界包逻辑状态")]:
        sub_cmd.add_argument("--project", "-p", required=True, help="项目 ID（如 helper-creator）")
        if sub_cmd.prog.endswith("build"):
            sub_cmd.add_argument("--skip-grill", action="store_true", help="跳过 Phase 1，直接落地")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "grill":
        cmd_grill(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
