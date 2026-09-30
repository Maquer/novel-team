#!/usr/bin/env python3
"""
grill-gate-bridge.py — grill-me 与质量门禁系统的衔接工具

功能：
  1. 启动 grill-me 追问门禁阈值决策（为什么是这个数字？）
  2. 将追问结果落地为 threshold-decision.md（决策记录）
  3. 生成阈值调优建议（基于追问答案 + 实际数据）

使用：
  # 启动阈值决策追问
  python3 tools/grill-gate-bridge.py start --project helper-creator

  # 落地决策记录
  python3 tools/grill-gate-bridge.py build --project helper-creator

  # 查看当前阈值状态
  python3 tools/grill-gate-bridge.py status --project helper-creator

  # 一步到位（启动追问 + 落地）
  python3 tools/grill-gate-bridge.py run --project helper-creator
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
CONFIG_DIR = BASE_DIR / "config"


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
# 门禁阈值追问问题库
# ============================================================

GATE_QUESTION_BANK = [
    {
        "id": "GQ01",
        "domain": "字数下限",
        "question": "为什么 word_count.soft_min=1500？1300 会怎样？1800 会怎样？这个阈值是基于什么数据决定的？",
        "follow_up": [
            "当前已写章节的平均字数是多少？1500 离平均值多远？",
            "有多少章低于 1500 字？这些章的质量如何？",
            "如果降到 1300，会放行多少低质量章节？如果升到 1800，会阻断多少正常章节？",
            "这个阈值的目标是什么？（防灌水？保信息密度？还是其他？）",
        ],
        "expected_output": {
            "current_value": 1500,
            "data_basis": "基于当前章节字数分布（需计算）",
            "alternative_values": {"low": 1300, "high": 1800},
            "decision_rationale": "为什么选 1500 而不是其他值",
        },
    },
    {
        "id": "GQ02",
        "domain": "AI 味阻断线",
        "question": "为什么 ai_tone.block_at=16？15 会漏多少 AI 味？17 会放行多少问题？",
        "follow_up": [
            "当前章节的 tier_1a 分数分布是怎样的？16 这个 cutoff 在分布的什么位置？",
            "有多少章在 15-16 区间？这些章的 AI 味是否可接受？",
            "如果降到 15，会阻断多少原本可以放的章节？如果升到 17，会放行多少问题章节？",
            "block_at 和 threshold（15.0）的关系是什么？为什么差 1？",
        ],
        "expected_output": {
            "current_value": 16,
            "threshold_relation": "block_at = threshold + 1（留 1 分 buffer）",
            "distribution_analysis": "当前章节的 tier_1a 分数分布",
            "sensitivity": "±1 分对通过率的影响",
        },
    },
    {
        "id": "GQ03",
        "domain": "AI 味预警线",
        "question": "为什么 ai_tone.warn_at=13？13 以下就不预警了吗？",
        "follow_up": [
            "13 以下的章节是否有 AI 味问题？如果有，为什么不在预警范围内？",
            "warn_at 和 block_at 之间的区间（13-16）是什么含义？",
            "这个区间内的章节需要作者自行判断还是可以自动处理？",
        ],
        "expected_output": {
            "current_value": 13,
            "warning_zone": "13-16 为预警区，作者需人工判断",
            "rationale": "为什么 13 以下是安全的",
        },
    },
    {
        "id": "GQ04",
        "domain": "超长警告线",
        "question": "为什么 word_count.warn_above=5500？超过多少字会有问题？",
        "follow_up": [
            "当前章节字数分布中，超过 5500 字的章节占比多少？",
            "长章节是否有质量问题？是信息密度稀释还是内容充实？",
            "warn_above 的目的是什么？（防拖沓？保节奏？）",
        ],
        "expected_output": {
            "current_value": 5500,
            "purpose": "预警超长章节，防止信息密度稀释",
            "impact": "超过此值的章节会收到 warning",
        },
    },
    {
        "id": "GQ05",
        "domain": "其他检查插件阈值",
        "question": "其他 13 个检查插件（fact_consistency/hook/cliche/protocol 等）的阈值在哪里定义？为什么？",
        "follow_up": [
            "这些插件的阈值是硬编码还是可从配置读取？",
            "哪些插件有可调节的阈值？哪些是固定规则？",
            "阈值的来源是什么？（经验？测试数据？领域知识？）",
        ],
        "expected_output": {
            "hardcoded_thresholds": ["插件名: 阈值"],
            "configurable_thresholds": ["插件名: 配置路径"],
            "decision_rationale": "每个阈值的决策依据",
        },
    },
]


def load_current_config() -> Dict:
    """加载当前阈值配置"""
    config_path = CONFIG_DIR / "novelkit.json"
    if not config_path.exists():
        return {}

    content = config_path.read_text(encoding="utf-8")
    # 去掉 docstring
    json_start = content.find("{")
    if json_start >= 0:
        content = content[json_start:]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


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


def extract_gate_answers(decision_tree: Dict) -> Dict:
    """从决策树中提取门禁阈值相关答案"""
    answers = {}
    for section_title, content in decision_tree.items():
        for gq in GATE_QUESTION_BANK:
            if gq["id"] in section_title or gq["domain"] in section_title:
                answers[gq["id"]] = {
                    "domain": gq["domain"],
                    "question": gq["question"],
                    "answer": content,
                }
    return answers


def generate_threshold_decision(doc_id: str, answers: Dict, current_config: Dict) -> str:
    """生成阈值决策文档"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 提取各字段答案
    gq01 = answers.get("GQ01", {})
    gq02 = answers.get("GQ02", {})
    gq03 = answers.get("GQ03", {})
    gq04 = answers.get("GQ04", {})
    gq05 = answers.get("GQ05", {})

    # 生成文档
    decision = f"""# 质量门禁阈值决策记录

> 生成日期：{today}
> 来源：grill-me 追问 + 当前配置分析
> 状态：validated（经追问确认）

---

## 一、当前阈值配置

```json
{json.dumps(current_config, ensure_ascii=False, indent=2)}
```

---

## 二、阈值决策依据

### GQ01：字数下限（soft_min）

**当前值**：{current_config.get('word_count', {}).get('soft_min', 'N/A')} 字

**追问记录**：
{gq01.get('answer', '待补充')}

**决策依据**：
- 数据基础：{gq01.get('expected_output', {}).get('data_basis', '待补充')}
- 替代方案对比：低 {gq01.get('expected_output', {}).get('alternative_values', {}).get('low', 'N/A')} / 高 {gq01.get('expected_output', {}).get('alternative_values', {}).get('high', 'N/A')}
- 选择理由：{gq01.get('expected_output', {}).get('decision_rationale', '待补充')}

---

### GQ02：AI 味阻断线（block_at）

**当前值**：{current_config.get('ai_tone', {}).get('block_at', 'N/A')}

**追问记录**：
{gq02.get('answer', '待补充')}

**决策依据**：
- 分数分布：{gq02.get('expected_output', {}).get('distribution_analysis', '待补充')}
- 敏感度分析：{gq02.get('expected_output', {}).get('sensitivity', '待补充')}
- 与 threshold 的关系：{gq02.get('expected_output', {}).get('threshold_relation', 'block_at = threshold + 1')}

---

### GQ03：AI 味预警线（warn_at）

**当前值**：{current_config.get('ai_tone', {}).get('warn_at', 'N/A')}

**追问记录**：
{gq03.get('answer', '待补充')}

**决策依据**：
- 预警区间：{gq03.get('expected_output', {}).get('warning_zone', '13-16')}
- 选择理由：{gq03.get('expected_output', {}).get('rationale', '待补充')}

---

### GQ04：超长警告线（warn_above）

**当前值**：{current_config.get('word_count', {}).get('warn_above', 'N/A')} 字

**追问记录**：
{gq04.get('answer', '待补充')}

**决策依据**：
- 目的：{gq04.get('expected_output', {}).get('purpose', '预警超长章节')}
- 影响：{gq04.get('expected_output', {}).get('impact', '待补充')}

---

### GQ05：其他检查插件阈值

**追问记录**：
{gq05.get('answer', '待补充')}

**决策依据**：
- 硬编码阈值：{json.dumps(gq05.get('expected_output', {}).get('hardcoded_thresholds', []), ensure_ascii=False)}
- 可配置阈值：{json.dumps(gq05.get('expected_output', {}).get('configurable_thresholds', []), ensure_ascii=False)}

---

## 三、阈值调优建议

基于追问结果，建议：

| 阈值项 | 当前值 | 建议值 | 调优理由 | 风险等级 |
|--------|--------|--------|---------|---------|
| soft_min | {current_config.get('word_count', {}).get('soft_min', 'N/A')} | 待定 | {gq01.get('answer', '待分析')[:50]}... | 中 |
| block_at | {current_config.get('ai_tone', {}).get('block_at', 'N/A')} | 待定 | {gq02.get('answer', '待分析')[:50]}... | 高 |
| warn_at | {current_config.get('ai_tone', {}).get('warn_at', 'N/A')} | 待定 | {gq03.get('answer', '待分析')[:50]}... | 低 |
| warn_above | {current_config.get('word_count', {}).get('warn_above', 'N/A')} | 待定 | {gq04.get('answer', '待分析')[:50]}... | 低 |

---

## 四、后续行动

- [ ] 基于决策记录更新 `config/novelkit.json`
- [ ] 重新运行门禁检查，验证新阈值效果
- [ ] 记录调优前后通过率变化

---
*本文件由 grill-gate-bridge.py 生成，基于 grill-me 追问结果。*
*阈值调整需谨慎，建议先备份原配置。*
"""
    return decision


