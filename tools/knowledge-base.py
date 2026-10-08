#!/usr/bin/env python3
"""
knowledge-base.py — AI拆书知识库（借鉴 MaliangAINovalWriter）

多维度知识提取：
  1. 文风叙事：叙事方式、文风特点、用词习惯
  2. 情节设计：核心冲突、悬念设计、故事节奏
  3. 人物塑造：角色塑造技巧与性格刻画
  4. 小说特点：世界观构建、金手指系统、力量体系
  5. 读者情绪：共鸣点、爽点布局、嗨点设计
  6. 热梗搞笑：流行梗、搞笑点、网络文化元素
  7. 章节大纲：章节结构与情节发展脉络

核心功能：
  1. 小说URL抓取（番茄小说等平台）
  2. AI多维度分析
  3. 知识库构建
  4. 检索与匹配

使用：
  python knowledge-base.py crawl --url "https://example.com/novel"
  python knowledge-base.py analyze --file novel.txt --dimensions all
  python knowledge-base.py search --query "如何写爽点"
  python knowledge-base.py list
"""

import sys
import json
import re
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class KnowledgeItem:
    """知识条目"""
    item_id: str
    dimension: str              # 文风叙事/情节设计/人物塑造等
    category: str               # 子类
    content: str                # 知识内容
    source: str                 # 来源（小说名/URL）
    confidence: float = 0.8     # 置信度
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    created_at: str = ""
    
    def __post_init__( self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "item_id": self.item_id,
            "dimension": self.dimension,
            "category": self.category,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "tags": self.tags,
            "examples": self.examples,
            "created_at": self.created_at,
        }


