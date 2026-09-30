#!/usr/bin/env python3
"""
角色上下文精准筛选 — 借鉴 Biz Novel Studio 单章上下文筛选机制

核心原则：把本章出场角色和相关世界设定注入 prompt，
不把全部角色塞进 prompt。

用法：
  python char-context-filter.py build --novel-id my-novel --chapter 3
  python char-context-filter.py build --novel-id my-novel --chapter 3 --full
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

BASE_DIR = Path("/var/minis/shared/novel-team")
PROJECTS_DIR = BASE_DIR / "projects"
LEDGER_DIR = BASE_DIR / "ledger"


def load_characters(novel_id: str) -> dict:
    f = PROJECTS_DIR / novel_id / "characters" / f"{novel_id}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"characters": []}


def load_facts(novel_id: str) -> dict:
    f = LEDGER_DIR / novel_id / "facts.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {}


def load_chapter(novel_id: str, chapter_num: int) -> str:
    chap_dir = PROJECTS_DIR / novel_id / "chapters"
    f = chap_dir / f"chapter-{chapter_num:03d}.md"
    if f.exists():
        return f.read_text(encoding="utf-8")
    return ""


def extract_mentions(text: str) -> Set[str]:
    """从章节文本提取可能出现的角色名/关键实体"""
    # 简单关键词匹配（实际应使用 NER）
    mentions = set()
    # 常见角色名模式
    patterns = [
        r"[\u4e00-\u9fa5]{2,4}",  # 2-4字中文
    ]
    for pat in patterns:
        matches = re.findall(pat, text)
        mentions.update(matches[:30])  # 限制数量
    return mentions


def find_relevant_chars(
    novel_id: str, chapter_text: str, all_chars: list
) -> List[Dict]:
    """从全部角色中筛选本章出现的角色"""
    mentions = extract_mentions(chapter_text)
    relevant = []
    related_facts = []

    # 加载最新事实账本
    facts = load_facts(novel_id)

    for char in all_chars:
        cid = char.get("id", "")
        cname = char.get("name", "")
        
        # 直接命中角色名
        if cname in mentions:
            relevant.append(char)
            # 查找相关事实
            for fid, fact in facts.items():
                if cname in fact.get("content", "") or cid in fact.get("id", ""):
                    related_facts.append(fact)

    return relevant, related_facts


def build_context(
    novel_id: str, chapter_num: int, full_mode: bool = False
) -> Dict:
    """
    构建章节上下文。
    full_mode=True 时包含所有相关角色的完整档案。
    full_mode=False 时只包含核心信息摘要。
    """
    chapter_text = load_chapter(novel_id, chapter_num)
    if not chapter_text:
        return {"error": f"未找到第{chapter_num}章"}

    chars_data = load_characters(novel_id)
    all_chars = chars_data.get("characters", [])

    relevant_chars, related_facts = find_relevant_chars(
        novel_id, chapter_text, all_chars
    )

    # 构建上下文结构
    context = {
        "chapter": chapter_num,
        "relevant_characters": [],
        "related_facts": related_facts[:10],  # 限制事实数量
        "world_context": _extract_world_context(novel_id, chapter_text),
    }

    # 根据模式决定角色信息详细程度
    for char in relevant_chars:
        entry = {
            "id": char.get("id", ""),
            "name": char.get("name", ""),
            "role": char.get("role", ""),
            "realm": char.get("realm", ""),
        }
        if full_mode:
            entry.update({
                "personality": char.get("personality", []),
                "appearance": char.get("appearance", {}),
                "goal": char.get("goal", ""),
            })
        context["relevant_characters"].append(entry)

    return context


def _extract_world_context(novel_id: str, chapter_text: str) -> Dict:
    """提取世界观相关上下文"""
    # 简单实现：提取地点/势力关键词
    locations = re.findall(r"(天剑宗|血煞门|逍遥阁|玄天大陆|外门|内门|秘境)", chapter_text)
    factions = set(locations)
    return {
        "mentioned_locations": list(factions),
        "key_settings": ["修炼体系: 淬体→炼气→筑基→金丹→元婴→化神→渡劫"],
    }


def main():
    parser = argparse.ArgumentParser(description="角色上下文精准筛选")
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--full", action="store_true", help="包含完整角色档案")
    args = parser.parse_args()

    result = build_context(args.novel_id, args.chapter, args.full)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser().add_argument("--novel-id").parse_args(["--novel-id", "my-novel"])
    main()
