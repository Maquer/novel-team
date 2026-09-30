# Second Brain MCP Server

Minis 第二大脑 MCP 接口 — 将 Obsidian 知识库暴露为标准 MCP tools，供外部 AI 工具（Codex/Cursor/Claude Desktop 等）通过 MCP 协议检索和读取。

## 架构

```
外部 AI 工具 (Codex/Cursor/Claude Desktop)
        ↓ MCP (JSON-RPC over stdio)
second-brain-mcp.py
        ↓ obsidian-search.py core
Obsidian 挂载 (/var/minis/mounts/loong/)
```

对标 [神游小爬虫《手把手教你搭建本地AI记忆系统》](https://mp.weixin.qq.com/s/sqFQLJ_Lch_vSeakKn8USg) 的 MCP 层设计：
- `memory_search` → 搜索
- `memory_get` → 读取原文
- `memory_source` → 出处追溯

## Tools

| Tool | 描述 | 参数 |
|------|------|------|
| `memory_search` | 关键词搜索 Obsidian 笔记 | `query` (必需), `folder`, `top` |
| `memory_get` | 读取笔记完整内容 | `path` (必需) |
| `memory_source` | 获取笔记元数据（路径、大小、时间、frontmatter） | `path` (必需) |
| `memory_list_folders` | 列出 Obsidian 目录结构 | `depth` (默认 3) |

## 使用

### 在 Minis 中（已注册）

```bash
# 搜索
minis-mcp-cli call second-brain memory_search --input '{"query": "AI工具"}'

# 读取
minis-mcp-cli call second-brain memory_get --input '{"path": "03-Resources/AI工具/some.md"}'

# 元数据
minis-mcp-cli call second-brain memory_source --input '{"path": "03-Resources/AI工具/some.md"}'
```

### 在外部 AI 工具中（Codex/Cursor/Claude Desktop 等）

在 MCP 配置中注册 stdio server：

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "python3",
      "args": ["/var/minis/shared/second-brain-mcp.py"]
    }
  }
}
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OBSIDIAN_ROOT` | `/var/minis/mounts/loong` | Obsidian 仓库路径 |

## 文件

- `second-brain-mcp.py` — MCP Server 本体
- `README.md` — 本文档