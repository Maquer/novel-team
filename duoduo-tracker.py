#!/usr/bin/env python3
# Version: 0.1.0
"""
多多视频 — 每日执行追踪面板
用法：
  python3 duoduo-tracker.py init               # 初始化数据库
  python3 duoduo-tracker.py log                # 记录今天发布了一条视频
  python3 duoduo-tracker.py log --title "xxx" --category A --product "挂脖风扇" --platform "拼多多"
  python3 duoduo-tracker.py report             # 显示今日/本周报告
  python3 duoduo-tracker.py plan               # 显示今天计划+待办
  python3 duoduo-tracker.py status             # 项目整体状态（第几天/发布数/距30条解锁）
  python3 duoduo-tracker.py suggest            # 智能推荐今天发什么
"""

import json, os, sys, time
from datetime import datetime, timedelta
from collections import Counter

DB_PATH = os.path.expanduser("~/.duoduo-tracker.json")
DEFAULT_PLATFORM = "拼多多"
UNLOCK_THRESHOLD = 30  # 30条后解锁高佣

# ============ 商品池 ============
PRODUCTS = {
    "A": [  # 开学季/宿舍用品
        {"name": "得力文具大礼包", "price": 19.9, "commission": 25, "per": 4.98},
        {"name": "大容量帆布笔袋", "price": 9.9, "commission": 30, "per": 2.97},
        {"name": "桌面增高架", "price": 25, "commission": 25, "per": 6.25},
        {"name": "磁吸酷毙灯", "price": 15, "commission": 30, "per": 4.5},
        {"name": "分层式挂篮", "price": 18, "commission": 25, "per": 4.5},
        {"name": "可折叠床上书桌", "price": 35, "commission": 20, "per": 7},
        {"name": "学生双肩书包", "price": 45, "commission": 20, "per": 9},
        {"name": "宿舍床帘+凉席", "price": 50, "commission": 15, "per": 7.5},
    ],
    "B": [  # 夏季降温
        {"name": "挂脖风扇", "price": 29, "commission": 25, "per": 7.25},
        {"name": "冰丝防晒袖套", "price": 9.9, "commission": 30, "per": 2.97},
        {"name": "冰丝凉席三件套", "price": 45, "commission": 20, "per": 9},
        {"name": "降温喷雾", "price": 19, "commission": 25, "per": 4.75},
        {"name": "便携小风扇", "price": 15, "commission": 30, "per": 4.5},
        {"name": "冰丝凉感坐垫", "price": 25, "commission": 25, "per": 6.25},
        {"name": "宿舍冰感三件套", "price": 40, "commission": 20, "per": 8},
    ],
    "C": [  # 秋季新品
        {"name": "保温杯", "price": 39, "commission": 20, "per": 7.8},
        {"name": "毛绒拖鞋", "price": 25, "commission": 30, "per": 7.5},
        {"name": "收纳凳", "price": 35, "commission": 20, "per": 7},
        {"name": "桌面收纳盒", "price": 19, "commission": 25, "per": 4.75},
        {"name": "暖手宝", "price": 45, "commission": 20, "per": 9},
    ],
}

# ============ 文案模板 ============
TITLES = {
    "A": [
        "开学必备！学生党省钱攻略来了📚",
        "宿舍幸福感拉满！这8样神器必须安排",
        "大一新生必看！学长整理的宿舍好物清单",
        "开学倒计时！最低成本布置学霸房",
        "室友看完都来要链接的宿舍好物😂",
    ],
    "B": [
        "40℃高温救命！出门就靠这几样行走的空调🥵",
        "夏天宿舍没空调？这个神器让你凉快一整夏❄️",
        "不开空调也能降温？省下一个亿电费！",
        "亲测有效！宿舍降温方案，成本不到50块",
        "挂脖风扇选购避坑指南！看完不花冤枉钱",
    ],
    "C": [
        "秋天必备！宿舍保暖神器，用了就不想换",
        "天气转凉了！这些好物让你暖到入冬",
        "收纳控必看！桌面秒变整洁的5个神器",
        "秋天宿舍改造计划！5件物品搞定",
    ],
}

HASHTAGS = {
    "A": ["#开学必备", "#文具推荐", "#学生党", "#宿舍好物", "#开学季"],
    "B": ["#夏日降温", "#宿舍神器", "#好物分享", "#凉感", "#夏天必备"],
    "C": ["#秋季好物", "#宿舍改造", "#保暖神器", "#收纳", "#秋天"],
}


def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
    return {"config": {"start_date": None}, "records": [], "stats": {}}


