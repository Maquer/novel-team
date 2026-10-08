#!/usr/bin/env python3
"""
outline-dynamic-adjust.py — 大纲动态调整工具

功能：
  1. 根据已写章节的实际长度，动态调整后续卷的章节数
  2. 根据情节密度自动拆分/合并章节
  3. 根据创作进度重新规划剩余卷

使用：
  # 分析当前进度，生成调整建议
  python3 tools/outline-dynamic-adjust.py analyze --project helper-creator

  # 应用调整建议
  python3 tools/outline-dynamic-adjust.py apply --project helper-creator

  # 查看当前大纲状态
  python3 tools/outline-dynamic-adjust.py status --project helper-creator
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


BASE_DIR = Path("/var/minis/shared/novel-team")
WORKSPACE_DIR = Path("/var/minis/workspace")


def get_project_dirs(project_id: str) -> Dict[str, Path]:
    """解析项目路径"""
    new_path = BASE_DIR / "novel-team" / "projects" / project_id
    old_path = BASE_DIR / "projects" / project_id

    if new_path.exists():
        return {
            "root": new_path,
            "world": new_path / "world",
            "outline": new_path / "outline",
            "chapters": new_path / "chapters",
        }
    elif old_path.exists():
        return {
            "root": old_path,
            "world": old_path / "world",
            "outline": old_path / "outline",
            "chapters": old_path / "chapters",
        }
    else:
        print(f"❌ 项目 '{project_id}' 不存在", file=sys.stderr)
        sys.exit(1)


def count_words(text: str) -> int:
    """统计中文字符数"""
    # 匹配中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def load_outline(project_dirs: Dict) -> Optional[Dict]:
    """加载大纲文件"""
    outline_path = project_dirs["outline"] / "vol-001-brief.yaml"
    if not outline_path.exists():
        return None

    content = outline_path.read_text(encoding="utf-8")

    # 简单解析五卷结构
    volumes = {}
    current_vol = None

    for line in content.split("\n"):
        # 匹配卷标题
        vol_match = re.match(r"### 第([一二三四五六七八九十]+)卷：(.+)", line)
        if vol_match:
            vol_num = vol_match.group(1)
            vol_title = vol_match.group(2).strip()
            current_vol = {"num": vol_num, "title": vol_title, "chapters": []}
            volumes[len(volumes) + 1] = current_vol
            continue

        # 匹配章节范围
        if current_vol and "章" in line and "—" in line:
            ch_match = re.search(r"Ch(\d+)-(\d+)", line)
            if ch_match:
                start, end = int(ch_match.group(1)), int(ch_match.group(2))
                current_vol["chapter_range"] = (start, end)
                current_vol["chapter_count"] = end - start + 1

    return {"volumes": volumes, "raw": content}


def analyze_chapters(project_dirs: Dict) -> Dict:
    """分析已写章节的实际长度"""
    chapters_dir = project_dirs["chapters"]
    if not chapters_dir.exists():
        return {"chapters": [], "total_words": 0}

    chapters = []
    total_words = 0

    for ch_file in sorted(chapters_dir.glob("ch*.md")):
        content = ch_file.read_text(encoding="utf-8")
        words = count_words(content)
        total_words += words

        # 提取章节号
        ch_num_match = re.search(r"ch(\d+)", ch_file.name)
        ch_num = int(ch_num_match.group(1)) if ch_num_match else 0

        chapters.append({
            "file": ch_file.name,
            "number": ch_num,
            "words": words,
        })

    return {
        "chapters": chapters,
        "total_words": total_words,
        "chapter_count": len(chapters),
    }


def generate_adjustment_recommendation(
    outline: Dict,
    chapter_analysis: Dict,
) -> Dict:
    """生成动态调整建议"""
    target_words = 1000000  # 目标字数
    target_chapters = target_words // 2500  # 目标章节数（按每章2500字）

    current_chapters = chapter_analysis["chapter_count"]
    current_words = chapter_analysis["total_words"]
    avg_words_per_chapter = current_words / max(current_chapters, 1)

    # 计算剩余
    remaining_words = target_words - current_words
    remaining_chapters = max(0, (remaining_words // int(avg_words_per_chapter)))

    # 分析当前各卷进度
    volumes = outline.get("volumes", {})
    recommendations = []

    for vol_num, vol_data in volumes.items():
        vol_title = vol_data.get("title", f"第{vol_num}卷")
        ch_range = vol_data.get("chapter_range", (0, 0))
        planned_start, planned_end = ch_range
        planned_count = planned_end - planned_start + 1

        # 已完成的章节
        completed_in_vol = sum(
            1 for ch in chapter_analysis["chapters"]
            if planned_start <= ch["number"] <= planned_end
        )

        # 进度判断
        progress = completed_in_vol / max(planned_count, 1)
        status = "✅ 已完成" if progress >= 1.0 else "🔄 进行中" if progress > 0 else "⏳ 未开始"

        # 如果当前卷已完成，建议下一卷
        if progress >= 1.0 and vol_num < max(volumes.keys()):
            next_vol = volumes.get(vol_num + 1, {})
            next_title = next_vol.get("title", f"第{vol_num + 1}卷")
            recommendations.append({
                "type": "volume_complete",
                "message": f"第{vol_num}卷《{vol_title}》已完成，准备进入第{vol_num + 1}卷《{next_title}》",
                "priority": "high",
            })

        # 如果进度超快或超慢，建议调整
        if progress > 1.5:
            recommendations.append({
                "type": "volume_fast",
                "message": f"第{vol_num}卷《{vol_title}》进度超快（{progress:.0%}），可能需要拆分或扩充",
                "priority": "medium",
            })
        elif 0 < progress < 0.3 and completed_in_vol > 0:
            recommendations.append({
                "type": "volume_slow",
                "message": f"第{vol_num}卷《{vol_title}》进度较慢（{progress:.0%}），可能需要精简或拆分",
                "priority": "medium",
            })

    # 全局调整建议
    if current_chapters < target_chapters * 0.3:
        recommendations.append({
            "type": "early_stage",
            "message": f"当前仅完成{current_chapters}章，建议保持快节奏，确保前30章有足够的爽点",
            "priority": "high",
        })
    elif current_chapters > target_chapters * 0.8:
        recommendations.append({
            "type": "late_stage",
            "message": f"当前已完成{current_chapters}章，接近目标（{target_chapters}章），建议加速收尾",
            "priority": "high",
        })

    # 字数调整
    if avg_words_per_chapter < 1800:
        recommendations.append({
            "type": "word_count_low",
            "message": f"平均每章{int(avg_words_per_chapter)}字，低于目标（2500字），建议扩充",
            "priority": "medium",
        })
    elif avg_words_per_chapter > 3500:
        recommendations.append({
            "type": "word_count_high",
            "message": f"平均每章{int(avg_words_per_chapter)}字，高于目标（2500字），建议精简",
            "priority": "low",
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "current_progress": {
            "chapters_written": current_chapters,
            "words_written": current_words,
            "avg_words_per_chapter": int(avg_words_per_chapter),
            "target_chapters": target_chapters,
            "target_words": target_words,
            "remaining_chapters": remaining_chapters,
            "remaining_words": remaining_words,
        },
        "recommendations": recommendations,
    }


def cmd_analyze(args):
    """分析当前进度，生成调整建议"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print("📊 大纲动态调整分析")
    print("=" * 60)
    print()

    # 加载大纲
    outline = load_outline(project_dirs)
    if not outline:
        print("❌ 未找到大纲文件")
        sys.exit(1)

    print(f"✅ 已加载大纲：{project_dirs['outline'] / 'vol-001-brief.yaml'}")
    print()

    # 分析章节
    chapter_analysis = analyze_chapters(project_dirs)
    print(f"✅ 已分析 {chapter_analysis['chapter_count']} 章正文")
    print(f"   总字数: {chapter_analysis['total_words']:,} 字")
    print(f"   平均每章: {chapter_analysis['total_words'] // max(chapter_analysis['chapter_count'], 1):,} 字")
    print()

    # 生成建议
    recommendation = generate_adjustment_recommendation(outline, chapter_analysis)

    # 输出结果
    print("【进度概览】")
    progress = recommendation["current_progress"]
    print(f"  已写章节: {progress['chapters_written']}/{progress['target_chapters']}")
    print(f"  已写字数: {progress['words_written']:,}/{progress['target_words']:,}")
    print(f"  剩余章节: ~{progress['remaining_chapters']} 章")
    print(f"  剩余字数: ~{progress['remaining_words']:,} 字")
    print()

    print("【调整建议】")
    if not recommendation["recommendations"]:
        print("  ✅ 当前进度正常，无需调整")
    else:
        for i, rec in enumerate(recommendation["recommendations"], 1):
            icon = "🔴" if rec["priority"] == "high" else "🟡" if rec["priority"] == "medium" else "⚪"
            print(f"  {icon} [{rec['type']}] {rec['message']}")
    print()

    # 保存建议
    output_path = project_dirs["outline"] / "dynamic-adjustment.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(recommendation, f, ensure_ascii=False, indent=2)
    print(f"✅ 建议已保存到: {output_path}")
    print()

    # 显示各卷进度
    print("【各卷进度】")
    volumes = outline.get("volumes", {})
    for vol_num, vol_data in sorted(volumes.items()):
        vol_title = vol_data.get("title", f"第{vol_num}卷")
        ch_range = vol_data.get("chapter_range", (0, 0))
        planned_start, planned_end = ch_range
        planned_count = planned_end - planned_start + 1

        completed = sum(
            1 for ch in chapter_analysis["chapters"]
            if planned_start <= ch["number"] <= planned_end
        )

        progress_pct = completed / max(planned_count, 1)
        status = "✅" if progress_pct >= 1.0 else "🔄" if progress_pct > 0 else "⏳"

        print(f"  {status} 第{vol_num}卷《{vol_title}》: {completed}/{planned_count} 章 ({progress_pct:.0%})")


