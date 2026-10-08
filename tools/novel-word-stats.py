#!/usr/bin/env python3
"""小说章节字数自动统计工具。

功能：
1. 从XBS书源文件解析可用的书源规则
2. 搜索热门小说（斗破/凡人/诡秘等）
3. 下载前10章内容
4. 统计每章字数分布
5. 输出markdown报告

用法：
    python3 novel-word-stats.py [--books 斗破苍穹,凡人修仙传,诡秘之主] [--output 输出目录]
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests


# 热门小说列表（带搜索关键词）
HOT_NOVELS = [
    {"name": "斗破苍穹", "keyword": "斗破苍穹", "author": "天蚕土豆", "genre": "玄幻热血"},
    {"name": "凡人修仙传", "keyword": "凡人修仙传", "author": "忘语", "genre": "写实修仙"},
    {"name": "诡秘之主", "keyword": "诡秘之主", "author": "爱潜水的乌贼", "genre": "悬疑神秘"},
    {"name": "遮天", "keyword": "遮天", "author": "辰东", "genre": "宏大叙事"},
    {"name": "完美世界", "keyword": "完美世界", "author": "辰东", "genre": "天才流"},
    {"name": "盘龙", "keyword": "盘龙", "author": "我吃西红柿", "genre": "爽文节奏"},
    {"name": "斗罗大陆", "keyword": "斗罗大陆", "author": "唐家三少", "genre": "青春玄幻"},
    {"name": "夜无疆", "keyword": "夜无疆", "author": "骑狼的胖子", "genre": "黑暗修仙"},
]

# 推荐书源（按成功率排序）
RECOMMENDED_SOURCES = [
    "疯读小说",  # API源，最稳定
    "cs-万相书城",
    "七彩小说网",
    "小说77",
    "笔趣阁5200",
]


def load_source_config(xbs_path: str) -> dict:
    """加载XBS书源配置。"""
    import subprocess
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        output_path = f.name
    
    try:
        result = subprocess.run(
            ['/tmp/xbsd', xbs_path, output_path],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"解密失败: {result.stderr}", file=sys.stderr)
            return {}
        
        with open(output_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载书源配置失败: {e}", file=sys.stderr)
        return {}
    finally:
        Path(output_path).unlink(missing_ok=True)


def find_source(sources: dict, name: str) -> Optional[dict]:
    """查找指定书源。"""
    for key, value in sources.items():
        if name in key or key in name:
            return value
    return None


def search_novel(source: dict, keyword: str) -> list:
    """使用书源搜索小说。"""
    try:
        search_rule = source.get('searchBook', {})
        host = search_rule.get('host', '')
        request_info = search_rule.get('requestInfo', '')
        
        if not host or not request_info:
            return []
        
        # 处理@js:规则（简化版，不执行JS）
        if request_info.startswith('@js:'):
            # 尝试提取URL模式
            url_match = re.search(r"url\s*=\s*'([^']+)'", request_info)
            if url_match:
                url = url_match.group(1)
            else:
                return []
        else:
            url = host + request_info.replace('%@keyWord', keyword)
        
        # 发起请求
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding
        
        # 解析搜索结果（简化版）
        if resp.status_code == 200:
            return [{"title": keyword, "url": url, "source": source.get('sourceName', 'unknown')}]
        
        return []
    except Exception as e:
        print(f"搜索失败 {keyword}: {e}", file=sys.stderr)
        return []


def download_chapters(book_url: str, source: dict, max_chapters: int = 10) -> list:
    """下载小说章节。"""
    chapters = []
    try:
        chapter_list_rule = source.get('chapterList', {})
        host = chapter_list_rule.get('host', book_url.split('/')[0:2])
        host = host if isinstance(host, str) else host[0]
        
        # 获取目录页
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(book_url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        
        if resp.status_code != 200:
            return chapters
        
        # 解析目录（简化版）
        list_selector = chapter_list_rule.get('list', '')
        title_selector = chapter_list_rule.get('title', '//a')
        
        from lxml import html as lxhtml
        tree = lxhtml.fromstring(resp.text)
        
        links = tree.xpath(list_selector) if list_selector else tree.xpath(title_selector)
        
        for i, link in enumerate(links[:max_chapters]):
            href = link.get('href', '') if hasattr(link, 'get') else ''
            title = link.text_content() if hasattr(link, 'text_content') else str(link)
            
            if href and title:
                full_url = f"{host}{href}" if href.startswith('/') else href
                chapters.append({"title": title, "url": full_url, "index": i+1})
        
        return chapters
    except Exception as e:
        print(f"下载目录失败: {e}", file=sys.stderr)
        return chapters


def download_chapter_content(url: str) -> str:
    """下载单个章节内容。"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding
        
        # 提取正文（简化版）
        from lxml import html as lxhtml
        tree = lxhtml.fromstring(resp.text)
        
        # 常见正文选择器
        selectors = [
            '//div[@id="content"]',
            '//div[@class="content"]',
            '//div[@class="novelcontent"]',
            '//article',
            '//main',
        ]
        
        for selector in selectors:
            elements = tree.xpath(selector)
            if elements:
                return elements[0].text_content()
        
        #  fallback: 取所有p标签
        paragraphs = tree.xpath('//p')
        return '\n'.join([p.text_content() for p in paragraphs if p.text_content()])
        
    except Exception as e:
        print(f"下载章节失败 {url}: {e}", file=sys.stderr)
        return ""


