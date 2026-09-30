#!/usr/bin/env python3
"""
章节字数检查脚本 — 借鉴 chinese-novelist-skill

v2 Phase 1 迁移：
- 文件加载走 novelkit.core.chapter.Chapter（路径自动 resolve 为绝对路径，
  frontmatter 解析统一；从结构上消灭相对路径/cwd 类 bug）
- 阈值走 novelkit 统一配置（config/novelkit.json）：fail 线 1500（取严，
  评审决策 2026-09-30，原 1350 不再保留双轨）、warn 线 5500、目标 2500
- 其余行为与 v1 一致

核心功能：
  1. 统计字数（默认门禁口径：全部非空白字符；--chinese-only 切回纯汉字口径）
  2. 检查章节是否达标（<1500 fail；>5500 warning；其余 pass）
  3. 生成检查报告
  4. 支持批量检查

使用：
  python wordcount-check.py chapter.md
  python wordcount-check.py --all ./chapters/
  python wordcount-check.py --all ./chapters/ --min-words 3500
  python wordcount-check.py chapter.md --chinese-only   # 纯汉字口径（旧默认）
"""

import sys
import re
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# novelkit 导入：仓库根目录（novelkit/ 所在）入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# 兼容 v1：tools/ 目录入 sys.path（project_guard 等仍在此）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from novelkit.core.chapter import Chapter
from novelkit.core.config import get_config
from novelkit.core import log as nlog


def count_chinese_words(text: str) -> int:
    """统计中文字数（排除标点符号和Markdown标记）"""
    # 移除Markdown标记
    text = re.sub(r'#{1,6}\s*', '', text)  # 标题
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 粗体
    text = re.sub(r'\*(.*?)\*', r'\1', text)  # 斜体
    text = re.sub(r'~~(.*?)~~', r'\1', text)  # 删除线
    text = re.sub(r'`(.*?)`', r'\1', text)  # 行内代码
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # 链接
    text = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', text)  # 另一种链接格式

    # 统计中文字符（汉字）
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def count_gate_words(text: str) -> int:
    """门禁口径计数：全部非空白字符（含标点，不含空白），与 gate-check 一致"""
    return len(re.sub(r'\s+', '', text))