def cmd_status(args):
    """查看当前大纲状态"""
    project_dirs = get_project_dirs(args.project)

    print("=" * 60)
    print(f"📋 项目 '{args.project}' 大纲状态")
    print("=" * 60)
    print()

    # 检查大纲文件
    outline_path = project_dirs["outline"] / "vol-001-brief.yaml"
    if outline_path.exists():
        size = outline_path.stat().st_size
        print(f"  ✅ vol-001-brief.yaml: {size:,} bytes")
    else:
        print(f"  ❌ vol-001-brief.yaml: 不存在")

    # 检查动态调整建议
    adjust_path = project_dirs["outline"] / "dynamic-adjustment.json"
    if adjust_path.exists():
        size = adjust_path.stat().st_size
        print(f"  📊 dynamic-adjustment.json: {size:,} bytes")

        # 读取并显示最新建议
        with open(adjust_path, encoding="utf-8") as f:
            data = json.load(f)
        recs = data.get("recommendations", [])
        if recs:
            print(f"     最新建议数: {len(recs)}")
    else:
        print(f"  ⏳ dynamic-adjustment.json: 未生成")

    print()

    # 检查已写章节
    chapters_dir = project_dirs["chapters"]
    if chapters_dir.exists():
        ch_files = list(chapters_dir.glob("ch*.md"))
        print(f"  📝 已写章节: {len(ch_files)} 章")
    else:
        print(f"  ⏳ 章节目录: 不存在")

    print()

    # 检查细纲文件
    outline_dir = project_dirs["outline"]
    brief_files = list(outline_dir.glob("ch-*-brief.md"))
    print(f"  📄 细纲文件: {len(brief_files)} 章")


def main():
    parser = argparse.ArgumentParser(
        description="大纲动态调整工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 分析当前进度，生成调整建议
  python3 tools/outline-dynamic-adjust.py analyze --project helper-creator

  # 查看当前大纲状态
  python3 tools/outline-dynamic-adjust.py status --project helper-creator
        """
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    p_analyze = sub.add_parser("analyze", help="分析当前进度，生成调整建议")
    p_analyze.add_argument("--project", "-p", required=True, help="项目 ID")

    p_status = sub.add_parser("status", help="查看当前大纲状态")
    p_status.add_argument("--project", "-p", required=True, help="项目 ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
