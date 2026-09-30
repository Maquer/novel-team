#!/usr/bin/env python3
# Version: 0.1.0
"""
minis-markdown-eval — Minis Markdown 评测数据集构建器

基于 MDEval (arXiv:2501.15000) 方法论，为 Minis 生态构建 Markdown Awareness
训练/评测数据集。覆盖 4 种场景：
  1. skill/SKILL.md — Skill 定义文档
  2. GLOBAL.md — 全局知识库
  3. daily log — 会话日志
  4. Obsidian 笔记 — 知识库条目

用法:
    python3 minis-markdown-eval.py build          # 构建完整数据集
    python3 minis-markdown-eval.py build --only skill
    python3 minis-markdown-eval.py eval <file>    # 评估单个文件
    python3 minis-markdown-eval.py stats          # 统计信息

输出:
    /var/minis/shared/minis-markdown-eval/
    ├── dataset.jsonl          # JSONL 格式训练数据
    ├── README.md              # 数据集说明
    └── metrics/               # 评估结果
"""

import os
import re
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import argparse

# ── 路径配置 ──────────────────────────────────────────────────────
SKILLS_DIR = "/var/minis/skills"
MEMORY_DIR = "/var/minis/memory"
OBSIDIAN_DIR = "/var/minis/mounts/loong"
OUTPUT_DIR = "/var/minis/shared/minis-markdown-eval"


# ── Markdown 质量标签生成器 ────────────────────────────────────────

def generate_excellent_sample(scene: str, topic: str) -> str:
    """
    生成高质量 Markdown 样本（excellent 级）。
    
    遵循 MDEval 论文最佳实践：
    - 结构层次清晰（header 层级连续）
    - 格式元素齐全（列表/code/table/引用）
    - 内容-结构对齐（header 后有足够内容）
    """
    templates = {
        'skill': f"""---
name: {topic.lower().replace(' ', '-')}
description: >
  {topic}的 Skill 描述。
slug: {topic.lower().replace(' ', '-')}
---

# {topic} — Skill Definition

## 🧠 Agent Identity

| 字段 | 内容 |
|------|------|
| **Role** | {topic} 专家 |
| **Trigger** | 用户提到"{topic}"相关词 |

## 📋 Core Missions

### 1. Mission One

描述具体任务目标...

### 2. Mission Two

描述具体任务目标...

## ⚙️ Parameters

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `param_a` | string | `"default"` | 参数A的说明 |
| `param_b` | int | `0` | 参数B的说明 |

## 📝 Examples

### 触发示例

\`\`\`
用户: "帮我{topic}"
\`\`\`

### 输出示例

\`\`\`markdown
# 输出结构
- 点一
- 点二
\`\`\`

## ⚠️ Limitations

- 能力边界一
- 能力边界二

> **注意**: 本文档遵循 MDEval excellent 标准。
""",
        'global': f"""# GLOBAL — {topic} 知识库

> 只存跨会话复用的知识：路径约定、归档规范、环境特性。

**最后更新：** {datetime.now().strftime("%Y-%m-%d %H:%M")} | **下次维护检查：** {datetime.now().strftime("%Y-%m-%d")}

---

## ⚡ 快速入口

> 90% 的日常查询在这里。

### 高频路径
| 查什么 | 在哪 |
|--------|------|
| 归档新内容 | \`03-Resources/\` → 格式见 §二 |
| 找某个项目 | \`skills/\` 下按名称找 |
| 查系统状态 | \`bash minis-dashboard.sh\` |
| 快速记录 | \`minis-capture.sh -t 标签 "内容"\` |

### 常用命令
\`\`\`bash
minis-cli search --query '关键词'
minis-cli dashboard
minis-cli audit
\`\`\`

## 📊 当前状态

### 活跃项目
1. **项目A** — 进行中，预计 09-30 完成
2. **项目B** — 待启动
3. **项目C** — 已归档

### 待处理事项
- [ ] 事项一
- [ ] 事项二
- [x] 事项三（已完成）

## 🔧 环境配置

| 组件 | 版本 | 状态 |
|------|------|------|
| Python | 3.11 | ✅ |
| Node | 22.23 | ✅ |
| Go | 1.23 | ✅ |

> **提示**: 每次配置变更后更新此表。
""",
        'dailylog': f"""# {datetime.now().strftime("%Y-%m-%d")} 工作记录

<!-- {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} -->

## 完成事项

### 1. 事项一

- 目标：描述目标
- 结果：描述结果
- 耗时：约 30 分钟

### 2. 事项二

\`\`\`python
# 代码示例
def example():
    return "hello"
\`\`\`

## 遇到的问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 问题A | 原因1 | 方案1 |
| 问题B | 原因2 | 方案2 |

## 下一步

- [ ] 待办一
- [ ] 待办二

> 💡 **今日洞察**: 从事项中提炼的洞察。
""",
        'obsidian': f"""# {topic} — 知识卡片

> 来源：{topic} 相关研究
> 标签：#knowledge #{topic.lower()} #research
> 创建日期：{datetime.now().strftime("%Y-%m-%d")}

## 核心观点

{topic} 的核心观点是...

### 关键论据

1. **论据一**：支持性描述
2. **论据二**：支持性描述
3. **论据三**：支持性描述

## 对比分析

| 维度 | 方案A | 方案B |
|------|-------|-------|
| 优点 | 优点1 | 优点2 |
| 缺点 | 缺点1 | 缺点2 |
| 适用场景 | 场景1 | 场景2 |

## 实施建议

\`\`\`bash
# 建议命令
command --option value
\`\`\`

## 相关链接
- [[相关笔记1]]
- [[相关笔记2]]

> **TL;DR**: {topic} 的关键结论用一句话概括。
""",
    }
    return templates.get(scene, templates['skill'])