class KnowledgeBase:
    """知识库"""
    
    # MaliangAINovalWriter 拆书维度
    DIMENSIONS = {
        "文风叙事": ["叙事方式", "文风特点", "用词习惯", "句式结构"],
        "情节设计": ["核心冲突", "悬念设计", "故事节奏", "情节转折"],
        "人物塑造": ["角色塑造", "性格刻画", "人物成长", "人物关系"],
        "小说特点": ["世界观构建", "金手指系统", "力量体系", "设定创新"],
        "读者情绪": ["共鸣点", "爽点布局", "嗨点设计", "情绪曲线"],
        "热梗搞笑": ["流行梗", "搞笑点", "网络文化", "梗的运用"],
        "章节大纲": ["章节结构", "情节发展", "伏笔埋设", "高潮设置"],
    }
    
    def __init__(self, db_path: str = "knowledge-base.json"):
        self.db_path = Path(db_path)
        self.items: Dict[str, KnowledgeItem] = {}
        self._load()
    
    def _load(self):
        """加载知识库"""
        if self.db_path.exists():
            data = json.loads(self.db_path.read_text())
            for item_id, item_data in data.items():
                self.items[item_id] = KnowledgeItem(**item_data)
    
    def _save(self):
        """保存知识库"""
        data = {k: v.to_dict() for k, v in self.items.items()}
        self.db_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def add(
        self,
        dimension: str,
        category: str,
        content: str,
        source: str,
        confidence: float = 0.8,
        tags: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
    ) -> str:
        """添加知识条目"""
        item_id = f"kb-{int(time.time())}-{len(self.items)}"
        
        item = KnowledgeItem(
            item_id=item_id,
            dimension=dimension,
            category=category,
            content=content,
            source=source,
            confidence=confidence,
            tags=tags or [],
            examples=examples or [],
        )
        
        self.items[item_id] = item
        self._save()
        return item_id
    
    def search(
        self,
        query: str,
        dimension: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """搜索知识库"""
        results = []
        query_words = set(re.findall(r'\w+', query.lower()))
        
        for item in self.items.values():
            # 维度筛选
            if dimension and item.dimension != dimension:
                continue
            
            # 关键词匹配
            item_text = f"{item.content} {' '.join(item.tags)} {' '.join(item.examples)}"
            item_words = set(re.findall(r'\w+', item_text.lower()))
            
            # 计算匹配度
            overlap = len(query_words & item_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1) * item.confidence
                results.append({
                    "item_id": item.item_id,
                    "dimension": item.dimension,
                    "category": item.category,
                    "content": item.content,
                    "source": item.source,
                    "confidence": item.confidence,
                    "score": score,
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def list_by_dimension(self, dimension: str) -> List[Dict]:
        """按维度列出"""
        return [item.to_dict() for item in self.items.values() if item.dimension == dimension]
    
    def list_all(self) -> List[Dict]:
        """列出所有"""
        return [item.to_dict() for item in self.items.values()]
    
    def delete(self, item_id: str) -> bool:
        """删除条目"""
        if item_id in self.items:
            del self.items[item_id]
            self._save()
            return True
        return False


class NovelCrawler:
    """小说爬虫"""
    
    # 支持的平台
    PLATFORMS = {
        "qidian": "起点中文网",
        "fanqie": "番茄小说",
        "jjwxc": "晋江文学城",
        "qimao": "七猫小说",
    }
    
    def __init__(self):
        pass
    
    def crawl(self, url: str) -> Optional[Dict]:
        """抓取小说内容"""
        # 简化实现：返回占位数据
        # 实际应调用requests或浏览器自动化
        return {
            "url": url,
            "title": "示例小说",
            "author": "示例作者",
            "content": "这是一段示例小说内容...",
            "word_count": 1000,
        }
    
    def detect_platform(self, url: str) -> Optional[str]:
        """检测平台"""
        for platform, name in self.PLATFORMS.items():
            if platform in url:
                return platform
        return None


class KnowledgeAnalyzer:
    """知识分析器"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
        self.crawler = NovelCrawler()
    
    def analyze_url(self, url: str) -> Dict:
        """分析URL并提取知识"""
        # 抓取内容
        novel = self.crawler.crawl(url)
        if not novel:
            return {"error": "无法抓取内容"}
        
        # 分析内容
        results = self.analyze_content(
            content=novel["content"],
            title=novel["title"],
            source=url,
        )
        
        results["novel_info"] = novel
        return results
    
    def analyze_content(
        self,
        content: str,
        title: str = "未知",
        source: str = "本地文件",
    ) -> Dict:
        """分析小说内容，提取多维度知识"""
        # 分章节
        chapters = re.split(r'第[一二三四五六七八九十\d]+章', content)
        chapter_count = len(chapters)
        
        # 提取关键元素
        keywords = self._extract_keywords(content)
        conflicts = self._extract_conflicts(content)
        characters = self._extract_characters(content)
        
        # 按维度提取知识
        added_items = []
        
        # 文风叙事
        style_items = self._analyze_style(content, title, source)
        added_items.extend(style_items)
        
        # 情节设计
        plot_items = self._analyze_plot(content, title, source)
        added_items.extend(plot_items)
        
        # 人物塑造
        char_items = self._analyze_character(content, title, source)
        added_items.extend(char_items)
        
        # 读者情绪
        emotion_items = self._analyze_emotion(content, title, source)
        added_items.extend(emotion_items)
        
        return {
            "novel_title": title,
            "chapter_count": chapter_count,
            "word_count": len(content),
            "keywords": keywords,
            "conflicts": conflicts,
            "characters": characters,
            "added_items": added_items,
        }
    
    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        # 简化：按字数频次
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', content)
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, c in sorted_words[:20] if c > 3]
    
    def _extract_conflicts(self, content: str) -> List[Dict]:
        """提取冲突"""
        conflicts = []
        patterns = [
            (r'(冲突|对抗|争夺|对决)', '冲突'),
            (r'(复仇|报仇|雪耻)', '复仇'),
            (r'(生死|存亡|绝境)', '生死危机'),
        ]
        for pattern, label in patterns:
            if re.search(pattern, content):
                conflicts.append({"type": label, "count": len(re.findall(pattern, content))})
        return conflicts
    
    def _extract_characters(self, content: str) -> List[Dict]:
        """提取角色"""
        # 简化：检测名字模式
        names = re.findall(r'[\u4e00-\u9fff]{2,3}(?:同学|先生|小姐|公子|姑娘|前辈|师傅)', content)
        unique_names = list(set(names))[:10]
        return [{"name": n, "frequency": names.count(n)} for n in unique_names]
    
    def _analyze_style(
        self,
        content: str,
        title: str,
        source: str,
    ) -> List[str]:
        """分析文风叙事"""
        items = []
        
        # 检测叙事视角
        if re.search(r'他|她|它', content):
            items.append(self.kb.add(
                dimension="文风叙事",
                category="叙事视角",
                content="采用第三人称叙事，以观察者视角描述故事发展",
                source=source,
                tags=["third-person", "observer"],
            ))
        
        # 检测文风特点
        if re.search(r'(简洁|精炼|朴实)', content):
            items.append(self.kb.add(
                dimension="文风叙事",
                category="语言风格",
                content="语言简洁精炼，避免冗长描写，注重情节推进",
                source=source,
                tags=["concise", "efficient"],
            ))
        
        return items
    
    def _analyze_plot(
        self,
        content: str,
        title: str,
        source: str,
    ) -> List[str]:
        """分析情节设计"""
        items = []
        
        # 检测悬念
        if re.search(r'(悬念|谜团|疑问|为什么|如何)', content):
            items.append(self.kb.add(
                dimension="情节设计",
                category="悬念设计",
                content="善用悬念和疑问推动读者继续阅读，保持好奇心",
                source=source,
                tags=["suspense", "curiosity"],
            ))
        
        # 检测节奏
        short_chapters = len(re.findall(r'第\d+章.*?(?=第\d+章|$)', content, re.DOTALL))
        if short_chapters > 5:
            items.append(self.kb.add(
                dimension="情节设计",
                category="故事节奏",
                content="章节短小精悍，节奏紧凑，适合移动端阅读",
                source=source,
                tags=["fast-paced", "mobile-friendly"],
            ))
        
        return items
    
    def _analyze_character(
        self,
        content: str,
        title: str,
        source: str,
    ) -> List[str]:
        """分析人物塑造"""
        items = []
        
        # 检测人物成长
        if re.search(r'(成长|突破|变强|升级)', content):
            items.append(self.kb.add(
                dimension="人物塑造",
                category="人物成长",
                content="主角有明显的成长轨迹，通过挑战不断变强",
                source=source,
                tags=["character-growth", "power-progression"],
            ))
        
        return items
    
    def _analyze_emotion(
        self,
        content: str,
        title: str,
        source: str,
    ) -> List[str]:
        """分析读者情绪"""
        items = []
        
        # 检测爽点
        if re.search(r'(爽|爽点|快感|解气|过瘾)', content):
            items.append(self.kb.add(
                dimension="读者情绪",
                category="爽点设计",
                content="精心设计爽点，让读者获得阅读快感和情绪释放",
                source=source,
                tags=["satisfaction", "emotional-release"],
            ))
        
        # 检测共鸣
        if re.search(r'(共鸣|共情|感动|泪点)', content):
            items.append(self.kb.add(
                dimension="读者情绪",
                category="情感共鸣",
                content="通过人物遭遇引发读者情感共鸣，增强代入感",
                source=source,
                tags=["empathy", "resonance"],
            ))
        
        return items


def main():
    parser = argparse.ArgumentParser(description="AI拆书知识库")
    parser.add_argument("--db", default="knowledge-base.json", help="知识库路径")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # analyze-url
    url_parser = subparsers.add_parser("crawl", help="抓取并分析URL")
    url_parser.add_argument("--url", "-u", required=True, help="小说URL")
    
    # analyze-content
    content_parser = subparsers.add_parser("analyze", help="分析内容")
    content_parser.add_argument("--file", "-f", help="小说文件")
    content_parser.add_argument("--content", "-c", help="小说内容")
    content_parser.add_argument("--title", default="未知", help="小说标题")
    content_parser.add_argument("--dimensions", default="all",
                               choices=["all", "文风叙事", "情节设计", "人物塑造", "小说特点", "读者情绪", "热梗搞笑", "章节大纲"])
    
    # search
    search_parser = subparsers.add_parser("search", help="搜索知识")
    search_parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    search_parser.add_argument("--dimension", default=None, help="维度筛选")
    search_parser.add_argument("--limit", "-n", type=int, default=10)
    
    # list
    list_parser = subparsers.add_parser("list", help="列出知识库")
    list_parser.add_argument("--dimension", default=None, help="维度筛选")
    
    # stats
    subparsers.add_parser("stats", help="统计信息")
    
    args = parser.parse_args()
    
    kb = KnowledgeBase(args.db)
    analyzer = KnowledgeAnalyzer(kb)
    
    if args.command == "crawl":
        result = analyzer.analyze_url(args.url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "analyze":
        if args.file:
            content = Path(args.file).read_text()
            source = args.file
        elif args.content:
            content = args.content
            source = "stdin"
        else:
            print("❌ 需要指定--file或--content参数")
            sys.exit(1)

        result = analyzer.analyze_content(content, args.title, source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "search":
        results = kb.search(args.query, args.dimension, args.limit)
        for r in results:
            print(f"【{r['dimension']} - {r['category']}】")
            print(f"  内容: {r['content'][:100]}...")
            print(f"  来源: {r['source']}")
            print(f"  匹配度: {r['score']:.2f}\n")
    
    elif args.command == "list":
        if args.dimension:
            items = kb.list_by_dimension(args.dimension)
        else:
            items = kb.list_all()
        print(json.dumps(items, ensure_ascii=False, indent=2))
    
    elif args.command == "stats":
        stats = {
            "total_items": len(kb.items),
            "by_dimension": {},
        }
        for item in kb.items.values():
            stats["by_dimension"][item.dimension] = stats["by_dimension"].get(item.dimension, 0) + 1
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
