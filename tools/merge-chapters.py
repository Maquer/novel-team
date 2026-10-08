#!/usr/bin/env python3
"""
merge-chapters.py — 合并章节工具（借鉴 MG_Obsidian_plugin Folder to TXT）

核心功能：
  1. 将文件夹中的md文件按顺序合并成一个txt
  2. 自动补章节标题
  3. 跳过YAML frontmatter
  4. 支持自定义输出格式

使用：
  python merge-chapters.py --input ./chapters --output novel.txt
  python merge-chapters.py --input ./chapters --output novel.epub --format epub
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class MergeChapters:
    """章节合并工具"""
    
    def __init__(self, input_dir: str, output_file: str, 
                 title_format: str = "第{chapter}章 {title}",
                 skip_frontmatter: bool = True):
        self.input_dir = Path(input_dir)
        self.output_file = Path(output_file)
        self.title_format = title_format
        self.skip_frontmatter = skip_frontmatter
        self.stats = {
            "files_processed": 0,
            "total_words": 0,
            "total_chapters": 0,
        }
    
    def find_chapters(self) -> List[Path]:
        """查找章节文件（按文件名排序）"""
        if not self.input_dir.is_dir():
            return []
        
        # 查找所有md文件
        files = list(self.input_dir.glob("*.md"))
        
        # 按文件名排序（支持第001章、001、chapter_1等格式）
        def sort_key(f):
            # 尝试提取数字
            match = re.search(r'(\d+)', f.stem)
            if match:
                return int(match.group(1))
            return f.stem
        
        return sorted(files, key=sort_key)
    
    def extract_title(self, content: str) -> str:
        """从内容中提取标题"""
        # 尝试从YAML frontmatter提取
        if 'title:' in content[:500]:
            match = re.search(r'title:\s*(.+)', content)
            if match:
                return match.group(1).strip()
        
        # 尝试从第一行提取
        lines = content.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('#'):
                return line.lstrip('#').strip()
            elif re.match(r'^第?\d+[章节回]', line):
                return line
        
        return "无标题"
    
    def extract_chapter_number(self, filename: str) -> int:
        """从文件名提取章节号"""
        match = re.search(r'(\d+)', filename)
        if match:
            return int(match.group(1))
        return 0
    
    def strip_frontmatter(self, content: str) -> str:
        """跳过YAML frontmatter"""
        if not self.skip_frontmatter:
            return content
        
        # 找到YAML结束标记
        lines = content.split('\n')
        result = []
        in_yaml = False
        yaml_end_found = False
        
        for line in lines:
            if line.strip() == '---':
                if not in_yaml:
                    in_yaml = True
                else:
                    in_yaml = False
                    yaml_end_found = True
                    continue
                continue
            
            if not in_yaml:
                result.append(line)
        
        return '\n'.join(result)
    
    def merge(self) -> Dict:
        """执行合并"""
        chapters = self.find_chapters()
        
        if not chapters:
            return {"error": "未找到章节文件"}
        
        output_lines = []
        chapter_count = 0
        
        for i, chapter_file in enumerate(chapters, 1):
            try:
                content = chapter_file.read_text(encoding='utf-8')
                
                # 提取标题
                title = self.extract_title(content)
                chapter_num = self.extract_chapter_number(chapter_file.stem)
                
                # 生成章节标题
                if chapter_num > 0:
                    chapter_title = self.title_format.format(chapter=chapter_num, title=title)
                else:
                    chapter_title = f"第{i}章 {title}"
                
                # 添加章节标题
                output_lines.append(f"\n{chapter_title}\n")
                output_lines.append("=" * 40)
                output_lines.append("")
                
                # 跳过frontmatter
                body = self.strip_frontmatter(content)
                
                # 添加正文
                output_lines.append(body)
                output_lines.append("")
                
                # 统计
                words = len(re.findall(r'[\u4e00-\u9fff]', body))
                self.stats["total_words"] += words
                chapter_count += 1
                
            except Exception as e:
                print(f"⚠️ 处理文件失败 {chapter_file.name}: {e}")
        
        self.stats["files_processed"] = len(chapters)
        self.stats["total_chapters"] = chapter_count
        
        # 写入输出
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text('\n'.join(output_lines), encoding='utf-8')
        
        return self.stats
    
    def print_stats(self):
        """打印统计信息"""
        print("\n=== 合并统计 ===\n")
        print(f"处理文件: {self.stats['files_processed']}")
        print(f"章节数量: {self.stats['total_chapters']}")
        print(f"总字数: {self.stats['total_words']:,}")
        print(f"\n输出文件: {self.output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="合并章节工具（借鉴MG_Obsidian_plugin）")
    parser.add_argument("--input", "-i", required=True, help="输入目录")
    parser.add_argument("--output", "-o", required=True, help="输出文件")
    parser.add_argument("--format", "-f", default="txt", choices=["txt", "md"], help="输出格式")
    parser.add_argument("--title-format", default="第{chapter}章 {title}", help="标题格式")
    parser.add_argument("--no-skip-frontmatter", action="store_true", help="保留YAML frontmatter")
    
    args = parser.parse_args()
    
    merger = MergeChapters(
        input_dir=args.input,
        output_file=args.output,
        title_format=args.title_format,
        skip_frontmatter=not args.no_skip_frontmatter,
    )
    
    stats = merger.merge()
    
    if "error" in stats:
        print(f"❌ {stats['error']}")
        return 1
    
    merger.print_stats()
    return 0


if __name__ == "__main__":
    sys.exit(main())
