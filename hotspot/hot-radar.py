#!/usr/bin/env python3
"""
hot-radar.py — 每日热榜轮询与选题候选池

可用源（09-18 实测 iSH 直连可达）:
  bilibili  B站排行榜   https://api.bilibili.com/x/web-interface/ranking/v2
  douyin    抖音热搜    https://www.douyin.com/aweme/v1/web/hot/search/list/
  weibo     微博热搜    需 --cookie "SUB=...; SUBP=..." 才能拿
  zhihu     知乎热榜    需 --cookie "z_c0=..." 才能拿

命令:
  python3 hot-radar.py snap                              # 抓一次, 写 snapshot-<时间>.json
  python3 hot-radar.py snap --only bilibili,douyin       # 只抓指定源
  python3 hot-radar.py watch --interval 3600 --rounds 24 # 每 1 小时抓一轮, 共 24 轮
  python3 hot-radar.py merge --days 1                    # 合并当日快照, 输出去重后的选题池
  python3 hot-radar.py pool                             # 直接给当日 top 30 (含出现频次/最高热度)
  python3 hot-radar.py feed                              # 追加当日 top 20 到 topics.md (供 AI 评分读)

产出:
  snapshots/*.json            每轮原始快照
  topics.md                   滚动选题池, 供 AI 评分 prompt 消费

设计原则:
  - 只抓结构化热榜, 不做二次爬网页 (避免 iSH 进程收割)
  - 单源失败不影响其他源, 记 status=error
  - 每轮 < 30 秒, 24 轮全跑 < 12 分钟
"""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from curl_cffi import requests as cr
except ImportError:
    sys.exit("需要 curl_cffi: pip install curl_cffi")

TZ = timezone(timedelta(hours=8))
HERE = Path(__file__).parent
SNAP_DIR = HERE / "snapshots"
TOPICS_MD = HERE / "topics.md"
UA = "chrome120"

# ---------------------------------------------------------------- 抓取函数
# 每个 fetch_* 返回 (items, status)
# items 元素: {rank, title, url, hot_value}

def fetch_bilibili(limit=50):
    r = cr.get("https://api.bilibili.com/x/web-interface/ranking/v2",
               params={"rid": 0}, impersonate=UA, timeout=15)
    if r.status_code != 200:
        return [], f"http_{r.status_code}"
    d = r.json()
    if d.get("code") != 0:
        return [], f"api_{d.get('code')}"
    items = []
    for i, it in enumerate(d["data"]["list"][:limit], 1):
        aid = it["aid"]
        bvid = it.get("bvid", "")
        items.append({
            "rank": i,
            "title": it["title"],
            "url": f"https://www.bilibili.com/video/{bvid or aid}",
            "hot_value": it.get("stat", {}).get("view", 0),
        })
    return items, "ok"


def fetch_douyin(limit=50):
    r = cr.get("https://www.douyin.com/aweme/v1/web/hot/search/list/",
               params={"device_platform": "webapp", "aid": 6383, "channel": "channel_pc_web"},
               impersonate=UA, timeout=15,
               headers={"Referer": "https://www.douyin.com/"})
    if r.status_code != 200:
        return [], f"http_{r.status_code}"
    d = r.json()
    if d.get("status_code") != 0:
        return [], f"api_{d.get('status_code')}"
    items = []
    for i, it in enumerate(d.get("data", {}).get("word_list", [])[:limit], 1):
        wid = it.get("event_time", 0)
        items.append({
            "rank": i,
            "title": it.get("word", ""),
            "url": f"https://www.douyin.com/search/{it.get('word','')}",
            "hot_value": it.get("hot_value", 0),
        })
    return items, "ok"


def fetch_weibo(cookie: str, limit=50):
    r = cr.get("https://weibo.com/ajax/side/hotSearch",
               impersonate=UA, timeout=15,
               headers={"Cookie": cookie, "Referer": "https://weibo.com/"})
    if r.status_code != 200:
        return [], f"http_{r.status_code}_cookie_missing_or_expired"
    d = r.json()
    items = []
    for i, it in enumerate(d.get("data", {}).get("realtime", [])[:limit], 1):
        items.append({
            "rank": i,
            "title": it.get("word", ""),
            "url": f"https://s.weibo.com/weibo?q=%23{it.get('word','')}%23",
            "hot_value": it.get("num", 0),
        })
    return items, "ok"


