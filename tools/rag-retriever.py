#!/usr/bin/env python3
"""
轻量剧情检索器（RAG风格）— 借鉴 Novel-Creator-Skill

功能：
  1. 章节索引建立
  2. BM25风格粗筛
  3. 语义重排精筛
  4. 查询触发判断
  5. 上下文建议生成
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

# 配置目录
LEDGER_DIR = Path("/var/minis/shared/novel-team/ledger")
INDEX_FILE = LEDGER_DIR / "plot_index.json"
CHAPTERS_DIR = LEDGER_DIR / "chapters"


def load_index() -> Dict:
    if not INDEX_FILE.exists():
        return {"version": "1.0", "chapters": {}, "entities": {}, "keywords": {}}
    return json.loads(INDEX_FILE.read_text(encoding='utf-8'))


def save_index(index: Dict) -> None:
    tmp = INDEX_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(INDEX_FILE)


def tokenize(text: str) -> List[str]:
    """简单中文分词：2-4字n-gram"""
    text = text.lower()
    tokens = []
    # 提取2-4字n-gram
    for i in range(len(text) - 1):
        tokens.append(text[i:i+2])
    for i in range(len(text) - 2):
        tokens.append(text[i:i+3])
    for i in range(len(text) - 3):
        tokens.append(text[i:i+4])
    # 去重并保持顺序
    seen = set()
    unique = []
    for t in tokens:
        if t not in seen and len(t) >= 2:
            seen.add(t)
            unique.append(t)
    return unique


def build_index(project_dir: str) -> Dict:
    """建立章节索引"""
    # 尝试多个可能的目录路径
    possible_paths = [
        Path(project_dir) / "chapters",
        Path(project_dir) / "03_manuscript",
        Path("/var/minis/shared/novel-team/ledger/chapters"),
    ]
    chapters_path = None
    for p in possible_paths:
        if p.exists():
            chapters_path = p
            break
    
    if not chapters_path:
        print(f"❌ 章节目录不存在，已尝试:")
        for p in possible_paths:
            print(f"   - {p}")
        return {}
    if not chapters_path.exists():
        print(f"❌ 章节目录不存在: {chapters_path}")
        return {}
    
    index = load_index()
    index["chapters"] = {}
    
    chapter_files = sorted(chapters_path.glob("*.md"))
    
    for chapter_file in chapter_files:
        chapter_no = int(re.search(r'(\d+)', chapter_file.stem) or [0])[0]
        content = chapter_file.read_text(encoding='utf-8')
        
        # 提取实体（简化版：匹配常见人名模式）
        entities = set()
        # 匹配"xxx道"、"xxx说"中的名字
        for m in re.finditer(r'([一-鿿]{2,4})(?:道|说|想|看|听|走|站)', content):
            entities.add(m.group(1))
        
        # 提取关键词（基于TF-IDF简化版）
        tokens = tokenize(content)
        token_counts = Counter(tokens)
        keywords = [t for t, _ in token_counts.most_common(20)]
        
        index["chapters"][str(chapter_no)] = {
            "file": chapter_file.name,
            "tokens": tokens,
            "keywords": keywords,
            "entities": list(entities),
            "word_count": len(content)
        }
    
    # 建立实体索引
    index["entities"] = {}
    for chapter_no, data in index["chapters"].items():
        for entity in data["entities"]:
            if entity not in index["entities"]:
                index["entities"][entity] = []
            index["entities"][entity].append(chapter_no)
    
    save_index(index)
    print(f"✅ 索引已建立，共{len(index['chapters'])}章")
    return index


def search(project_id: str, query: str, top_k: int = 4) -> List[Dict]:
    """检索相关章节片段"""
    index = load_index()
    
    if not index.get("chapters"):
        print("⚠️ 索引为空，请先运行 build-index")
        return []
    
    # 查询分词
    query_tokens = tokenize(query)
    query_entities = [e for e in index.get("entities", {}).keys() if e in query]
    
    # 判断是否需要检索
    should_retrieve = bool(query_entities or len(query_tokens) >= 3)
    
    if not should_retrieve:
        print("💡 简单查询，无需检索上下文")
        return []
    
    # BM25风格粗筛（简化版：基于token重叠）
    scores = {}
    for chapter_no, data in index["chapters"].items():
        chapter_tokens = set(data.get("tokens", []))
        query_set = set(query_tokens)
        
        # 计算token重叠度
        overlap = len(chapter_tokens & query_set)
        if overlap > 0:
            # 简单TF-IDF权重
            tf = overlap / max(len(chapter_tokens), 1)
            idf = 1 + log(1 + len(index["chapters"]) / max(1, sum(1 for c in index["chapters"].values() if query_tokens[0] in c.get("tokens", []))))
            scores[chapter_no] = tf * idf
        
        # 实体匹配加成
        chapter_entities = set(data.get("entities", []))
        entity_overlap = len(chapter_entities & set(query_entities))
        if entity_overlap > 0:
            scores[chapter_no] = scores.get(chapter_no, 0) + entity_overlap * 2
    
    # 排序取Top-K
    sorted_chapters = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
    
    results = []
    for chapter_no, score in sorted_chapters:
        data = index["chapters"][chapter_no]
        results.append({
            "chapter": int(chapter_no),
            "score": round(score, 3),
            "entities": data.get("entities", []),
            "keywords": data.get("keywords", [])[:5],
            "word_count": data.get("word_count", 0)
        })
    
    return results


def log_query(query: str, results: List[Dict]) -> None:
    """记录查询日志"""
    log_file = LEDGER_DIR / "query_log.jsonl"
    entry = {
        "query": query,
        "results": results,
        "timestamp": now().isoformat()
    }
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def now():
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz)


def cmd_build(args):
    """建立索引"""
    build_index(args.project_dir)


def cmd_search(args):
    """搜索章节"""
    results = search(args.project_id, args.query, args.top_k)
    
    if not results:
        print("未找到相关章节")
        return
    
    print(f"\n📊 检索结果（共{len(results)}章）:")
    print("-" * 60)
    for r in results:
        print(f"第{r['chapter']}章 (得分: {r['score']})")
        print(f"  实体: {', '.join(r['entities'][:3])}")
        print(f"  关键词: {', '.join(r['keywords'][:5])}")
        print(f"  字数: {r['word_count']:,}")
        print()


def cmd_status(args):
    """查看索引状态"""
    index = load_index()
    
    print("\n📊 索引状态")
    print("=" * 60)
    print(f"版本: {index.get('version', '1.0')}")
    print(f"章节数: {len(index.get('chapters', {}))}")
    print(f"实体数: {len(index.get('entities', {}))}")
    print(f"总词项数: {sum(len(c.get('tokens', [])) for c in index.get('chapters', {}).values())}")
    print()
    
    if index.get('entities'):
        print("【高频实体Top10】")
        entity_counts = [(e, len(chapters)) for e, chapters in index['entities'].items()]
        for entity, count in sorted(entity_counts, key=lambda x: -x[1])[:10]:
            print(f"  {entity}: {count}章")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG剧情检索器")
    subparsers = parser.add_subparsers(dest="command")
    
    # build
    p_build = subparsers.add_parser("build", help="建立索引")
    p_build.add_argument("--project-dir", required=True, help="项目目录")
    
    # search
    p_search = subparsers.add_parser("search", help="搜索章节")
    p_search.add_argument("--project-id", required=True, help="项目ID")
    p_search.add_argument("--query", required=True, help="查询关键词")
    p_search.add_argument("--top-k", type=int, default=4, help="返回结果数")
    
    # status
    subparsers.add_parser("status", help="查看索引状态")
    
    args = parser.parse_args()
    
    if args.command == "build":
        cmd_build(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()
