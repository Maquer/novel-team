#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter-extract.py — 小说章节提取器

从 .txt 文件提取章节列表，输出为 JSON 或 Markdown。

用法：
    python3 chapter-extract.py --input "我的公公叫康熙.txt" --output research/chapters.json
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Chapter:
    """章节信息"""
    number: int
    title: str
    line_start: int
    line_end: int
    word_count: int = 0
    preview: str = ""


def extract_chapters(text: str) -> List[Chapter]:
    """从文本中提取章节列表"""
    lines = text.split('\n')
    chapters = []

    # 匹配章节标题模式
    pattern = re.compile(r'^第[一二三四五六七八九十百千0-9]+章\s+[^\n]+$')

    current_chapter = None
    for i, line in enumerate(lines):
        line = line.strip()
        if pattern.match(line):
            # 保存上一章
            if current_chapter:
                current_chapter.line_end = i
                current_chapter.word_count = len(current_chapter.preview.replace('\n', ''))
                chapters.append(current_chapter)

            # 开始新章节
            match = re.match(r'第([一二三四五六七八九十百千0-9]+)章\s+(.+)', line)
            if match:
                num_str = match.group(1)
                title = match.group(2).strip()
                current_chapter = Chapter(
                    number=i,  # 先用行号占位
                    title=title,
                    line_start=i,
                    line_end=i,
                    preview=line[:100]
                )

    # 保存最后一章
    if current_chapter:
        current_chapter.line_end = len(lines)
        current_chapter.word_count = len(current_chapter.preview.replace('\n', ''))
        chapters.append(current_chapter)

    # 重新编号
    for idx, ch in enumerate(chapters, 1):
        ch.number = idx

    return chapters


def main():
    parser = argparse.ArgumentParser(description="小说章节提取器")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--format", "-f", default="json", choices=["json", "markdown"],
                        help="输出格式")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}", file=sys.stderr)
        sys.exit(1)

    # 读取文件
    text = input_path.read_text(encoding='utf-8', errors='replace')

    # 提取章节
    chapters = extract_chapters(text)

    # 输出
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        data = {
            "source": str(input_path),
            "total_chapters": len(chapters),
            "chapters": [asdict(c) for c in chapters[:100]]  # 只输出前100章预览
        }
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        lines = [f"# 《{input_path.stem}》章节列表\n\n"]
        for ch in chapters[:100]:
            lines.append(f"**第{ch.number}章** {ch.title}\n")
        output_path.write_text('\n'.join(lines), encoding='utf-8')

    print(f"已提取 {len(chapters)} 章，保存到 {output_path}")
    print(json.dumps({"total": len(chapters), "sample": [asdict(c) for c in chapters[:5]]},
                      ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
