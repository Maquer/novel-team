#!/usr/bin/env python3
"""
Markdown→HTML 双备份同步器

借鉴 ai-fiction-writer 的双备份机制：
  .md 供人编辑（Source of Truth）
  .html 供 AI 消费（自动同步）

用法：
  python3 md-to-html-sync.py sync --novel-id my-novel --file chapter.md
  python3 md-to-html-sync.py sync-all --novel-id my-novel
  python3 md-to-html-sync.py watch --novel-id my-novel --dir chapters/
"""

import re
import sys
import json
import html as html_module
from pathlib import Path
from typing import Dict, List, Optional

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve

WORLD_DIR = Path("/var/minis/shared/novel-team/.md-sync")


def extract_frontmatter(text: str) -> tuple:
    """提取 YAML frontmatter 并返回 (metadata_dict, body_text)"""
    metadata = {}
    body = text

    # 检测 YAML frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if match:
        fm_text = match.group(1)
        body = text[match.end():]
        # 解析简单 YAML（不支持复杂嵌套）
        for line in fm_text.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                metadata[key] = val

    return metadata, body


def md_to_html(text: str) -> str:
    """将 Markdown 转换为 HTML（简化版）"""
    lines = text.split('\n')
    html_lines = []
    in_code_block = False
    in_list = False
    list_type = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.startswith('```'):
            if not in_code_block:
                in_code_block = True
                html_lines.append('<pre><code>')
            else:
                in_code_block = False
                html_lines.append('</code></pre>')
            i += 1
            continue

        if in_code_block:
            html_lines.append(html_module.escape(line))
            i += 1
            continue

        # 标题
        if line.startswith('# '):
            html_lines.append(f'<h1>{html_module.escape(line[2:].strip())}</h1>')
            i += 1
            continue
        if line.startswith('## '):
            html_lines.append(f'<h2>{html_module.escape(line[3:].strip())}</h2>')
            i += 1
            continue
        if line.startswith('### '):
            html_lines.append(f'<h3>{html_module.escape(line[4:].strip())}</h3>')
            i += 1
            continue
        if line.startswith('#### '):
            html_lines.append(f'<h4>{html_module.escape(line[5:].strip())}</h4>')
            i += 1
            continue

        # 分隔线
        if re.match(r'^[-*_]{3,}$', line.strip()):
            html_lines.append('<hr>')
            i += 1
            continue

        # 列表
        if re.match(r'^[\-\*]\s+', line):
            if not in_list:
                in_list = True
                list_type = 'ul'
                html_lines.append('<ul>')
            html_lines.append(f'<li>{_inline_md(line.lstrip('- ').lstrip('* '))}</li>')
            i += 1
            continue
        if re.match(r'^\d+\.\s+', line):
            if not in_list or list_type != 'ol':
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                in_list = True
                list_type = 'ol'
                html_lines.append('<ol>')
            content = re.sub(r'^\d+\.\s+', '', line)
            html_lines.append(f'<li>{_inline_md(content)}</li>')
            i += 1
            continue
        elif in_list:
            html_lines.append(f'</{list_type}>')
            in_list = False
            list_type = None

        # 空行
        if line.strip() == '':
            if in_list:
                html_lines.append(f'</{list_type}>')
                in_list = False
            html_lines.append('')
            i += 1
            continue

        # 普通段落
        html_lines.append(f'<p>{_inline_md(line)}</p>')
        i += 1

    if in_list:
        html_lines.append(f'</{list_type}>')

    return '\n'.join(html_lines)


def _inline_md(text: str) -> str:
    """处理行内 Markdown 格式"""
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # 行内代码
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # 链接
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    # 转义 HTML 特殊字符（保留上面已处理的）
    text = html_module.escape(text)
    # 还原已处理的标签
    text = text.replace('&lt;strong&gt;', '<strong>')
    text = text.replace('&lt;/strong&gt;', '</strong>')
    text = text.replace('&lt;em&gt;', '<em>')
    text = text.replace('&lt;/em&gt;', '</em>')
    text = text.replace('&lt;code&gt;', '<code>')
    text = text.replace('&lt;/code&gt;', '</code>')
    text = text.replace('&lt;a href=', '<a href=')
    text = text.replace('&lt;/a&gt;', '</a>')
    return text


