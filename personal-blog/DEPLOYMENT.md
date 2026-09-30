# personal-blog 部署交接文档

**上线时间**：2026-09-27
**生产地址**：https://personal-blog-7x4.pages.dev
**架构**：Cloudflare Pages（静态资产 + Pages Functions 视图计数 API）

---

## 一、线上验证结果（全部通过）

| 项目 | 结果 |
|------|------|
| 首页 / | 200，渐变 Hero + 精选文章卡片（3 篇，带分类/日期/阅读数） |
| 文章列表 /articles.html | 200（经 308 → /articles），分类过滤可用 |
| 文章详情 /article.html?slug=hello-world | 200，标题/分类/日期/标签/正文全渲染 |
| /api/categories | 字符串数组 `["AI","前端","技术"]`（前端契约） |
| /api/articles?limit=N | `{data: [...]}` 包装格式，按日期降序 |
| /api/articles?category=X | 分类过滤 |
| /api/articles/recent | 原始数组（首页用） |
| /api/articles/:slug | 单篇 + **视图数 +1（KV 持久化，跨部署保留）** |
| 404 路由 | 正确 JSON 404 |

## 二、架构与数据流

```
浏览器
 ├─ 静态页 → Pages 资产存储（6 个文件，blake3/sha256 哈希去重）
 └─ /api/* → Pages Functions worker（functionsBundle.js）
               ├─ 文章数据：内联在 worker 代码里（functions-data.json 构建时注入）
               └─ 视图计数：worker 内直接调 Cloudflare KV API
                    （KV namespace: personal-blog-views, id 7c781ffaf51147e09d71b3f9ee4c9b3c）
                    key 格式: views:<slug>
```

**为什么 worker 直连 KV API 而不是用 KV 绑定？**
2026-09-27 实测：当前 Pages 后端（新一代）**不再从 `_worker.bundle` 的 metadata 里应用 KV 绑定**
——部署成功但运行时 `env` 里只有 `ASSETS/CF_PAGES*`，`env.VIEWS` 为 undefined。
项目级 PATCH 的绑定字段也被静默忽略。所以视图计数改为 worker 服务端直连
`api.cloudflare.com` 的 KV REST API（token 只存在于 worker 代码中，访客不可见）。

## 三、更新文章的方法

1. 编辑 `/var/minis/workspace/personal-blog/deploy/functions-data.json`
   （字段：id/title/slug/excerpt/content/date/category/tags/views）
2. 重新生成并部署：
   ```bash
   CLOUDFLARE_API_TOKEN=... python3 /var/minis/workspace/personal-blog/final-deploy.py
   ```
   脚本自动：内联数据 → ESM 语法自检 → 构建 multipart → 部署 → 输出 deployment id
3. 改静态页（html/css/js）：
   - 先重传资产：`python3 /var/minis/workspace/personal-blog/deploy-static.py`（如有）
     或走 wrangler 流程
   - 再重新部署（manifest 哈希变化会触发新资产上传）

## 四、iSH 环境踩坑记录（重要）

| 坑 | 现象 | 解法 |
|----|------|------|
| **iSH Node 的 WebAssembly 是 JS 假壳** | `WebAssembly.validate()` 恒 true，`Instance` 无 exports → wrangler 内联 undici 7 的 llhttp 解析全崩（`Cannot read properties of undefined (reading 'llhttp_alloc')`），**wrangler 任何网络命令全废** | 所有 API 调用改用 Node 内置 fetch（Node 22 自带 undici 6，不走 WASM）或 Python urllib |
| **`_worker.bundle` 模块 MIME 硬要求** | 模块 part 用 `text/javascript` → 部署**静默失败**（accept 200 → deploy stage failure，无任何错误信息）；改 `application/javascript+module` → 成功 | 对齐 wrangler `toMimeType('esm')` |
| **Pages 新代丢弃 bundle 内绑定** | metadata.bindings 被忽略（见上） | worker 直连 KV REST API |
| **`.workers.dev` DNS 污染** | 本网络（国内）解析到 Meta IP 段，workers.dev 全不可达；`.pages.dev` 和 api.cloudflare.com 正常 | 只用 `.pages.dev` 子域 |
| **`POST /workers/scripts` 405** | API token 认证方式不允许该端点（PUT 隐式创建可以） | 用 PUT 部署自动建脚本（本次已删） |

## 五、前端契约（app.js 为准）

- `GET /api/articles?limit=N[&category=X]` → `{"data": [article]}`
- `GET /api/articles/recent` → `[article]`（原始数组）
- `GET /api/articles/:slug` → `article`（原始对象）
- `GET /api/categories` → `["字符串", ...]`

## 六、已知限制

1. **html_handling 308**：`/articles.html` → 308 → `/articles`（浏览器自动跟随，功能无损）
2. **视图计数延迟**：每次计数 = 2 次 KV API 调用（get+put），单次文章请求多 ~100-300ms
3. **token 在 worker 代码里**：能看到脚本源码的人（= 账号所有者）能看到 API token。
   如需收紧：CF 后台建一个只含 `Account KV Read/Write` 权限的窄 token 替换
4. **workspace 丢失风险**：源文件在 `/var/minis/workspace/personal-blog/`（第 3 次丢失灾区），
   建议关键文件同步到 `/var/minis/shared/` 或 Obsidian

## 七、文件清单

| 文件 | 用途 |
|------|------|
| `deploy/` | 静态站点源（6 文件）+ functions-data.json |
| `deploy/functionsBundle.js` | 由 final-deploy.py 内联数据生成的最终 worker |
| `final-deploy.py` | **一键部署**（数据内联→自检→multipart→部署） |
| `workers-deploy.py` | 调试用 Workers API 流（已不需要，保留参考） |
| `gen-inner-bundle.py` | 调试用内层 multipart 生成（已不需要） |
| `wrangler.toml` | 原始配置（wrangler 在 iSH 跑不了，仅作参考） |
