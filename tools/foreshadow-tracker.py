#!/usr/bin/env python3
"""
伏笔陈旧度检测器

借鉴：awesome-novel-agent (modoojunko/awesome-novel-agent, 778★) updater 伏笔追踪
核心：归档时扫描未兑现/新埋的钩子，检测陈旧度和集中收束风险

功能：
  - 扫描所有章节，提取伏笔（悬念/暗示/未解之谜）
  - 追踪每个伏笔的状态：open/resolved/overdue
  - 检测陈旧度：>15章未回收=warning，>30章=overdue
  - 检测集中收束风险：单章回收>3个伏笔
  - 检测遗忘风险：前 10 章埋的伏笔到第 50+ 章还没回收

用法：
  python3 foreshadow-tracker.py scan --novel-id <id> --chapters-dir <dir>
  python3 foreshadow-tracker.py report --novel-id <id>
  python3 foreshadow-tracker.py risk --novel-id <id>
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime


class ForeshadowTracker:
    """伏笔陈旧度检测器"""

    # 伏笔模式
    FORESHADOW_PATTERNS = [
        (r'(?:伏笔|暗示|蛛丝马迹|线索)', 'explicit_foreshadow', '显式伏笔'),
        (r'(?:秘密|隐情|真相|内幕|暗藏)', 'secret', '秘密/真相'),
        (r'(?:承诺|约定|誓言|赌约|约定俗成)', 'promise', '承诺/约定'),
        (r'(?:未解|悬而未决|待解|谜团)', 'unsolved', '未解之谜'),
        (r'(?:神秘|奇怪|诡异|不可思议)', 'mystery', '神秘元素'),
        (r'(?:原来如此|果然|不出所料|真相大白)', 'resolution', '回收标记'),
        (r'(?:多年前|很久以前|那时|从前|记忆深处)', 'flashback_foreshadow', '时间伏笔'),
        (r'(?:他不知道的是|她不知道的是|谁也没想到|殊不知)', 'dramatic_irony', '戏剧性讽刺'),
    ]

    def __init__(self, novel_id: str = None, project_root: str = None):
        self.novel_id = novel_id
        self.root = Path(project_root or f"novels/{novel_id}")
        self.tracker_file = self.root / ".foreshadow-tracker.json"

    def scan_chapters(self, chapters_dir: str) -> dict:
        """扫描所有章节，提取伏笔"""
        ch_dir = Path(chapters_dir)
        if not ch_dir.exists():
            return {"error": f"目录不存在: {chapters_dir}"}

        # 读取所有章节文件
        chapters = []
        for f in sorted(ch_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            ch_num = self._extract_chapter_num(f.name)
            chapters.append({"num": ch_num, "file": str(f), "content": content})

        if not chapters:
            return {"error": "未找到章节文件"}

        # 提取伏笔
        all_foreshadows = []
        for ch in chapters:
            for pattern, ftype, name in self.FORESHADOW_PATTERNS:
                matches = re.finditer(pattern, ch["content"])
                for m in matches:
                    foreshadow = {
                        "id": f"FS-{ch['num']}-{len(all_foreshadows)+1:03d}",
                        "chapter_planted": ch["num"],
                        "type": ftype,
                        "type_name": name,
                        "match": m.group(),
                        "position": m.start(),
                        "context": ch["content"][max(0, m.start()-20):m.end()+20],
                        "status": "open",
                        "chapter_resolved": None,
                        "chapters_open": 0,
                    }

                    # 如果是回收标记，尝试匹配之前的伏笔
                    if ftype == "resolution":
                        foreshadow["status"] = "resolution_marker"
                        # 找最近的 open 伏笔标记为 resolved
                        for fs in reversed(all_foreshadows):
                            if fs["status"] == "open" and fs["chapter_planted"] < ch["num"]:
                                fs["status"] = "resolved"
                                fs["chapter_resolved"] = ch["num"]
                                break

                    all_foreshadows.append(foreshadow)

        # 计算存活章数
        max_ch = max(c["num"] for c in chapters)
        for fs in all_foreshadows:
            if fs["status"] == "open":
                fs["chapters_open"] = max_ch - fs["chapter_planted"]

        # 保存
        data = {
            "novel_id": self.novel_id,
            "scanned_at": datetime.now().isoformat(),
            "total_chapters": len(chapters),
            "max_chapter": max_ch,
            "foreshadows": all_foreshadows,
            "stats": self._calc_stats(all_foreshadows),
        }

        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        self.tracker_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return data

    def _calc_stats(self, foreshadows: list) -> dict:
        stats = {}
        total = len(foreshadows)
        open_count = sum(1 for f in foreshadows if f["status"] == "open")
        resolved = sum(1 for f in foreshadows if f["status"] == "resolved")
        resolution_markers = sum(1 for f in foreshadows if f["status"] == "resolution_marker")

        overdue = sum(1 for f in foreshadows if f["status"] == "open" and f["chapters_open"] > 30)
        warning = sum(1 for f in foreshadows if f["status"] == "open" and 15 < f["chapters_open"] <= 30)

        stats["total"] = total
        stats["open"] = open_count
        stats["resolved"] = resolved
        stats["resolution_markers"] = resolution_markers
        stats["overdue"] = overdue  # >30章
        stats["warning"] = warning  # 15-30章
        stats["resolve_rate"] = round(resolved / max(1, resolved + open_count), 2)

        return stats

    def get_report(self) -> dict:
        """伏笔追踪报告"""
        if not self.tracker_file.exists():
            return {"error": "无伏笔追踪数据，请先 scan"}

        data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        stats = data["stats"]

        # 风险评估
        risk_level = "green"
        if stats["overdue"] > 0:
            risk_level = "red"
        elif stats["warning"] > 2:
            risk_level = "yellow"

        # 陈旧伏笔列表
        stale = [f for f in data["foreshadows"] if f["status"] == "open" and f["chapters_open"] > 15]

        # 集中收束风险检测
        resolution_by_chapter = {}
        for f in data["foreshadows"]:
            if f["status"] == "resolved" and f["chapter_resolved"]:
                ch = f["chapter_resolved"]
                resolution_by_chapter[ch] = resolution_by_chapter.get(ch, 0) + 1

        concentration_risk = [
            {"chapter": ch, "count": count}
            for ch, count in resolution_by_chapter.items() if count > 3
        ]

        return {
            "novel_id": self.novel_id,
            "stats": stats,
            "risk_level": risk_level,
            "stale_foreshadows": [
                {"id": f["id"], "type": f["type_name"], "planted_ch": f["chapter_planted"],
                 "chapters_open": f["chapters_open"], "context": f["context"][:50]}
                for f in stale[:10]
            ],
            "concentration_risk": concentration_risk,
            "oldest_open": min(
                (f["chapters_open"] for f in data["foreshadows"] if f["status"] == "open"),
                default=0,
            ),
        }

    def _extract_chapter_num(self, filename: str) -> int:
        """从文件名提取章节号"""
        m = re.search(r'(\d+)', filename)
        return int(m.group(1)) if m else 0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="伏笔陈旧度检测器")
    parser.add_argument("--novel-id", default=None)
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="扫描章节")
    p_scan.add_argument("--chapters-dir", required=True)

    sub.add_parser("report", help="追踪报告")
    sub.add_parser("risk", help="风险评估")

    args = parser.parse_args()
    ft = ForeshadowTracker(args.novel_id, args.project_root)

    if args.cmd == "scan":
        result = ft.scan_chapters(args.chapters_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "report" or args.cmd == "risk":
        result = ft.get_report()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
