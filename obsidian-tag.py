#!/usr/bin/env python3
# Version: 0.1.0
"""
自动标签提取 — 扫描 Obsidian 笔记，自动提取/建议标签，检测标签一致性。

用法:
    # 扫描指定文件，提取标签建议
    python3 obsidian-tag.py --scan "01-Projects/水果采购/水果采购.md"

    # 扫描整个目录，提取所有笔记的标签建议
    python3 obsidian-tag.py --scan-dir "01-Projects/水果采购"

    # 检查标签一致性（哪些笔记缺标签、标签是否合理）
    python3 obsidian-tag.py --audit

    # 批量添加标签到笔记
    python3 obsidian-tag.py --apply "01-Projects/水果采购/README.md"
"""

import argparse
import os
import re
import sys
import json
from pathlib import Path

OBSIDIAN_ROOT = "/var/minis/mounts/loong"

# ═══════════════════════════════════════════════════
# 标签提取规则
# ═══════════════════════════════════════════════════

# 已知有效的标签集合（从已有笔记中学习的）
KNOWN_TAGS = set()


def load_known_tags():
    """从已有笔记中收集已知标签。"""
    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        return

    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md'):
                continue
            try:
                content = open(os.path.join(dirpath, fname), 'r', encoding='utf-8', errors='replace').read()
            except (OSError, PermissionError):
                continue

            for tag in re.findall(r'#([\w\-/·]+)', content):
                KNOWN_TAGS.add(tag)


def extract_existing_tags(content: str) -> list:
    """从笔记中提取已存在的标签。"""
    # YAML front matter 中的 tags
    tags = set()
    in_front = False
    for line in content.split('\n'):
        if line.strip() == '---':
            in_front = not in_front
            continue
        if in_front:
            m = re.match(r'tags:\s*(.*)', line)
            if m:
                for tag in re.findall(r'#([\w\-/·]+)', m.group(1)):
                    tags.add(tag)
            elif line.strip().startswith('- '):
                m = re.match(r'\s*-\s*#?([\w\-/·]+)', line)
                if m:
                    tags.add(m.group(1))

    # 正文中的 #tag
    for tag in re.findall(r'#([\w\-/·]+)', content):
        tags.add(tag)

    return sorted(tags)


def suggest_tags(content: str, filename: str, folder: str) -> list:
    """基于内容、文件名和目录位置，建议标签。

    09-13 已知局限：
    - 正则 r'[\u4e00-\u9fff]{2,}' 无上限，整段中文标题可能被当 1 个标签
    - 正则 r'[\u4e00-\u9fff]{2,4}' 靠标点截断，可能产生碎片（"一套可落"/"地的优化"）
    - folder_tags 直接把 03-Resources → #资源，无区分度
    - 曾尝试用 jieba 分词 + 黑名单，但 jieba 有动词泛滥、专有名词拆错、英文组合拆开 3 个新问题
    - 结论：自动打标签不适合大规模 apply，只当辅助报告。iSH 环境已卸载 jieba。
    """
    suggestions = set()
    title = Path(filename).stem

    # 1) 从标题提取关键词
    # 去掉常见前缀
    title_clean = re.sub(r'^[\d\-\s]+', '', title)
    for word in re.findall(r'[\u4e00-\u9fff]{2,}', title_clean):
        if word and len(word) >= 2:
            suggestions.add(word)

    # 2) 从目录推断领域标签
    folder_tags = {
        "01-Projects": "项目",
        "02-Areas": "领域",
        "03-Resources": "资源",
        "04-Archives": "归档",
        "AI工具": "AI工具",
        "公众号文章": "公众号",
    }
    folder_parts = Path(folder).parts if folder else []
    for part in folder_parts:
        if part in folder_tags:
            suggestions.add(folder_tags[part])

    # 3) 从第一行内容/标题行提取
    first_content = ''
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# ') and not line.startswith('##'):
            first_content = line[2:]
            break
        elif line and not line.startswith('>') and not line.startswith('---'):
            first_content = line
            break

    if first_content:
        for word in re.findall(r'[\u4e00-\u9fff]{2,4}', first_content):
            suggestions.add(word)

    # 4) 去重：已有标签不打扰
    existing = set(extract_existing_tags(content))
    suggestions -= existing

    # 5) 过滤：保留已知标签或高频词
    if KNOWN_TAGS:
        filtered = suggestions & KNOWN_TAGS
        if filtered:
            return sorted(filtered)

    return sorted(suggestions)[:8]


def audit_tags() -> dict:
    """检查标签一致性：哪些笔记缺标签、标签是否规范。"""
    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        return {"error": "Obsidian 未挂载"}

    results = {
        "total_files": 0,
        "no_tags": [],
        "too_few_tags": [],
        "too_many_tags": [],
        "suggestions": [],
    }

    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md') or fname.startswith('.'):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            results["total_files"] += 1

            try:
                content = open(full, 'r', encoding='utf-8', errors='replace').read()
            except (OSError, PermissionError):
                continue

            tags = extract_existing_tags(content)
            if not tags:
                suggestions = suggest_tags(content, fname, os.path.relpath(dirpath, root))
                results["no_tags"].append({
                    "path": rel,
                    "suggested": suggestions,
                })
            elif len(tags) == 1 and len(tags[0]) <= 2:
                results["too_few_tags"].append({"path": rel, "tags": tags})

    results["no_tags"] = results["no_tags"][:30]  # 限制输出
    return results


