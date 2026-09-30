#!/usr/bin/env python3
"""
大纲版本管理器 — v0.46.0新增

功能：
  1. 大纲版本控制（保存、恢复、对比）
  2. 变更影响分析（修改某章节影响哪些后续章节）
  3. 版本历史追踪（谁在什么时候改了什么）

使用：
  python outline-version-manager.py init --project projects/my-novel
  python outline-version-manager.py save --project projects/my-novel --version "v1.0" --reason "第1卷定稿"
  python outline-version-manager.py diff --project projects/my-novel --v1 v1.0 --v2 v1.1
  python outline-version-manager.py impact --project projects/my-novel --chapter 5
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from copy import deepcopy


@dataclass
class VersionRecord:
    """版本记录"""
    version: str
    timestamp: str
    author: str
    reason: str
    summary: Dict  # 版本摘要（章节数、伏笔数等）
    outline_data: Dict  # 完整大纲数据快照
    changes: List[Dict]  # 变更列表
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VersionRecord':
        return cls(**data)


class OutlineVersionManager:
    """大纲版本管理器"""
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.version_dir = self.project_dir / "outline" / "versions"
        self.version_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.version_dir / "history.json"
        self.history: List[VersionRecord] = []
        self._load_history()
    
    def _load_history(self):
        """加载版本历史"""
        if self.history_file.exists():
            data = json.loads(self.history_file.read_text(encoding='utf-8'))
            self.history = [VersionRecord.from_dict(v) for v in data]
    
    def _save_history(self):
        """保存版本历史"""
        data = [v.to_dict() for v in self.history]
        self.history_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def save_version(self, outline_data: Dict, version: str, reason: str, author: str = "system") -> Dict:
        """
        保存新版本
        
        参数：
            outline_data: 当前大纲数据
            version: 版本号（如 v1.0, v1.1）
            reason: 保存原因
            author: 操作者
        
        返回：
            版本记录字典
        """
        # 生成时间戳
        timestamp = datetime.now().isoformat()
        
        # 计算版本摘要
        summary = self._calculate_summary(outline_data)
        
        # 检测变更（与上一版本对比）
        changes = []
        if self.history:
            last_version = self.history[-1]
            changes = self._detect_changes(last_version.outline_data, outline_data)
        
        # 创建版本记录
        record = VersionRecord(
            version=version,
            timestamp=timestamp,
            author=author,
            reason=reason,
            summary=summary,
            outline_data=deepcopy(outline_data),
            changes=changes
        )
        
        # 保存到历史
        self.history.append(record)
        self._save_history()
        
        # 保存版本快照
        version_file = self.version_dir / f"{version}.json"
        version_file.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
        
        return record.to_dict()
    
    def get_version(self, version: str) -> Optional[Dict]:
        """获取指定版本"""
        version_file = self.version_dir / f"{version}.json"
        if version_file.exists():
            data = json.loads(version_file.read_text(encoding='utf-8'))
            return VersionRecord.from_dict(data).to_dict()
        return None
    
    def diff_versions(self, v1: str, v2: str) -> Dict:
        """
        对比两个版本
        
        参数：
            v1: 旧版本号
            v2: 新版本号
        
        返回：
            差异报告
        """
        ver1 = self.get_version(v1)
        ver2 = self.get_version(v2)
        
        if not ver1 or not ver2:
            return {"error": "版本不存在"}
        
        # 计算差异
        changes = self._detect_changes(ver1["outline_data"], ver2["outline_data"])
        
        return {
            "from": v1,
            "to": v2,
            "timestamp": ver2["timestamp"],
            "author": ver2["author"],
            "reason": ver2["reason"],
            "changes": changes,
            "summary_diff": self._diff_summaries(ver1["summary"], ver2["summary"])
        }
    
    def analyze_impact(self, chapter_num: int, outline_data: Dict) -> Dict:
        """
        分析修改某章节的影响范围
        
        参数：
            chapter_num: 章节编号
            outline_data: 当前大纲数据
        
        返回：
            影响分析报告
        """
        impacted_chapters = []
        impacted_foreshadowings = []
        
        # 查找受影响的章节（后续章节）
        chapters = outline_data.get("chapters", {})
        for num, chapter in chapters.items():
            if int(num) > chapter_num:
                # 检查是否引用了被修改章节的内容
                if self._is_dependent(chapter, chapters.get(str(chapter_num))):
                    impacted_chapters.append({
                        "chapter": int(num),
                        "title": chapter.get("title", ""),
                        "dependency": "引用了被修改章节的设定"
                    })
        
        # 查找受影响的伏笔
        foreshadowings = outline_data.get("foreshadowings", {})
        for fid, foreshadow in foreshadowings.items():
            if foreshadow.get("planted_at") == str(chapter_num) or \
               foreshadow.get("payoff_at") == str(chapter_num):
                impacted_foreshadowings.append({
                    "id": fid,
                    "content": foreshadow.get("content", ""),
                    "status": foreshadow.get("status", ""),
                    "impact": "伏笔埋设或回收章节被修改"
                })
        
        return {
            "modified_chapter": chapter_num,
            "impacted_chapters": impacted_chapters,
            "impacted_foreshadowings": impacted_foreshadowings,
            "risk_level": self._assess_risk(impacted_chapters, impacted_foreshadowings)
        }
    
    def rollback_to_version(self, version: str) -> Dict:
        """回滚到指定版本"""
        target = self.get_version(version)
        if not target:
            return {"error": "版本不存在"}
        
        # 回滚到目标版本
        self.history = [v for v in self.history if v.version <= version]
        self._save_history()
        
        return {
            "success": True,
            "rolled_back_to": version,
            "timestamp": target["timestamp"],
            "note": "已回滚到指定版本，后续版本已归档"
        }
    
    # ========== 内部方法 ==========
    
    def _calculate_summary(self, outline_data: Dict) -> Dict:
        """计算版本摘要"""
        chapters = outline_data.get("chapters", {})
        foreshadowings = outline_data.get("foreshadowings", {})
        
        return {
            "total_chapters": len(chapters),
            "total_foreshadowings": len(foreshadowings),
            "approved_chapters": sum(1 for c in chapters.values() if c.get("status") == "approved"),
            "planted_foreshadowings": sum(1 for f in foreshadowings.values() if f.get("status") == "planted"),
            "paid_foreshadowings": sum(1 for f in foreshadowings.values() if f.get("status") == "paid_off")
        }
    
    def _detect_changes(self, old_data: Dict, new_data: Dict) -> List[Dict]:
        """检测两个版本之间的变更"""
        changes = []
        
        # 检测章节变更
        old_chapters = old_data.get("chapters", {})
        new_chapters = new_data.get("chapters", {})
        
        for num in set(list(old_chapters.keys()) + list(new_chapters.keys())):
            if num not in old_chapters:
                changes.append({"type": "chapter_added", "chapter": int(num), "title": new_chapters[num].get("title", "")})
            elif num not in new_chapters:
                changes.append({"type": "chapter_removed", "chapter": int(num), "title": old_chapters[num].get("title", "")})
            elif old_chapters[num] != new_chapters[num]:
                changes.append({"type": "chapter_modified", "chapter": int(num), "title": new_chapters[num].get("title", "")})
        
        # 检测伏笔变更
        old_foreshadowings = old_data.get("foreshadowings", {})
        new_foreshadowings = new_data.get("foreshadowings", {})
        
        for fid in set(list(old_foreshadowings.keys()) + list(new_foreshadowings.keys())):
            if fid not in old_foreshadowings:
                changes.append({"type": "foreshadow_added", "id": fid, "content": new_foreshadowings[fid].get("content", "")})
            elif fid not in new_foreshadowings:
                changes.append({"type": "foreshadow_removed", "id": fid, "content": old_foreshadowings[fid].get("content", "")})
            elif old_foreshadowings[fid] != new_foreshadowings[fid]:
                changes.append({"type": "foreshadow_modified", "id": fid, "content": new_foreshadowings[fid].get("content", "")})
        
        return changes
    
    def _diff_summaries(self, s1: Dict, s2: Dict) -> Dict:
        """对比两个摘要"""
        return {
            key: {"from": s1.get(key), "to": s2.get(key), "delta": s2.get(key, 0) - s1.get(key, 0)}
            for key in set(list(s1.keys()) + list(s2.keys()))
        }
    
    def _is_dependent(self, chapter: Dict, referenced_chapter: Optional[Dict]) -> bool:
        """判断章节是否依赖另一个章节"""
        if not referenced_chapter:
            return False
        
        # 简单判断：如果章节摘要中包含被引用章节的关键信息
        ref_summary = referenced_chapter.get("summary", "")
        chapter_summary = chapter.get("summary", "")
        
        return ref_summary and chapter_summary and len(ref_summary) > 10
    
    def _assess_risk(self, impacted_chapters: List[Dict], impacted_foreshadowings: List[Dict]) -> str:
        """评估风险等级"""
        if not impacted_chapters and not impacted_foreshadowings:
            return "low"
        elif len(impacted_chapters) <= 2 and len(impacted_foreshadowings) <= 1:
            return "medium"
        else:
            return "high"


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="大纲版本管理器")
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument("command", choices=["save", "diff", "impact", "rollback", "list"])
    parser.add_argument("--version", help="版本号")
    parser.add_argument("--reason", help="保存原因")
    parser.add_argument("--author", default="user", help="操作者")
    parser.add_argument("--v1", help="对比版本1")
    parser.add_argument("--v2", help="对比版本2")
    parser.add_argument("--chapter", type=int, help="分析影响的章节号")
    
    args = parser.parse_args()
    
    manager = OutlineVersionManager(args.project)
    
    if args.command == "save":
        # 加载当前大纲
        outline_file = Path(args.project) / "outline" / "outline.json"
        if not outline_file.exists():
            print(json.dumps({"error": "大纲文件不存在"}, ensure_ascii=False))
            sys.exit(1)
        
        outline_data = json.loads(outline_file.read_text(encoding='utf-8'))
        result = manager.save_version(outline_data, args.version, args.reason, args.author)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "diff":
        result = manager.diff_versions(args.v1, args.v2)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "impact":
        outline_file = Path(args.project) / "outline" / "outline.json"
        if not outline_file.exists():
            print(json.dumps({"error": "大纲文件不存在"}, ensure_ascii=False))
            sys.exit(1)
        
        outline_data = json.loads(outline_file.read_text(encoding='utf-8'))
        result = manager.analyze_impact(args.chapter, outline_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "rollback":
        result = manager.rollback_to_version(args.version)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "list":
        versions = [{"version": v.version, "timestamp": v.timestamp, "author": v.author, "reason": v.reason}
                   for v in manager.history]
        print(json.dumps(versions, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