def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def cmd_init():
    db = load_db()
    db["config"]["start_date"] = today_str()
    db["stats"] = {"total_posts": 0, "total_revenue": 0.0, "categories": {"A": 0, "B": 0, "C": 0}}
    save_db(db)
    print(f"✅ 已初始化，起始日期：{today_str()}")
    print(f"📌 发满 {UNLOCK_THRESHOLD} 条次月解锁高佣选品广场")


def cmd_log(title="", category="A", product="", platform=DEFAULT_PLATFORM, views=0, orders=0, revenue=0.0):
    db = load_db()
    now = datetime.now()
    record = {
        "id": len(db["records"]) + 1,
        "date": today_str(),
        "time": now.strftime("%H:%M"),
        "title": title or f"未命名-产品-{db['stats'].get('total_posts', 0)+1}",
        "category": category,
        "product": product,
        "platform": platform,
        "views": views,
        "orders": orders,
        "revenue": revenue,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    db["records"].append(record)
    db["stats"]["total_posts"] = len(db["records"])
    db["stats"]["total_revenue"] = sum(r.get("revenue", 0) for r in db["records"])
    cat_key = category.upper()
    db["stats"]["categories"][cat_key] = db["stats"]["categories"].get(cat_key, 0) + 1
    save_db(db)
    print(f"✅ 已记录 # {record['id']}：{record['title']} ({category}-{product})")
    remaining = UNLOCK_THRESHOLD - db["stats"]["total_posts"]
    print(f"📊 累计发布：{db['stats']['total_posts']}/{UNLOCK_THRESHOLD}，距解锁高佣还差 {max(0, remaining)} 条")


def cmd_report():
    db = load_db()
    records = db["records"]
    today = today_str()
    today_records = [r for r in records if r["date"] == today]

    print("=" * 40)
    print(f"📊 多多视频报告 | {today}")
    print("=" * 40)

    if not today_records:
        print("⚪ 今天还没发布，开始吧！")
    else:
        print(f"\n📌 今日发布：{len(today_records)} 条")
        for r in today_records:
            rev = f" 佣金¥{r['revenue']}" if r.get("revenue") else ""
            print(f"  #{r['id']:2d} [{r['category']}] {r['product']:<12s} | {r['title'][:20]:<20s}{rev}")

    total = db["stats"]["total_posts"]
    remaining = max(0, UNLOCK_THRESHOLD - total)
    print(f"\n📈 累计发布：{total}/{UNLOCK_THRESHOLD}")
    print(f"💰 累计佣金：¥{db['stats']['total_revenue']:.2f}")

    cats = db["stats"].get("categories", {})
    if cats:
        print(f"📂 品类分布：", end="")
        for k, v in sorted(cats.items()):
            print(f"  {k}:{v}", end="")
        print()

    # 本周数据
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    week_records = [r for r in records if r["date"] >= week_start]
    week_revenue = sum(r.get("revenue", 0) for r in week_records)
    print(f"📅 本周：{len(week_records)} 条 | ¥{week_revenue:.2f}")

    # 距解锁
    if remaining > 0:
        per_day = total / max(1, (datetime.now() - datetime.fromisoformat(db["config"]["start_date"])).days)
        est_days = max(1, int(remaining / max(1, per_day)))
        print(f"⏳ 按当前节奏，约 {est_days} 天后解锁高佣")
    else:
        print(f"🎉 已解锁高佣！")

    print("=" * 40)


def cmd_plan():
    db = load_db()
    records = db["records"]
    today = today_str()
    today_count = len([r for r in records if r["date"] == today])
    total = db["stats"]["total_posts"]
    remaining = max(0, UNLOCK_THRESHOLD - total)

    # 判断项目第几天
    if db["config"]["start_date"]:
        days = (datetime.now() - datetime.fromisoformat(db["config"]["start_date"])).days + 1
    else:
        days = 1

    print("=" * 40)
    print(f"📋 多多视频执行计划 | 第{days}天")
    print("=" * 40)
    print(f"\n📌 今天已发：{today_count} 条")
    print(f"📈 累计：{total}/{UNLOCK_THRESHOLD}")

    if today_count >= 6:
        print(f"\n✅ 今天发布任务已完成！明日继续。")
    else:
        need = 6 - today_count
        print(f"\n⬜ 还需发布：{need} 条（今天目标 6 条）")

    # 推荐品类分布
    print(f"\n🎯 推荐品类组合：")
    cat_a_used = db["stats"]["categories"].get("A", 0)
    cat_b_used = db["stats"]["categories"].get("B", 0)
    cat_c_used = db["stats"]["categories"].get("C", 0)

    cats = [("A", cat_a_used), ("B", cat_b_used), ("C", cat_c_used)]
    cats.sort(key=lambda x: x[1])  # 少发的优先发

    for i, (cat, used) in enumerate(cats):
        pct = used / max(1, total) * 100 if total > 0 else 0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        bar = bar[:10]
        print(f"  品类{cat}：{used:3d}条 {bar} {pct:.0f}%")

    # 今日待办
    print(f"\n⏰ 今日待办：")
    print(f"  □ 上午 10:00-11:30 → 发布 2-3 条（建议品类{cats[0][0]}）")
    print(f"  □ 下午 14:00-15:30 → 发布 2-3 条")
    print(f"  □ 晚上 19:00-21:00 → 发布 2 条 + 数据记录")
    print(f"  □ 21:30 复盘 → python3 duoduo-tracker.py report")

    print("=" * 40)


def cmd_status():
    db = load_db()
    records = db["records"]
    total = db["stats"]["total_posts"]
    remaining = max(0, UNLOCK_THRESHOLD - total)

    if db["config"]["start_date"]:
        start = datetime.fromisoformat(db["config"]["start_date"])
        days = (datetime.now() - start).days + 1
        per_day = total / max(1, days)
    else:
        days = 0
        per_day = 0

    print(f"📊 项目状态：")
    print(f"  启动天数：{days} 天")
    print(f"  总发布数：{total}/{UNLOCK_THRESHOLD}")
    print(f"  日均发布：{per_day:.1f} 条")
    print(f"  距高佣解锁：{remaining} 条")
    if per_day > 0:
        unlock_date = datetime.now() + timedelta(days=max(1, int(remaining/per_day)))
        print(f"  预估解锁日：{unlock_date.strftime('%m-%d')}")
    cats = db["stats"].get("categories", {})
    print(f"  品类分布：{json.dumps(cats)}")
    print(f"  累计佣金：¥{db['stats']['total_revenue']:.2f}")


def cmd_suggest():
    db = load_db()
    total = db["stats"]["total_posts"]
    cats = db["stats"].get("categories", {})
    today = today_str()
    today_count = len([r for r in db["records"] if r["date"] == today])

    # 找出发得最少的品类
    cat_order = sorted(cats.items(), key=lambda x: x[1])
    primary_cat = cat_order[0][0]
    secondary_cat = cat_order[1][0] if len(cat_order) > 1 else "A"

    print(f"🎯 今天建议主推品类：{primary_cat}（已发{cats.get(primary_cat, 0)}条）")
    print(f"   次推：{secondary_cat}（已发{cats.get(secondary_cat, 0)}条）")

    # 推荐商品
    print(f"\n📦 推荐商品（品类{primary_cat}）：")
    for p in PRODUCTS.get(primary_cat, []):
        rev = f"¥{p['per']:.2f}"
        print(f"  {p['name']:<16s} 售价¥{p['price']:>5.1f} 佣金{p['commission']}% 单笔{rev}")

    # 推荐文案
    print(f"\n📝 文案模板（品类{primary_cat}）：")
    for t in TITLES.get(primary_cat, []):
        print(f"  \"{t}\"")

    # 推荐标签
    print(f"\n🏷️ 话题标签：")
    for h in HASHTAGS.get(primary_cat, []):
        print(f"  {h}")

    # 今日发布节奏
    need = max(0, 6 - today_count)
    print(f"\n⏰ 今天还需发布：{need} 条")
    if need > 0:
        print(f"   建议分布：品类{primary_cat} {need} 条")
        print(f"   下午时段可以混合品类{secondary_cat} 1-2 条")

    print()


# ============ CLI 入口 ============
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "init":
        cmd_init()
    elif cmd == "log":
        kwargs = {}
        i = 0
        while i < len(args):
            a = args[i]
            if "=" in a:
                k, v = a.split("=", 1)
                kwargs[k.strip("-")] = v
                i += 1
            elif a.startswith("--"):
                k = a.strip("-")
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    kwargs[k] = args[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        title = kwargs.get("title", "")
        cat = kwargs.get("category", "A").upper()
        product = kwargs.get("product", "")
        platform = kwargs.get("platform", DEFAULT_PLATFORM)
        views = int(kwargs.get("views", 0))
        orders = int(kwargs.get("orders", 0))
        revenue = float(kwargs.get("revenue", 0.0))
        cmd_log(title, cat, product, platform, views, orders, revenue)
    elif cmd == "report":
        cmd_report()
    elif cmd == "plan":
        cmd_plan()
    elif cmd == "status":
        cmd_status()
    elif cmd == "suggest":
        cmd_suggest()
    else:
        print(f"未知命令：{cmd}")
        print(__doc__)
        sys.exit(1)