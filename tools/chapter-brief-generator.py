#!/usr/bin/env python3
"""
chapter-brief-generator.py — 单章细纲生成器（Phase 4）

功能：
  根据全卷细纲 + 世界核心逻辑 + 角色档案，生成每章的写作指令。

使用：
  # 生成第 N 章细纲
  python3 tools/chapter-brief-generator.py \\
    --project helper-creator \\
    --chapter 1

  # 批量生成第一卷全部细纲
  python3 tools/chapter-brief-generator.py \\
    --project helper-creator \\
    --volume 1 \\
    --batch

  # 查看帮助
  python3 tools/chapter-brief-generator.py --help
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


BASE_DIR = Path("/var/minis/shared/novel-team")
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


def load_json(path: Path) -> Optional[Dict]:
    """安全加载 JSON 文件"""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON 解析失败 {path}: {e}", file=sys.stderr)
        return None


def load_yaml_simple(path: Path) -> Optional[Dict]:
    """简单 YAML 解析（不依赖 pyyaml）"""
    if not path.exists():
        return None
    
    result = {}
    current_key = None
    current_list = None
    current_dict = None
    indent_stack = []
    
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.startswith("#"):
                continue
            
            # 计算缩进级别
            indent = len(line) - len(line.lstrip())
            
            # 列表项
            if stripped.lstrip().startswith("- "):
                value = stripped.lstrip()[2:].strip()
                if current_list is not None:
                    # 处理字典项 (- key: value)
                    if ": " in value:
                        k, v = value.split(": ", 1)
                        if current_dict is None:
                            current_dict = {}
                        current_dict[k.strip()] = v.strip()
                    else:
                        current_list.append(value)
                continue
            
            # 键值对
            if ": " in stripped:
                key, value = stripped.split(": ", 1)
                key = key.strip()
                value = value.strip()
                
                # 弹出缩进栈
                while indent_stack and indent_stack[-1][1] >= indent:
                    indent_stack.pop()
                
                if indent_stack:
                    parent_key, parent_obj = indent_stack[-1]
                    if isinstance(parent_obj, dict):
                        if value == "" or value is None:
                            # 开始嵌套结构
                            new_dict = {}
                            parent_obj[key] = new_dict
                            indent_stack.append((key, new_dict))
                            current_dict = new_dict
                            current_list = None
                        else:
                            parent_obj[key] = value
                else:
                    result[key] = value
                    if value == "":
                        new_dict = {}
                        result[key] = new_dict
                        indent_stack.append((key, new_dict))
                        current_dict = new_dict
                    else:
                        current_dict = None
                        current_list = None
                
                current_key = key
                continue
            
            # 纯键（值为空，等待子项）
            if stripped.strip().endswith(":"):
                key = stripped.strip()[:-1].strip()
                result[key] = {}
                indent_stack.append((key, result[key]))
                current_key = key
                current_dict = result[key]
                current_list = None
    
    return result


def load_world_logic(project_dirs: Dict) -> Dict:
    """加载世界核心逻辑"""
    logic_path = project_dirs["world"] / "core-logic.md"
    laws_path = project_dirs["world"] / "iron-laws.md"
    
    logic = {}
    if logic_path.exists():
        content = logic_path.read_text(encoding="utf-8")
        # 简单提取各节内容
        sections = re.split(r"\n## ", content)
        for section in sections:
            if section.strip():
                lines = section.split("\n")
                title = lines[0].strip()
                body = "\n".join(lines[1:]).strip()
                logic[title] = body
    
    laws = {}
    if laws_path.exists():
        content = laws_path.read_text(encoding="utf-8")
        # 提取铁律表格
        law_rows = re.findall(r"\| (IL\d+|SL\d+|CL\d+|PL\d+|TL\d+) \|([^|]+)\|([^|]+)\|", content)
        for row in law_rows:
            laws[row[0]] = {"content": row[1].strip(), "consequence": row[2].strip()}
    
    return {"logic": logic, "laws": laws}


def load_characters(project_dirs: Dict) -> Dict:
    """加载角色档案"""
    characters = {}
    char_dir = project_dirs["characters"]
    if not char_dir.exists():
        return characters
    
    for f in char_dir.glob("*.json"):
        data = load_json(f)
        if data and "name" in data:
            characters[data["name"]] = data
    
    return characters


def load_volume_brief(project_dirs: Dict, volume_num: int) -> Optional[Dict]:
    """加载卷级细纲"""
    brief_path = project_dirs["outline"] / f"vol-{volume_num:03d}-brief.yaml"
    if not brief_path.exists():
        # 尝试无零填充格式
        brief_path = project_dirs["outline"] / f"vol-{volume_num}-brief.yaml"
    
    if not brief_path.exists():
        return None
    
    return load_yaml_simple(brief_path)


def generate_chapter_brief(
    chapter_num: int,
    volume_brief: Dict,
    world_logic: Dict,
    characters: Dict,
    project_dirs: Dict,
) -> str:
    """生成单章细纲"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 从卷细纲找到对应章节
    chapters = volume_brief.get("chapters", [])
    chapter_data = None
    for ch in chapters:
        if ch.get("chapter") == chapter_num:
            chapter_data = ch
            break
    
    if not chapter_data:
        # 如果没有预定义章节，生成通用模板
        chapter_data = {
            "chapter": chapter_num,
            "title": f"第{chapter_num}章",
            "scene": "待定",
            "characters": [],
            "conflict": "待定",
            "thrill_level": "L1",
            "info_reveal": "待定",
            "hook": "待定",
        }
    
    # 提取关键信息
    title = chapter_data.get("title", f"第{chapter_num}章")
    scene = chapter_data.get("scene", "待定")
    thrill = chapter_data.get("thrill_level", "L1")
    hook = chapter_data.get("hook", "待定")
    
    # 角色信息
    char_list = chapter_data.get("characters", [])
    char_details = []
    for name in char_list:
        if name in characters:
            char_details.append({
                "name": name,
                "realm": characters[name].get("realm", "未知"),
                "reason": characters[name].get("role_in_chapter", "出场"),
            })
    
    # 铁律约束
    law_table = []
    for law_id, law_data in world_logic["laws"].items():
        law_table.append(f"- **{law_id}**: {law_data['content']} → {law_data['consequence']}")
    
    # 生成细纲
    brief = f"""# 第{chapter_num}章细纲：《{title}》

> 生成日期：{today}
> 所属卷：第{volume_brief.get('volume', {}).get('id', '1')}卷（{volume_brief.get('volume', {}).get('chapter_range', [chapter_num, chapter_num])}章）
> 爽点层级：{thrill}
> 字数目标：2000-3000

## 基础信息
- **章节**：{chapter_num}
- **标题**：{title}
- **场景**：{scene}
- **出场角色**：{', '.join(char_list) if char_list else '待定'}

## 出场角色详情
| 角色 | 境界 | 在场理由 | 本章变化 |
|------|------|---------|---------|
"""
    
    for c in char_details:
        brief += f"| {c['name']} | {c['realm']} | {c['reason']} | 待定 |\n"
    
    brief += f"""
## 核心冲突
{chapter_data.get('conflict', '待定')}

## 爽点设计
- **层级**：{thrill}
- **压抑点**：待定（根据冲突设计）
- **释放点**：待定（根据冲突设计）
- **余韵**：待定

## 信息揭示
- **读者知道**：{chapter_data.get('info_reveal', '待定')}
- **角色知道**：待定
- **信息差**：待定

## 章末钩子
{hook}

## 世界包约束
| 约束类型 | 具体内容 | 违反后果 |
|---------|---------|---------|
| 境界匹配 | 大境差一阶=绝对压制 | P0 阻断 |
| 资源限制 | 低层不接触高阶资源 | P0 阻断 |
| 知情边界 | 角色只能知道它该知道的 | P0 阻断 |
| 金手指隐藏 | 鉴灵匣不得暴露 | P0 阻断 |

## 写作禁忌
- 不得提前揭示鉴灵匣功能
- 不得让林辰主动暴露能力
- 场景过渡需自然（禁止硬切）
- 不得使用现代词汇（秒/分钟/℃等）

## 场景过渡要求
- **上一章结尾**：待定（查看 ch{chapter_num-1}.md）
- **本章开头衔接**：待定
- **切换点**：待定

## 创作指令
基于以上细纲，创作本章正文。要求：
1. 开篇钩子：前100字内建立吸引力
2. 节奏紧凑：每段有推进，无拖沓
3. 对话自然：潜台词>直白表达
4. 过渡连贯：场景切换有桥段
5. 符合铁律：不违反任何 IL/SL/CL/PL/TL 规则

---
*细纲生成完毕，开始创作。*
"""
    
    return brief


