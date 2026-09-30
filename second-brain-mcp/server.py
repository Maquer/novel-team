#!/usr/bin/env python3
"""
Minis 第二大脑 MCP Server — Obsidian 知识库 → MCP tools。
外部 AI 工具（Codex/Cursor/Claude Desktop 等）通过 MCP 协议搜索/读取/追溯 Minis 笔记。

协议: MCP JSON-RPC 2.0 over stdio（同步，一行一条消息）
Tools:
  memory_search       — 关键词搜索 Obsidian 笔记
  memory_get          — 读取笔记完整内容
  memory_source       — 获取笔记元数据（出处追溯）
  memory_list_folders — 列出目录结构
"""

import json
import os
import re
import sys
from pathlib import Path

# ── Config ──────────────────────────────────────────────
OBSIDIAN_ROOT = os.environ.get("OBSIDIAN_ROOT", "/var/minis/mounts/loong")
MAX_SCAN_DEPTH = 6
SUMMARY_MAX_CHARS = 400
DEFAULT_TOP = 10
MAX_CONTENT_CHARS = 20000

# ── Obsidian search core ───────────────────────────────

STOP_WORDS = {
    'obsidian', '知识库', '笔记', 'wiki', '笔记库', '查一下', '搜一下', '找一下',
    '看看', '翻一下', '有没有', '搜索', '查找', '查询', '里', '的', '中',
    '一下', '帮我', '给我', '能', '不能', '可以', '请问',
    '关于', '对于', '什么', '怎么', '哪', '哪个', '哪些',
    '东西', '内容', '信息', '资料', '文件', '数据',
}


def extract_query(text):
    cleaned = text
    for sw in STOP_WORDS:
        cleaned = re.sub(re.escape(sw), ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'[^\u4e00-\u9fff\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    chinese = re.findall(r'[\u4e00-\u9fff]{2,}', cleaned)
    if chinese:
        return max(chinese, key=len)[:20]
    english = re.findall(r'[a-zA-Z]{2,}', cleaned)
    if english:
        return max(english, key=len)[:20]
    return cleaned[:20]


def scan_files(root, folder_filter=None, max_depth=MAX_SCAN_DEPTH):
    root_path = Path(root)
    if not root_path.exists():
        return []
    files = []
    start_depth = len(root_path.parts)
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_depth = len(Path(dirpath).parts) - start_depth
        if current_depth >= max_depth:
            dirnames.clear()
            continue
        if folder_filter:
            rel = os.path.relpath(dirpath, root_path)
            if rel == '.':
                pass
            elif rel == folder_filter or rel.startswith(folder_filter + os.sep):
                pass
            elif folder_filter.startswith(rel + os.sep) or folder_filter == rel:
                pass
            else:
                dirnames.clear()
                continue
        for fname in filenames:
            if fname.endswith('.md'):
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, root_path)
                files.append({"path": rel, "full_path": full})
    return files