def apply_tags(filepath: str):
    """将建议标签添加到笔记的 YAML front matter 中。"""
    full = os.path.join(OBSIDIAN_ROOT, filepath) if not os.path.isabs(filepath) else filepath
    filename = Path(filepath).name
    folder = str(Path(filepath).parent)

    try:
        content = open(full, 'r', encoding='utf-8', errors='replace').read()
    except (OSError, PermissionError) as e:
        print(f"❌ 无法读取: {e}")
        return

    existing_tags = extract_existing_tags(content)
    suggested = suggest_tags(content, filename, folder)
    new_tags = [t for t in suggested if t not in existing_tags]

    if not new_tags:
        print(f"✅ 无需修改: {filepath}（标签已完整）")
        return

    new_tag_str = " ".join(f"#{t}" for t in new_tags)

    lines = content.split('\n')

    # 检测是否有 front matter
    if len(lines) >= 2 and lines[0].strip() == '---':
        # 找到 front matter 结束位置
        fm_end = None
        for i in range(1, min(len(lines), 30)):
            if lines[i].strip() == '---':
                fm_end = i
                break

        if fm_end is None:
            # 找不到结束标记，回退到无 front matter 处理
            lines.insert(0, '---')
            lines.insert(1, f"tags: {new_tag_str}")
            lines.insert(2, '---')
            new_content = '\n'.join(lines)
        else:
            # 在 front matter 内查找 tags 行
            inserted = False
            insert_pos = None
            for i in range(1, fm_end):
                stripped = lines[i].strip()
                if stripped.startswith('tags:'):
                    # 已有 tags 行 — 追加而不是覆盖
                    if stripped.startswith('tags: ['):
                        # 列表格式: tags: [tag1, tag2]
                        lines[i] = f"{lines[i].rstrip()[:-1]}, #{new_tags[-1]}] " \
                                   + ' '.join(f"#{t}" for t in new_tags[:-1])
                    else:
                        # 空格分隔格式: tags: tag1 tag2
                        lines[i] = lines[i].rstrip() + f" {new_tag_str}"
                    inserted = True
                    break
                elif stripped == '':
                    # 记录空白行位置作为插入点
                    insert_pos = i

            if not inserted:
                # 在 front matter 末尾前插入
                lines.insert(fm_end, f"tags: {new_tag_str}")
                new_content = '\n'.join(lines)
                _write_backup_and_save(full, new_content, content, filepath, new_tag_str)
                return

            new_content = '\n'.join(lines)
            _write_backup_and_save(full, new_content, content, filepath, new_tag_str)
            return
    else:
        lines.insert(0, '---')
        lines.insert(1, f"tags: {new_tag_str}")
        lines.insert(2, '---')
        new_content = '\n'.join(lines)

    _write_backup_and_save(full, new_content, content, filepath, new_tag_str)


def _write_backup_and_save(full, new_content, old_content, filepath, tag_str):
    """备份后写入，返回成功标志。"""
    backup = full + '.bak'
    try:
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(old_content)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(new_content)
    except (OSError, PermissionError) as e:
        print(f"❌ 写入失败: {e}")
        return
    print(f"✅ 已添加标签 {tag_str} → {filepath}（备份: {backup}）")


def main():
    parser = argparse.ArgumentParser(description='Obsidian 自动标签提取')
    parser.add_argument('--scan', help='扫描单个文件，提取标签建议')
    parser.add_argument('--scan-dir', help='扫描整个目录')
    parser.add_argument('--audit', '-a', action='store_true', help='检查标签一致性')
    parser.add_argument('--apply', help='将建议标签应用到指定文件')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')

    args = parser.parse_args()

    load_known_tags()

    if args.scan:
        filepath = args.scan
        if not os.path.isabs(filepath):
            filepath = os.path.join(OBSIDIAN_ROOT, filepath)
        filename = Path(args.scan).name
        folder = str(Path(args.scan).parent)
        try:
            content = open(filepath, 'r', encoding='utf-8', errors='replace').read()
        except (OSError, PermissionError) as e:
            print(f"❌ {e}")
            sys.exit(1)

        existing = extract_existing_tags(content)
        suggested = suggest_tags(content, filename, folder)

        if args.json:
            print(json.dumps({"existing": existing, "suggested": suggested}, ensure_ascii=False, indent=2))
        else:
            print(f"📄 {args.scan}")
            print(f"  现有标签: {existing}")
            print(f"  建议标签: {suggested}")
        sys.exit(0)

    if args.scan_dir:
        dirpath = os.path.join(OBSIDIAN_ROOT, args.scan_dir)
        if not os.path.exists(dirpath):
            print(f"❌ 目录不存在: {dirpath}")
            sys.exit(1)

        results = {}
        for f in sorted(os.listdir(dirpath)):
            if f.endswith('.md'):
                fp = os.path.join(dirpath, f)
                try:
                    content = open(fp, 'r', encoding='utf-8', errors='replace').read()
                    existing = extract_existing_tags(content)
                    suggested = suggest_tags(content, f, args.scan_dir)
                    if existing or suggested:
                        results[f] = {"existing": existing, "suggested": suggested}
                except (OSError, PermissionError):
                    continue

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for fname, info in results.items():
                print(f"📄 {fname}")
                if info['existing']:
                    print(f"  现有: {', '.join(info['existing'])}")
                if info['suggested']:
                    print(f"  建议: {', '.join(info['suggested'])}")
                print()
        sys.exit(0)

    if args.audit:
        results = audit_tags()
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"🔍 标签一致性检查\n")
            print(f"  总笔记: {results['total_files']} 篇")
            print(f"  缺标签: {len(results['no_tags'])} 篇")
            for item in results['no_tags'][:10]:
                suggestions = ', '.join(item['suggested'][:5]) if item['suggested'] else '（无法建议）'
                print(f"    📄 {item['path']}")
                print(f"       建议: {suggestions}")
        sys.exit(0)

    if args.apply:
        apply_tags(args.apply)
        sys.exit(0)

    parser.print_help()


if __name__ == '__main__':
    main()