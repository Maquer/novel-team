#!/usr/bin/env python3
"""
TinyFish MCP 客户端 (Minis/iSH 直连版)

底层：直接调 TinyFish 托管 MCP 服务器 https://agent.tinyfish.ai/mcp
协议：MCP Streamable HTTP (JSON-RPC 2.0)
认证：TINYFISH_API_KEY 环境变量，通过 X-API-Key header 发送

支持的 MCP 工具：
  search           — 免费 web 搜索，支持 recency_minutes / after_date / before_date
  fetch_content    — 免费并行抓取最多 10 个 URL，返回干净 Markdown/HTML/JSON
  run_web_automation — 付费浏览器自动化（新用户 600 credits 免费额度）
  get_run / list_runs / cancel_run — 自动化任务管理
  start_browser    — 原始 CDP 浏览器会话（付费）

用法：
  tinyfish search  "query" [--recency-minutes N] [--domain-type web|news|research_paper]
  tinyfish fetch   <url> [url2 ...] [--format markdown|html|json] [--selector "main,article"]
  tinyfish monitor <url> [--interval-minutes 30] [--out <dir>]
  tinyfish doctor
  tinyfish list    # 列出所有 MCP 工具
"""
import json
import os
import sys
import time
import hashlib
import urllib.request
import urllib.error

MCP_URL = "https://agent.tinyfish.ai/mcp"
PROTOCOL_VERSION = "2025-06-18"
CLIENT_NAME = "minis-tinyfish-client"
CLIENT_VERSION = "1.0.0"

# ============ 底层 MCP 客户端 ============

def _headers(api_key: str, session_id: str = None) -> dict:
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "X-API-Key": api_key,
        "X-TF-Request-Origin": CLIENT_NAME,
        "X-TF-Client-Name": CLIENT_NAME,
        "X-TF-Client-Version": CLIENT_VERSION,
    }
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h

def _post(payload: dict, api_key: str, session_id: str = None):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(MCP_URL, data=body, headers=_headers(api_key, session_id), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            sid = resp.headers.get("Mcp-Session-Id") or session_id
            data = resp.read()
            return _decode_sse_or_json(data), sid
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}")

def _decode_sse_or_json(data: bytes):
    txt = data.decode("utf-8", errors="replace").strip()
    if not txt:
        return None
    if txt.startswith("event:") or txt.startswith("data:"):
        # SSE: 拼接所有 data: 行
        buf = []
        for line in txt.split("\n"):
            if line.startswith("data:"):
                buf.append(line[5:].strip())
        raw = "\n".join(buf)
        if not raw:
            return None
        return json.loads(raw)
    return json.loads(txt)

class Client:
    def __init__(self, api_key: str):
        self.key = api_key
        self.sid = None
        # initialize
        result, self.sid = _post(
            {"jsonrpc": "2.0", "id": 0, "method": "initialize",
             "params": {"protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION}}},
            self.key,
        )
        if "error" in result:
            raise RuntimeError(f"initialize failed: {result['error']}")
        # initialized 通知
        try:
            _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.key, self.sid)
        except Exception:
            pass

    def list_tools(self):
        result, _ = _post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, self.key, self.sid)
        if "error" in result:
            raise RuntimeError(f"tools/list failed: {result['error']}")
        return result["result"]["tools"]

    def call(self, tool: str, args: dict) -> dict:
        result, _ = _post(
            {"jsonrpc": "2.0", "id": int(time.time()),
             "method": "tools/call",
             "params": {"name": tool, "arguments": args}},
            self.key, self.sid,
        )
        if "error" in result:
            raise RuntimeError(f"tools/call failed: {result['error']}")
        return result["result"]

# ============ 高层工具 ============

def extract_text(result: dict) -> str:
    """MCP 工具响应 → 可读文本。"""
    parts = []
    for c in result.get("content", []):
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
        else:
            parts.append(json.dumps(c, ensure_ascii=False, indent=2))
    return "\n".join(parts)

def cmd_search(c: Client, query: str, **kw) -> dict:
    args = {"query": query}
    if kw.get("recency_minutes"): args["recency_minutes"] = int(kw["recency_minutes"])
    if kw.get("domain_type"): args["domain_type"] = kw["domain_type"]
    if kw.get("location"): args["location"] = kw["location"]
    if kw.get("language"): args["language"] = kw["language"]
    if kw.get("after_date"): args["after_date"] = kw["after_date"]
    if kw.get("before_date"): args["before_date"] = kw["before_date"]
    if kw.get("include_thumbnail"): args["include_thumbnail"] = str(kw["include_thumbnail"]).lower()
    if kw.get("page"): args["page"] = int(kw["page"])
    if kw.get("purpose"): args["purpose"] = kw["purpose"]
    return c.call("search", args)

def cmd_fetch(c: Client, urls: list, fmt: str = "markdown", selectors: str = None) -> dict:
    args = {"urls": urls, "format": fmt}
    if selectors:
        args["include_selectors"] = [s.strip() for s in selectors.split(",")]
    return c.call("fetch_content", args)

def cmd_list(c: Client) -> list:
    return c.list_tools()

