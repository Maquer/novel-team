#!/usr/bin/env python3
"""
追读力系统

借鉴：webnovel-writer (lingfengQAQ/webnovel-writer, 7302★) v5.3 追读力系统
核心：量化追踪每章的追读力，确保读者持续追更

四维度：
1. Hook（钩子）——章首/章末的吸引力
2. Cool-point（爽点）——让读者"爽"的关键时刻
3. 微兑现——小预期的兑现，保持满足感
4. 债务追踪——未兑现的预期，追踪不让债务过重

用法：
  python3 reading-power.py analyze --novel-id <id> --chapter <N> --content <file>
  python3 reading-power.py report --novel-id <id>
  python3 reading-power.py debt --novel-id <id>  # 查看债务追踪
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime


class ReadingPowerSystem:
    """追读力量化追踪系统"""

    def __init__(self, novel_id: str = None, project_root: str = None):
        self.novel_id = novel_id
        self.root = Path(project_root or f"novels/{novel_id}")
        self.rp_file = self.root / ".reading-power.json"
        self.data = self._load()

    def _load(self):
        if self.rp_file.exists():
            return json.loads(self.rp_file.read_text(encoding="utf-8"))
        return {
            "novel_id": self.novel_id,
            "chapters": {},
            "debt_ledger": [],
            "cumulative_score": 0,
        }

    def _save(self):
        self.rp_file.parent.mkdir(parents=True, exist_ok=True)
        self.rp_file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def analyze_chapter(self, chapter: int, content: str) -> dict:
        """分析单章追读力"""
        result = {
            "chapter": chapter,
            "analyzed_at": datetime.now().isoformat(),
            "hook": self._check_hook(content),
            "cool_point": self._check_cool_point(content),
            "micro_payoff": self._check_micro_payoff(content),
            "debt": self._check_debt(content, chapter),
            "total_score": 0,
        }

        # 计算总分
        scores = [
            result["hook"]["score"],
            result["cool_point"]["score"],
            result["micro_payoff"]["score"],
        ]
        result["total_score"] = sum(scores) / len(scores)

        # 更新债务账本
        for debt in result["debt"]["new_debts"]:
            self.data["debt_ledger"].append({
                "id": f"DEBT-{chapter}-{len(self.data['debt_ledger'])+1:03d}",
                "chapter_planted": chapter,
                "type": debt["type"],
                "desc": debt["desc"],
                "status": "open",
                "chapters_open": 0,
            })

        # 回收债务
        for resolved in result["debt"]["resolved_debts"]:
            for d in self.data["debt_ledger"]:
                if d["id"] == resolved and d["status"] == "open":
                    d["status"] = "resolved"
                    d["chapter_resolved"] = chapter

        # 更新章节记录
        self.data["chapters"][str(chapter)] = result
        self._save()

        return result

    def _check_hook(self, content: str) -> dict:
        """Hook 钩子检测——章首+章末吸引力"""
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if not lines:
            return {"score": 0, "level": "none", "desc": "无内容"}

        # 章首（前 200 字）
        opening = content[:200]
        # 章末（后 200 字）
        ending = content[-200:]

        hook_patterns = [
            (r'[？！]', '悬念/疑问'),
            (r'突然|忽然|猛然|陡然', '突发事件'),
            (r'是谁|为什么|怎么会|到底', '疑问词'),
            (r'不可能|不会吧|怎么会这样', '震惊反应'),
            (r'(?:只|就)在(?:这|那)(?:一|瞬|刻)', '时间定格'),
            (r'然而|但是|不过', '转折'),
            (r'身影|脚步声|声音|光芒', '氛围钩子'),
        ]

        opening_hooks = 0
        ending_hooks = 0
        for pat, name in hook_patterns:
            if re.search(pat, opening):
                opening_hooks += 1
            if re.search(pat, ending):
                ending_hooks += 1

        score = min(100, (opening_hooks + ending_hooks) * 25)
        level = 'strong' if score >= 75 else 'medium' if score >= 50 else 'weak' if score >= 25 else 'none'

        return {
            "score": score,
            "level": level,
            "opening_hooks": opening_hooks,
            "ending_hooks": ending_hooks,
            "desc": f"章首{opening_hooks}个钩子，章末{ending_hooks}个钩子",
        }

    def _check_cool_point(self, content: str) -> dict:
        """Cool-point 爽点检测——让读者"爽"的关键时刻"""
        cool_patterns = [
            (r'(?:打脸|反杀|逆转|翻盘|绝杀)', '反转爽点'),
            (r'(?:装逼|显圣|出手|亮剑|出手)', '实力展示'),
            (r'(?:突破|晋升|进阶|升级|突破境界)', '突破爽点'),
            (r'(?:打斗|交手|对决|拼杀|激战)', '战斗爽点'),
            (r'(?:获得|得到|收获|入手|夺|抢)', '获得爽点'),
            (r'(?:震惊|骇然|倒吸.*凉气|目瞪口呆|不敢相信)', '震惊反应'),
            (r'(?:臣服|跪|膜拜|敬畏|恐惧|颤抖)', '威压爽点'),
        ]

        cool_points = []
        for pat, name in cool_patterns:
            matches = re.finditer(pat, content)
            for m in matches:
                cool_points.append({
                    "type": name,
                    "match": m.group(),
                    "position": m.start(),
                })

        score = min(100, len(cool_points) * 30)
        level = 'strong' if score >= 60 else 'medium' if score >= 30 else 'weak' if score >= 15 else 'none'

        return {
            "score": score,
            "level": level,
            "count": len(cool_points),
            "points": cool_points[:5],
            "desc": f"检测到{len(cool_points)}个爽点",
        }

    def _check_micro_payoff(self, content: str) -> dict:
        """微兑现检测——小预期的兑现"""
        # 微兑现：前面铺垫的小预期在本章得到小满足
        payoff_patterns = [
            (r'(?:终于|总算|好歹|至少).*?(?:成功|做到|完成|得到)', '目标达成'),
            (r'(?:原来|其实|事实是)', '真相揭示'),
            (r'(?:回应|回答|答复)', '问题回应'),
            (r'(?:兑现|履行|遵守|承诺)', '承诺兑现'),
            (r'(?:果然|果真|不出所料)', '预期验证'),
        ]

        payoffs = []
        for pat, name in payoff_patterns:
            matches = re.finditer(pat, content)
            for m in matches:
                payoffs.append({"type": name, "match": m.group(), "position": m.start()})

        score = min(100, len(payoffs) * 25)
        level = 'sufficient' if score >= 50 else 'moderate' if score >= 25 else 'insufficient' if score >= 10 else 'none'

        return {
            "score": score,
            "level": level,
            "count": len(payoffs),
            "payoffs": payoffs[:5],
            "desc": f"检测到{len(payoffs)}个微兑现",
        }

    def _check_debt(self, content: str, chapter: int) -> dict:
        """债务追踪——未兑现的预期"""
        # 新债务：本章埋下的悬念/伏笔
        debt_patterns = [
            (r'(?:不知道|不知道为什么|神秘|奇怪|诡异)', '悬念', 'mystery'),
            (r'(?:伏笔|暗示|线索|蛛丝马迹)', '伏笔', 'foreshadow'),
            (r'(?:承诺|约定|誓言|赌约)', '承诺', 'promise'),
            (r'(?:秘密|隐情|真相|内幕)', '秘密', 'secret'),
            (r'(?:未解|悬而未决|待解)', '未解之谜', 'unsolved'),
        ]

        new_debts = []
        for pat, name, dtype in debt_patterns:
            matches = re.finditer(pat, content)
            for m in matches:
                new_debts.append({
                    "type": dtype,
                    "desc": f"{name}：{m.group()}",
                    "position": m.start(),
                })

        # 检查可回收的旧债务（简化：检查"果然""原来""真相"等是否回收了之前的悬念）
        resolved = []
        resolve_patterns = [r'果然', r'原来', r'真相.*是', r'事实.*是', r'原来如此']
        for pat in resolve_patterns:
            if re.search(pat, content):
                # 标记可能有债务被回收
                for d in self.data["debt_ledger"]:
                    if d["status"] == "open" and d["chapter_planted"] < chapter:
                        resolved.append(d["id"])
                        break

        return {
            "new_debts": new_debts,
            "resolved_debts": resolved[:3],  # 最多标记3个
            "desc": f"新债务{len(new_debts)}个，回收{len(resolved)}个",
        }

    def get_debt_report(self) -> dict:
        """债务追踪报告"""
        open_debts = [d for d in self.data["debt_ledger"] if d["status"] == "open"]
        resolved_debts = [d for d in self.data["debt_ledger"] if d["status"] == "resolved"]

        # 更新债务存活章数
        max_chapter = max(
            int(c) for c in self.data["chapters"].keys()
        ) if self.data["chapters"] else 0

        for d in open_debts:
            d["chapters_open"] = max_chapter - d["chapter_planted"]

        # 风险评估
        risk = "green"
        overdue = [d for d in open_debts if d["chapters_open"] > 30]
        heavy = [d for d in open_debts if d["chapters_open"] > 15]
        if overdue:
            risk = "red"
        elif heavy:
            risk = "yellow"

        return {
            "total_debts": len(self.data["debt_ledger"]),
            "open_debts": len(open_debts),
            "resolved_debts": len(resolved_debts),
            "overdue": len(overdue),  # >30章未回收
            "heavy": len(heavy),      # >15章未回收
            "risk_level": risk,
            "open_debt_list": [
                {"id": d["id"], "type": d["type"], "desc": d["desc"],
                 "planted_ch": d["chapter_planted"], "chapters_open": d["chapters_open"]}
                for d in open_debts
            ],
        }

    def get_report(self) -> dict:
        """完整追读力报告"""
        chapters = []
        for ch_str, data in sorted(self.data["chapters"].items(), key=lambda x: int(x[0])):
            chapters.append({
                "chapter": int(ch_str),
                "total_score": data["total_score"],
                "hook": data["hook"]["level"],
                "cool_point": data["cool_point"]["level"],
                "micro_payoff": data["micro_payoff"]["level"],
            })

        avg_score = sum(c["total_score"] for c in chapters) / len(chapters) if chapters else 0

        # 节奏检查
        rhythm_issues = self._check_rhythm(chapters)

        return {
            "novel_id": self.novel_id,
            "total_chapters": len(chapters),
            "avg_score": round(avg_score, 1),
            "chapters": chapters,
            "debt": self.get_debt_report(),
            "rhythm_issues": rhythm_issues,
        }

    def _check_rhythm(self, chapters: list) -> list:
        """节奏检查——借鉴 awesome-novel-agent 阈值"""
        issues = []
        if len(chapters) < 3:
            return issues

        # 连续高压 >3 章
        high_streak = 0
        for c in chapters:
            if c["total_score"] >= 70:
                high_streak += 1
                if high_streak > 3:
                    issues.append({
                        "type": "连续高压",
                        "desc": f"第{c['chapter']}章：连续{high_streak}章高压，读者可能疲劳",
                        "severity": "warning",
                    })
            else:
                high_streak = 0

        # 连续平淡 >2 章
        low_streak = 0
        for c in chapters:
            if c["total_score"] <= 30:
                low_streak += 1
                if low_streak > 2:
                    issues.append({
                        "type": "连续平淡",
                        "desc": f"第{c['chapter']}章：连续{low_streak}章平淡，读者可能弃书",
                        "severity": "warning",
                    })
            else:
                low_streak = 0

        return issues


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="追读力系统")
    parser.add_argument("--novel-id", default=None)
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="cmd")

    p_analyze = sub.add_parser("analyze", help="分析单章")
    p_analyze.add_argument("--chapter", type=int, required=True)
    p_analyze.add_argument("--content", required=True, help="正文文件路径")

    sub.add_parser("report", help="完整报告")
    sub.add_parser("debt", help="债务追踪")

    args = parser.parse_args()
    rp = ReadingPowerSystem(args.novel_id, args.project_root)

    if args.cmd == "analyze":
        content = Path(args.content).read_text(encoding="utf-8")
        result = rp.analyze_chapter(args.chapter, content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "report":
        result = rp.get_report()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "debt":
        result = rp.get_debt_report()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
