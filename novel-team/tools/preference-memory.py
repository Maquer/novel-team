#!/usr/bin/env python3
"""
创作记忆系统 — 借鉴 chinese-novelist-skill

核心功能：
  1. 跨会话学习用户偏好
  2. 存储创作习惯
  3. 自动应用偏好到新项目

使用：
  python preference-memory.py --novel-id my-novel --set genre=玄幻
  python preference-memory.py --novel-id my-novel --get
  python preference-memory.py --novel-id my-novel --apply
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


# 配置
PREFERENCE_DIR = Path("/var/minis/shared/novel-team/.preference-memory")
PREFERENCE_DIR.mkdir(parents=True, exist_ok=True)


class PreferenceMemory:
    """创作记忆系统"""
    
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.storage_path = PREFERENCE_DIR / f"{novel_id}.json"
        self.preferences: Dict = self._load()
    
    def _load(self) -> Dict:
        """加载偏好数据"""
        if self.storage_path.exists():
            return json.loads(self.storage_path.read_text(encoding='utf-8'))
        return {
            "novel_id": self.novel_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "genre_preference": [],
            "style_preference": [],
            "chapter_count_preference": None,
            "word_count_preference": None,
            "hook_preference": None,
            "pacing_preference": None,
            "character_type_preference": None,
            "custom_preferences": {},
            "creation_history": [],
        }
    
    def _save(self):
        """保存偏好数据"""
        self.preferences["updated_at"] = datetime.now().isoformat()
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.preferences, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def set_preference(self, key: str, value):
        """设置偏好"""
        if key in self.preferences:
            self.preferences[key] = value
        else:
            self.preferences["custom_preferences"][key] = value
        self._save()
    
    def get_preference(self, key: str) -> Optional[any]:
        """获取偏好"""
        if key in self.preferences:
            return self.preferences[key]
        return self.preferences.get("custom_preferences", {}).get(key)
    
    def record_creation(self, chapter_num: int, word_count: int, status: str = "completed"):
        """记录创作历史"""
        record = {
            "chapter": chapter_num,
            "word_count": word_count,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        self.preferences["creation_history"].append(record)
        self._save()
    
    def get_learning_summary(self) -> Dict:
        """获取学习摘要"""
        history = self.preferences.get("creation_history", [])
        
        if not history:
            return {
                "total_chapters": 0,
                "avg_word_count": 0,
                "completion_rate": 0,
                "preferred_genre": None,
                "preferred_style": None,
            }
        
        # 计算统计
        total_chapters = len(history)
        completed = len([h for h in history if h["status"] == "completed"])
        word_counts = [h["word_count"] for h in history]
        avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
        
        return {
            "total_chapters": total_chapters,
            "completed_chapters": completed,
            "completion_rate": completed / total_chapters if total_chapters > 0 else 0,
            "avg_word_count": int(avg_words),
            "preferred_genre": self.get_preference("genre_preference"),
            "preferred_style": self.get_preference("style_preference"),
        }
    
    def apply_to_project(self, project_config: Dict) -> Dict:
        """将偏好应用到新项目配置"""
        applied = project_config.copy()
        
        # 应用题材偏好
        if self.get_preference("genre_preference"):
            applied["genre"] = self.get_preference("genre_preference")
        
        # 应用风格偏好
        if self.get_preference("style_preference"):
            applied["style"] = self.get_preference("style_preference")
        
        # 应用章节数偏好
        if self.get_preference("chapter_count_preference"):
            applied["target_chapters"] = self.get_preference("chapter_count_preference")
        
        # 应用字数偏好
        if self.get_preference("word_count_preference"):
            applied["target_words"] = self.get_preference("word_count_preference")
        
        return applied
    
    def print_summary(self):
        """打印偏好摘要"""
        summary = self.get_learning_summary()
        
        print("\n=== 创作记忆摘要 ===\n")
        print(f"小说ID: {self.novel_id}")
        print(f"创建时间: {self.preferences['created_at'][:19]}")
        print(f"更新时间: {self.preferences['updated_at'][:19]}")
        print()
        print(f"总章节数: {summary['total_chapters']}")
        print(f"已完成: {summary['completed_chapters']}")
        print(f"完成率: {summary['completion_rate']*100:.1f}%")
        print(f"平均字数: {summary['avg_word_count']:,}")
        print()
        
        if summary['preferred_genre']:
            print(f"偏好题材: {', '.join(summary['preferred_genre'])}")
        if summary['preferred_style']:
            print(f"偏好风格: {summary['preferred_style']}")
        
        print("\n=== 自定义偏好 ===\n")
        for k, v in self.preferences.get("custom_preferences", {}).items():
            print(f"  {k}: {v}")
        print()


def cmd_set(args):
    """设置偏好命令"""
    memory = PreferenceMemory(args.novel_id)
    
    # 解析键值对
    for kv in args.pref:
        if '=' in kv:
            key, value = kv.split('=', 1)
            memory.set_preference(key.strip(), value.strip())
            print(f"✅ 已设置: {key.strip()} = {value.strip()}")
        else:
            print(f"❌ 格式错误: {kv}（应为 key=value）")
            return 1
    
    return 0


def cmd_get(args):
    """获取偏好命令"""
    memory = PreferenceMemory(args.novel_id)
    
    if args.key:
        value = memory.get_preference(args.key)
        if value:
            print(f"{args.key}: {value}")
        else:
            print(f"未设置: {args.key}")
    else:
        memory.print_summary()
    
    return 0


def cmd_apply(args):
    """应用偏好命令"""
    memory = PreferenceMemory(args.novel_id)
    
    # 模拟项目配置
    project_config = {
        "genre": "玄幻",
        "style": "爽文",
        "target_chapters": 30,
        "target_words": 100000,
    }
    
    applied = memory.apply_to_project(project_config)
    
    print("\n=== 应用偏好后的项目配置 ===\n")
    for k, v in applied.items():
        print(f"  {k}: {v}")
    print()
    
    return 0


def cmd_history(args):
    """查看创作历史命令"""
    memory = PreferenceMemory(args.novel_id)
    
    history = memory.preferences.get("creation_history", [])
    
    if not history:
        print("\n暂无创作历史")
        return 0
    
    print(f"\n📊 {args.novel_id} 的创作历史（共{len(history)}条）:\n")
    
    for h in history[-10:]:  # 显示最近10条
        status_icon = "✅" if h["status"] == "completed" else "⏳"
        print(f"  {status_icon} 第{h['chapter']}章 - {h['word_count']:,}字 - {h['timestamp'][:19]}")
    
    print()
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="创作记忆系统（借鉴chinese-novelist-skill）")
    parser.add_argument("--novel-id", "-n", required=True, help="小说ID")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # set命令
    p_set = subparsers.add_parser("set", help="设置偏好")
    p_set.add_argument("--pref", "-p", nargs="+", required=True, help="偏好设置（key=value格式）")
    
    # get命令
    p_get = subparsers.add_parser("get", help="获取偏好")
    p_get.add_argument("--key", "-k", help="偏好键名（不指定则显示摘要）")
    
    # apply命令
    subparsers.add_parser("apply", help="应用偏好到新项目")
    
    # history命令
    p_history = subparsers.add_parser("history", help="查看创作历史")
    
    args = parser.parse_args()
    
    if args.command == "set":
        sys.exit(cmd_set(args))
    elif args.command == "get":
        sys.exit(cmd_get(args))
    elif args.command == "apply":
        sys.exit(cmd_apply(args))
    elif args.command == "history":
        sys.exit(cmd_history(args))
    else:
        parser.print_help()