def generate_html(metadata: Dict, body_html: str, source_file: str) -> str:
    """生成完整的 HTML 页面"""
    title = metadata.get('title', Path(source_file).stem)
    author = metadata.get('author', '未知作者')
    date = metadata.get('date', '')

    # 将 YAML frontmatter 作为注释保留在 HTML 中（供 AI 消费）
    yaml_comment = '<!-- YAML\n'
    for k, v in metadata.items():
        yaml_comment += f'  {k}: {v}\n'
    yaml_comment += '-->\n'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_module.escape(title)}</title>
  <style>
    body {{ font-family: "Noto Serif SC", "Source Han Serif", Georgia, serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.8; color: #333; }}
    h1 {{ font-size: 1.8em; border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
    h2 {{ font-size: 1.4em; margin-top: 2em; }}
    h3 {{ font-size: 1.2em; margin-top: 1.5em; }}
    p {{ margin: 1em 0; text-indent: 2em; }}
    pre {{ background: #f5f5f5; padding: 1em; overflow-x: auto; }}
    code {{ background: #f0f0f0; padding: 0.1em 0.3em; }}
    blockquote {{ border-left: 4px solid #ccc; margin: 1em 0; padding-left: 1em; color: #666; }}
    hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
    ul, ol {{ margin: 1em 0; padding-left: 2em; }}
    li {{ margin: 0.3em 0; }}
  </style>
</head>
<body>
{yaml_comment}
<h1>{html_module.escape(title)}</h1>
<p><em>作者：{html_module.escape(author)}</em>{f' · <time>{date}</time>' if date else ''}</p>
<hr>
{body_html}
</body>
</html>'''


class MarkdownSync:
    """Markdown↔HTML 双备份同步器"""

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.cache_dir = WORLD_DIR / novel_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def sync_file(self, md_path: str, output_dir: Optional[str] = None) -> Dict:
        """同步单个文件"""
        src = Path(md_path)
        if not src.exists():
            return {"status": "error", "message": f"文件不存在：{md_path}"}

        # 读取并解析
        raw_text = src.read_text(encoding='utf-8')
        metadata, body = extract_frontmatter(raw_text)

        # 生成 HTML
        body_html = md_to_html(body)
        html_content = generate_html(metadata, body_html, str(src))

        # 确定输出路径
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.cache_dir / "html"
        out_dir.mkdir(parents=True, exist_ok=True)

        html_path = out_dir / (src.stem + '.html')
        tmp = html_path.with_suffix('.tmp')
        tmp.write_text(html_content, encoding='utf-8')
        tmp.replace(html_path)

        # 记录同步日志
        log_path = self.cache_dir / "sync-log.json"
        log = []
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                log = []
        log.append({
            "file": str(src),
            "output": str(html_path),
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "word_count": len(body.replace('\n', '')),
            "metadata_keys": list(metadata.keys()),
        })
        tmp_log = log_path.with_suffix('.tmp')
        tmp_log.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp_log.replace(log_path)

        return {
            "status": "ok",
            "source": str(src),
            "output": str(html_path),
            "word_count": len(body.replace('\n', '')),
            "metadata": metadata,
        }

    def sync_all(self, root_dir: Optional[str] = None) -> List[Dict]:
        """同步目录下所有 .md 文件"""
        if root_dir is None:
            root_dir = str(resolve(self.novel_id).chapters())

        root = Path(root_dir)
        if not root.exists():
            return [{"status": "error", "message": f"目录不存在：{root_dir}"}]

        results = []
        for md_file in sorted(root.rglob("*.md")):
            # 跳过子目录中的特殊文件
            if md_file.name.startswith('.'):
                continue
            result = self.sync_file(str(md_file))
            results.append(result)

        return results


def main():
    import argparse
    import json
    import datetime

    parser = argparse.ArgumentParser(description='Markdown→HTML 双备份同步器')
    subparsers = parser.add_subparsers(dest="command")

    # sync 命令
    p_sync = subparsers.add_parser("sync", help="同步单个文件")
    p_sync.add_argument("--novel-id", required=True)
    p_sync.add_argument("--file", "-f", required=True, help="Markdown 文件路径")
    p_sync.add_argument("--output-dir", "-o", help="输出目录")

    # sync-all 命令
    p_all = subparsers.add_parser("sync-all", help="同步目录下所有文件")
    p_all.add_argument("--novel-id", required=True)
    p_all.add_argument("--dir", "-d", help="根目录（默认 projects/<novel-id>/chapters）")
    p_all.add_argument("--json", action="store_true", help="JSON 输出")

    # status 命令
    p_status = subparsers.add_parser("status", help="同步状态")
    p_status.add_argument("--novel-id", required=True)
    p_status.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    syncer = MarkdownSync(args.novel_id)

    if args.command == "sync":
        result = syncer.sync_file(args.file, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "sync-all":
        results = syncer.sync_all(args.dir)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            ok = sum(1 for r in results if r.get("status") == "ok")
            err = sum(1 for r in results if r.get("status") == "error")
            print(f"同步完成：{ok} 成功，{err} 失败")
            for r in results:
                if r.get("status") == "ok":
                    print(f"  ✅ {r['source']} → {r['output']}")

    elif args.command == "status":
        log_path = syncer.cache_dir / "sync-log.json"
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text(encoding='utf-8'))
                print(f"最近 {len(log)} 次同步记录：")
                for entry in log[-10:]:
                    print(f"  {entry['timestamp'][:16]} | {Path(entry['file']).name} | {entry['word_count']}字")
            except json.JSONDecodeError:
                print("日志文件格式错误")
        else:
            print("暂无同步记录")


if __name__ == "__main__":
    main()