def cmd_monitor(c: Client, url: str, out_dir: str, label: str = None) -> dict:
    """单次抓取 + 本地 diff 检查。返回 {'changed': bool, 'summary': str, 'text': str}。"""
    result = c.call("fetch_content", {"urls": [url], "format": "markdown"})
    text = extract_text(result)
    # 尝试提取 markdown 主体（若 MCP 返回 JSON 结构）
    try:
        j = json.loads(text)
        item = j.get("results", [{}])[0] if isinstance(j, dict) else {}
        md = item.get("text") or item.get("markdown") or text
    except Exception:
        md = text
    md = (md or "").strip()
    digest = hashlib.sha256(md.encode("utf-8")).hexdigest()
    os.makedirs(out_dir, exist_ok=True)
    label = label or hashlib.sha1(url.encode()).hexdigest()[:10]
    hist_file = os.path.join(out_dir, f"{label}.json")
    if os.path.exists(hist_file):
        hist = json.load(open(hist_file))
        changed = hist["digest"] != digest
        if changed:
            hist["history"].insert(0, {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                       "digest": digest,
                                       "len": len(md),
                                       "snapshot": os.path.join(out_dir, f"{label}-{int(time.time())}.md")})
            with open(hist["history"][0]["snapshot"], "w") as f: f.write(md)
            # 只保留最近 20 次快照
            for old in hist["history"][20:]:
                try: os.remove(old["snapshot"])
                except FileNotFoundError: pass
            hist["history"] = hist["history"][:20]
            hist["digest"] = digest
            hist["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(hist_file, "w") as f: json.dump(hist, f, indent=2, ensure_ascii=False)
            return {"changed": True, "label": label, "digest": digest,
                    "len": len(md), "url": url, "history_file": hist_file}
        else:
            return {"changed": False, "label": label, "digest": digest, "url": url}
    else:
        os.makedirs(out_dir, exist_ok=True)
        first_snap = os.path.join(out_dir, f"{label}-{int(time.time())}.md")
        with open(first_snap, "w") as f: f.write(md)
        hist = {"url": url, "label": label, "digest": digest,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "history": [{"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "digest": digest, "len": len(md), "snapshot": first_snap}]}
        with open(hist_file, "w") as f: json.dump(hist, f, indent=2, ensure_ascii=False)
        return {"changed": True, "label": label, "digest": digest,
                "len": len(md), "url": url, "history_file": hist_file, "first_run": True}

def cmd_doctor(c: Client) -> dict:
    info = {"mcp_url": MCP_URL, "client": CLIENT_NAME, "protocol": PROTOCOL_VERSION, "tools": []}
    for t in c.list_tools():
        info["tools"].append({"name": t["name"], "desc": t.get("description", "")[:120]})
    info["reachable"] = True
    return info

# ============ CLI ============

def _get_key() -> str:
    key = os.environ.get("TINYFISH_API_KEY")
    if not key:
        print(json.dumps({
            "error": "TINYFISH_API_KEY 未设置",
            "how_to_fix": "点这个链接设置：[Set TINYFISH_API_KEY](minis://settings/environments?create_key=TINYFISH_API_KEY&create_value=&create_note=TinyFish%20API%20key%20from%20https://agent.tinyfish.ai)",
            "get_key_at": "https://agent.tinyfish.ai",
        }, ensure_ascii=False, indent=2))
        sys.exit(2)
    return key

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    key = _get_key()
    c = Client(key)

    if cmd == "search":
        query = sys.argv[2]
        kw = {}
        for i, a in enumerate(sys.argv[3:]):
            if a.startswith("--recency-minutes="): kw["recency_minutes"] = a.split("=", 1)[1]
            elif a.startswith("--domain-type="): kw["domain_type"] = a.split("=", 1)[1]
            elif a.startswith("--location="): kw["location"] = a.split("=", 1)[1]
            elif a.startswith("--language="): kw["language"] = a.split("=", 1)[1]
            elif a.startswith("--after-date="): kw["after_date"] = a.split("=", 1)[1]
            elif a.startswith("--before-date="): kw["before_date"] = a.split("=", 1)[1]
            elif a.startswith("--thumbnail="): kw["include_thumbnail"] = a.split("=", 1)[1]
            elif a.startswith("--page="): kw["page"] = a.split("=", 1)[1]
            elif a.startswith("--purpose="): kw["purpose"] = a.split("=", 1)[1]
        r = cmd_search(c, query, **kw)
        print(extract_text(r))
    elif cmd == "fetch":
        urls = sys.argv[2:2 + _count_urls(sys.argv[2:])]
        fmt, sel = "markdown", None
        rest = sys.argv[2 + len(urls):]
        for a in rest:
            if a.startswith("--format="): fmt = a.split("=", 1)[1]
            elif a.startswith("--selector="): sel = a.split("=", 1)[1]
        r = cmd_fetch(c, urls, fmt, sel)
        print(extract_text(r))
    elif cmd == "monitor":
        url = sys.argv[2]
        out_dir, label = "/var/minis/shared/tinyfish/monitor", None
        for a in sys.argv[3:]:
            if a.startswith("--out="): out_dir = a.split("=", 1)[1]
            elif a.startswith("--label="): label = a.split("=", 1)[1]
        r = cmd_monitor(c, url, out_dir, label)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif cmd == "list":
        tools = cmd_list(c)
        for t in tools:
            print(f"{t['name']:24s} {t.get('description','')[:100]}")
    elif cmd == "doctor":
        print(json.dumps(cmd_doctor(c), ensure_ascii=False, indent=2))
    elif cmd == "raw":
        # 透传原始工具调用：tinyfish raw <tool> '<json-args>'
        tool = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        r = c.call(tool, args)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(__doc__)

def _count_urls(args):
    """count positional URL args (stops at first --flag)."""
    n = 0
    for a in args:
        if a.startswith("-"): break
        n += 1
    return n

if __name__ == "__main__":
    main()
