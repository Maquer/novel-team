#!/usr/bin/env python3
# Version: 0.1.0
"""
记忆 Dreaming — 离线记忆固化+去冗余
=====================================

借鉴 MindMemOS (mindscale-noah) 的 dreaming pipeline：让记忆"睡一觉"后
离线整理固化，去除冗余、合并重复、发现矛盾、归档陈旧卡片。

与 auto-learn 的关系：
- auto-learn = 实时蒸馏（对话/笔记 → 新卡片）
- dreaming   = 离线整理（卡片 → 去冗余/合并/归档）

用法:
    # 只出报告（默认，不改数据）
    python3 obsidian-dreaming.py --report

    # 报告 + 建议的具体动作
    python3 obsidian-dreaming.py --report --suggest

    # 执行归档（把陈旧卡片 status 改为 archived）
    python3 obsidian-dreaming.py --archive

    # 执行合并（把重复卡片标记 merged-into，不改文件）
    python3 obsidian-dreaming.py --merge

    # 执行补链接（在相关卡片之间添加双向 wiki-link）
    python3 obsidian-dreaming.py --link

    # 干跑（打印会做什么，不落盘）
    python3 obsidian-dreaming.py --archive --dry-run

    # JSON 输出
    python3 obsidian-dreaming.py --report --json
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
DREAMING_LOG = "/var/minis/shared/.dreaming-log.jsonl"
OBSIDIAN_ROOT = "/var/minis/mounts/loong"

# 关键词表
ARCHIVE_MIN_AGE_DAYS = 21
ARCHIVE_MIN_SCORE = 40
CONTRADICTION_KEYWORDS = {
    "失败": ["成功", "通过", "OK", "✅"],
    "下线": ["上线", "启用", "恢复"],
    "禁用": ["启用", "打开"],
    "删除": ["保留", "恢复"],
    "终止": ["继续", "重启"],
    "错误": ["正确", "修复", "通过"],
    "不支持": ["支持", "可用"],
    "不可用": ["可用", "正常"],
}
# 反向：任何包含"失败"但同卡片另一 claim 包含"成功"→ 矛盾候选
NEGATIVE_PATTERNS = ["失败", "错误", "下线", "禁用", "删除", "终止", "不可用", "不支持", "崩溃"]
POSITIVE_PATTERNS = ["成功", "通过", "可用", "正常", "修复", "启用", "恢复", "上线"]


def load_store():
    if not os.path.exists(KNOWLEDGE_STORE):
        return {"cards": [], "audit_log": []}
    try:
        with open(KNOWLEDGE_STORE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"cards": [], "audit_log": []}


def save_store(store):
    with open(KNOWLEDGE_STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def log_event(event_type, details):
    """追加 dreaming 审计日志（JSONL，便于 grep/tail）"""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        **details,
    }
    with open(DREAMING_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ─────────────────────────────────────────────
# 相似性计算
# ─────────────────────────────────────────────
WIKI_RE = re.compile(r'\[\[([^\]]+)\]\]')
TAG_RE = re.compile(r'#([\w\-/]+)')
TOKEN_RE = re.compile(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}')


def tokenize(text):
    """中英文混合分词（轻量，无外部依赖）"""
    if not text:
        return set()
    tokens = set(TOKEN_RE.findall(text))
    # 去停用词
    stop = {'这个', '那个', '一个', '我们', '他们', '他们', '什么', '怎么', '可以', '能够', '已经', '还是'}
    return {t for t in tokens if t not in stop and len(t) > 1}


def card_text(card):
    """卡片拼接文本用于相似度计算"""
    parts = [card.get('title', '')]
    parts.extend(card.get('claims', []))
    parts.append(card.get('l1_overview', ''))
    parts.append(card.get('content_preview', ''))
    return ' '.join(parts)


def jaccard(a, b):
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def seq_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def detect_tag_redundancy(cards):
    """
    标签冗余：同一标签出现次数远高于平均 → 提示可以合并/删除。
    特别针对 session-commit 这种元数据标签被当作内容标签的情况。
    """
    from collections import Counter
    tag_counter = Counter()
    for c in cards:
        for t in c.get('tags', []):
            tag_counter[t] += 1
    if not tag_counter:
        return []
    total = sum(tag_counter.values())
    unique = len(tag_counter)
    # 冗余信号：单一标签占比 > 20% 或前 3 标签占比 > 50%
    redundancy = []
    for t, n in tag_counter.most_common():
        ratio = n / total
        if ratio >= 0.15:
            redundancy.append({
                "tag": t,
                "count": n,
                "ratio": round(ratio, 3),
                "note": "session-commit/日期类元数据标签，应作为字段而非标签",
            } if ('session-commit' == t or re.match(r'\d{4}-\d{2}-\d{2}', t)) else {
                "tag": t, "count": n, "ratio": round(ratio, 3),
                "note": "高频标签，可考虑作为主要分类字段",
            })
    return {
        "total_tags": total,
        "unique_tags": unique,
        "redundancy_ratio": round(1 - unique/total, 3) if total else 0,
        "high_frequency": redundancy,
    }


def detect_duplicates(cards, threshold=0.25):
    """
    检测近重复卡片：标题+claim 相似度 > threshold。
    返回 [(i, j, score, reason), ...]
    """
    results = []
    n = len(cards)
    texts = [card_text(c) for c in cards]
    tokens = [tokenize(t) for t in texts]

    for i in range(n):
        for j in range(i+1, n):
            jac = jaccard(tokens[i], tokens[j])
            title_sim = seq_ratio(cards[i].get('title',''), cards[j].get('title',''))
            # 同日期优先：都是 daily-log 且日期相同
            si = cards[i].get('source','')
            sj = cards[j].get('source','')
            di = re.search(r'\d{4}-\d{2}-\d{2}', si)
            dj = re.search(r'\d{4}-\d{2}-\d{2}', sj)
            same_date = bool(di and dj and di.group() == dj.group())

            score = jac * 0.7 + title_sim * 0.3
            if same_date:
                score += 0.15  # 同日同主题加分
            if score >= threshold:
                reasons = []
                if same_date: reasons.append("same-date")
                if jac > 0.4: reasons.append(f"jaccard={jac:.2f}")
                if title_sim > 0.6: reasons.append(f"title-sim={title_sim:.2f}")
                results.append({
                    "i": i, "j": j,
                    "card_i": cards[i].get('id',''), "card_j": cards[j].get('id',''),
                    "title_i": cards[i].get('title','')[:60],
                    "title_j": cards[j].get('title','')[:60],
                    "score": round(score, 3),
                    "reasons": reasons,
                })
    return sorted(results, key=lambda x: -x['score'])


def detect_contradictions(cards):
    """
    检测矛盾：同卡片内 negative pattern 与 positive pattern 共现于相近主题。
    或跨卡片：同一"主题词"下，两卡片一正一反。
    """
    results = []
    # 卡片内矛盾
    for c in cards:
        text = card_text(c)
        neg = [w for w in NEGATIVE_PATTERNS if w in text]
        pos = [w for w in POSITIVE_PATTERNS if w in text]
        if neg and pos:
            # 同卡片同时有正反 → 可能记录演进（如"曾经失败，后来修复"），降级为 info
            results.append({
                "type": "intra-card-tension",
                "card": c.get('id',''),
                "title": c.get('title','')[:60],
                "negatives": neg,
                "positives": pos,
                "note": "同卡片含正反表述，可能是演进记录，需人工判断",
            })
    # 跨卡片矛盾：主题词相同，一正一反
    topic_cards = defaultdict(list)
    for c in cards:
        text = card_text(c)
        # 提取主题词（简单：取标题+claim 的中文关键词）
        for w in TOKEN_RE.findall(c.get('title','')):
            topic_cards[w].append(c)
    for topic, cs in topic_cards.items():
        if len(cs) < 2:
            continue
        for i in range(len(cs)):
            for j in range(i+1, len(cs)):
                ti = card_text(cs[i])
                tj = card_text(cs[j])
                ci_neg = any(w in ti for w in NEGATIVE_PATTERNS)
                ci_pos = any(w in ti for w in POSITIVE_PATTERNS)
                cj_neg = any(w in tj for w in NEGATIVE_PATTERNS)
                cj_pos = any(w in tj for w in POSITIVE_PATTERNS)
                if (ci_neg and cj_pos) or (ci_pos and cj_neg):
                    results.append({
                        "type": "cross-card-contradiction",
                        "topic": topic,
                        "card_a": cs[i].get('id',''),
                        "card_b": cs[j].get('id',''),
                        "title_a": cs[i].get('title','')[:60],
                        "title_b": cs[j].get('title','')[:60],
                        "a_polarity": "neg" if ci_neg else "pos",
                        "b_polarity": "neg" if cj_neg else "pos",
                    })
    return results


def detect_stale(cards, min_age_days=ARCHIVE_MIN_AGE_DAYS, min_score=ARCHIVE_MIN_SCORE):
    """陈旧卡片：created 超过 N 天 + score 低 + 状态非 committed"""
    now = datetime.now()
    stale = []
    for c in cards:
        created = c.get('created','')
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created)
        except Exception:
            continue
        age_days = (now - dt).days
        score = c.get('score', 0) or 0
        status = c.get('status', 'draft')
        if age_days >= min_age_days and score < min_score and status in ('approved', 'draft'):
            stale.append({
                "card": c.get('id',''),
                "title": c.get('title','')[:60],
                "age_days": age_days,
                "score": score,
                "status": status,
                "source": c.get('source',''),
            })
    return sorted(stale, key=lambda x: -x['age_days'])


def detect_orphans(cards):
    """孤立卡片：无 wiki-link 出去 + 无其他卡片引用它"""
    title_to_id = {c.get('title',''): c.get('id','') for c in cards}
    # 计算每张卡片的入度和出度
    out_deg = {c.get('id',''): 0 for c in cards}
    in_deg = {c.get('id',''): 0 for c in cards}
    for c in cards:
        text = card_text(c)
        links = WIKI_RE.findall(text)
        out_deg[c.get('id','')] += len(links)
        for link in links:
            if link in title_to_id:
                in_deg[title_to_id[link]] += 1
    orphans = []
    for c in cards:
        cid = c.get('id','')
        if out_deg.get(cid,0) == 0 and in_deg.get(cid,0) == 0:
            orphans.append({
                "card": cid,
                "title": c.get('title','')[:60],
                "out_deg": 0,
                "in_deg": 0,
                "status": c.get('status',''),
            })
    return orphans


def find_link_candidates(cards, min_sim=0.12, top_k=3):
    """
    找到可以加链接的卡片对：相似但还没互链。
    用于补链接动作。
    """
    existing_links = set()
    for c in cards:
        text = card_text(c)
        for link in WIKI_RE.findall(text):
            existing_links.add((c.get('title',''), link))

    n = len(cards)
    texts = [card_text(c) for c in cards]
    tokens = [tokenize(t) for t in texts]
    candidates = []
    for i in range(n):
        for j in range(i+1, n):
            sim = jaccard(tokens[i], tokens[j])
            if sim < min_sim:
                continue
            t_i = cards[i].get('title','')
            t_j = cards[j].get('title','')
            # 已互链？跳过
            if (t_i, t_j) in existing_links or (t_j, t_i) in existing_links:
                continue
            candidates.append({
                "card_i": cards[i].get('id',''),
                "card_j": cards[j].get('id',''),
                "title_i": t_i[:60],
                "title_j": t_j[:60],
                "sim": round(sim, 3),
            })
    return sorted(candidates, key=lambda x: -x['sim'])[:top_k * 10]  # 给足够候选


# ─────────────────────────────────────────────
# 动作
# ─────────────────────────────────────────────
def do_archive(store, stale_cards, dry_run=False):
    """把陈旧卡片 status 改为 archived"""
    if not stale_cards:
        return {"archived": 0, "details": []}
    archived = 0
    details = []
    if not dry_run:
        by_id = {c['id']: c for c in store['cards']}
        for s in stale_cards:
            c = by_id.get(s['card'])
            if not c:
                continue
            old_status = c.get('status','')
            c['status'] = 'archived'
            c['archived_at'] = datetime.now().isoformat(timespec='seconds')
            c['archived_reason'] = f"stale: age={s['age_days']}d score={s['score']}"
            archived += 1
            details.append({"card": c['id'], "title": c.get('title','')[:60],
                            "from_status": old_status, "to_status": "archived"})
            log_event("archive", details[-1])
        save_store(store)
    else:
        archived = len(stale_cards)
        details = [{"would_archive": s['card'], "title": s['title']} for s in stale_cards]
        for s in stale_cards:
            log_event("archive-dry-run", {"card": s['card'], "title": s['title']})
    return {"archived": archived, "details": details}


def do_merge(store, duplicates, keep_highest_score=True, dry_run=False):
    """
    标记重复卡片为 merged-into，指向保留的那张。
    不改文件内容，只改 status。
    """
    if not duplicates:
        return {"merged": 0, "details": []}
    by_id = {c['id']: c for c in store['cards']}
    details = []
    merged = 0
    processed = set()
    for d in duplicates:
        key = (d['card_i'], d['card_j'])
        if key in processed:
            continue
        processed.add(key)
        ci = by_id.get(d['card_i'])
        cj = by_id.get(d['card_j'])
        if not ci or not cj:
            continue
        # 选保留的：score 高的
        if keep_highest_score:
            keep, drop = (ci, cj) if (ci.get('score',0) or 0) >= (cj.get('score',0) or 0) else (cj, ci)
        else:
            keep, drop = ci, cj
        if not dry_run:
            old_status = drop.get('status','')
            drop['status'] = 'merged'
            drop['merged_into'] = keep.get('id','')
            drop['merged_at'] = datetime.now().isoformat(timespec='seconds')
            drop['merge_reason'] = f"dup of {keep.get('title','')[:40]} (sim={d['score']})"
            merged += 1
            entry = {"merged": drop['id'], "keep": keep['id'],
                     "title_merged": drop.get('title','')[:60],
                     "title_keep": keep.get('title','')[:60],
                     "sim": d['score']}
            details.append(entry)
            log_event("merge", entry)
    if not dry_run and details:
        save_store(store)
    return {"merged": merged, "details": details}


def do_link(store, candidates, dry_run=False):
    """
    在相关卡片之间添加双向 wiki-link（追加到 content_preview 尾部）。
    注意：不改 Obsidian 里的 .md 文件，只更新 knowledge-store 的 content_preview 快照。
    """
    if not candidates:
        return {"linked": 0, "details": []}
    by_id = {c['id']: c for c in store['cards']}
    details = []
    linked = 0
    seen = set()
    for cand in candidates:
        key = (cand['card_i'], cand['card_j'])
        if key in seen:
            continue
        seen.add(key)
        ci = by_id.get(cand['card_i'])
        cj = by_id.get(cand['card_j'])
        if not ci or not cj:
            continue
        linked += 1
        entry = {"a": ci['id'], "b": cj['id'],
                 "title_a": ci.get('title','')[:60],
                 "title_b": cj.get('title','')[:60],
                 "sim": cand['sim']}
        if not dry_run:
            add_link_to_card(ci, cj)
            add_link_to_card(cj, ci)
            log_event("link", entry)
        details.append(entry)
    if not dry_run and details:
        save_store(store)
    return {"linked": linked, "details": details}


def add_link_to_card(source, target):
    """给 source 卡片追加指向 target 的 wiki-link"""
    # 更新 content_preview 的尾部
    marker = "\n\n## 相关卡片\n"
    existing = source.get('content_preview','')
    if marker in existing:
        block = existing.split(marker)[1]
        if f"[[{target.get('title','')}]]" not in block:
            existing = existing + f"- [[{target.get('title','')}]]\n"
            source['content_preview'] = existing
    else:
        existing = existing + marker + f"- [[{target.get('title','')}]]\n"
        source['content_preview'] = existing


# ─────────────────────────────────────────────
# 报告
# ─────────────────────────────────────────────
def build_report(store, args):
    cards = store.get('cards', [])
    now = datetime.now()
    report = {
        "generated_at": now.isoformat(timespec='seconds'),
        "stats": {
            "total_cards": len(cards),
            "by_status": dict(Counter(c.get('status','?') for c in cards)),
            "by_type": dict(Counter(c.get('type','?') for c in cards)),
            "by_scope": dict(Counter(c.get('scope','(none)') for c in cards)),
            "cards_with_evidence": sum(1 for c in cards if c.get('evidence')),
        },
    }
    if args.tag_redundancy or args.all:
        report["tag_redundancy"] = detect_tag_redundancy(cards)
    if args.duplicates or args.merge or args.all:
        report["duplicates"] = detect_duplicates(cards, threshold=args.dup_threshold)
    if args.contradictions or args.all:
        report["tensions"] = detect_contradictions(cards)
    if args.stale or args.archive or args.all:
        report["stale"] = detect_stale(cards)
    if args.orphans or args.all:
        report["orphans"] = detect_orphans(cards)
    if args.link_candidates or args.link or args.all:
        report["link_candidates"] = find_link_candidates(cards)
    return report


def print_report(report, as_json=False, dup_threshold=0.25):
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    s = report['stats']
    print(f"\n🌙 记忆 Dreaming 报告 — {report['generated_at']}")
    print(f"   总卡片: {s['total_cards']}")
    print(f"   状态: {s['by_status']}")
    print(f"   类型: {s['by_type']}")
    print(f"   范围: {s['by_scope']}")
    print(f"   有证据: {s['cards_with_evidence']}/{s['total_cards']}")
    print()

    if 'tag_redundancy' in report:
        tr = report['tag_redundancy']
        print(f"🏷️  标签冗余: {tr['total_tags']} tags → {tr['unique_tags']} unique (冗余率 {tr['redundancy_ratio']*100:.0f}%)")
        for h in tr['high_frequency']:
            print(f"   [{h['ratio']*100:.0f}%] {h['tag']} × {h['count']}  — {h['note']}")
        print()

    if 'duplicates' in report:
        dups = report['duplicates']
        print(f"🔁 近重复卡片: {len(dups)} 对 (阈值 {dup_threshold})")
        for d in dups[:10]:
            print(f"   [{d['score']:.2f}] {d['title_i'][:40]}  ↔  {d['title_j'][:40]}")
            print(f"        reasons: {d['reasons']}")
        print()

    if 'tensions' in report:
        cons = report['tensions']
        print(f"⚠️  张力/矛盾: {len(cons)} 条")
        for c in cons[:10]:
            if c['type'] == 'intra-card-tension':
                print(f"   [卡片内张力] {c['title'][:50]}")
                print(f"        正:{c['positives']}  负:{c['negatives']}  (可能是演进记录)")
            else:
                print(f"   [跨卡矛盾] 主题={c['topic']}")
                print(f"        A({c['a_polarity']})={c['title_a'][:40]}")
                print(f"        B({c['b_polarity']})={c['title_b'][:40]}")
        print()

    if 'stale' in report:
        st = report['stale']
        print(f"📉 陈旧卡片: {len(st)} 张 (age≥{ARCHIVE_MIN_AGE_DAYS}d + score<{ARCHIVE_MIN_SCORE} + status≠committed)")
        for s_ in st[:10]:
            print(f"   [{s_['age_days']}d, score={s_['score']}, {s_['status']}] {s_['title'][:55]}")
        print()

    if 'orphans' in report:
        orp = report['orphans']
        print(f"🏝️  孤立卡片: {len(orp)} 张 (无出链+无入链)")
        for o in orp[:10]:
            print(f"   {o['title'][:60]}  [{o['status']}]")
        print()

    if 'link_candidates' in report:
        lc = report['link_candidates']
        print(f"🔗 可补链接: {len(lc)} 对")
        for l in lc[:10]:
            print(f"   [{l['sim']:.2f}] {l['title_i'][:40]}  ↔  {l['title_j'][:40]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="MindMemOS 借鉴：记忆离线 Dreaming — 固化+去冗余")
    parser.add_argument("--report", action="store_true", help="生成检测报告（默认）")
    parser.add_argument("--all", action="store_true", help="检测所有维度")
    parser.add_argument("--tag-redundancy", action="store_true")
    parser.add_argument("--duplicates", action="store_true")
    parser.add_argument("--contradictions", action="store_true",
                        help="检测张力/矛盾（--tensions）")
    parser.add_argument("--stale", action="store_true")
    parser.add_argument("--orphans", action="store_true")
    parser.add_argument("--link-candidates", action="store_true")
    parser.add_argument("--dup-threshold", type=float, default=0.25)
    parser.add_argument("--archive", action="store_true", help="执行归档（改 status）")
    parser.add_argument("--merge", action="store_true", help="执行合并（标记 merged-into）")
    parser.add_argument("--link", action="store_true", help="执行补链接")
    parser.add_argument("--dry-run", action="store_true", help="干跑，不落盘")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--min-age-days", type=int, default=ARCHIVE_MIN_AGE_DAYS)
    parser.add_argument("--min-score", type=int, default=ARCHIVE_MIN_SCORE)
    args = parser.parse_args()

    store = load_store()

    # 默认行为：无参数 = report + all
    if not (args.report or args.archive or args.merge or args.link
            or args.duplicates or args.contradictions or args.stale
            or args.orphans or args.link_candidates or args.all):
        args.report = True
        args.all = True

    report = build_report(store, args)
    if args.report or not (args.archive or args.merge or args.link):
        print_report(report, args.json, dup_threshold=args.dup_threshold)

    if args.archive:
        st = report.get('stale', [])
        r = do_archive(store, st, dry_run=args.dry_run)
        if not args.json:
            print(f"🗂️  归档: {r['archived']} 张" + (" (dry-run)" if args.dry_run else ""))
        log_event("archive-summary", {"count": r['archived'], "dry_run": args.dry_run})

    if args.merge:
        d = report.get('duplicates', [])
        r = do_merge(store, d, dry_run=args.dry_run)
        if not args.json:
            print(f"🔁 合并: {r['merged']} 张" + (" (dry-run)" if args.dry_run else ""))
        log_event("merge-summary", {"count": r['merged'], "dry_run": args.dry_run})

    if args.link:
        lc = report.get('link_candidates', [])
        r = do_link(store, lc, dry_run=args.dry_run)
        if not args.json:
            print(f"🔗 补链接: {r['linked']} 对" + (" (dry-run)" if args.dry_run else ""))
        log_event("link-summary", {"count": r['linked'], "dry_run": args.dry_run})


if __name__ == "__main__":
    main()