def generate_poor_sample(scene: str, topic: str) -> str:
    """
    生成低质量 Markdown 样本（poor 级）。
    
    常见问题：
    - 无结构层次（只有纯文本）
    - 格式不一致
    - 段落过长
    - 缺少必要元素
    """
    templates = {
        'skill': f"""{topic} skill

this is a skill for {topic}

missions:
1. do something
2. do another thing

parameters: none

examples:
- example 1
- example 2

limitations:
- no limitations known""",
        'global': f"""GLOBAL knowledge base

last updated: today

quick links: none really

common commands: just type stuff

status: active

environment: working okay""",
        'dailylog': f"""2026-09-27 work log

done stuff today:
- did thing one
- did thing two
- did more things

problems:
none really

next steps:
- maybe do more
- probably continue

insights: nothing special""",
        'obsidian': f"""{topic} notes

the main idea is that {topic} is important

arguments:
- argument one
- argument two
- argument three

comparison:
it depends

recommendations:
just do it

links:
none

summary: {topic} is cool""",
    }
    return templates.get(scene, templates['skill'])


# ── 数据集构建器 ───────────────────────────────────────────────────

def collect_existing_samples() -> List[Dict[str, Any]]:
    """从 Minis 生态收集真实 Markdown 样本。"""
    samples = []
    
    # 1. Skills SKILL.md
    if os.path.isdir(SKILLS_DIR):
        for skill_name in os.listdir(SKILLS_DIR):
            skill_dir = os.path.join(SKILLS_DIR, skill_name)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if os.path.isfile(skill_md):
                try:
                    content = open(skill_md, 'r', encoding='utf-8', errors='replace').read()
                    if len(content) > 100:  # 过滤太短的
                        samples.append({
                            'scene': 'skill',
                            'source': f'skills/{skill_name}/SKILL.md',
                            'content': content,
                            'length': len(content),
                        })
                except Exception:
                    pass
    
    # 2. GLOBAL.md / SOUL.md
    for fname in ['GLOBAL.md', 'SOUL.md']:
        fpath = os.path.join(MEMORY_DIR, fname)
        if os.path.isfile(fpath):
            try:
                content = open(fpath, 'r', encoding='utf-8', errors='replace').read()
                samples.append({
                    'scene': 'global',
                    'source': f'memory/{fname}',
                    'content': content,
                    'length': len(content),
                })
            except Exception:
                pass
    
    # 3. Daily logs（最近 7 天）
    from datetime import timedelta
    today = datetime.now()
    for days_ago in range(7):
        date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        fpath = os.path.join(MEMORY_DIR, f'{date}.md')
        if os.path.isfile(fpath):
            try:
                content = open(fpath, 'r', encoding='utf-8', errors='replace').read()
                samples.append({
                    'scene': 'dailylog',
                    'source': f'memory/{date}.md',
                    'content': content,
                    'length': len(content),
                })
            except Exception:
                pass
    
    # 4. Obsidian 笔记（采样前 50 个）
    if os.path.isdir(OBSIDIAN_DIR):
        count = 0
        for root, dirs, files in os.walk(OBSIDIAN_DIR):
            for fname in files:
                if fname.endswith('.md') and count < 50:
                    fpath = os.path.join(root, fname)
                    try:
                        content = open(fpath, 'r', encoding='utf-8', errors='replace').read()
                        if len(content) > 200:  # 过滤太短的
                            rel_path = os.path.relpath(fpath, OBSIDIAN_DIR)
                            samples.append({
                                'scene': 'obsidian',
                                'source': rel_path,
                                'content': content,
                                'length': len(content),
                            })
                            count += 1
                    except Exception:
                        pass
            if count >= 50:
                break
    
    return samples


