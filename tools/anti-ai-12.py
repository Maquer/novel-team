#!/usr/bin/env python3
"""
anti-ai-12.py — 去AI味12条创作纪律（借鉴 NovelCraft）

定位说明：
  这是「创作纪律清单」，不是 AI 味检测器。
  用途：写前对照（设定姿态）+ 写后自检（对照反面示例）。
  ⚠️ 不要和 humanizer-check / novel-humanizer 混用——
    后者是量化检测器（lieflat 规则），前者是定性纪律，两者互补但不替代。

使用：
  python anti-ai-12.py check chapter.md      # 写后回看
  python anti-ai-12.py preview               # 显示12条纪律
  python anti-ai-12.py --text "文本"         # 直接检测
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple

# 配置
import json
from pathlib import Path

# 自定义禁词存储路径
CUSTOM_BLACKLIST_PATH = Path("/var/minis/shared/novel-team/.blacklist.json")

# 默认禁词列表（从51mazi借鉴）
DEFAULT_BLACKLIST = [
    "首先", "其次", "再次", "最后",
    "综上所述", "总而言之",
    "不禁", "仿佛", "映入眼帘",
    "心中一凛", "脸色一变", "眸光微凝",
    "淡淡的说", "冷冷地说",
    "一种说不出的", "真正的X是Y", "X的意义在于",
    "对X而言", "一切都在", "她心想", "她意识到",
]

# 加载自定义禁词
def load_custom_blacklist() -> list:
    """加载自定义禁词"""
    if CUSTOM_BLACKLIST_PATH.exists():
        try:
            data = json.loads(CUSTOM_BLACKLIST_PATH.read_text(encoding='utf-8'))
            return data.get("blacklist", [])
        except:
            pass
    return []

# 12条纪律定义
DISCIPLINES = [
    {
        "id": 1,
        "name": "眼前有事",
        "rule": "人物每场只办一件眼下的事。不贴标签，写他在谁面前退让、碰到什么会撒谎。",
        "pattern": r"(善良|聪明|冷漠|温柔|坚强|懦弱).*?(人|性格|气质)",
        "example_bad": "他是一个冷漠的人。",
        "example_good": "他把门关上了。门没锁，但他也没再开。",
    },
    {
        "id": 2,
        "name": "视角细节",
        "rule": "细节跟着人物视角走。紧张的人先看出口，等钱的人盯着手机亮不亮。",
        "pattern": r"房间里有|房间里陈设|墙上挂着|桌上放着",
        "example_bad": "房间里陈设简朴，墙上有斑驳的痕迹。",
        "example_good": "他数了数墙上的裂缝。七条。最长那条能伸进去两根手指。",
    },
    {
        "id": 3,
        "name": "对白做事",
        "rule": "人物说话在试探、遮掩、说服、拖延或保住面子。可以答非所问、说一半。",
        "pattern": r"\"[^\"]+\"\s*[，。！？]\s*\"[^\"]+\"\s*[，。！？]\s*\"[^\"]+\"",
        "example_bad": "\"你昨天去哪了？\"\"我去见了一个朋友，聊了很久。\"",
        "example_good": "他没抬头。\"忙。\"",
    },
    {
        "id": 4,
        "name": "设定后置",
        "rule": "规则等人物碰到再讲。先让读者看见它怎么被使用，再补名字与来历。",
        "pattern": r"(灵力|修为|境界|等级|规则|体系).*(分为|就是|是).*(九阶|三级|四种|五种)",
        "example_bad": "灵力分为九阶，每阶又分三个层次……",
        "example_good": "他攥紧拳头。指甲掐进肉里，但骨头缝里有什么东西松了一下。",
    },
    {
        "id": 5,
        "name": "反乒乓链",
        "rule": "300字内一问一答超过8拍是AI信号。插入动作拍打断节奏。",
        "pattern": r'([「""]?.+?[」""]?[\s\n]*){8,}',
        "example_bad": "连续八轮问答",
        "example_good": "第三轮他站起来倒了杯水。\"明天。\"\"这么急？\"",
    },
    {
        "id": 6,
        "name": "冷开场",
        "rule": "章首用对话或动作顶第一行。避开\"时间标记+场景状态\"式开头。",
        "pattern": r"^清[晨午晚]|^夜[晚深]|^阳光|^月光",
        "example_bad": "清晨的阳光透过窗帘洒进房间。",
        "example_good": "他把手机按掉。第三遍了。",
    },
    {
        "id": 7,
        "name": "硬结尾",
        "rule": "章尾停在动作、物件、完整台词或未解决后果上。避开升华、总结、预告。",
        "pattern": r"(终于明白|真正的.*是|这一夜注定|从这一刻起)",
        "example_bad": "从这一刻起，他终于明白真正的勇气。",
        "example_good": "他站起来。膝盖上沾了两片草叶。他拍了一下，没拍掉。",
    },
    {
        "id": 8,
        "name": "拒微闭环",
        "rule": "300字内不把\"出现→确认→执行→反馈\"四项走齐。留一项给下一场。",
        "pattern": r"收到.*确认.*(立刻|马上|立刻).*约定",
        "example_bad": "他收到消息，确认是老王，立刻回了电话，约定明天见面。",
        "example_good": "手机震了一下。他看了一眼，没回。过了一个小时才打过去。",
    },
    {
        "id": 9,
        "name": "五行卡",
        "rule": "每场写前回答五个问题：人物想办什么？阻力从哪来？演到哪停？哪些不解释？哪条留到下一场？",
        "pattern": "",
        "example_bad": "（自检提示，非自动检测）",
        "example_good": "（自检提示，非自动检测）",
    },
    {
        "id": 10,
        "name": "闲笔有来路",
        "rule": "闲笔必须从当前场景或人物关系长出来。删掉它，这一场的信息/气氛/关系要受损。",
        "pattern": r"树荫挪了|红灯滑进|阳光正好|微风拂面",
        "example_bad": "树荫挪了位置，他看了看时间。",
        "example_good": "他数了一遍瓶子。少了一瓶。上次明明是六个。",
    },
    {
        "id": 11,
        "name": "时间密度",
        "rule": "一章之内至少有一处快、一处慢。动笔前先定本场时间密度。",
        "pattern": r"(收拾了行李|连夜赶路|三天后的傍晚|住进客栈)",
        "example_bad": "他收拾了行李，连夜赶路，三天后的傍晚到了镇上。",
        "example_good": "他把最后一件东西塞进包。带子卡了一下，他解了两次才解开。",
    },
    {
        "id": 12,
        "name": "情感配给",
        "rule": "一场只给一个情绪峰值。峰值之外的感受一行带过。人物最动情时，先让他办手里的事。",
        "pattern": r"(又愤怒又悲伤|难以名状|复杂的心情|百感交集)",
        "example_bad": "他又愤怒又悲伤，心中涌起一股难以名状的情绪。",
        "example_good": "他把请柬折好，塞回信封。手很稳。下楼时扶了一把扶手，才发现扶手是凉的。",
    },
]


class AntiAI12Checker:
    """去AI味12条纪律检查器"""
    
    def __init__(self):
        self.hits: List[Dict] = []
        self.custom_blacklist = load_custom_blacklist()
    
    def check(self, text: str) -> List[Dict]:
        """检查文本是否违反12条纪律"""
        self.hits = []
        
        # 检查12条纪律
        for discipline in DISCIPLINES:
            pattern = discipline.get("pattern", "")
            if not pattern:
                continue
            
            matches = re.findall(pattern, text)
            if matches:
                self.hits.append({
                    "id": discipline["id"],
                    "name": discipline["name"],
                    "rule": discipline["rule"],
                    "matches": len(matches),
                    "example_bad": discipline["example_bad"],
                })
        
        # 检查自定义禁词
        for word in self.custom_blacklist:
            if word in text:
                self.hits.append({
                    "id": "custom",
                    "name": f"自定义禁词: {word}",
                    "rule": "自定义禁词",
                    "matches": text.count(word),
                    "example_bad": word,
                })
        
        return self.hits
    
    def add_blacklist_word(self, word: str):
        """添加自定义禁词"""
        if word not in self.custom_blacklist:
            self.custom_blacklist.append(word)
            self._save_blacklist()
    
    def remove_blacklist_word(self, word: str):
        """移除自定义禁词"""
        if word in self.custom_blacklist:
            self.custom_blacklist.remove(word)
            self._save_blacklist()
    
    def _save_blacklist(self):
        """保存自定义禁词"""
        tmp = CUSTOM_BLACKLIST_PATH.with_suffix('.tmp')
        data = {"blacklist": self.custom_blacklist}
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(CUSTOM_BLACKLIST_PATH)
    
    def get_score(self) -> Tuple[int, int]:
        """返回（命中数, 总条数）"""
        return len(self.hits), len(DISCIPLINES)
    
    def get_level(self) -> str:
        """返回等级"""
        total = len(DISCIPLINES)
        hit_count = len(self.hits)
        
        if hit_count == 0:
            return "✅ 优秀（无AI味信号）"
        elif hit_count <= 2:
            return "🟡 良好（轻微AI味）"
        elif hit_count <= 4:
            return "🟠 一般（明显AI味）"
        else:
            return "🔴 需修改（严重AI味）"
    
    def print_report(self, text: str = ""):
        """打印检查报告"""
        if text:
            self.check(text)
        
        hit_count, total = self.get_score()
        level = self.get_level()
        
        print("\n" + "=" * 60)
        print("📝 去AI味12条纪律检查报告")
        print("=" * 60)
        print(f"命中: {hit_count}/{total}  {level}")
        print("-" * 60)
        
        if self.hits:
            print("\n【命中纪律】")
            for hit in self.hits:
                print(f"\n  {hit['id']}. {hit['name']}")
                print(f"     规则: {hit['rule'][:50]}...")
                print(f"     反面示例: {hit['example_bad']}")
        else:
            print("\n✅ 未发现明显AI味信号")
        
        print("\n" + "-" * 60)
        print("【建议】")
        if hit_count > 0:
            print("  1. 逐条对照反面示例，重写命中段落")
            print("  2. 参考正面示例，保持具体、即时、可感")
            print("  3. 完成后再次运行检查")
        else:
            print("  无需修改，继续保持当前写作风格")
        print("=" * 60)


def cmd_check(args):
    """检查文件"""
    checker = AntiAI12Checker()
    
    if args.file:
        text = Path(args.file).read_text(encoding='utf-8', errors='replace')
        print(f"📄 正在检查: {args.file}")
    elif args.text:
        text = args.text
        print("📝 正在检查文本...")
    else:
        print("❌ 错误: 请提供文件或文本")
        return 1
    
    checker.print_report(text)
    return 0


def cmd_preview(args):
    """预览12条纪律"""
    print("\n=== 去AI味12条纪律 ===\n")
    
    for d in DISCIPLINES:
        print(f"{d['id']}. {d['name']}")
        print(f"   规则: {d['rule'][:60]}...")
        print(f"   反面: {d['example_bad']}")
        print()
    
    # 显示自定义禁词
    checker = AntiAI12Checker()
    if checker.custom_blacklist:
        print("\n=== 自定义禁词 ===\n")
        for word in checker.custom_blacklist:
            print(f"  • {word}")
        print()


def cmd_blacklist(args):
    """管理自定义禁词"""
    checker = AntiAI12Checker()
    
    if args.action == "add":
        checker.add_blacklist_word(args.word)
        print(f"✅ 已添加禁词: {args.word}")
        return 0
    elif args.action == "remove":
        checker.remove_blacklist_word(args.word)
        print(f"✅ 已移除禁词: {args.word}")
        return 0
    elif args.action == "list":
        print(f"\n📋 自定义禁词列表 (共{len(checker.custom_blacklist)}个):\n")
        for i, word in enumerate(checker.custom_blacklist, 1):
            print(f"  {i}. {word}")
        print()
        return 0
    else:
        print("❌ 未知操作")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="去AI味12条纪律检查器（借鉴NovelCraft+51mazi）")
    subparsers = parser.add_subparsers(dest="command")
    
    # check命令
    p_check = subparsers.add_parser("check", help="检查文本")
    p_check.add_argument("file", nargs="?", help="输入文件路径")
    p_check.add_argument("--text", "-t", help="直接输入文本")
    
    # preview命令
    subparsers.add_parser("preview", help="预览12条纪律")
    
    # blacklist命令
    p_bl = subparsers.add_parser("blacklist", help="管理自定义禁词")
    p_bl.add_argument("action", choices=["add", "remove", "list"])
    p_bl.add_argument("--word", "-w", help="禁词（add/remove时使用）")
    
    args = parser.parse_args()
    
    if args.command == "check":
        sys.exit(cmd_check(args))
    elif args.command == "preview":
        cmd_preview(args)
    elif args.command == "blacklist":
        sys.exit(cmd_blacklist(args))
    else:
        parser.print_help()