def fetch_zhihu(cookie: str, limit=20):
    r = cr.get("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
               params={"limit": limit}, impersonate=UA, timeout=15,
               headers={"Cookie": cookie, "Referer": "https://www.zhihu.com/"})
    if r.status_code != 200:
        return [], f"http_{r.status_code}_cookie_missing_or_expired"
    d = r.json()
    items = []
    for i, it in enumerate(d[:limit], 1):
        tgt = it.get("target", {})
        mid = tgt.get("id", "")
        items.append({
            "rank": i,
            "title": tgt.get("title", ""),
            "url": f"https://www.zhihu.com/question/{mid}" if mid else "",
            "hot_value": it.get("detail_text", "").split()[-1] if it.get("detail_text") else 0,
        })
    return items, "ok"


SOURCES = {
    "bilibili": fetch_bilibili,
    "douyin":   fetch_douyin,
}  # weibo/zhihu 需要 cookie, 在 main() 里注入


# ---------------------------------------------------------------- 命令
def cmd_snap(args):
    SNAP_DIR.mkdir(exist_ok=True)
    now = datetime.now(TZ)
    ts = now.strftime("%Y%m%d_%H%M%S")
    sources = args.only.split(",") if args.only else list(SOURCES)
    payload = {"fetched_at": now.isoformat(), "sources": {}}

    for name in sources:
        fn = SOURCES.get(name)
        if not fn:
            if name == "weibo" and args.cookie_weibo:
                items, status = fetch_weibo(args.cookie_weibo)
            elif name == "zhihu" and args.cookie_zhihu:
                items, status = fetch_zhihu(args.cookie_zhihu)
            else:
                payload["sources"][name] = {"status": "skipped_no_cookie", "items": []}
                continue
            try:
                items, status = (items, status)
            except Exception as e:
                items, status = [], f"err_{type(e).__name__}"
            payload["sources"][name] = {"status": status, "count": len(items), "items": items}
            continue
        try:
            items, status = fn(limit=args.limit)
            payload["sources"][name] = {"status": status, "count": len(items), "items": items}
        except Exception as e:
            payload["sources"][name] = {"status": f"err_{type(e).__name__}", "items": []}

    path = SNAP_DIR / f"snapshot-{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[{now:%H:%M:%S}] snap → {path.name}")
    for name, s in payload["sources"].items():
        print(f"  {name:9s} {s.get('status'):30s} n={s.get('count', 0)}")
    return path


def cmd_watch(args):
    print(f"watch: interval={args.interval}s rounds={args.rounds} only={args.only}")
    for i in range(1, args.rounds + 1):
        ns = argparse.Namespace(only=args.only, limit=args.limit,
                                cookie_weibo=args.cookie_weibo, cookie_zhihu=args.cookie_zhihu)
        cmd_snap(ns)
        if i < args.rounds:
            print(f"  sleeping {args.interval}s …")
            time.sleep(args.interval)
    print("watch done")


def _load_day(day_str: str | None):
    """加载当日所有快照"""
    SNAP_DIR.mkdir(exist_ok=True)
    target = day_str or datetime.now(TZ).strftime("%Y%m%d")
    return sorted(SNAP_DIR.glob(f"snapshot-{target}_*.json"))