def cmd_start(args):
    """启动阈值决策追问"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print("🍳 质量门禁阈值决策追问启动")
    print("=" * 60)
    print()
    print(f"项目：{args.project}")
    print(f"工作区：{WORKSPACE_DIR}")
    print()

    # 检查当前配置
    config = load_current_config()
    print("【当前阈值配置】")
    print(json.dumps(config, ensure_ascii=False, indent=2))
    print()

    # 显示追问领域
    print("即将启动 grill-me 阈值决策追问模式。")
    print()
    print("追问领域：")
    for gq in GATE_QUESTION_BANK:
        print(f"  {gq['id']}: {gq['domain']}")
        print(f"    Q: {gq['question'][:60]}...")
    print()
    print("追问完成后，运行：")
    print(f"  python3 {TOOLS_DIR / 'grill-gate-bridge.py'} build --project {args.project}")
    print()
    print("💡 提示：追问时提供具体数据（如当前章节字数分布），便于决策")


def cmd_build(args):
    """落地阈值决策文件"""
    project_dirs = get_project_dirs(args.project)
    workspace_tree = WORKSPACE_DIR / "DECISION-TREE.md"
    project_tree = project_dirs["root"] / "DECISION-TREE.md"

    print("=" * 60)
    print("🔨 阈值决策文件落地")
    print("=" * 60)
    print()

    # 检查决策树
    if not workspace_tree.exists():
        print("❌ 未找到 DECISION-TREE.md")
        print(f"   预期位置: {workspace_tree}")
        print()
        print("请先运行追问：")
        print(f"  python3 {TOOLS_DIR / 'grill-gate-bridge.py'} start --project {args.project}")
        sys.exit(1)

    print(f"✅ 找到决策树: {workspace_tree}")
    print()

    # 复制决策树到项目目录
    project_tree.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(workspace_tree, project_tree)
    print(f"✅ 已复制到项目目录: {project_tree}")
    print()

    # 加载决策树
    decision_tree = load_decision_tree(project_dirs)
    if not decision_tree:
        print("❌ 无法解析决策树")
        sys.exit(1)

    # 提取门禁阈值答案
    answers = extract_gate_answers(decision_tree)
    print(f"✅ 提取到 {len(answers)} 个阈值相关问题答案")
    print()

    # 加载当前配置
    config = load_current_config()
    print(f"✅ 已加载当前配置: {CONFIG_DIR / 'novelkit.json'}")
    print()

    # 生成阈值决策文档
    doc_id = f"threshold-decision-{datetime.now().strftime('%Y%m%d')}"
    decision_content = generate_threshold_decision(doc_id, answers, config)

    # 保存决策文档
    docs_dir = project_dirs["root"] / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    decision_path = docs_dir / f"{doc_id}.md"
    decision_path.write_text(decision_content, encoding="utf-8")

    print(f"✅ 已生成阈值决策文档: {decision_path.name}")
    print()

    print("=" * 60)
    print("✅ 阈值决策落地完成")
    print("=" * 60)
    print()
    print("下一步：")
    print(f"  1. 审阅 {decision_path}")
    print("  2. 基于决策记录决定是否调整 config/novelkit.json")
    print("  3. 调整后重新运行门禁检查验证效果")


def cmd_status(args):
    """查看当前阈值状态"""
    project_dirs = get_project_dirs(args.project)
    config = load_current_config()

    print("=" * 60)
    print(f"📋 项目 '{args.project}' 门禁阈值状态")
    print("=" * 60)
    print()

    # 显示当前配置
    print("【当前阈值配置】")
    print(json.dumps(config, ensure_ascii=False, indent=2))
    print()

    # 检查决策文件
    docs_dir = project_dirs["root"] / "docs"
    decision_files = list(docs_dir.glob("threshold-decision-*.md")) if docs_dir.exists() else []

    if decision_files:
        print(f"【阈值决策记录】{len(decision_files)} 个")
        for df in sorted(decision_files, reverse=True)[:3]:
            size = df.stat().st_size
            print(f"  - {df.name}: {size:,} bytes")
    else:
        print("【阈值决策记录】未生成")
        print("  运行以下命令生成：")
        print(f"    python3 {TOOLS_DIR / 'grill-gate-bridge.py'} build --project {args.project}")

    print()

    # 检查已写章节字数分布
    chapters_dir = project_dirs["chapters"]
    if chapters_dir.exists():
        ch_files = sorted(chapters_dir.glob("ch*.md"))
        if ch_files:
            word_counts = []
            for cf in ch_files:
                content = cf.read_text(encoding="utf-8")
                chinese_chars = len([c for c in content if '\u4e00' <= c <= '\u9fff'])
                word_counts.append(chinese_chars)

            if word_counts:
                avg_words = sum(word_counts) // len(word_counts)
                min_words = min(word_counts)
                max_words = max(word_counts)
                below_threshold = sum(1 for w in word_counts if w < config.get('word_count', {}).get('soft_min', 1500))

                print("【已写章节字数分布】")
                print(f"  章节数: {len(ch_files)}")
                print(f"  平均字数: {avg_words}")
                print(f"  最小字数: {min_words}")
                print(f"  最大字数: {max_words}")
                print(f"  低于阈值(soft_min={config.get('word_count', {}).get('soft_min', 1500)}): {below_threshold} 章")
                print()

                # 判断阈值是否需要调整
                if below_threshold > 0:
                    print("⚠️  有章节低于字数阈值，建议运行阈值决策追问")
                elif avg_words < config.get('word_count', {}).get('soft_min', 1500) * 1.5:
                    print("💡  平均字数较低，可考虑下调 soft_min")
                else:
                    print("✅  字数分布正常，阈值无需调整")
        else:
            print("【已写章节字数分布】暂无章节数据")
    else:
        print("【已写章节字数分布】章节目录不存在")


def main():
    parser = argparse.ArgumentParser(
        description="grill-me 与质量门禁系统的衔接工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 启动阈值决策追问
  python3 tools/grill-gate-bridge.py start --project helper-creator

  # 落地决策记录
  python3 tools/grill-gate-bridge.py build --project helper-creator

  # 查看当前阈值状态
  python3 tools/grill-gate-bridge.py status --project helper-creator
        """
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    p_start = sub.add_parser("start", help="启动阈值决策追问")
    p_start.add_argument("--project", "-p", required=True, help="项目 ID")

    p_build = sub.add_parser("build", help="落地阈值决策文件")
    p_build.add_argument("--project", "-p", required=True, help="项目 ID")

    p_status = sub.add_parser("status", help="查看当前阈值状态")
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