def generate_synthetic_samples() -> List[Dict[str, Any]]:
    """生成合成样本（excellent + poor 对照）。"""
    topics = {
        'skill': ['agent-assistant', 'code-reviewer', 'content-writer', 'data-analyst', 'research-bot'],
        'global': ['system-config', 'project-rules', 'team-handbook', 'api-docs', 'setup-guide'],
        'dailylog': ['monday-log', 'tuesday-log', 'project-update', 'bug-fix-log', 'meeting-notes'],
        'obsidian': ['ml-paper', 'python-tutorial', 'product-review', 'travel-guide', 'cooking-recipe'],
    }
    
    samples = []
    for scene, topic_list in topics.items():
        for topic in topic_list:
            # excellent 样本
            excellent = generate_excellent_sample(scene, topic)
            samples.append({
                'scene': scene,
                'quality': 'excellent',
                'topic': topic,
                'content': excellent,
                'length': len(excellent),
                'source': 'synthetic',
            })
            
            # poor 样本
            poor = generate_poor_sample(scene, topic)
            samples.append({
                'scene': scene,
                'quality': 'poor',
                'topic': topic,
                'content': poor,
                'length': len(poor),
                'source': 'synthetic',
            })
    
    return samples


def build_dataset(output_dir: str, max_real_samples: int = 100, max_synthetic_per_scene: int = 20) -> Dict[str, Any]:
    """
    构建完整数据集。
    
    返回:
        dict: {total_samples, by_scene, by_quality, save_path}
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 收集真实样本
    print(f"📂 收集真实 Markdown 样本...")
    real_samples = collect_existing_samples()
    real_samples = real_samples[:max_real_samples]  # 限制数量
    print(f"   收集到 {len(real_samples)} 个真实样本")
    
    # 生成合成样本
    print(f"🤖 生成合成对照样本...")
    synthetic_samples = generate_synthetic_samples()
    # 按 scene + quality 分组，限制每个组合的数量
    from collections import Counter
    scene_quality_counts = Counter()
    filtered_synthetic = []
    for s in synthetic_samples:
        key = f"{s['scene']}_{s['quality']}"
        if scene_quality_counts[key] < max_synthetic_per_scene:
            filtered_synthetic.append(s)
            scene_quality_counts[key] += 1
    print(f"   生成 {len(filtered_synthetic)} 个合成样本")
    
    # 合并样本
    all_samples = real_samples + filtered_synthetic
    
    # 评估每个样本
    print(f"📊 评估 Markdown Awareness...")
    from mdeval_assessor import calculate_md_awareness
    for s in all_samples:
        if 'score' not in s:  # 避免重复评估
            s.update(calculate_md_awareness(s['content']))
    
    # 统计
    by_scene = {}
    by_quality = {'excellent': [], 'poor': []}
    for s in all_samples:
        scene = s.get('scene', 'unknown')
        by_scene.setdefault(scene, []).append(s)
        quality = s.get('quality', 'unknown')
        if quality in by_quality:
            by_quality[quality].append(s)
    
    # 保存为 JSONL
    output_file = os.path.join(output_dir, 'dataset.jsonl')
    with open(output_file, 'w', encoding='utf-8') as f:
        for s in all_samples:
            # 只保存必要字段
            saveable = {k: v for k, v in s.items() 
                       if k in ['scene', 'quality', 'topic', 'source', 'content', 
                               'score', 'level', 'length', 'elements_count']}
            f.write(json.dumps(saveable, ensure_ascii=False) + '\n')
    
    # 保存统计报告
    stats = {
        'total_samples': len(all_samples),
        'by_scene': {k: len(v) for k, v in by_scene.items()},
        'by_quality': {k: len(v) for k, v in by_quality.items()},
        'avg_score_by_scene': {k: sum(s['score'] for s in v) / len(v) for k, v in by_scene.items()},
        'avg_score_by_quality': {k: sum(s['score'] for s in v) / len(v) for k, v in by_quality.items()},
        'save_path': output_file,
        'build_time': datetime.now().isoformat(),
    }
    
    stats_file = os.path.join(output_dir, 'stats.json')
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # 保存 README
    readme = f"""# minis-markdown-eval 数据集

**构建时间**: {stats['build_time']}
**总样本数**: {stats['total_samples']}

## 数据集结构

| 场景 | 样本数 | 平均 MA 分数 |
|------|--------|-------------|
"""
    for scene, count in stats['by_scene'].items():
        avg = stats['avg_score_by_scene'].get(scene, 0)
        readme += f"| {scene} | {count} | {avg:.1f}/100 |\n"
    
    readme += f"""
## 质量分布

