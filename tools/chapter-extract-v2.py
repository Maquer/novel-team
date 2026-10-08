#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter-extract-v2.py — 增强版章节提取器

从 .txt 文件提取章节列表，支持全文扫描。

用法：
    python3 chapter-extract-v2.py --input "我的公公叫康熙.txt" --output research/chapters-full.json
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List


@dataclass
class Chapter:
    number: int
    title: str
    line_start: int
    line_end: int
    word_count: int = 0


def extract_chapters(text: str) -> List[Chapter]:
    lines = text.split('\n')
    chapters = []

    # 匹配章节标题模式（支持各种格式）
    patterns = [
        r'^第[一二三四五六七八九十百千零0-9]+章\s+[^\n]+',  # 第X章 标题
        r'^第[一二三四五六七八九十百千零0-9]+章[：:]\s*[^\n]+',  # 第X章：标题
        r'^第[一二三四五六七八九十百千零0-9]+章\s*$',  # 第X章（无标题）
    ]

    chapter_starts = []
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                # 提取章节号和标题
                match = re.match(r'第([一二三四五六七八九十百千零0-9]+)章\s*[：:]?\s*(.+)?', line.strip())
                if match:
                    num_str = match.group(1)
                    title = match.group(2) if match.group(2) else ""
                    # 清理标题（去掉求票等后缀）
                    title = re.sub(r'[（(].*[)）]$', '', title).strip()
                    chapter_starts.append({
                        'line': i,
                        'num': len(chapter_starts) + 1,
                        'title': title or f"第{num_str}章"
                    })
                break

    # 构建章节列表
    for idx, ch_info in enumerate(chapter_starts):
        start_line = ch_info['line']
        end_line = chapter_starts[idx + 1]['line'] if idx + 1 < len(chapter_starts) else len(lines)

        # 计算字数
        chapter_text = '\n'.join(lines[start_line:end_line])
        word_count = len(re.sub(r'\s+', '', chapter_text))

        chapters.append(Chapter(
            number=ch_info['num'],
            title=ch_info['title'],
            line_start=start_line,
            line_end=end_line,
            word_count=word_count
        ))

    return chapters


def main():
    parser = argparse.ArgumentParser(description="小说章节提取器 v2")
    parser.add_argument("--input", "-i", required=True, help="输入文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"读取文件：{input_path}")
    text = input_path.read_text(encoding='utf-8', errors='replace')
    print(f"文件大小：{len(text):,} 字符")

    chapters = extract_chapters(text)
    print(f"提取章节：{len(chapters)} 章")

    # 统计
    total_words = sum(c.word_count for c in chapters)
    avg_words = total_words / len(chapters) if chapters else 0
    min_words = min(c.word_count for c in chapters) if chapters else 0
    max_words = max(c.word_count for c in chapters) if chapters else 0

    output_data = {
        "source": str(input_path),
        "total_chapters": len(chapters),
        "total_words": total_words,
        "avg_words_per_chapter": round(avg_words, 1),
        "min_words": min_words,
        "max_words": max_words,
        "chapters": [asdict(c) for c in chapters]
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n统计摘要：")
    print(f"  总字数：{total_words:,}")
    print(f"  平均每章：{avg_words:.1f} 字")
    print(f"  最短章：{min_words} 字")
    print(f"  最长章：{max_words} 字")
    print(f"\n已保存到 {output_path}")


if __name__ == "__main__":
    main()
