# webkit — 无 key 版 Web 搜索 / 抓取 / 监控

**定位**：Minis/iSH 环境下零 API Key 的通用 Web 工具。全部功能不依赖任何第三方服务。

## 我做了什么

1. **搜索**：走 `cn.bing.com`（iSH 沙箱里少数能直连的免费搜索源，返回结构化结果 + 资讯卡带时间戳）。
2. **抓取**：`requests` + `BeautifulSoup` 提取正文 + `html2text` 转 Markdown。零 key、零成本、无配额。
3. **监控**：抓取 → sha256 → 与上次比对 → 有变化才存快照。本地 diff，无云端消耗。

## 依赖（已装好）

- `py3-beautifulsoup4`
- `py3-html2text`
- `py3-requests`

## 修改/新建的文件

| 路径 | 作用 |
|------|------|
| `/var/minis/shared/webkit/webkit.py` | 核心 CLI（search / fetch / monitor） |
| `/var/minis/shared/webkit/README.md` | 本文档 |
| `/var/minis/shared/webkit/monitor/` | 监控快照目录（首次运行自动创建） |

## 用法

```bash
# 1) 搜索
python3 /var/minis/shared/webkit/webkit.py search "OpenAI GPT-6 Astra 最新"
python3 /var/minis/shared/webkit/webkit.py search "AI 新闻 今天"
python3 /var/minis/shared/webkit/webkit.py search "react state management 2026"

# 2) 抓取干净 Markdown
python3 /var/minis/shared/webkit/webkit.py fetch https://news.qq.com/rain/a/20260904A02YJP00
python3 /var/minis/shared/webkit/webkit.py fetch https://example.com --selector="article,main"

# 3) 页面监控（sha256 diff）
python3 /var/minis/shared/webkit/webkit.py monitor <url> --label mypage
python3 /var/minis/shared/webkit/webkit.py monitor <url> --out /tmp/mon --label=myotherpage
```

## 验证结果（2026-09-04 19:12）

| # | 要求 | 结果 | 证据 |
|---|------|------|------|
| 1 | 实时搜索 | ✅ | `search "OpenAI GPT-6 Astra 最新"` 返回 5 条主结果 + 摘要，含知乎/腾讯/penchan 等 |
| 2 | 抓取任意网页返回干净 Markdown | ✅ | 抓取腾讯新闻页 → 11,352 字节 Markdown，含标题、正文、图片链接；导航/样式已剥离 |
| 3 | "最近一小时"新鲜度 | ⚠️ 部分 | Bing 资讯卡原生带时间戳（如"7 小时前"），但**没有 TinyFish 那样 `recency_minutes=60` 的原生参数**。要精确到"最近一小时"只能靠查询词（`今天` / `最新` / `刚刚`）+ 事后人工过滤。 |
| 4 | 页面监控最小示例 | ✅ | 首次建基线（`changed=true, first_run=true, len=11352`）；立即重跑（`changed=false, digest` 一致）；快照保存到 `monitor/gpt6-<ts>.md` |

## 常用参数

**search**
- 参数：位置参数 `<query>`
- 附加：`--page N`（暂未使用，Bing 默认返回第一页）
- 输出：Markdown 结果列表（标题、URL、摘要）

**fetch**
- 参数：位置参数 `<url>`
- 附加：`--selector="CSS 选择器,逗号分隔"`（优先用这些选择器提取正文）
- 默认提取顺序：`--selector` > `article` > `main` > `[role=main]` > `#content` > `#main` > `body`
- 自动剔除：`script/style/nav/footer/header/aside/form/iframe` + cookie/banner/advert 相关元素

**monitor**
- 参数：位置参数 `<url>`
- 附加：`--label <name>` 或 `--label=<name>`（默认用 URL 的 sha1 前 10 位）
- 附加：`--out <dir>` 或 `--out=<dir>`（默认 `/var/minis/shared/webkit/monitor`）
- 输出：JSON，含 `changed` / `digest` / `len` / `history_file`
- 快照保留：最近 20 份，超出自动清理

## 与 TinyFish 集成的关系

**TinyFish** 是官方托管 MCP 服务，功能更强（浏览器渲染 + `recency_minutes=60` 精确过滤），但**必须配 API Key**。已完成接入但当前阻塞在 key 上。

- 官方集成：`/var/minis/shared/tinyfish/tinyfish.py`（等 API Key 到位即可用）
- **本方案**：`/var/minis/shared/webkit/webkit.py`（无 key，零成本，日常够用）

推荐工作流：日常搜索/抓取用 `webkit.py`；有"精确小时窗口过滤"或"复杂 JS 页面渲染"需求时，切到 TinyFish。

## 已知限制

1. **搜索新鲜度**：Bing 没有原生 `recency_minutes` 参数，只能用查询词近似。需要精确小时过滤就走 TinyFish。
2. **JS-heavy 页面**：`webkit.py` 只抓初始 HTML，不执行 JS。JS 动态渲染的内容抓不到。用 Minis 的 `browser_use` 工具（LLM 调用）或 TinyFish 的浏览器渲染。
3. **Wikipedia 等部分外站超时**：iSH 到某些境外站连接不稳定（`en.wikipedia.org` 测试超时），换成国内站或 `browser_use` 绕过。
4. **Bing 反爬**：当前 UA 是 iPhone Safari，正常频率不会被限流。若高频调用可能被 challenge——这时改用 `browser_use` 走真实浏览器。
5. **Markdown 质量**：静态页面的正文提取足够干净，但导航/推荐位等杂讯可能残留。用 `--selector=article` 收窄。

## 定时监控

iSH cron 不工作。要定时跑监控用 Apple Shortcuts 触发 shell 命令：

```bash
python3 /var/minis/shared/webkit/webkit.py monitor <url> --label <name>
```

Shortcuts 里加一个 Shell Script action，输出 JSON，然后判断 `changed` 字段决定是否通知。
