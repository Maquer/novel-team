#!/usr/bin/env python3
"""
角色档案四档深度 + 形象演变覆盖率扫描

借鉴 Biz Novel Studio 拆书角色档案机制：
  简要 / 标准 / 深入 / 完整 四档深度
  形象演变按 25% / 50% / 75% / 100% 覆盖率增量扫描出场章节

覆盖度阈值：
  简要  ≥10 行
  标准  ≥30 行  
  深入  ≥80 行 + 回溯原文片段
  完整  ≥150 行 + 外貌词条清单 + 形象演变记录

用法：
  python character-depth.py init --novel-id my-novel --char-id char-001
  python character-depth.py scan --novel-id my-novel --char-id char-001
  python character-depth.py depth --novel-id my-novel
  python character-depth.py outline --novel-id my-novel --char-id char-001
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# FIX 2026-10-04：移除天命/my-novel 写死路径，按 --novel-id 动态解析。
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BASE_DIR / "projects"


def characters_dir(novel_id: str) -> Path:
    """按 novel_id 解析角色档案目录（project_guard 约定）。"""
    from project_guard import resolve
    try:
        return resolve(novel_id).root_dir / "characters"
    except Exception:
        return PROJECTS_DIR / novel_id / "characters"

# 四档深度阈值（字符数）
DEPTH_THRESHOLDS = {
    "简要": 100,
    "标准": 300,
    "深入": 800,
    "完整": 1500,
}

# 形象演变覆盖率节点
EVOLUTION_NODES = [0.25, 0.50, 0.75, 1.0]


def characters_file(novel_id: str) -> Path:
    p = CHARACTERS_DIR / f"{novel_id}.json"
    return p if p.parent == CHARACTERS_DIR else CHARACTERS_DIR / f"{novel_id}.json"


def load_characters(novel_id: str) -> dict:
    f = characters_file(novel_id)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"characters": [], "evolution": {}}


def save_characters(novel_id: str, data: dict):
    f = characters_file(novel_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_chapters(novel_id: str) -> list:
    chap_dir = PROJECTS_DIR / novel_id / "chapters"
    chapters = []
    for f in sorted(chap_dir.glob("chapter-*.md")):
        try:
            num = int(f.stem.split("-")[1])
            chapters.append({"num": num, "path": f, "content": f.read_text(encoding="utf-8")})
        except (IndexError, ValueError):
            continue
    return sorted(chapters, key=lambda x: x["num"])


def calc_depth(chars_data: dict) -> dict:
    """计算每个角色的深度等级"""
    results = {}
    for char in chars_data.get("characters", []):
        cid = char["id"]
        content = json.dumps(char, ensure_ascii=False)
        length = len(content)

        level = "简要"
        for lvl, threshold in DEPTH_THRESHOLDS.items():
            if length >= threshold:
                level = lvl

        results[cid] = {
            "name": char.get("name", ""),
            "level": level,
            "length": length,
            "next_threshold": next(
                (t for l, t in DEPTH_THRESHOLDS.items() if t > length), None
            ),
        }
    return results


def scan_evolution(novel_id: str, char_id: str) -> dict:
    """
    按覆盖率节点扫描角色形象演变。
    提取每章中的外貌、服装、状态、场景锚点描述。
    """
    data = load_characters(novel_id)
    chapters = load_chapters(novel_id)
    total = len(chapters)

    if not total:
        return {"error": "无章节文件"}

    # 查找角色
    target = None
    for c in data.get("characters", []):
        if c["id"] == char_id:
            target = c
            break
    if not target:
        return {"error": f"未找到角色 {char_id}"}

    # 按覆盖率节点切分章节
    evolution = {}
    current_node_idx = 0
    node_threshold = EVOLUTION_NODES[0] * total
    current_chapters = []

    for i, ch in enumerate(chapters):
        current_chapters.append(ch)

        # 检查是否到达下一个覆盖率节点
        while (current_node_idx < len(EVOLUTION_NODES)
               and i + 1 >= EVOLUTION_NODES[current_node_idx] * total):
            coverage = EVOLUTION_NODES[current_node_idx]
            node_key = f"{int(coverage*100)}%"
            evolution[node_key] = _extract_appearance(current_chapters, char_id)
            current_node_idx += 1

    # 处理剩余章节（100%覆盖率）
    if current_node_idx < len(EVOLUTION_NODES):
        node_key = f"{int(EVOLUTION_NODES[-1]*100)}%"
        evolution[node_key] = _extract_appearance(current_chapters, char_id)

    return {
        "char_id": char_id,
        "char_name": target.get("name", ""),
        "total_chapters": total,
        "evolution": evolution,
    }


def _extract_appearance(chapters: list, char_id: str) -> dict:
    """从章节列表中提取角色外貌描述"""
    descriptions = []
    for ch in chapters:
        # 简单关键词匹配（实际应使用 NLP）
        content = ch["content"]
        lines = content.split("\n")
        for line in lines:
            if any(kw in line for kw in ["外貌", "穿着", "衣服", "长袍", "头发", 
                                         "眼睛", "面容", "身材", "站姿", "目光"]):
                descriptions.append({
                    "chapter": ch["num"],
                    "line": line.strip()[:100],
                })
    return {
        "appearance_entries": descriptions,
        "entry_count": len(descriptions),
    }


def outline_depth(novel_id: str, char_id: str) -> dict:
    """生成角色档案深度报告 + 补全建议"""
    data = load_characters(novel_id)
    char = None
    for c in data.get("characters", []):
        if c["id"] == char_id:
            char = c
            break
    if not char:
        return {"error": f"未找到角色 {char_id}"}

    content = json.dumps(char, ensure_ascii=False)
    length = len(content)

    # 确定当前档位
    current_level = "简要"
    for lvl, threshold in DEPTH_THRESHOLDS.items():
        if length >= threshold:
            current_level = lvl

    # 生成补全建议
    suggestions = []
    if current_level == "简要":
        suggestions.extend([
            "补充基本属性：年龄、性别、出身",
            "补充性格特征（至少3个）",
            "补充核心目标/驱动力",
        ])
    elif current_level == "标准":
        suggestions.extend([
            "添加历史背景段落",
            "补充与其他角色的关系网络",
            "回溯原文片段补充具体描写",
        ])
    elif current_level == "深入":
        suggestions.extend([
            "建立形象演变时间线（按出场章节记录外貌变化）",
            "补充心理活动描写参考",
            "添加对话风格特征",
        ])
    elif current_level == "完整":
        suggestions.append("档案已完整，可进入创作阶段")

    return {
        "char_id": char_id,
        "char_name": char.get("name", ""),
        "current_level": current_level,
        "length": length,
        "suggestions": suggestions,
    }


def main():
    parser = argparse.ArgumentParser(description="角色档案深度分析")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描角色形象演变")
    p_scan.add_argument("--novel-id", required=True)
    p_scan.add_argument("--char-id", required=True)

    p_depth = sub.add_parser("depth", help="查看所有角色深度评级")
    p_depth.add_argument("--novel-id", required=True)

    p_outline = sub.add_parser("outline", help="生成补全建议")
    p_outline.add_argument("--novel-id", required=True)
    p_outline.add_argument("--char-id", required=True)

    args = parser.parse_args()

    if args.cmd == "scan":
        r = scan_evolution(args.novel_id, args.char_id)
        print(f"形象演变扫描 — {r.get('char_name', args.char_id)}")
        print(f"总章节数: {r.get('total_chapters', 0)}")
        for node, data in r.get("evolution", {}).items():
            print(f"  {node}: {data['entry_count']} 条外貌描写")

    elif args.cmd == "depth":
        data = load_characters(args.novel_id)
        results = calc_depth(data)
        print("角色深度评级：")
        for cid, info in results.items():
            icons = {"简要": "📝", "标准": "📄", "深入": "📚", "完整": "✨"}
            print(f"  {icons.get(info['level'], '?')} [{cid}] {info['name']}: {info['level']} "
                  f"({info['length']}字符)")

    elif args.cmd == "outline":
        r = outline_depth(args.novel_id, args.char_id)
        print(f"补全建议 — {r.get('char_name', args.char_id)}")
        print(f"当前档位: {r['current_level']} ({r['length']}字符)")
        print("补全建议：")
        for s in r["suggestions"]:
            print(f"  • {s}")


if __name__ == "__main__":
    main()