def count_chinese_chars(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def analyze_novel(novel_info: dict, sources: dict, output_dir: str) -> dict:
    """分析一部小说的章节字数分布。"""
    novel_name = novel_info['name']
    keyword = novel_info['keyword']
    
    print(f"\n正在分析《{novel_name}》...", file=sys.stderr)
    
    lengths = []
    
    # 尝试各个书源
    for source_name in RECOMMENDED_SOURCES:
        source = find_source(sources, source_name)
        if not source:
            continue
        
        print(f"  尝试书源: {source_name}", file=sys.stderr)
        
        # 搜索
        results = search_novel(source, keyword)
        if not results:
            continue
        
        # 下载前几章
        for result in results[:1]:  # 只取第一个结果
            chapters = download_chapters(result['url'], source, max_chapters=10)
            if not chapters:
                continue
            
            print(f"    找到 {len(chapters)} 章", file=sys.stderr)
            
            # 下载并统计
            for ch in chapters[:10]:
                content = download_chapter_content(ch['url'])
                chars = count_chinese_chars(content)
                if chars > 500:  # 过滤太短的章节
                    lengths.append(chars)
                    print(f"      第{ch['index']}章: {chars}字", file=sys.stderr)
                
                time.sleep(0.5)  # 避免频率过高
        
        if lengths:
            break  # 成功获取数据，跳出
    
    return {
        "name": novel_name,
        "author": novel_info['author'],
        "genre": novel_info['genre'],
        "chapter_count": len(lengths),
        "lengths": lengths,
        "source_used": next(iter(RECOMMENDED_SOURCES)) if lengths else None
    }


def generate_report(results: list, output_dir: str):
    """生成统计报告。"""
    report_lines = [
        "# 热门小说章节字数统计分析\n",
        "> 统计时间：2026-10-03\n",
        "> 数据来源：XBS书源自动抓取\n\n",
        "---\n",
        "",
        "## 一、统计结果汇总\n",
        "",
        "| 作品 | 作者 | 类型 | 章节数 | P50字数 | 结论 |",
        "|------|------|------|--------|---------|------|",
    ]
    
    for r in results:
        if r['lengths']:
            sorted_lengths = sorted(r['lengths'])
            p50 = sorted_lengths[len(sorted_lengths)//2] if sorted_lengths else 0
            conclusion = "✅达标" if p50 >= 2000 else "⚠️偏低"
            report_lines.append(
                f"| {r['name']} | {r['author']} | {r['genre']} | "
                f"{r['chapter_count']}章 | ~{p50}字 | {conclusion} |"
            )
        else:
            report_lines.append(f"| {r['name']} | - | {r['genre']} | 0章 | - | ❌失败 |")
    
    report_lines.extend([
        "",
        "---\n",
        "",
        "## 二、详细分布\n",
        "",
    ])
    
    for r in results:
        if not r['lengths']:
            continue
        
        sorted_lengths = sorted(r['lengths'])
        avg = sum(sorted_lengths) / len(sorted_lengths)
        p10 = sorted_lengths[int(len(sorted_lengths)*0.1)] if len(sorted_lengths) > 10 else sorted_lengths[0]
        p25 = sorted_lengths[int(len(sorted_lengths)*0.25)]
        p75 = sorted_lengths[int(len(sorted_lengths)*0.75)]
        p90 = sorted_lengths[int(len(sorted_lengths)*0.9)]
        
        report_lines.append(f"### 《{r['name']}》\n")
        report_lines.append(f"- 平均: {avg:.0f}字")
        report_lines.append(f"- P10: {p10}字, P25: {p25}字, P50: {sorted_lengths[len(sorted_lengths)//2]}字")
        report_lines.append(f"- P75: {p75}字, P90: {p90}字\n")
    
    # 保存报告
    output_path = Path(output_dir) / "章节字数统计-自动抓取.md"
    output_path.write_text('\n'.join(report_lines), encoding='utf-8')
    print(f"\n报告已保存到: {output_path}", file=sys.stderr)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='小说章节字数自动统计工具')
    parser.add_argument('--books', '-b', help='要分析的小说列表（逗号分隔）')
    parser.add_argument('--output', '-o', default='./output', help='输出目录')
    parser.add_argument('--xbs', default='/var/minis/shared/sourceModelList-filtered.xbs', help='XBS文件路径')
    args = parser.parse_args()
    
    # 创建输出目录
    Path(args.output).mkdir(parents=True, exist_ok=True)
    
    # 加载书源配置
    print("正在加载书源配置...", file=sys.stderr)
    sources = load_source_config(args.xbs)
    if not sources:
        print("加载书源配置失败", file=sys.stderr)
        sys.exit(1)
    
    print(f"加载了 {len(sources)} 个书源", file=sys.stderr)
    
    # 确定要分析的小说
    if args.books:
        keywords = [b.strip() for b in args.books.split(',')]
        novels = [n for n in HOT_NOVELS if n['keyword'] in keywords or any(k in n['name'] for k in keywords)]
    else:
        novels = HOT_NOVELS[:5]  # 默认分析前5本
    
    print(f"准备分析 {len(novels)} 部小说", file=sys.stderr)
    
    # 分析每部小说
    results = []
    for novel in novels:
        result = analyze_novel(novel, sources, args.output)
        results.append(result)
        time.sleep(1)  # 避免请求过快
    
    # 生成报告
    generate_report(results, args.output)
    
    print("\n分析完成！", file=sys.stderr)


if __name__ == "__main__":
    main()