| 质量 | 样本数 | 平均 MA 分数 |
|------|--------|-------------|
"""
    for quality, count in stats['by_quality'].items():
        avg = stats['avg_score_by_quality'].get(quality, 0)
        readme += f"| {quality} | {count} | {avg:.1f}/100 |\n"
    
    readme += f"""
## 使用方法

```bash
# 加载数据集
import json
with open('dataset.jsonl') as f:
    dataset = [json.loads(line) for line in f]

# 评估单个文件
from mdeval_assessor import calculate_md_awareness
result = calculate_md_awareness(your_markdown_text)
print(f"MA Score: {result['score']}/100")
```

## 生成方式

- **真实样本**：从 `/var/minis/skills/`、`/var/minis/memory/`、`/var/minis/mounts/loong/` 收集
- **合成样本**：通过 `generate_excellent_sample()` / `generate_poor_sample()` 生成对照

## 用途

1. **训练**：微调小模型提升 Markdown Awareness
2. **评测**：评估 Minis 生态生成的 Markdown 质量
3. **基准**：作为 skill-eval-gate.py 的 Markdown 维度补充
"""
    
    readme_file = os.path.join(output_dir, 'README.md')
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"\n✅ 数据集已保存:")
    print(f"   📄 {output_file}")
    print(f"   📊 {stats_file}")
    print(f"   📖 {readme_file}")
    
    return stats


# ── CLI 入口 ───────────────────────────────────────────────────────

def cmd_build(args):
    """构建数据集命令。"""
    stats = build_dataset(
        output_dir=args.output,
        max_real_samples=args.max_real,
        max_synthetic_per_scene=args.max_synthetic,
    )
    print(f"\n📈 统计摘要:")
    print(f"   总样本: {stats['total_samples']}")
    print(f"   场景分布: {stats['by_scene']}")
    print(f"   质量分布: {stats['by_quality']}")


def cmd_eval(args):
    """评估单个文件命令。"""
    from mdeval_assessor import calculate_md_awareness
    
    if os.path.isfile(args.file):
        content = open(args.file, 'r', encoding='utf-8', errors='replace').read()
        result = calculate_md_awareness(content)
        print(f"\n📄 文件: {args.file}")
        print(f"📊 MA Score: {result['score']}/100 ({result['level']})")
        print(f"📐 Elements: {result['elements_count']}")
        print(f"📋 Details:")
        for dim, data in result['details'].items():
            print(f"   {dim}: {data['score']}/{data['max']}")
    else:
        # 当作纯文本评估
        result = calculate_md_awareness(args.file)
        print(f"\n📝 文本评估:")
        print(f"📊 MA Score: {result['score']}/100 ({result['level']})")
        print(f"📐 Elements: {result['elements_count']}")


def cmd_stats(args):
    """显示数据集统计命令。"""
    stats_file = os.path.join(args.dataset_dir, 'stats.json')
    if os.path.isfile(stats_file):
        stats = json.load(open(stats_file))
        print(f"\n📊 minis-markdown-eval 数据集统计")
        print(f"   构建时间: {stats['build_time']}")
        print(f"   总样本: {stats['total_samples']}")
        print(f"\n   场景分布:")
        for scene, count in stats['by_scene'].items():
            avg = stats['avg_score_by_scene'].get(scene, 0)
            print(f"     {scene}: {count} samples, avg MA={avg:.1f}")
        print(f"\n   质量分布:")
        for quality, count in stats['by_quality'].items():
            avg = stats['avg_score_by_quality'].get(quality, 0)
            print(f"     {quality}: {count} samples, avg MA={avg:.1f}")
    else:
        print(f"❌ 数据集不存在: {stats_file}")
        print(f"   请先运行: python3 minis-markdown-eval.py build")


def main():
    parser = argparse.ArgumentParser(description='minis-markdown-eval 数据集构建器')
    sub = parser.add_subparsers(dest='command')
    
    # build 子命令
    build_p = sub.add_parser('build', help='构建 Markdown 评测数据集')
    build_p.add_argument('--output', '-o', default=OUTPUT_DIR, help='输出目录')
    build_p.add_argument('--max-real', type=int, default=100, help='最大真实样本数')
    build_p.add_argument('--max-synthetic', type=int, default=20, help='每个场景的最大合成样本数')
    
    # eval 子命令
    eval_p = sub.add_parser('eval', help='评估单个 Markdown 文件')
    eval_p.add_argument('file', help='要评估的文件或文本')
    
    # stats 子命令
    stats_p = sub.add_parser('stats', help='显示数据集统计信息')
    stats_p.add_argument('--dataset-dir', '-d', default=OUTPUT_DIR, help='数据集目录')
    
    args = parser.parse_args()
    
    if args.command == 'build':
        cmd_build(args)
    elif args.command == 'eval':
        cmd_eval(args)
    elif args.command == 'stats':
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
