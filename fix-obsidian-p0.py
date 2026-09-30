#!/usr/bin/env python3
# Version: 0.1.0
"""
Obsidian 知识库 P0 修复脚本
- 孤立笔记补链
- 缺标签笔记补标签
- 近重复卡片合并建议
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime

OBSIDIAN_ROOT = "/var/minis/mounts/loong"

# ── 孤立笔记补链规则 ──
ISOLATED_LINK_RULES = {
    # Areas 目录 → 补链到 MOC
    "02-Areas/": "[[MOC]]",
    # Projects 目录 → 补链到对应项目主笔记
    "01-Projects/多多视频/": "[[多多视频]]",
    "01-Projects/公众号自动化/": "[[公众号自动化]]",
    # Archives 目录 → 补链到 MOC
    "04-Archives/": "[[MOC]]",
    # Inbox 目录 → 补链到对应 Areas
    "00-Inbox/": "[[MOC]]",
}

# 标签补全规则
TAG_FIX_RULES = {
    "README.md": ["README", "索引"],
    "任务看板.md": ["任务", "看板"],
    "核心概念图谱.md": ["图谱", "核心概念"],
    "AI工具知识库.md": ["AI工具", "知识库"],
    "本周日志.md": ["日志", "周志"],
    "收件箱待处理.md": ["收件箱", "待处理"],
    "近期归档.md": ["归档", "近期"],
    "audience.md": ["受众", "画像"],
    "identity.md": ["身份", "定位"],
    "memory.md": ["经验", "沉淀"],
    "platforms.md": ["平台", "矩阵"],
    "style.md": ["风格", "表达"],
    "preferences.md": ["偏好", "红线"],
    "_template": ["模板"],
    "闪念": ["闪念", "inbox"],
    "周志": ["周志", "日志"],
    "日志": ["日志"],
    "notes": ["笔记"],
}


def get_all_md_files():
    """获取所有 .md 文件"""
    files = []
    for root, dirs, filenames in os.walk(OBSIDIAN_ROOT):
        # 跳过隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in filenames:
            if f.endswith('.md'):
                files.append(os.path.join(root, f))
    return files


def read_frontmatter(filepath):
    """读取 YAML frontmatter"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.startswith('---'):
            return None, content
        match = re.match(r'^---\n(.*?)\n---\n?(.*)$', content, re.DOTALL)
        if not match:
            return None, content
        fm_text = match.group(1)
        body = match.group(2)
        # 简单解析
        fm = {}
        for line in fm_text.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                fm[key.strip()] = val.strip()
        return fm, body
    except Exception as e:
        return None, ""


def write_frontmatter(filepath, fm, body):
    """写入 YAML frontmatter"""
    fm_lines = ['---']
    for k, v in fm.items():
        if isinstance(v, list):
            fm_lines.append(f'{k}:')
            for item in v:
                fm_lines.append(f'  - "{item}"')
        else:
            fm_lines.append(f'{k}: "{v}"')
    fm_lines.append('---')
    new_content = '\n'.join(fm_lines) + '\n' + body
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


def add_link_to_body(body, link):
    """在正文末尾添加链接"""
    # 检查是否已有该链接
    link_text = link.replace('[[' , '').replace(']]', '')
    if link_text in body:
        return body
    # 在末尾添加
    if body.strip():
        return body.rstrip() + '\n\n' + link
    return link


def fix_isolated_notes():
    """修复孤立笔记：添加补链"""
    print("🔗 修复孤立笔记...")
    fixed = 0
    files = get_all_md_files()
    
    for filepath in files:
        rel_path = os.path.relpath(filepath, OBSIDIAN_ROOT)
        fm, body = read_frontmatter(filepath)
        if fm is None:
            continue
        
        # 检查是否有外部链接（入链）
        has_outgoing = bool(re.search(r'\[\[.+?\]\]', body))
        
        # 如果是孤立笔记，添加补链
        if not has_outgoing:
            for prefix, target_link in ISOLATED_LINK_RULES.items():
                if rel_path.startswith(prefix):
                    new_body = add_link_to_body(body, target_link)
                    if new_body != body:
                        write_frontmatter(filepath, fm, new_body)
                        print(f"  ✅ {rel_path} → {target_link}")
                        fixed += 1
                        break
    
    print(f"  完成：修复 {fixed} 篇孤立笔记")
    return fixed


def fix_missing_tags():
    """修复缺标签笔记"""
    print("\n🏷️ 修复缺标签笔记...")
    fixed = 0
    files = get_all_md_files()
    
    for filepath in files:
        rel_path = os.path.relpath(filepath, OBSIDIAN_ROOT)
        fm, body = read_frontmatter(filepath)
        if fm is None:
            continue
        
        # 检查是否有 tags
        tags = fm.get('tags', '')
        if not tags:
            # 根据文件名匹配规则
            filename = os.path.basename(filepath)
            suggested_tags = []
            
            for key, tag_list in TAG_FIX_RULES.items():
                if key in rel_path or key in filename:
                    suggested_tags.extend(tag_list)
            
            if suggested_tags:
                fm['tags'] = list(set(suggested_tags))
                write_frontmatter(filepath, fm, body)
                print(f"  ✅ {rel_path} → tags: {fm['tags']}")
                fixed += 1
    
    print(f"  完成：修复 {fixed} 篇缺标签笔记")
    return fixed


def merge_duplicate_cards():
    """输出近重复卡片合并建议"""
    print("\n📋 近重复卡片合并建议...")
    
    # 运行 dreaming --dry-run 获取数据
    import subprocess
    result = subprocess.run(
        ['python3', '/var/minis/shared/obsidian-dreaming.py', '--dry-run'],
        capture_output=True, text=True
    )
    
    # 解析输出中的近重复对
    lines = result.stdout.split('\n')
    duplicates = []
    current_pair = None
    
    for line in lines:
        if '[' in line and '↔' in line:
            if current_pair:
                duplicates.append(current_pair)
            current_pair = {'lines': [line]}
        elif current_pair and line.strip().startswith('['):
            current_pair['lines'].append(line)
    
    if current_pair:
        duplicates.append(current_pair)
    
    print(f"  发现 {len(duplicates)} 组近重复")
    for i, dup in enumerate(duplicates[:5]):
        print(f"  {i+1}. {''.join(dup['lines'][:1])[:80]}...")
    
    return len(duplicates)


def main():
    print("=" * 60)
    print("Obsidian 知识库 P0 修复")
    print(f"日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # 1. 修复孤立笔记
    fix_isolated_notes()
    
    # 2. 修复缺标签
    fix_missing_tags()
    
    # 3. 输出近重复建议
    merge_duplicate_cards()
    
    print("\n✅ P0 修复完成")
    print("\n下一步建议：")
    print("  1. 运行 obsidian-graph.py --stats 验证连通率")
    print("  2. 运行 obsidian-tag.py --audit 验证标签一致性")
    print("  3. 检查 Inbox 清理状态")


if __name__ == '__main__':
    main()