def search_ob(query, root=OBSIDIAN_ROOT, folder=None, top=DEFAULT_TOP):
    files = scan_files(root, folder)
    tokens = [t for t in re.findall(r'[\u4e00-\u9fff\w]{2,}', query) if t]
    if not tokens:
        tokens = [query]
    results = []
    for f in files:
        try:
            content = open(f["full_path"], 'r', encoding='utf-8', errors='replace').read()
        except (OSError, PermissionError):
            continue
        score = 0
        matched = []
        title = Path(f["path"]).stem
        for token in tokens:
            tc = title.lower().count(token.lower())
            bc = content.lower().count(token.lower())
            cnt = tc * 5 + bc
            if cnt > 0:
                score += cnt
                matched.append(token)
        if score > 0:
            lines = content.split('\n')
            summary_lines = []
            for i, line in enumerate(lines):
                for token in tokens:
                    if token.lower() in line.lower() and len(summary_lines) < 3:
                        start = max(0, i - 1)
                        end = min(len(lines), i + 2)
                        ctx = ' '.join(lines[start:end]).strip()
                        if ctx:
                            summary_lines.append(ctx[:SUMMARY_MAX_CHARS])
                        break
            if not summary_lines:
                summary_lines.append(content[:SUMMARY_MAX_CHARS].replace('\n', ' ').strip())
            results.append({
                "path": f["path"],
                "title": title,
                "score": score,
                "matched": matched,
                "summary": ' | '.join(summary_lines),
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top]


def get_ob(path):
    full = os.path.join(OBSIDIAN_ROOT, path)
    if not Path(full).exists():
        return None, f"File not found: {path}"
    try:
        content = open(full, 'r', encoding='utf-8', errors='replace').read()
        return content, None
    except Exception as e:
        return None, str(e)


def source_ob(path):
    full = os.path.join(OBSIDIAN_ROOT, path)
    if not Path(full).exists():
        return None, f"File not found: {path}"
    stat = os.stat(full)
    try:
        content = open(full, 'r', encoding='utf-8', errors='replace').read()
    except Exception as e:
        return None, str(e)
    frontmatter = {}
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            for line in content[3:end].strip().split('\n'):
                if ':' in line:
                    k, _, v = line.partition(':')
                    frontmatter[k.strip()] = v.strip()
    title = Path(path).stem
    for line in content.split('\n')[:10]:
        if line.startswith('# '):
            title = line[2:].strip()
            break
    parts = Path(path).parts
    folder = "/".join(parts[:-1]) if len(parts) > 1 else "/"
    return {
        "path": path,
        "title": frontmatter.get("title", title),
        "folder": folder,
        "size_bytes": stat.st_size,
        "size_kb": round(stat.st_size / 1024, 1),
        "last_modified": stat.st_mtime,
        "line_count": content.count('\n') + 1,
        "frontmatter_keys": list(frontmatter.keys()),
        "source": "obsidian",
        "source_url": f"obsidian://{path}",
    }, None


def list_folders_ob(depth=3):
    root_path = Path(OBSIDIAN_ROOT)
    if not root_path.exists():
        return []
    folders = []
    start_depth = len(root_path.parts)
    for dirpath, dirnames, filenames in os.walk(root_path):
        current_depth = len(Path(dirpath).parts) - start_depth
        if current_depth >= depth:
            dirnames.clear()
            continue
        rel = os.path.relpath(dirpath, root_path)
        if rel == '.':
            rel = '/'
        folders.append({
            "path": rel,
            "depth": current_depth,
            "files": len([f for f in filenames if f.endswith('.md')]),
        })
    folders.sort(key=lambda x: (x["depth"], x["path"]))
    return folders


# ── MCP Tool Definitions ───────────────────────────────

TOOLS = [
    {
        "name": "memory_search",
        "description": (
            "搜索 Obsidian 知识库笔记。关键词匹配标题和正文，返回最相关结果。"
            "query 支持自然语言（自动提取关键词），folder 限制搜索范围，"
            "top 控制返回数量。返回结果含路径、标题、命中分、摘要。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "folder": {"type": "string", "description": "限制文件夹（如 03-Resources/AI工具）"},
                "top": {"type": "integer", "description": "返回数量", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_get",
        "description": "读取 Obsidian 笔记完整内容。通过相对路径定位。大文件自动截断。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "笔记相对路径（如 03-Resources/AI工具/some.md）"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "memory_source",
        "description": "获取笔记元数据：标题、路径、文件夹、大小、最后修改、行数、frontmatter。用于追溯出处。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "笔记相对路径"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "memory_list_folders",
        "description": "列出 Obsidian 知识库目录结构和各文件夹笔记数。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "depth": {"type": "integer", "description": "目录深度", "default": 3},
            },
        },
    },
]


# ── MCP Server (sync stdio) ────────────────────────────

def send_response(writer, req_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": req_id}
    if error:
        msg["error"] = error
    if result is not None:
        msg["result"] = result
    writer.write(json.dumps(msg, ensure_ascii=False) + "\n")
    writer.flush()


def main():
    stdin = sys.stdin
    stdout = sys.stdout
    initialized = False

    while True:
        try:
            line = stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError, EOFError):
            continue

        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})

        # --- initialize ---
        if method == "initialize":
            send_response(stdout, req_id, result={
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "second-brain-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            })
            initialized = True
            continue

        if method == "notifications/initialized":
            continue

        if not initialized:
            send_response(stdout, req_id, error={
                "code": -32603, "message": "Not initialized"
            })
            continue

        # --- tools/list ---
        if method == "tools/list":
            send_response(stdout, req_id, result={"tools": TOOLS})
            continue

        # --- tools/call ---
        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            text_result = None

            if tool_name == "memory_search":
                query = args.get("query", "")
                folder = args.get("folder")
                top = args.get("top", DEFAULT_TOP)
                if not query:
                    text_result = "Error: query is required"
                else:
                    if len(query) > 20:
                        query = extract_query(query)
                    results = search_ob(query, folder=folder, top=top)
                    if not results:
                        text_result = "未找到匹配的笔记。"
                    else:
                        lines = [f"找到 {len(results)} 条结果："]
                        for i, r in enumerate(results, 1):
                            lines.append(f"\n{'─'*50}")
                            lines.append(f"#{i} {r['title']} (score: {r['score']})")
                            lines.append(f"  📍 {r['path']}")
                            lines.append(f"  🔖 命中: {', '.join(r['matched'])}")
                            lines.append(f"  💡 {r['summary'][:200]}")
                        text_result = "\n".join(lines)

            elif tool_name == "memory_get":
                path = args.get("path", "")
                if not path:
                    text_result = "Error: path is required"
                else:
                    content, error = get_ob(path)
                    if error:
                        text_result = f"Error: {error}"
                    elif len(content) > MAX_CONTENT_CHARS:
                        text_result = content[:MAX_CONTENT_CHARS] + f"\n\n... [截断，共 {len(content)} 字符]"
                    else:
                        text_result = content

            elif tool_name == "memory_source":
                path = args.get("path", "")
                if not path:
                    text_result = "Error: path is required"
                else:
                    info, error = source_ob(path)
                    if error:
                        text_result = f"Error: {error}"
                    else:
                        text_result = json.dumps(info, ensure_ascii=False, indent=2)

            elif tool_name == "memory_list_folders":
                depth = args.get("depth", 3)
                folders = list_folders_ob(depth=depth)
                lines = [f"Obsidian 目录结构（{OBSIDIAN_ROOT}）："]
                for f in folders:
                    indent = "  " * f["depth"]
                    lines.append(f"{indent}📂 {f['path']} ({f['files']} 笔记)")
                text_result = "\n".join(lines)

            else:
                send_response(stdout, req_id, error={
                    "code": -32601, "message": f"Unknown tool: {tool_name}"
                })
                continue

            send_response(stdout, req_id, result={
                "content": [{"type": "text", "text": text_result}]
            })
            continue

        # Unknown method with request id
        if req_id is not None:
            send_response(stdout, req_id, error={
                "code": -32601, "message": f"Unknown method: {method}"
            })


if __name__ == "__main__":
    main()