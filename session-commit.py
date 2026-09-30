#!/usr/bin/env python3
# Version: 0.1.0
"""
Session 自动记忆提交 — 借鉴 OpenViking 的 Session Commit 设计。

从 daily log 中提取当日关键决策/发现/偏好，
以结构化格式追加到 knowledge-store，作为长期记忆。

用法:
    python3 session-commit.py                    # 提交今日
    python3 session-commit.py --days 3           # 提交最近3天
    python3 session-commit.py --dry-run          # 预览不写入
    python3 session-commit.py --json             # JSON 输出
"""

import json, os, re, sys, argparse
from pathlib import Path
from datetime import datetime, timedelta

DAILY_LOG_DIR = "/var/minis/memory"
KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
COMMIT_LOG = "/var/minis/shared/.session-commit-log.json"

# 记忆类型分类关键词
TYPE_KWS = {
    "decision": ["决策", "决定", "选择", "决定用", "方案", "策略", "采用", "放弃", "停止"],
    "discovery": ["发现", "发现并", "踩坑", "bug", "修复", "新增", "落地", "部署"],
    "preference": ["偏好", "喜欢", "不喜欢", "习惯", "风格", "要求", "偏好"],
    "insight": ["核心", "原理", "机制", "本质", "关键", "总结", "思考", "反思", "注意"],
    "tool": ["工具", "skill", "脚本", "命令", "pip", "npm", "安装", "配置"],
}

# 提取模式
SECTION_RE = re.compile(r'^##\s+(.+?)$', re.MULTILINE)
BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
BULLET_RE = re.compile(r'^\s*[-*]\s+(.+)$', re.MULTILINE)
DECISION_TABLE_RE = re.compile(r'\|.*\|.*\|.*\|', re.MULTILINE)
CODE_BLOCK_RE = re.compile(r'```.*?```', re.DOTALL)


def _load_store():
    if os.path.exists(KNOWLEDGE_STORE):
        try:
            return json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
        except:
            pass
    return {"cards": [], "pending": []}


