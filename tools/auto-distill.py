#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto-distill.py — 自动拆书入库工具

完整流程：扫描 → 提取章节 → 节奏分析 → 生成报告 → 入库索引

用法：
    python3 auto-distill.py --dir /var/minis/mounts/loong
"""

import argparse
import json
import os
import re
import sys
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class DistillResult:
    novel_title: str
    source_file: str
    status: str  # success | failed
    chapters_extracted: int
    total_words: int
    avg_words_per_chapter: float
    rhythm_pattern: str
    patterns: List[str]
    recommendations: List[str]
    output_files: List[str]
    error: Optional[str] = None


def run_command(cmd: List[str]) -> tuple:
    """运行命令并返回 (stdout, stderr, returncode)"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "命令超时", 1
    except Exception as e:
        return "", str(e), 1


def distill_novel(book_path: Path, output_dir: Path) -> DistillResult:
    """对单本小说进行拆书分析"""
    novel_title = book_path.stem
    print(f"\n{'='*60}")
    print(f"开始拆解：{novel_title}")
    print(f"{'='*60}")

    result = DistillResult(
        novel_title=novel_title,
        source_file=str(book_path),
        status="success",
        chapters_extracted=0,
        total_words=0,
        avg_words_per_chapter=0,
        rhythm_pattern="",
        patterns=[],
        recommendations=[],
        output_files=[],
    )

    try:
        # 步骤1：提取章节
        chapters_json = output_dir / f"{novel_title}_chapters.json"
        cmd1 = [
            sys.executable, str(Path(__file__).parent / "chapter-extract-v2.py"),
            "--input", str(book_path),
            "--output", str(chapters_json)
        ]
        stdout, stderr, rc = run_command(cmd1)
        if rc != 0:
            result.status = "failed"
            result.error = f"章节提取失败: {stderr}"
            return result

        result.output_files.append(str(chapters_json))

        # 解析章节数据
        chapters_data = json.loads(chapters_json.read_text(encoding='utf-8'))
        result.chapters_extracted = chapters_data.get("total_chapters", 0)
        result.total_words = chapters_data.get("total_words", 0)
        result.avg_words_per_chapter = chapters_data.get("avg_words_per_chapter", 0)

        # 步骤2：节奏分析
        rhythm_json = output_dir / f"{novel_title}_rhythm.json"
        cmd2 = [
            sys.executable, str(Path(__file__).parent / "novel-rhythm-analyzer.py"),
            "--novel", novel_title,
            "--input", str(chapters_json),
            "--output", str(rhythm_json)
        ]
        stdout, stderr, rc = run_command(cmd2)
        if rc == 0 and rhythm_json.exists():
            result.output_files.append(str(rhythm_json))

            # 读取节奏分析结果
            rhythm_data = json.loads(rhythm_json.read_text(encoding='utf-8'))
            result.rhythm_pattern = "中长章节风格" if result.avg_words_per_chapter > 2500 else "标准章节风格"
            result.patterns = [p["name"] for p in rhythm_data.get("patterns", [])]
            result.recommendations = rhythm_data.get("recommendations", [])

        # 步骤3：生成摘要报告
        report_md = output_dir / f"{novel_title}_分析.md"
        report_lines = [
            f"# 《{novel_title}》拆书报告",
            f"",
            f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 基本信息",
            f"",
            f"- **总章节数**：{result.chapters_extracted:,}",
            f"- **总字数**：{result.total_words:,}",
            f"- **平均每章**：{result.avg_words_per_chapter:.1f}字",
            f"- **风格判断**：{result.rhythm_pattern}",
            f"",
            f"## 识别模式",
            f"",
        ]
        for p in result.patterns:
            report_lines.append(f"- {p}")
        report_lines.append("")
        report_lines.append("## 建议")
        report_lines.append("")
        for r in result.recommendations:
            report_lines.append(f"- {r}")
        report_lines.append("")
        report_lines.append("## 输出文件")
        report_lines.append("")
        for f in result.output_files:
            report_lines.append(f"- [{Path(f).name}]({f})")

        report_md.write_text('\n'.join(report_lines), encoding='utf-8')
        result.output_files.append(str(report_md))

        print(f"✓ 完成：{result.chapters_extracted:,}章，{result.total_words:,}字")

    except Exception as e:
        result.status = "failed"
        result.error = str(e)
        print(f"✗ 失败：{e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="自动拆书入库工具")
    parser.add_argument("--dir", "-d", default="/var/minis/mounts/loong",
                        help="Obsidian 知识库目录")
    parser.add_argument("--output", "-o", default="research/distill-output",
                        help="输出目录")
    parser.add_argument("--index", default="research/novel-index-v2.json",
                        help="索引文件路径")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = Path(args.index)
    if not index_path.is_absolute():
        index_path = Path(__file__).resolve().parent.parent / index_path

    # 扫描小说
    root = Path(args.dir)
    novels = list(root.rglob("*.txt"))
    novels = [n for n in novels if not n.name.startswith('.')]

    print(f"找到 {len(novels)} 本小说")

    # 批量拆解
    all_results = []
    for novel_path in novels:
        result = distill_novel(novel_path, output_dir)
        all_results.append({
            **asdict(result),
            "analysis_date": datetime.now().isoformat()
        })

        if result.status == "failed":
            print(f"  ⚠ {result.error}")

    # 保存索引
    index_data = {
        "generated_at": datetime.now().isoformat(),
        "total_novels": len(all_results),
        "successful": sum(1 for r in all_results if r["status"] == "success"),
        "failed": sum(1 for r in all_results if r["status"] == "failed"),
        "novels": all_results,
        "summary": {
            "total_chapters": sum(r["chapters_extracted"] for r in all_results),
            "total_words": sum(r["total_words"] for r in all_results),
        }
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n{'='*60}")
    print(f"批量拆解完成")
    print(f"  - 成功：{index_data['successful']} 本")
    print(f"  - 失败：{index_data['failed']} 本")
    print(f"  - 总章节：{index_data['summary']['total_chapters']:,}")
    print(f"  - 总字数：{index_data['summary']['total_words']:,}")
    print(f"  - 索引保存到：{index_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
