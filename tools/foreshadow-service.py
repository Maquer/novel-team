#!/usr/bin/env python3
"""
foreshadow-service.py — 伏笔管理系统（借鉴 MuMuAINovel）

核心功能：
  1. 伏笔埋设：生成稳定ID，存入数据库
  2. 伏笔回收：语义匹配，自动检测回收
  3. 时间线管理：可视化伏笔时间线
  4. 未回收提醒：检查未回收伏笔

使用：
  python foreshadow-service.py plant --chapter 1 --content "他看了一眼桌上的刀"
  python foreshadow-service.py recall --chapter 5
  python foreshadow-service.py timeline
  python foreshadow-service.py check-unresolved
"""

import sys
import json
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# 配置
LEDGER_DIR = Path("/var/minis/shared/novel-team/.foreshadow")
LEDGER_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Foreshadow:
    """伏笔数据模型"""
    id: str
    chapter_id: str
    content: str
    category: str  # "planted" | "recalled" | "abandoned"
    confidence: float  # 0.0-1.0，回收置信度
    created_at: str
    recalled_at: Optional[str] = None
    recall_chapter: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "chapter_id": self.chapter_id,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "recalled_at": self.recalled_at,
            "recall_chapter": self.recall_chapter,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Foreshadow":
        return cls(
            id=data["id"],
            chapter_id=data["chapter_id"],
            content=data["content"],
            category=data["category"],
            confidence=data.get("confidence", 0.0),
            created_at=data["created_at"],
            recalled_at=data.get("recalled_at"),
            recall_chapter=data.get("recall_chapter"),
            tags=data.get("tags", []),
        )


