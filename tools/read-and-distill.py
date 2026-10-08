#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
read-and-distill.py — 自动拆书工具

扫描 Obsidian 中的小说文件，提取核心模式并入库。

用法：
    python3 read-and-distill.py --dir /var/minis/mounts/loong --output research/novel-index.json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 让 novelkit 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from novelkit.core import log


@dataclass
class BookInfo:
    """书籍元数据"""
    title: str
    path: str
    size_bytes: int
    line_count: int
    chapter_count: int = 0
    word_count: int = 0
    first_line: str = ""
    last_line: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "unanalyzed"  # unanalyzed | analyzed
    analysis_date: Optional[str] = None
    patterns: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def scan_novels(root_dir: str) -> List[BookInfo]:
    """扫描目录下的小说文件"""
    root = Path(root_dir)
    books = []

    for filepath in root.rglob("*.txt"):
        if filepath.name.startswith('.'):
            continue

        # 检查是否可能是小说（简单启发式）
        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')

            # 简单判断：如果有"第X章"标记，认为是小说
            has_chapter = bool(re.search(r'第[一二三四五六七八九十百千0-9]+章', content))

            if not has_chapter:
                continue

            # 提取章节数
            chapters = re.findall(r'第[一二三四五六七八九十百千0-9]+章', content)
            chapter_count = len(chapters)

            # 提取书名（文件名去掉扩展名）
            title = filepath.stem

            # 获取文件信息
            book = BookInfo(
                title=title,
                path=str(filepath.relative_to(root)),
                size_bytes=filepath.stat().st_size,
                line_count=len(lines),
                chapter_count=chapter_count,
                word_count=len(content.replace('\n', '').replace(' ', '')),
                first_line=lines[0].strip() if lines else "",
                last_line=lines[-1].strip() if lines else "",
                tags=["清穿", "宫廷"] if "康熙" in title.lower() else ["小说"],
            )
            books.append(book)

        except Exception as e:
            log.warn(f"读取失败 {filepath}: {e}")

    return books


def extract_patterns(book: BookInfo, sample_size: int = 50000) -> List[str]:
    """从小说中提取核心模式（简化版）"""
    patterns = []

    try:
        filepath = Path("/var/minis/mounts/loong") / book.path
        content = filepath.read_text(encoding='utf-8', errors='replace')

        # 提取开篇特征
        first_section = content[:sample_size]

        # 识别开篇钩子类型
        if '穿越' in first_section or '两世' in first_section:
            patterns.append("穿越设定")
        if '系统' in first_section:
            patterns.append("系统流")
        if '重生' in first_section:
            patterns.append("重生流")

        # 识别题材
        if any(x in first_section for x in ['康熙', '阿哥', '格格', '旗', '八旗']):
            patterns.append("清穿宫廷")
        if any(x in first_section for x in ['修炼', '境界', '丹田', '灵气']):
            patterns.append("修仙")
        if any(x in first_section for x in ['玄幻', '大陆', '武魂']):
            patterns.append("玄幻")

        # 识别叙事风格（简化）
        if '我' in first_section[:1000] and first_section.count('我') > 20:
            patterns.append("第一人称倾向")

        # 提取章节标题模式
        chapters = re.findall(r'(第[一二三四五六七八九十百千0-9]+章\s+[^\n]+)', content)
        if chapters:
            patterns.append(f"章节结构：{len(chapters)}章")
            # 统计标题长度分布
            title_lengths = [len(c) for c in chapters[:50]]
            if title_lengths:
                avg_len = sum(title_lengths) / len(title_lengths)
                if avg_len > 10:
                    patterns.append("长标题风格")
                else:
                    patterns.append("短标题风格")

    except Exception as e:
        log.warn(f"提取模式失败 {book.title}: {e}")

    return patterns


def distill_book(book: BookInfo) -> BookInfo:
    """对单本书进行拆解分析"""
    log.info(f"拆解中：{book.title}")

    # 提取模式
    book.patterns = extract_patterns(book)
    book.status = "analyzed"
    book.analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return book


def main():
    parser = argparse.ArgumentParser(description="自动拆书工具")
    parser.add_argument("--dir", default="/var/minis/mounts/loong",
                        help="Obsidian 知识库目录")
    parser.add_argument("--output", default="research/novel-index.json",
                        help="输出文件路径")
    parser.add_argument("--batch", action="store_true",
                        help="批量分析所有小说")
    args = parser.parse_args()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent.parent / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 扫描小说
    log.info(f"扫描目录：{args.dir}")
    books = scan_novels(args.dir)
    log.info(f"找到 {len(books)} 本小说")

    # 批量分析
    if args.batch or len(books) > 0:
        analyzed = []
        for book in books:
            analyzed.append(distill_book(book))

        # 保存索引
        index = {
            "generated_at": datetime.now().isoformat(),
            "total_books": len(analyzed),
            "books": [b.to_dict() for b in analyzed],
            "summary": {
                "total_chapters": sum(b.chapter_count for b in analyzed),
                "total_words": sum(b.word_count for b in analyzed),
                "genres": list(set(p for b in analyzed for p in b.patterns if "清穿" in p or "宫廷" in p or "修仙" in p or "玄幻" in p)),
            }
        }

        output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        log.info(f"已保存到 {output_path}")
        print(json.dumps(index, ensure_ascii=False, indent=2))
    else:
        log.info("未找到小说文件")
        print(json.dumps({"books": [], "message": "No novels found"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
