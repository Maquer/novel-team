#!/usr/bin/env python3
# Version: 0.1.0
"""
session-stamp.py — Minis 会话扫描索引（只读）
把 Minis 会话标题套上 ChatStamp 风格的「MMDD｜类型｜主题」格式，输出可扫列表。

【能力边界】Minis 没有暴露 rename/写标题 API：
  - minis-sessions-cli 只有 list/search/messages/send/retry/status/open（只读+发消息）
  - minis-config 的 session topic 只有 primaryModel/subModel/thinkingLevel
  - chat topic 只有 UI 偏好（autoFocus/FAB/字号/亮屏），无 title 字段
  所以本工具只生成可扫索引，不修改 App 内的真实会话标题。
  要真正改名：用 --names 模式复制名字，粘到 App 会话列表的重命名框。

【设计】沿用 ChatStamp 三选策略的最便宜一档：
  现成标题清晰 → 只套 MMDD｜类型｜ 格式包装（零 LLM、瞬时）。
  类型用关键词表分类（功能/设计/修复/优化/发布/探索/文档/研究）。
  无法判定时兜底「探索」。

用法：
  python3 session-stamp.py                    # 最近 30 条，updated 日期，中文类型
  python3 session-stamp.py --limit 50
  python3 session-stamp.py --date created     # 用创建时间而非最后活跃
  python3 session-stamp.py --names            # 只输出可复制的名字（每行一个）
  python3 session-stamp.py --locale en        # 英文类型
"""
import argparse, json, subprocess, sys
from datetime import datetime

# 类型关键词表（按优先级，先匹配的优先；探索作兜底）
TYPE_RULES_ZH = [
    ("修复", ["修复", "fix", "bug", "报错", "崩溃", "异常", "error", "闪退", "crash", "失败", "排错", "debug", "panic", "traceback", "回滚"]),
    ("发布", ["发布", "推送", "publish", "草稿箱", "草稿", "deploy", "上线", "发版", "发布检查", "直推", "推送草稿"]),
    ("优化", ["优化", "opt", "性能", "refactor", "重构", "省token", "省 token", "提速", "精简", "压缩", "升级", "迭代", "重写", "改写", "v2", "v3", "v4"]),
    ("设计", ["设计", "海报", "封面", "排版", "logo", "配图", "视觉", "风格", "配色", "图标", "design", "插画", "小黑", "logo", "渐变"]),
    ("文档", ["文档", "归档", "笔记", "readme", "记录", "总结", "知识卡片", "撰写", "写一篇", "写文章", "markdown", "归档笔记"]),
    ("研究", ["研究", "调研", "对比", "分析", "research", "评估", "审计", "排查", "审查", "评测", "验证", "dry-run", "dry run", "探查", "摸排"]),
    ("功能", ["功能", "实现", "开发", "添加", "build", "feature", "接入", "集成", "写脚本", "写个", "落地", "部署", "安装", "配置", "造skill", "建skill", "创建skill", "编排"]),
    ("探索", ["探索", "查看", "获取", "了解", "看看", "explore", "看一下", "仓库", "github", "信息", "测试", "查询", "检查", "读取", "读取", "看一下"]),
]
TYPE_MAP_EN = {"修复": "fix", "发布": "release", "优化": "perf", "设计": "design",
               "文档": "docs", "研究": "research", "功能": "feat", "探索": "explore"}

def classify(text):
    """关键词分类类型，返回 zh 类型名；无匹配兜底「探索」。"""
    t = text.lower()
    for typ, kws in TYPE_RULES_ZH:
        for kw in kws:
            if kw in t:
                return typ
    return "探索"

def mmdd(dt_str):
    """'2026-09-06 16:24' -> '0906'。"""
    try:
        dt = datetime.strptime(dt_str[:16], "%Y-%m-%d %H:%M")
        return f"{dt.month:02d}{dt.day:02d}"
    except Exception:
        return "????"

def run_list(limit):
    r = subprocess.run(["minis-sessions-cli", "list", "--limit", str(limit)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("minis-sessions-cli 调用失败: " + r.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    env = json.loads(r.stdout)
    if not env.get("ok"):
        print("list 返回未 ok: " + r.stdout[:200], file=sys.stderr)
        sys.exit(1)
    return env.get("data", {}).get("sessions", [])

def main():
    ap = argparse.ArgumentParser(description="Minis 会话扫描索引（MMDD｜类型｜主题，只读）")
    ap.add_argument("--limit", type=int, default=30, help="最近 N 条（默认 30）")
    ap.add_argument("--date", choices=["updated", "created"], default="updated",
                    help="updated=最后活跃时间(默认), created=创建时间")
    ap.add_argument("--locale", choices=["zh", "en"], default="zh", help="类型语言")
    ap.add_argument("--names", action="store_true", help="只输出可复制名字（每行一个）")
    args = ap.parse_args()

    sessions = run_list(args.limit)
    if not sessions:
        print("无会话记录。", file=sys.stderr)
        return

    rows = []
    for s in sessions:
        date_field = s.get("last_active") if args.date == "updated" else s.get("started_at")
        if not date_field:  # 回退
            date_field = s.get("started_at") or s.get("last_active") or ""
        title = (s.get("title") or "").strip() or "未命名"
        preview = s.get("preview") or ""
        typ = classify(title + " " + preview)
        if args.locale == "en":
            typ = TYPE_MAP_EN.get(typ, "explore")
        stamp = mmdd(date_field)
        name = f"{stamp}｜{typ}｜{title}"
        sid = (s.get("session_id") or "")[:8]
        mc = s.get("message_count", "?")
        rows.append((name, mc, sid))

    if args.names:
        for name, _, _ in rows:
            print(name)
        print(f"\n# 共 {len(rows)} 条 · 复制名字粘到 App 会话重命名框（Minis 无 rename API）", file=sys.stderr)
        return

    print(f"{'MMDD｜类型｜主题':<42} 消息   会话ID")
    print("-" * 72)
    for name, mc, sid in rows:
        print(f"{name:<42} [{mc:>3}]   {sid}")
    print(f"\n共 {len(rows)} 条 · --names 只出名字 · --date created 用创建日期 · --locale en 英文类型")
    print("注：Minis 无 rename API，本工具只读不改标题；改名请复制 --names 输出粘到 App 重命名框。")

if __name__ == "__main__":
    main()