class ForeshadowService:
    """伏笔管理服务"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = LEDGER_DIR / f"{project_id}.json"
        self.foreshadows: List[Foreshadow] = []
        self._load()
    
    def _load(self):
        """加载伏笔数据"""
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.foreshadows = [Foreshadow.from_dict(f) for f in data.get("foreshadows", [])]
    
    def _save(self):
        """保存伏笔数据"""
        tmp = self.storage_path.with_suffix('.tmp')
        data = {"foreshadows": [f.to_dict() for f in self.foreshadows]}
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def generate_stable_id(self, chapter_id: str, content: str) -> str:
        """
        生成稳定的伏笔唯一标识符
        
        使用 chapter_id + content_hash 的方式，确保：
        1. 同一章节、相同内容的伏笔只有一个唯一ID
        2. 重新分析同一章节不会产生新ID
        3. 标识符足够短且可读
        """
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]
        return f"F{chapter_id}_{content_hash}"
    
    def plant(self, chapter_id: str, content: str, 
              category: str = "planted", tags: List[str] = None) -> Foreshadow:
        """埋设伏笔"""
        # 生成稳定ID
        foreshadow_id = self.generate_stable_id(chapter_id, content)
        
        # 检查是否已存在
        existing = self.get_by_id(foreshadow_id)
        if existing:
            print(f"⚠️ 伏笔已存在: {foreshadow_id}")
            return existing
        
        # 创建伏笔
        foreshadow = Foreshadow(
            id=foreshadow_id,
            chapter_id=chapter_id,
            content=content,
            category=category,
            confidence=1.0,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
        )
        
        self.foreshadows.append(foreshadow)
        self._save()
        
        return foreshadow
    
    def get_by_id(self, foreshadow_id: str) -> Optional[Foreshadow]:
        """根据ID获取伏笔"""
        for f in self.foreshadows:
            if f.id == foreshadow_id:
                return f
        return None
    
    def get_by_chapter(self, chapter_id: str) -> List[Foreshadow]:
        """根据章节获取伏笔"""
        return [f for f in self.foreshadows if f.chapter_id == chapter_id]
    
    def get_active(self) -> List[Foreshadow]:
        """获取未回收伏笔"""
        return [f for f in self.foreshadows if f.category == "planted"]
    
    def get_timeline(self, limit: int = 20) -> List[Foreshadow]:
        """获取时间线（按创建时间排序）"""
        sorted_foreshadows = sorted(
            self.foreshadows,
            key=lambda f: f.created_at,
            reverse=True
        )
        return sorted_foreshadows[:limit]
    
    def recall(self, foreshadow_id: str, chapter_id: str, 
               confidence: float = 0.8) -> Optional[Foreshadow]:
        """回收伏笔"""
        foreshadow = self.get_by_id(foreshadow_id)
        if not foreshadow:
            return None
        
        if foreshadow.category == "recalled":
            print(f"⚠️ 伏笔已回收: {foreshadow_id}")
            return foreshadow
        
        # 更新状态
        foreshadow.category = "recalled"
        foreshadow.confidence = confidence
        foreshadow.recalled_at = datetime.now().isoformat()
        foreshadow.recall_chapter = chapter_id
        
        self._save()
        
        return foreshadow
    
    def semantic_match(self, content: str, threshold: float = 0.7) -> List[Tuple[Foreshadow, float]]:
        """
        语义匹配：检查新内容是否回收了已埋设的伏笔
        
        简化版：使用关键词匹配和相似度计算
        实际应使用Embedding模型做语义相似度
        """
        matches = []
        
        # 获取所有未回收伏笔
        active = self.get_active()
        
        for f in active:
            # 计算相似度（简化版：关键词重叠）
            similarity = self._calculate_similarity(f.content, content)
            
            if similarity >= threshold:
                matches.append((f, similarity))
        
        # 按相似度排序
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（简化版）
        
        实际应使用：
        1. Embedding向量余弦相似度
        2. 或Jaccard相似度
        """
        # 提取关键词
        keywords1 = set(re.findall(r'[\u4e00-\u9fff]{2,}', text1))
        keywords2 = set(re.findall(r'[\u4e00-\u9fff]{2,}', text2))
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # Jaccard相似度
        intersection = keywords1 & keywords2
        union = keywords1 | keywords2
        
        return len(intersection) / len(union) if union else 0.0
    
    def check_unresolved(self) -> List[Foreshadow]:
        """检查未回收伏笔"""
        return self.get_active()
    
    def print_timeline(self):
        """打印ASCII时间线图"""
        print("\n=== 伏笔时间线 ===\n")
        
        timeline = self.get_timeline(50)
        if not timeline:
            print("  暂无伏笔记录")
            return
        
        # 按章节分组
        by_chapter = {}
        for f in timeline:
            ch = f.chapter_id
            if ch not in by_chapter:
                by_chapter[ch] = []
            by_chapter[ch].append(f)
        
        # 按章节排序
        sorted_chapters = sorted(by_chapter.keys(), key=lambda x: int(x.replace('ch', '').replace('chapter', '')) if x.replace('ch', '').replace('chapter', '').isdigit() else 999)
        
        for ch in sorted_chapters[:10]:  # 最多显示10章
            foreshadows = by_chapter[ch]
            planted = [f for f in foreshadows if f.category == "planted"]
            recalled = [f for f in foreshadows if f.category == "recalled"]
            
            print(f"【第{ch}章】")
            
            if recalled:
                for f in recalled:
                    print(f"  ✅ {f.content[:30]}... → 回收于{f.recall_chapter}")
            
            if planted:
                for f in planted:
                    days_since = (datetime.now() - datetime.fromisoformat(f.created_at)).days
                    print(f"  ⏳ {f.content[:30]}... (创建{days_since}天前)")
            
            print()
        
        # 统计
        total = len(self.foreshadows)
        planted_count = len([f for f in self.foreshadows if f.category == "planted"])
        recalled_count = len([f for f in self.foreshadows if f.category == "recalled"])
        
        print(f"\n【统计】总伏笔: {total} | 待回收: {planted_count} | 已回收: {recalled_count}")
        if total > 0:
            print(f"回收率: {recalled_count/total*100:.1f}%")
    
    def print_summary(self):
        """打印统计摘要"""
        total = len(self.foreshadows)
        planted = len([f for f in self.foreshadows if f.category == "planted"])
        recalled = len([f for f in self.foreshadows if f.category == "recalled"])
        abandoned = len([f for f in self.foreshadows if f.category == "abandoned"])
        
        print("\n=== 伏笔统计 ===\n")
        print(f"总伏笔数: {total}")
        print(f"  待回收: {planted}")
        print(f"  已回收: {recalled}")
        print(f"  已废弃: {abandoned}")
        
        if total > 0:
            recall_rate = recalled / total * 100
            print(f"\n回收率: {recall_rate:.1f}%")
        
        print()