def cmd_generate(args):
    """生成单章细纲"""
    project_dirs = get_project_dirs(args.project)
    
    # 加载依赖数据
    world_logic = load_world_logic(project_dirs)
    characters = load_characters(project_dirs)
    
    # 确定卷号
    volume_num = args.volume if args.volume else 1
    
    # 加载卷细纲
    volume_brief = load_volume_brief(project_dirs, volume_num)
    if not volume_brief:
        print(f"⚠️ 未找到 vol-{volume_num:03d}-brief.yaml，使用通用模板")
        volume_brief = {
            "volume": {"id": str(volume_num), "chapter_range": [args.chapter, args.chapter]},
            "chapters": []
        }
    
    # 生成细纲
    brief = generate_chapter_brief(
        args.chapter,
        volume_brief,
        world_logic,
        characters,
        project_dirs,
    )
    
    # 输出
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = project_dirs["outline"] / f"ch-{args.chapter:03d}-brief.md"
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(brief, encoding="utf-8")
    
    print(f"✅ 已生成: {out_path}")
    print(f"   字数: {len(brief)} 字符")
    print(f"   章节: 第{args.chapter}章 《{brief.split('《')[1].split('》')[0] if '《' in brief else '未知'}》")


def cmd_batch(args):
    """批量生成卷内全部细纲"""
    project_dirs = get_project_dirs(args.project)
    
    # 加载依赖数据
    world_logic = load_world_logic(project_dirs)
    characters = load_characters(project_dirs)
    
    # 加载卷细纲
    volume_brief = load_volume_brief(project_dirs, args.volume)
    if not volume_brief:
        print(f"❌ 未找到 vol-{args.volume:03d}-brief.yaml")
        sys.exit(1)
    
    # 确定章节范围
    chapter_range = volume_brief.get("volume", {}).get("chapter_range", [1, 30])
    start, end = chapter_range[0], chapter_range[1]
    
    # 加载已有细纲（避免覆盖）
    existing = set()
    outline_dir = project_dirs["outline"]
    for f in outline_dir.glob("ch-*-brief.md"):
        match = re.search(r"ch-(\d+)-brief", f.name)
        if match:
            existing.add(int(match.group(1)))
    
    print(f"📝 批量生成第{args.volume}卷细纲（Ch{start}~Ch{end}）")
    print(f"   已有细纲: {existing}")
    print()
    
    generated = 0
    skipped = 0
    
    for ch_num in range(start, end + 1):
        if ch_num in existing and not args.force:
            print(f"  ⏭️  Ch{ch_num:03d} 已存在，跳过（加 --force 强制覆盖）")
            skipped += 1
            continue
        
        brief = generate_chapter_brief(
            ch_num,
            volume_brief,
            world_logic,
            characters,
            project_dirs,
        )
        
        out_path = outline_dir / f"ch-{ch_num:03d}-brief.md"
        out_path.write_text(brief, encoding="utf-8")
        print(f"  ✅  Ch{ch_num:03d} → {out_path.name}")
        generated += 1
    
    print()
    print(f"✅ 完成：生成 {generated} 个，跳过 {skipped} 个")


def main():
    parser = argparse.ArgumentParser(
        description="单章细纲生成器（Phase 4）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 生成第1章细纲
  python3 tools/chapter-brief-generator.py --project helper-creator --chapter 1
  
  # 批量生成第1卷全部细纲
  python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch
  
  # 强制覆盖已有细纲
  python3 tools/chapter-brief-generator.py --project helper-creator --chapter 1 --force
        """
    )
    
    parser.add_argument("--project", "-p", required=True, help="项目 ID")
    parser.add_argument("--chapter", "-c", type=int, help="章节号（单独生成时用）")
    parser.add_argument("--volume", "-v", type=int, default=1, help="卷号（批量生成时用）")
    parser.add_argument("--batch", "-b", action="store_true", help="批量生成整卷细纲")
    parser.add_argument("--output", "-o", help="输出路径")
    parser.add_argument("--force", "-f", action="store_true", help="强制覆盖已有细纲")
    
    args = parser.parse_args()
    
    if not args.chapter and not args.batch:
        parser.error("必须指定 --chapter 或 --batch")
    
    if args.batch:
        cmd_batch(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()
