# TinyFish — Minis 接入说明

**官方来源**：<https://github.com/tinyfish-io/tinyfish-web-agent-integrations>
**底层服务**：托管 MCP 服务器 `https://agent.tinyfish.ai/mcp`
**认证**：`TINYFISH_API_KEY`（在 <https://agent.tinyfish.ai> 获取；新用户 600 免费自动化 credits，搜索/fetch 始终免费）
**许可**：MIT

---

## 我做了什么

1. **安装了官方本地 MCP 代理** `@tiny-fish/mcp` v0.1.0（Node 22.23.2 满足要求），全局命令 `tinyfish-mcp`。
   它把 `https://agent.tinyfish.ai/mcp` 反向代理到 `127.0.0.1:3711/mcp`，供 Claude/Cursor 等只用本地 MCP 的客户端使用。**Minis 走直连托管服务器，不需要它。**
2. **写了直连客户端** [`tinyfish.py`](minis://shared/tinyfish/tinyfish.py)：纯 stdlib Python，直接走 MCP Streamable HTTP 协议。5 个子命令：`search` / `fetch` / `monitor` / `list` / `doctor`，外加 `raw` 透传任意 MCP 工具。
3. **写了页面监控脚本** [`tinyfish-monitor.sh`](minis://shared/tinyfish/tinyfish-monitor.sh)：单次抓取 + sha256 diff + 快照落盘。首次运行建立基线，后续运行只报"变/未变"。
4. **未做**：把 Minis 注册为 MCP 客户端（Minis 未提供 MCP client 入口），改用 Python 直连协议达成同样效果。

## 修改/新建的文件

| 路径 | 作用 |
|------|------|
| `/var/minis/shared/tinyfish/tinyfish.py` | 核心 CLI |
| `/var/minis/shared/tinyfish/tinyfish-monitor.sh` | 页面监控包装 |
| `/var/minis/shared/tinyfish/README.md` | 本文档 |
| `/var/minis/shared/tinyfish/monitor/` | 监控快照目录（首次运行创建） |

## 前置：设置 API Key

点这个链接（会自动跳到 Minis 设置页，值需粘贴）：

[Set TINYFISH_API_KEY](minis://settings/environments?create_key=TINYFISH_API_KEY&create_value=&create_note=TinyFish%20API%20key%20from%20https://agent.tinyfish.ai)

Key 从 <https://agent.tinyfish.ai> 免费获取。

## 常用调用

```bash
# 冒烟：列出所有可用工具
python3 /var/minis/shared/tinyfish/tinyfish.py doctor

# 1) 搜索（免费）
python3 /var/minis/shared/tinyfish/tinyfish.py search "React 2026 news"
python3 /var/minis/shared/tinyfish/tinyfish.py search "OpenAI announcement" --domain-type=news --recency-minutes=1440
python3 /var/minis/shared/tinyfish/tinyfish.py search "transformer attention" --domain-type=research_paper

# 2) 抓取干净 Markdown（免费，最多 10 URL 并行）
python3 /var/minis/shared/tinyfish/tinyfish.py fetch https://example.com/article
python3 /var/minis/shared/tinyfish/tinyfish.py fetch https://a.com https://b.com --selector=main,article
python3 /var/minis/shared/tinyfish/tinyfish.py fetch https://example.com --format=html

# 3) 页面监控（首次建基线，之后 sha256 diff）
bash /var/minis/shared/tinyfish/tinyfish-monitor.sh https://example.com mypage
# → 首次返回 changed=true first_run=true；后续运行看 changed 字段
# → 快照存 /var/minis/shared/tinyfish/monitor/mypage-<ts>.md

# 4) 原始 MCP 透传（付费工具，如 run_web_automation / get_run / start_browser）
python3 /var/minis/shared/tinyfish/tinyfish.py raw run_web_automation '{"goal":"打开 example.com，提取标题"}'
```

## 关键参数

**search 工具**

| 参数 | 说明 |
|------|------|
| `query` | 必填 |
| `domain_type` | `web`（默认）/ `news` / `research_paper` |
| `recency_minutes` | 1–5,256,000，"过去 N 分钟"，1 小时 = 60 |
| `after_date` / `before_date` | `YYYY-MM-DD` 窗口，不能与 recency_minutes 同用 |
| `location` / `language` | 国家/语言代码 |
| `purpose` | 排序意图说明（可选） |

**fetch_content 工具**

| 参数 | 说明 |
|------|------|
| `urls` | 1–10 个，并行 |
| `format` | `markdown`（默认，最佳 LLM 消费）/ `html` / `json` |
| `include_selectors` / `exclude_selectors` | CSS 选择器，收窄/剔除内容 |
| `include_etag_and_last_modified` | 返回验证器，供下次条件请求 |

**免费/付费边界**

- `search` / `fetch_content` — 免费
- `run_web_automation` / `start_browser` — 消耗 credits（新用户 600 免费）

## 页面监控（"支持页面监控"的最小可用示例）

TinyFish 没有独立"监控"工具，最小可用范式是 **fetch + 本地 diff**：

```
bash /var/minis/shared/tinyfish/tinyfish-monitor.sh <url> <label>
```

- **首次**：抓 → 存快照 → 记 sha256 基线（返回 `changed=true, first_run=true`）
- **后续**：抓 → sha256 比对 → 有变化才存新快照 + 报警
- **节流**：本地 diff 在 iSH 侧完成，重复未变的 URL 不会浪费抓取消耗
- **快照保留**：最近 20 份，自动清理

**定时触发**：iSH cron 不工作，请用 Apple Shortcuts 定时触发（例如每天 8:00 调用一次），或直接手动跑。

## 故障排查

| 症状 | 原因 | 处理 |
|------|------|------|
| `Unauthorized: Valid OAuth Bearer token required` | Key 未设置或已失效 | 重设 `TINYFISH_API_KEY` |
| `initialize failed: HTTP 401` | 同上 | 同上 |
| `HTTP 502 ... -32000 cannot reach` | 网络不通或 TinyFish 短暂不可用 | 稍后重试；必要时切 IPv4（`curl -s4`） |
| `HTTP 502 ... -32001` | Key 无效 | 换 key |
| 页面监控显示 `changed=false` 但页面明明变了 | 抓取内容含时间戳/随机值 | 用 `--selector=main,article` 收窄到主内容 |

## 与本地 MCP 代理的关系

`@tiny-fish/mcp` 是为**只用本地 MCP 的客户端**准备的（旧版 Cursor / 早期 Claude Desktop）。Minis 无 MCP client 入口，我用 Python 直连托管服务器，等价且更轻：

- 无需 Node 常驻进程
- 无需本地端口
- 无需 CORS/Origin 检查
- 直连 AWS ALB，少一跳

代理仍保留在全局 Node 里，若以后 Minis 加了 MCP client 入口可以直接把 `http://127.0.0.1:3711/mcp` 配进去。
