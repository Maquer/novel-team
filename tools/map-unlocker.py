#!/usr/bin/env python3
"""
迷雾地图解锁器 — ai-fiction-writer novel-worldbuilding 融合

借鉴 ai-fiction-writer 的动态迷雾地图机制：
地图不是一次性画完的，而是随正文描写逐步解锁的迷雾地图。

层级：
  L0 世界图（全局）—— 项目初始化时解锁
  L1 区域图（省/州/城市集群）—— 正文首次提到
  L2 城市图（单个城市内部）—— 正文首次进入
  L3 场景图（建筑、街道、室内）—— 正文首次描写
  L4 动态细节（场景内物品、人物位置）—— 正文描写到具体细节

用法：
  python3 map-unlocker.py scan --novel-id my-novel --chapter 5 --text "..."
  python3 map-unlocker.py scan --novel-id my-novel --chapter-file ch05.md
  python3 map-unlocker.py confirm --novel-id my-novel --location "东海城" --level L2
  python3 map-unlocker.py suggest --novel-id my-novel
  python3 map-unlocker.py status --novel-id my-novel
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TRACKING_DIR = Path("/var/minis/shared/novel-team/.map-unlocker")

# 地名后缀分类
PLACE_SUFFIXES = {
    'place': ['城', '镇', '村', '庄', '岛', '山', '谷', '渊', '潭', '湖', '河', '江', '海', '峰', '岭', '原'],
    'scene': ['楼', '阁', '殿', '堂', '府', '院', '宫', '寺', '观', '塔', '桥', '门', '巷', '街', '道', '广场'],
    'faction': ['宗', '门', '派', '帮', '盟', '会', '教'],
    'region': ['域', '区', '地带', '境', '界', '地域', '大陆', '半岛', '群岛'],
}
_ALL_SUFFIXES = set()
for suffixes in PLACE_SUFFIXES.values():
    _ALL_SUFFIXES.update(suffixes)

# 动词前缀过滤
VERB_PREFIXES = {'踏入', '来到', '穿过', '走进', '到达', '前往', '进入', '回到', '经过', '走上', '奔向'}

# 常见非地名前缀
NON_PLACE_PREFIXES = {'萧辰', '王执事', '众人', '弟子', '大家', '旁边', '远处', '附近', '繁华', '长街'}


class MapUnlocker:
    """迷雾地图解锁器"""

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.tracking_dir = TRACKING_DIR / novel_id
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.data_path = self.tracking_dir / "map-data.json"
        self.data = self._load()

    def _load(self) -> Dict:
        if self.data_path.exists():
            return json.loads(self.data_path.read_text(encoding='utf-8'))
        return {"novel_id": self.novel_id, "locations": {}, "unlocked": [], "suggestions": [], "history": []}

    def _save(self):
        tmp = self.data_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.data_path)

    def _is_valid_location(self, name: str) -> bool:
        """检查是否是有效的地点名"""
        if len(name) < 2 or len(name) > 6:
            return False
        if not re.match(r'^[\u4e00-\u9fa5]+$', name):
            return False
        if any(name.startswith(vp) for vp in VERB_PREFIXES):
            return False
        if any(name.startswith(np) for np in NON_PLACE_PREFIXES):
            return False
        return True

    def _guess_type(self, name: str) -> str:
        """根据名称推断类型"""
        for ptype, suffixes in PLACE_SUFFIXES.items():
            if name[-1] in suffixes:
                return ptype
        return 'place'

    def _extract_locations(self, text: str) -> List[Tuple[str, str, int]]:
        """从文本中提取地点名称

        策略：按标点分割文本，在每段中查找以地名后缀结尾的词，
        取后缀前2-4字+后缀构成候选名，过滤动词/人名前缀。
        返回：[(地点名, 类型, 在文本中的位置)]
        """
        found = []
        used = set()

        # 按标点分割成若干片段
        segments = re.split(r'([，。！？、；：])', text)
        seg_text = ''.join(segments[::2])  # 只保留文字部分

        for i, ch in enumerate(seg_text):
            if ch not in _ALL_SUFFIXES:
                continue

            # 跳过已使用的位置
            if any(j in used for j in range(max(0, i-5), i+2)):
                continue

            # 向前取1-4字作为候选名（不含后缀）
            for prefix_len in range(1, 5):
                start = max(0, i - prefix_len)
                sub = seg_text[start:i + 1]
                if self._is_valid_location(sub):
                    ptype = self._guess_type(sub)
                    found.append((sub, ptype, start))
                    for j in range(start, i + 1):
                        used.add(j)
                    break

        # 去重：同名只保留最早出现的
        seen = set()
        unique = []
        for name, ptype, pos in sorted(found, key=lambda x: x[2]):
            if name not in seen:
                seen.add(name)
                unique.append((name, ptype, pos))
        return unique

    def scan_chapter(self, chapter_num: int, text: str) -> Dict:
        locations = self._extract_locations(text)
        new_locations = []
        repeated_locations = []

        for name, ptype, pos in locations:
            if name in self.data["locations"]:
                repeated_locations.append({"name": name, "type": ptype,
                    "level": self.data["locations"][name]["level"]})
            else:
                level = {'region': 'L1', 'place': 'L2', 'scene': 'L3', 'faction': 'L1'}.get(ptype, 'L2')
                ctx_start = max(0, pos - 15)
                ctx_end = min(len(text), pos + len(name) + 15)
                self.data["locations"][name] = {
                    "name": name, "type": ptype, "level": level,
                    "status": "pending", "first_mentioned": f"ch{chapter_num:02d}",
                    "context": text[ctx_start:ctx_end].replace('\n', ' '),
                    "added_at": datetime.now().isoformat(),
                }
                new_locations.append({"name": name, "type": ptype, "level": level,
                    "context": text[ctx_start:ctx_end].replace('\n', ' ')})

        self.data["suggestions"] = new_locations
        self._save()
        return {"chapter": chapter_num, "new_locations": new_locations,
                "repeated_locations": repeated_locations, "total_unique": len(self.data["locations"])}

    def confirm_location(self, name: str, level: str = None) -> Optional[Dict]:
        if name not in self.data["locations"]:
            return None
        if level:
            self.data["locations"][name]["level"] = level
        self.data["locations"][name]["status"] = "confirmed"
        self.data["locations"][name]["confirmed_at"] = datetime.now().isoformat()
        if name not in self.data["unlocked"]:
            self.data["unlocked"].append(name)
        self.data["history"].append({"action": "confirm", "location": name,
            "level": level or self.data["locations"][name]["level"],
            "timestamp": datetime.now().isoformat()})
        self._save()
        return self.data["locations"][name]

    def get_status(self) -> Dict:
        confirmed = sum(1 for loc in self.data["locations"].values() if loc["status"] == "confirmed")
        by_level = {}
        for loc in self.data["locations"].values():
            lv = loc.get("level", "L2")
            by_level.setdefault(lv, []).append(loc["name"])
        return {"novel_id": self.novel_id, "total_locations": len(self.data["locations"]),
                "confirmed_locations": confirmed, "pending_suggestions": len(self.data["suggestions"]),
                "by_level": by_level, "locations": self.data["locations"],
                "history": self.data["history"][-20:]}

    def export_markdown(self) -> str:
        s = self.get_status()
        lines = ["# 迷雾地图状态\n", f"**项目**：{s['novel_id']}",
                 f"**总地点**：{s['total_locations']}", f"**已确认**：{s['confirmed_locations']}",
                 f"**待确认**：{s['pending_suggestions']}", ""]
        for level in ["L0", "L1", "L2", "L3", "L4"]:
            locs = s['by_level'].get(level, [])
            if locs:
                lines.append(f"### {level}（{len(locs)} 个）\n")
                for name in sorted(locs):
                    icon = "✅" if name in self.data["unlocked"] else "⬜"
                    lines.append(f"- {icon} {name}")
                lines.append("")
        lines.append("## 全部地点\n")
        for name, info in sorted(self.data["locations"].items()):
            icon = "✅" if info["status"] == "confirmed" else "⬜"
            lines.append(f"- {icon} **{name}**（{info.get('level', 'L2')}）— {info.get('first_mentioned', '?')}")
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="迷雾地图解锁器")
    subparsers = parser.add_subparsers(dest="command")

    p_scan = subparsers.add_parser("scan", help="扫描章节提取地点")
    p_scan.add_argument("--novel-id", required=True)
    p_scan.add_argument("--chapter", "-c", type=int)
    p_scan.add_argument("--text", "-t", help="章节文本")
    p_scan.add_argument("--chapter-file", help="章节文件路径")
    p_scan.add_argument("--json", action="store_true")

    p_confirm = subparsers.add_parser("confirm", help="确认地点解锁")
    p_confirm.add_argument("--novel-id", required=True)
    p_confirm.add_argument("--location", "-l", required=True)
    p_confirm.add_argument("--level", help="层级（L1-L4）")

    p_status = subparsers.add_parser("status", help="查看地图状态")
    p_status.add_argument("--novel-id", required=True)
    p_status.add_argument("--json", action="store_true")

    p_suggest = subparsers.add_parser("suggest", help="导出解锁建议")
    p_suggest.add_argument("--novel-id", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    unlocker = MapUnlocker(args.novel_id)

    if args.command == "scan":
        text = args.text or (Path(args.chapter_file).read_text(encoding='utf-8') if args.chapter_file else "")
        if not text:
            print("❌ 需要 --text 或 --chapter-file")
            sys.exit(1)
        chapter = args.chapter or 1
        result = unlocker.scan_chapter(chapter, text)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n📍 第 {chapter} 章地点扫描结果：")
            if result["new_locations"]:
                print(f"\n发现 {len(result['new_locations'])} 个新地点：")
                for loc in result["new_locations"]:
                    print(f"  📌 {loc['name']}（{loc['level']}）— {loc['context'][:50]}...")
            else:
                print("  无新地点")
            if result["repeated_locations"]:
                print(f"\n重复出现 {len(result['repeated_locations'])} 次：")
                for loc in result["repeated_locations"][:3]:
                    print(f"  📍 {loc['name']}（{loc['level']}）")
            print(f"\n总地点数：{result['total_unique']}")

    elif args.command == "confirm":
        result = unlocker.confirm_location(args.location, args.level)
        if result:
            print(f"✅ 已确认解锁 '{args.location}'（{result.get('level', 'L2')}）")
        else:
            print(f"❌ 未找到地点 '{args.location}'")
            sys.exit(1)

    elif args.command == "status":
        if args.json:
            print(json.dumps(unlocker.get_status(), ensure_ascii=False, indent=2))
        else:
            print(unlocker.export_markdown())

    elif args.command == "suggest":
        suggestions = unlocker.data.get("suggestions", [])
        if not suggestions:
            print("## 地图解锁建议\n\n暂无新的地点需要确认。\n")
        else:
            print("# 地图解锁建议\n")
            for loc in suggestions:
                icon = {"region": "🗺️", "place": "📍", "scene": "🏛️", "faction": "⚔️"}.get(loc["type"], "📌")
                print(f"### {icon} {loc['name']}（{loc['level']}）\n")
                print(f"- **类型**：{loc['type']}")
                print(f"- **上下文**：{loc['context'][:80]}...")
                print(f"- **操作**：`python3 map-unlocker.py confirm --location \"{loc['name']}\"`")
                print("")
        out_path = TRACKING_DIR / args.novel_id / "map-suggestions.md"
        out_path.write_text(unlocker.export_markdown(), encoding='utf-8')
        print(f"\n💾 已保存到：{out_path}")


if __name__ == "__main__":
    main()