def extract_content_from_chapter(file_path: Path) -> str:
    """从章节文件中提取正文内容（排除标题等元数据）。

    v2 Phase 1 说明：此函数的行为原样保留，未改用 Chapter.body——
    它有一套自己的逻辑（跳过 "#第X章" 标题行；无标题行时 frontmatter
    会被计入）。这是 v1 的既有口径，口径统一是 Phase 3/4 的决策，
    本阶段只求行为一致。唯一变化：调用方现在传入 Chapter.resolve 后的
    绝对路径。
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"读取失败: {e}"

    # 查找正文开始位置（通常是第一个一级标题或二级标题之后）
    lines = content.split('\n')

    # 跳过开头的元数据（如 # 第XX章 标题）
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith('#') and '章' in line:
            content_start = i + 1
            break

    # 提取正文
    main_content = '\n'.join(lines[content_start:])
    return main_content


def check_chapter(file_path: Path, min_words: int = None,
                  chinese_only: bool = False) -> Dict:
    """检查单个章节的字数（默认门禁口径；chinese_only=True 回退纯汉字口径）"""
    cfg = get_config().word_count
    if min_words is None:
        min_words = cfg["target"]
    fail_below = cfg["soft_min"]      # 1500（统一取严，原 1350）
    warn_above = cfg["warn_above"]    # 5500

    try:
        chapter = Chapter.load(file_path)
    except FileNotFoundError:
        return {
            'file': str(file_path),
            'exists': False,
            'word_count': 0,
            'status': 'error',
            'message': f'文件不存在: {file_path}'
        }

    main_content = extract_content_from_chapter(chapter.path)
    # 默认门禁口径计数；--chinese-only 切回原纯汉字口径
    counter = count_chinese_words if chinese_only else count_gate_words
    caliber = '纯汉字' if chinese_only else '门禁口径（全字符）'
    word_count = counter(main_content)

    # 预测性分析（v0.46.0）
    prediction = predict_completion_rate(chapter.path.parent, min_words,
                                         chinese_only=chinese_only)

    # 状态对齐统一配置：<soft_min fail；>warn_above warn；其余 pass。
    # min_words 为写作目标，仅用于提示，不改变 fail 线。
    if word_count < fail_below:
        status = 'fail'
    elif word_count > warn_above:
        status = 'warn'
    else:
        status = 'pass'
    if status == 'pass':
        message = f'字数: {word_count}（{caliber}）(✓ 达标，目标{min_words}字)'
    elif status == 'warn':
        message = f'字数: {word_count}（{caliber}）(⚠️ 超长，超过{warn_above}字，建议拆分)'
    else:
        message = f'字数: {word_count}（{caliber}）(✗ 不足，低于门禁线{fail_below}字，目标{min_words}字)'

    return {
        'file': str(chapter.path),
        'exists': True,
        'word_count': word_count,
        'min_words': min_words,
        'caliber': caliber,
        'status': status,
        'message': message,
        'prediction': prediction
    }


def predict_completion_rate(chapters_dir: Path, min_words: int, days_ahead: int = 7,
                            chinese_only: bool = False) -> Dict:
    """
    预测性分析：基于当前进度预测能否按时完成（v0.46.0新增）

    参数：
        chapters_dir: 章节目录
        min_words: 目标字数
        days_ahead: 预测天数
        chinese_only: True 用纯汉字口径，否则用门禁口径

    返回：
        预测结果字典
    """
    counter = count_chinese_words if chinese_only else count_gate_words
    # 统计已完成章节
    chapter_files = list(chapters_dir.glob("*.md"))
    if not chapter_files:
        return {
            "status": "no_data",
            "message": "暂无章节数据，无法预测"
        }

    # 计算日均产量
    total_words = 0
    for f in chapter_files:
        content = extract_content_from_chapter(f)
        total_words += counter(content)

    # 假设每天创作1章（可根据实际调整）
    daily_output = total_words / len(chapter_files) if chapter_files else 0
    target_daily = min_words

    # 预测状态
    if daily_output >= target_daily:
        prediction_status = "on_track"
        message = f"当前日均产量{daily_output:.0f}字，达标（目标{target_daily}字）"
    elif daily_output >= target_daily * 0.8:
        prediction_status = "at_risk"
        message = f"当前日均产量{daily_output:.0f}字，略低于目标（目标{target_daily}字），存在延期风险"
    else:
        prediction_status = "behind"
        message = f"当前日均产量{daily_output:.0f}字，远低于目标（目标{target_daily}字），预计延期"

    # 计算预计完成天数
    if daily_output > 0:
        estimated_days = int(min_words / daily_output)
    else:
        estimated_days = 999

    return {
        "status": prediction_status,
        "message": message,
        "daily_output": round(daily_output, 2),
        "target_daily": target_daily,
        "estimated_days_per_chapter": estimated_days,
        "days_ahead": days_ahead,
        "projected_total": int(daily_output * days_ahead)
    }


def check_all_chapters(directory: Path, pattern: str = '第*.md',
                       min_words: int = None, chinese_only: bool = False) -> List[Dict]:
    """检查目录下所有符合模式的章节文件"""
    cfg = get_config().word_count
    if min_words is None:
        min_words = cfg["target"]
    if not directory.exists():
        nlog.error(f'目录不存在 - {directory}')
        return []

    chapter_files = sorted(directory.glob(pattern))
    results = []

    for chapter_file in chapter_files:
        result = check_chapter(chapter_file, min_words, chinese_only=chinese_only)
        results.append(result)

    return results


def print_results(results: List[Dict], min_words: int):
    """打印检查结果"""
    if not results:
        print('没有找到章节文件')
        return

    total_words = 0
    passed = 0
    warned = 0
    failed = 0

    print('\n' + '=' * 60)
    print('章节字数检查报告')
    print('=' * 60)

    for result in results:
        if not result['exists']:
            print(f'\n❌ {result["file"]}')
            print(f'   {result["message"]}')
            continue

        total_words += result['word_count']
        if result['status'] == 'pass':
            passed += 1
            icon = '✅'
        elif result['status'] == 'warn':
            warned += 1
            icon = '⚠️ '
        else:
            failed += 1
            icon = '❌'

        print(f'\n{icon} {Path(result["file"]).name}')
        print(f'   {result["message"]}')

    print('\n' + '-' * 60)
    print(f'总计: {len(results)} 章 | {passed} 章达标 | {warned} 章超长警告 | {failed} 章不足 | 总字数: {total_words:,}')
    print('-' * 60)

    if failed > 0:
        print(f'\n⚠️  有 {failed} 章内容不足 {min_words} 字，建议使用扩充技巧:')
        print('   - 添加细节描写（环境、心理、动作）')
        print('   - 增加对话场景')
        print('   - 扩展人物内心活动')
        print('   - 补充背景故事')


def main():
    import argparse

    cfg = get_config().word_count
    parser = argparse.ArgumentParser(description='章节字数检查工具（借鉴chinese-novelist-skill）')
    parser.add_argument('target', help='章节文件或目录路径')
    parser.add_argument('--min-words', '-m', type=int, default=cfg["target"],
                        help=f'目标字数（默认{cfg["target"]}，门禁fail线{cfg["soft_min"]}字）')
    parser.add_argument('--pattern', '-p', default='第*.md', help='文件匹配模式（默认第*.md）')
    parser.add_argument('--json', '-j', action='store_true', help='以JSON格式输出')
    parser.add_argument('--chinese-only', action='store_true', help='用纯汉字口径计数（旧默认行为）')

    args = parser.parse_args()

    target_path = Path(args.target)

    if target_path.is_file():
        # 单文件检查
        result = check_chapter(target_path, args.min_words, chinese_only=args.chinese_only)
        results = [result]
    elif target_path.is_dir():
        # 批量检查
        results = check_all_chapters(target_path, args.pattern, args.min_words,
                                     chinese_only=args.chinese_only)
    else:
        nlog.error(f'路径不存在 - {args.target}')
        return 1

    if args.json:
        import json
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_results(results, args.min_words)

    # warn（超长）不对齐门禁阻断，不计入退出码失败；只有 fail/error 才返回 1
    return 0 if all(r['status'] in ('pass', 'warn') for r in results if r['exists']) else 1


if __name__ == '__main__':
    sys.exit(main())