def _aggregate(files):
    """跨轮聚合: 按 title 去重, 记录出现频次/首次/末次/最高热度/来源分布"""
    from collections import defaultdict
    pool = defaultdict(lambda: {"titles": set(), "platforms": set(), "max_hot": 0,
                                 "first_seen": "", "last_seen": "", "ranks": []})
    for f in files:
        data = json.loads(f.read_text())
        ts = data["fetched_at"]
        for src_name, s in data["sources"].items():
            if s.get("status") != "ok":
                continue
            for it in s.get("items", []):
                t = it["title"].strip()
                if not t:
                    continue
                p = pool[t]
                p["titles"].add(t)
                p["platforms"].add(src_name)
                p["max_hot"] = max(p["max_hot"], it.get("hot_value", 0))
                p["ranks"].append({"at": ts, "src": src_name, "rank": it["rank"], "hot": it.get("hot_value", 0)})
                if not p["first_seen"] or ts < p["first_seen"]:
                    p["first_seen"] = ts
                if not p["last_seen"] or ts > p["last_seen"]:
                    p["last_seen"] = ts
    result = []
    for title, info in pool.items():
        result.append({
            "title": title,
            "occurrences": len(info["ranks"]),
            "platforms": sorted(info["platforms"]),
            "max_hot": info["max_hot"],
            "first_seen": info["first_seen"],
            "last_seen": info["last_seen"],
            "detail": info["ranks"],
        })
    # 排序: 出现次数优先(跨轮重复上榜=高热度信号), 再按最高热度, 再按标题
    result.sort(key=lambda x: (-x["occurrences"], -x["max_hot"], x["title"]))
    return result


def cmd_merge(args):
    files = _load_day(args.day)
    if not files:
        print(f"no snapshots for {args.day or 'today'}", file=sys.stderr)
        sys.exit(1)
    agg = _aggregate(files)
    top = agg[:args.top]
    out = HERE / f"merged-{(args.day or datetime.now(TZ).strftime('%Y%m%d'))}.json"
    out.write_text(json.dumps({"day": args.day or datetime.now(TZ).strftime("%Y%m%d"),
                                "snapshots_count": len(files), "pool_size": len(agg), "top": top},
                               ensure_ascii=False, indent=2))
    print(f"merged → {out.name}  pool={len(agg)}  from {len(files)} snapshots")
    for i, x in enumerate(top[:10], 1):
        print(f"  {i:2d}. [{','.join(x['platforms'])}] x{x['occurrences']} {x['title'][:30]}")


def cmd_pool(args):
    files = _load_day(args.day)
    if not files:
        print(f"no snapshots for {args.day or 'today'}.  Run: hot-radar.py snap first.", file=sys.stderr)
        sys.exit(1)
    agg = _aggregate(files)[:args.top]
    for i, x in enumerate(agg, 1):
        print(f"{i:2d}. x{x['occurrences']} [{','.join(x['platforms'])}] {x['title']}")


def cmd_feed(args):
    files = _load_day(args.day)
    if not files:
        print("no snapshots today", file=sys.stderr)
        sys.exit(1)
    agg = _aggregate(files)[:args.top]
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    with TOPICS_MD.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## {now} TOP {len(agg)}\n")
        for x in agg:
            f.write(f"- x{x['occurrences']} [{','.join(x['platforms'])}] {x['title']}\n")
    print(f"appended to {TOPICS_MD}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--only", help="逗号分隔, 例: bilibili,douyin,weibo")
        sp.add_argument("--limit", type=int, default=50)
        sp.add_argument("--cookie-weibo", default=os.environ.get("WEIBO_COOKIE", ""))
        sp.add_argument("--cookie-zhihu", default=os.environ.get("ZHIHU_COOKIE", ""))

    sp = sub.add_parser("snap"); add_common(sp); sp.set_defaults(fn=cmd_snap)
    sp = sub.add_parser("watch"); add_common(sp)
    sp.add_argument("--interval", type=int, default=3600)
    sp.add_argument("--rounds", type=int, default=1)
    sp.set_defaults(fn=cmd_watch)
    sp = sub.add_parser("merge"); sp.add_argument("--day", default=None)
    sp.add_argument("--top", type=int, default=30); sp.set_defaults(fn=cmd_merge)
    sp = sub.add_parser("pool"); sp.add_argument("--day", default=None)
    sp.add_argument("--top", type=int, default=30); sp.set_defaults(fn=cmd_pool)
    sp = sub.add_parser("feed"); sp.add_argument("--day", default=None)
    sp.add_argument("--top", type=int, default=20); sp.set_defaults(fn=cmd_feed)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
