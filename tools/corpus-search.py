#!/usr/bin/env python3
"""
语料检索器

借鉴：Chinese-WebNovel-Skill (Tomsawyerhu/Chinese-WebNovel-Skill, 836★)
核心：先匹配素材，再构思，再写作。不靠 prompt 空想。

功能：
  从本地小说语料库中按关键词/标签/类型检索相似素材和结构范本，
  供写作时参考。

用法：
  python3 corpus-search.py --list-tags           # 列出所有标签
  python3 corpus-search.py --list-types          # 列出所有类型
  python3 corpus-search.py --keyword '真假千金'  # 关键词搜索
  python3 corpus-search.py --type '开头钩子' --tag '危机压身' --limit 5
  python3 corpus-search.py --add <file> --type X --tags A,B  # 添加语料
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

CORPUS_DIR = Path("data/articles")
INDEX_FILE = Path("data/corpus-index.json")


class CorpusSearcher:
    """本地小说语料检索器"""

    def __init__(self, project_root: str = None):
        self.root = Path(project_root or ".")
        self.corpus_dir = self.root / "data" / "articles"
        self.index_file = self.root / "data" / "corpus-index.json"
        self.index = self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        return {
            "entries": [],
            "created_at": datetime.now().isoformat(),
            "total": 0,
        }

    def _save_index(self):
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.index_file.write_text(
            json.dumps(self.index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, file_path: str, entry_type: str = "", tags: list = None, source: str = ""):
        """添加语料"""
        path = Path(file_path)
        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}

        content = path.read_text(encoding="utf-8")
        title = path.stem

        # 自动提取标签
        if not tags:
            tags = self._auto_extract_tags(content)

        # 自动判断类型
        if not entry_type:
            entry_type = self._auto_detect_type(content)

        entry = {
            "id": f"CORPUS-{len(self.index['entries'])+1:04d}",
            "title": title,
            "type": entry_type,
            "tags": tags or [],
            "source": source,
            "file": str(path),
            "word_count": len(re.sub(r'[\s\n\r\t]', '', content)),
            "excerpt": content[:200],
            "added_at": datetime.now().isoformat(),
        }

        self.index["entries"].append(entry)
        self.index["total"] = len(self.index["entries"])
        self._save_index()

        return {"success": True, "entry": entry}

    def search(self, keyword: str = None, entry_type: str = None, tag: str = None, limit: int = 10):
        """检索语料"""
        results = []

        for entry in self.index["entries"]:
            # 关键词搜索
            if keyword:
                if keyword not in entry.get("title", "") and keyword not in entry.get("excerpt", ""):
                    continue

            # 类型过滤
            if entry_type and entry.get("type") != entry_type:
                continue

            # 标签过滤
            if tag and tag not in entry.get("tags", []):
                continue

            results.append(entry)

        return results[:limit]

    def list_tags(self):
        """列出所有标签"""
        tag_set = set()
        for entry in self.index["entries"]:
            for t in entry.get("tags", []):
                tag_set.add(t)
        return sorted(tag_set)

    def list_types(self):
        """列出所有类型"""
        type_set = set()
        for entry in self.index["entries"]:
            if entry.get("type"):
                type_set.add(entry["type"])
        return sorted(type_set)

    def get_stats(self):
        """语料统计"""
        entries = self.index["entries"]
        return {
            "total": len(entries),
            "by_type": {t: sum(1 for e in entries if e.get("type") == t)
                        for t in self.list_types()},
            "total_words": sum(e.get("word_count", 0) for e in entries),
            "total_tags": len(self.list_tags()),
        }

    def _auto_extract_tags(self, content: str) -> list:
        """自动从内容提取标签"""
        tags = []
        tag_patterns = [
            (r'修仙|境界|灵根', '修仙'),
            (r'系统|面板|任务', '系统流'),
            (r'都市|现代|公司', '都市'),
            (r'重生|穿越', '穿越重生'),
            (r'真假千金|替身', '身份反转'),
            (r'豪门|总裁|霸总', '豪门总裁'),
            (r'宫斗|后宫|妃', '宫斗'),
            (r'末世|丧尸|变异', '末世'),
            (r'无限|副本|主神', '无限流'),
            (r'悬疑|推理|破案', '悬疑'),
            (r'恐怖|灵异|鬼', '灵异'),
            (r'甜|宠|糖', '甜宠'),
            (r'虐|纠葛|三角', '虐恋'),
            (r'种田|日常|温馨', '种田'),
            (r'战斗|打斗|激战', '战斗'),
            (r'钩子|悬念', '钩子'),
            (r'开头', '开头'),
            (r'结尾|章末', '章末'),
            (r'对话|对白', '对话'),
            (r'转场|过渡', '转场'),
        ]
        for pat, tag in tag_patterns:
            if re.search(pat, content):
                tags.append(tag)
        return tags or ["未分类"]

    def _auto_detect_type(self, content: str) -> str:
        """自动判断语料类型"""
        if len(content) < 500:
            return "短片段"
        if re.search(r'第.{1,3}章', content[:200]):
            return "完整章节"
        if re.search(r'^#', content, re.MULTILINE):
            return "大纲"
        if re.search(r'角色|人物|设定', content[:100]):
            return "设定"
        return "正文片段"


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="语料检索器")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list-tags", help="列出所有标签")
    sub.add_parser("list-types", help="列出所有类型")
    sub.add_parser("stats", help="语料统计")

    p_search = sub.add_parser("search", help="检索语料")
    p_search.add_argument("--keyword", default=None)
    p_search.add_argument("--type", default=None)
    p_search.add_argument("--tag", default=None)
    p_search.add_argument("--limit", type=int, default=10)

    p_add = sub.add_parser("add", help="添加语料")
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--type", default="")
    p_add.add_argument("--tags", default="")
    p_add.add_argument("--source", default="")

    args = parser.parse_args()
    cs = CorpusSearcher()

    if args.cmd == "list-tags":
        print(json.dumps(cs.list_tags(), ensure_ascii=False, indent=2))
    elif args.cmd == "list-types":
        print(json.dumps(cs.list_types(), ensure_ascii=False, indent=2))
    elif args.cmd == "stats":
        print(json.dumps(cs.get_stats(), ensure_ascii=False, indent=2))
    elif args.cmd == "search":
        tags = args.tags.split(",") if args.tags else None
        results = cs.search(keyword=args.keyword, entry_type=args.type, tag=args.tag, limit=args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.cmd == "add":
        tags = args.tags.split(",") if args.tags else None
        result = cs.add(args.file, args.type, tags, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