def cmd_plant(args):
    """埋设伏笔"""
    service = ForeshadowService(args.project_id)
    
    foreshadow = service.plant(
        chapter_id=args.chapter,
        content=args.content,
        category=args.category,
        tags=args.tags.split(',') if args.tags else None
    )
    
    print(f"✅ 已埋设伏笔: {foreshadow.id}")
    print(f"   章节: {foreshadow.chapter_id}")
    print(f"   内容: {foreshadow.content[:50]}...")
    print(f"   标签: {', '.join(foreshadow.tags) if foreshadow.tags else '无'}")


def cmd_recall(args):
    """回收伏笔"""
    service = ForeshadowService(args.project_id)
    
    # 如果有ID，直接回收
    if args.id:
        foreshadow = service.recall(args.id, args.chapter, args.confidence)
        if foreshadow:
            print(f"✅ 已回收伏笔: {foreshadow.id}")
        else:
            print(f"❌ 伏笔不存在: {args.id}")
        return
    
    # 否则进行语义匹配
    print(f"🔍 正在检测语义匹配...")
    matches = service.semantic_match(args.content, args.threshold)
    
    if matches:
        print(f"\n发现 {len(matches)} 个潜在匹配:\n")
        for f, confidence in matches[:5]:
            print(f"  [{confidence:.2f}] {f.id}")
            print(f"      原伏笔: {f.content[:40]}...")
            print(f"      当前内容: {args.content[:40]}...")
            print()
        
        # 自动回收高于阈值的
        for f, confidence in matches:
            if confidence >= args.threshold:
                service.recall(f.id, args.chapter, confidence)
                print(f"✅ 自动回收: {f.id} (置信度: {confidence:.2f})")
    else:
        print("❌ 未发现匹配的伏笔")


def cmd_timeline(args):
    """查看时间线"""
    service = ForeshadowService(args.project_id)
    service.print_timeline()


def cmd_check(args):
    """检查未回收伏笔"""
    service = ForeshadowService(args.project_id)
    unresolved = service.check_unresolved()
    
    if unresolved:
        print(f"\n⚠️ 发现 {len(unresolved)} 个未回收伏笔:\n")
        for f in unresolved:
            print(f"  [{f.chapter_id}] {f.content[:40]}...")
            print(f"      创建时间: {f.created_at[:19]}")
            print()
    else:
        print("\n✅ 所有伏笔已回收")


def cmd_summary(args):
    """查看统计"""
    service = ForeshadowService(args.project_id)
    service.print_summary()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="伏笔管理系统（借鉴MuMuAINovel）")
    parser.add_argument("--project-id", "-p", required=True, help="项目ID")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # plant命令
    p_plant = subparsers.add_parser("plant", help="埋设伏笔")
    p_plant.add_argument("--chapter", "-c", required=True, help="章节ID")
    p_plant.add_argument("--content", required=True, help="伏笔内容")
    p_plant.add_argument("--category", default="planted", help="类别")
    p_plant.add_argument("--tags", help="标签（逗号分隔）")
    
    # recall命令
    p_recall = subparsers.add_parser("recall", help="回收伏笔")
    p_recall.add_argument("--id", help="伏笔ID（直接回收）")
    p_recall.add_argument("--chapter", "-c", help="当前章节")
    p_recall.add_argument("--content", help="当前内容（用于语义匹配）")
    p_recall.add_argument("--threshold", "-t", type=float, default=0.7, help="相似度阈值")
    
    # timeline命令
    subparsers.add_parser("timeline", help="查看时间线")
    
    # check命令
    subparsers.add_parser("check", help="检查未回收伏笔")
    
    # summary命令
    subparsers.add_parser("summary", help="查看统计")
    
    args = parser.parse_args()
    
    if args.command == "plant":
        cmd_plant(args)
    elif args.command == "recall":
        cmd_recall(args)
    elif args.command == "timeline":
        cmd_timeline(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "summary":
        cmd_summary(args)
    else:
        parser.print_help()
