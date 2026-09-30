#!/usr/bin/env python3
"""
无 key 版的 Web 搜索 / 抓取 / 监控 CLI

策略：
  search — 走 cn.bing.com/search（iSH 沙箱里少数能直连的免费搜索源）
  fetch  — curl 抓 HTML → BeautifulSoup 提取正文 → html2text 转 Markdown
  monitor — fetch + 本地 sha256 diff + 快照落盘

零外部 API，零 key。依赖：requests / beautifulsoup4 / html2text（已 apk 安装）。

用法：
  webkit search "query" [--page N]
  webkit fetch  <url> [--selector "main,article"]
  webkit monitor <url> [--label xxx] [--out <dir>]
"""
import os, sys, time, hashlib, json, re
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import html2text

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
H2T = html2text.HTML2Text()
H2T.ignore_images = False
H2T.ignore_links = False
H2T.ignore_emphasis = False
H2T.body_width = 0  # 不折行
H2T.mark_code = True
H2T.mark_list = True

# ============ 搜索 ============

def cmd_search(query: str, page: int = 0) -> str:
    url = f"https://cn.bing.com/search?q={requests.utils.quote(query)}&setlang=zh-cn&setmkt=zh-CN"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    lines = [f"# Bing 搜索结果：{query}\n", f"来源：{url}\n"]

    # 提取主搜索结果（Bing 用 li.b_algo）
    # 注意：某些页面 h2 里没有 <a>（移动端渲染），标题链接是 li 里第 2 个 <a>
    for idx, li in enumerate(soup.select("li.b_algo"), 1):
        h2 = li.find("h2")
        if not h2: continue
        a = h2.find("a")
        if a:
            title = a.get_text(" ", strip=True)
            link = a.get("href", "")
        else:
            # 标题文本直接从 h2 拿；链接取 li 里第 2 个 a（第 1 个是域名链接）
            title = h2.get_text(" ", strip=True)
            all_a = li.find_all("a")
            link = all_a[1].get("href", "") if len(all_a) > 1 else (all_a[0].get("href", "") if all_a else "")
        p = li.find("p")
        snippet = p.get_text(" ", strip=True) if p else ""
        lines.append(f"\n## {idx}. {title}\n")
        lines.append(f"- URL: {link}")
        if snippet:
            lines.append(f"- 摘要: {snippet[:400]}")

    # 提取"资讯"卡片（带时间戳）
    news_items = soup.select("div.b_card.b_ans.b_context.b_contextDefault div.b_topCard a, li.b_algoNews a")
    if news_items:
        lines.append("\n## 带时间戳的资讯\n")
        seen = set()
        for a in news_items[:10]:
            text = a.get_text(" ", strip=True)
            href = a.get("href", "")
            if text and href and href not in seen:
                seen.add(href)
                lines.append(f"- {text[:120]} — {href}")

    return "\n".join(lines)

# ============ 抓取 ============

JUNK_SELECTORS = [
    "script", "style", "nav", "footer", "header", "aside", "form",
    "iframe", "noscript", "[role='navigation']", "[role='banner']",
    "[class*='cookie']", "[class*='banner']", "[class*='advert']",
    "[id*='cookie']", "[id*='consent']", "[id*='advert']",
]

def _extract_body(soup: BeautifulSoup, selector: str = None) -> Tag:
    if selector:
        for sel in selector.split(","):
            sel = sel.strip()
            found = soup.select(sel)
            if found:
                return found[0]
    for cand in ["article", "main", "[role='main']", "#content", "#main"]:
        found = soup.select(cand)
        if found:
            return found[0]
    return soup.find("body") or soup

def _clean_html(tag: Tag) -> str:
    for s in tag.select(", ".join(JUNK_SELECTORS)):
        s.decompose()
    # 移除脚本/样式文本节点
    return str(tag)

def cmd_fetch(url: str, selector: str = None) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30, allow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.find("title").get_text(" ", strip=True) if soup.find("title") else ""
    body = _extract_body(soup, selector)
    html = _clean_html(body)
    md = H2T.handle(html).strip()
    # 折叠多余空行
    md = re.sub(r"\n{3,}", "\n\n", md)
    header = f"# {title}\n\n> 来源：{r.url}\n\n---\n\n"
    return header + md

# ============ 监控 ============

def cmd_monitor(url: str, out_dir: str, label: str = None) -> dict:
    try:
        md = cmd_fetch(url)
    except Exception as e:
        return {"error": f"fetch failed: {e}", "url": url}
    digest = hashlib.sha256(md.encode("utf-8")).hexdigest()
    label = label or hashlib.sha1(url.encode()).hexdigest()[:10]
    os.makedirs(out_dir, exist_ok=True)
    hist_file = os.path.join(out_dir, f"{label}.json")
    if os.path.exists(hist_file):
        hist = json.load(open(hist_file))
        changed = hist["digest"] != digest
        if changed:
            snap = os.path.join(out_dir, f"{label}-{int(time.time())}.md")
            with open(snap, "w") as f: f.write(md)
            hist["history"].insert(0, {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                       "digest": digest, "len": len(md), "snapshot": snap})
            for old in hist["history"][20:]:
                try: os.remove(old["snapshot"])
                except FileNotFoundError: pass
            hist["history"] = hist["history"][:20]
            hist["digest"] = digest
            hist["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(hist_file, "w") as f: json.dump(hist, f, indent=2, ensure_ascii=False)
            return {"changed": True, "label": label, "digest": digest,
                    "len": len(md), "url": url, "history_file": hist_file}
        return {"changed": False, "label": label, "digest": digest, "url": url}
    else:
        snap = os.path.join(out_dir, f"{label}-{int(time.time())}.md")
        with open(snap, "w") as f: f.write(md)
        hist = {"url": url, "label": label, "digest": digest,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "history": [{"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "digest": digest, "len": len(md), "snapshot": snap}]}
        with open(hist_file, "w") as f: json.dump(hist, f, indent=2, ensure_ascii=False)
        return {"changed": True, "label": label, "digest": digest,
                "len": len(md), "url": url, "history_file": hist_file, "first_run": True}

# ============ CLI ============

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "search":
        q = sys.argv[2]
        page = 0
        for a in sys.argv[3:]:
            if a.startswith("--page="): page = int(a.split("=", 1)[1])
        print(cmd_search(q, page))
    elif cmd == "fetch":
        url = sys.argv[2]
        sel = None
        for a in sys.argv[3:]:
            if a.startswith("--selector="): sel = a.split("=", 1)[1]
        print(cmd_fetch(url, sel))
    elif cmd == "monitor":
        url = sys.argv[2]
        out, label = "/var/minis/shared/webkit/monitor", None
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--out":
                i += 1; out = args[i]
            elif a == "--label":
                i += 1; label = args[i]
            elif a.startswith("--out="): out = a.split("=", 1)[1]
            elif a.startswith("--label="): label = a.split("=", 1)[1]
            i += 1
        r = cmd_monitor(url, out, label)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