def _save_store(store):
    json.dump(store, open(KNOWLEDGE_STORE, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


def _load_commit_log():
    if os.path.exists(COMMIT_LOG):
        try:
            return json.load(open(COMMIT_LOG, 'r', encoding='utf-8'))
        except:
            pass
    return {"commits": [], "stats": {"total": 0}}


def _save_commit_log(log):
    json.dump(log, open(COMMIT_LOG, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


def _read_daily_logs(days=1):
    """读取最近 N 天的 daily log。"""
    logs = []
    for i in range(days):
        d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        fpath = os.path.join(DAILY_LOG_DIR, f"{d}.md")
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            logs.append({"date": d, "content": content, "path": fpath})
    return logs


def _extract_sections(content):
    """提取 ## 标题段落。"""
    # 去除代码块
    clean = CODE_BLOCK_RE.sub('', content)
    sections = []
    parts = SECTION_RE.split(clean)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ''
        sections.append({"title": title, "body": body})
    return sections


def _classify_entry(title, body):
    """根据标题和正文内容分类记忆类型。"""
    text = (title + ' ' + body[:300]).lower()
    scores = {}
    for t, kws in TYPE_KWS.items():
        scores[t] = sum(1 for kw in kws if kw in text)
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return "general"


def _extract_commit_items(log_entry):
    """从一篇 daily log 中提取待提交条目。"""
    items = []
    sections = _extract_sections(log_entry["content"])

    for sec in sections:
        title = sec["title"]
        body = sec["body"]

        if len(body) < 20:
            continue

        # 提取加粗文本（通常包含关键信息）
        bolds = BOLD_RE.findall(body)
        # 提取关键 bullet 点
        bullets = BULLET_RE.findall(body)

        claims = []
        for b in bolds:
            if len(b) >= 4:
                claims.append(b)
        for b in bullets[:3]:
            if len(b) >= 8 and b not in claims:
                claims.append(b)
        # 取第一句作为摘要
        first = body.split('\n')[0].strip()
        if len(first) >= 10 and first not in claims:
            claims.insert(0, first[:100])

        if not claims:
            continue

        mem_type = _classify_entry(title, body)

        items.append({
            "date": log_entry["date"],
            "title": title,
            "type": mem_type,
            "claims": claims[:5],
            "preview": body[:200],
        })

    return items


def commit(days=1, dry_run=False):
    """从 daily log 提取并提交记忆。"""
    logs = _read_daily_logs(days)
    if not logs:
        print("⚠️ 没有找到 daily log")
        return {"processed": 0, "committed": 0}

    store = _load_store()
    commit_log = _load_commit_log()

    # 收集已有卡片索引（避免重复提交）
    existing = set()
    for c in store.get("cards", []):
        if c.get("type") == "memory" and c.get("source", "").startswith("daily-log/"):
            existing.add((c.get("source", ""), c.get("title", "")))

    committed = []
    skipped = 0
    for log_entry in logs:
        items = _extract_commit_items(log_entry)
        for item in items:
            src = f"daily-log/{item['date']}"
            # 去重：同日同标题跳过
            if (src, item["title"]) in existing:
                skipped += 1
                continue

            card = {
                "id": f"SC-{item['date']}-{os.urandom(2).hex()}",
                "title": item["title"],
                "type": "memory",
                "type_label": "记忆",
                "icon": "🧠",
                "claims": item["claims"],
                "tags": ["session-commit", item["date"], item["type"]],
                "source": src,
                "created": datetime.now().isoformat(),
                "status": "committed",
                "score": min(len(item["claims"]) * 15 + len(item["preview"]) // 5, 100),
                "content_preview": item["preview"],
            }

            # 生成 L0/L1
            try:
                from tiering import generate_tiers
                tiers = generate_tiers(item["preview"], item["title"])
                card["l0_abstract"] = tiers["l0_abstract"]
                card["l1_overview"] = tiers["l1_overview"]
            except Exception:
                card["l0_abstract"] = item["title"][:50]
                card["l1_overview"] = item["preview"][:200]

            # ── Grounded Claims: 捕获来源证据 ──
            try:
                from grounded_claims import capture_evidence
                evidence = capture_evidence(card)
                card["evidence"] = evidence
            except Exception:
                pass

            store["cards"].append(card)
            existing.add((src, item["title"]))
            committed.append(card["id"])

            commit_log["commits"].append({
                "id": card["id"],
                "date": item["date"],
                "title": item["title"],
                "type": item["type"],
                "ts": card["created"],
            })

    if not dry_run:
        _save_store(store)
        commit_log["stats"]["total"] = len(commit_log["commits"])
        _save_commit_log(commit_log)

    return {
        "processed": sum(len(_extract_commit_items(l)) for l in logs),
        "committed": len(committed),
        "skipped": skipped,
        "ids": committed[:5],
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description='Session 自动记忆提交')
    parser.add_argument('--days', type=int, default=1, help='扫描最近天数')
    parser.add_argument('--dry-run', action='store_true', help='仅预览')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    parser.add_argument('--status', action='store_true', help='查看提交历史')
    args = parser.parse_args()

    if args.status:
        log = _load_commit_log()
        commits = log.get("commits", [])
        print(f"📋 提交历史: {log['stats']['total']} 条")
        for c in commits[-10:]:
            print(f"  🧠 {c['title'][:30]} [{c['type']}] — {c['date']}")
        sys.exit(0)

    result = commit(days=args.days, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"📚 扫描: 最近 {args.days} 天")
        print(f"📝 提取: {result['processed']} 条记忆")
        print(f"🧠 提交: {result['committed']} 条")
        if result.get('skipped', 0) > 0:
            print(f"⏭️  跳过: {result['skipped']} 条（重复）")
        if result.get('dry_run'):
            print("  [DRY-RUN] 未写入")
        if result.get('ids'):
            for cid in result['ids'][:3]:
                print(f"  🆔 {cid}")


if __name__ == '__main__':
    main()