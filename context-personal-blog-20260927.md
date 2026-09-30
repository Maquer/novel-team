# 上下文打包：personal-blog Cloudflare 部署（2026-09-27 会话交接）

> 用途：新会话/子代理接手时读本文件即可完整恢复上下文。
> 技术细节完整版见 `/var/minis/workspace/personal-blog/DEPLOYMENT.md`（已含踩坑表+契约+更新方法）。

## 1. 任务与结果
- **任务**：把用户的个人博客（静态页 6 文件 + 3 路由 API + 视图计数）部署到 Cloudflare Pages
- **结果**：✅ 已上线 https://personal-blog-7x4.pages.dev，全链路验证通过
  - 静态页 200（首页/列表/详情/关于，列表页有 308 重定向但功能无损）
  - API 4 端点按前端契约工作；视图计数 KV 持久化（hello-world 已 4 次）
  - 浏览器实测首页/详情页渲染正常（截图存档过）

## 2. 关键坐标
| 项 | 值 |
|----|-----|
| Account | `6ddb238e2db8f43a4e974040d1437c2f` |
| Pages 项目 | `personal-blog`（production_branch=main） |
| 生产域 | `personal-blog-7x4.pages.dev` |
| KV namespace | `personal-blog-views` id=`7c781ffaf51147e09d71b3f9ee4c9b3c`（key 格式 `views:<slug>`） |
| 认证 | env 变量 `CLOUDFLARE_API_TOKEN`（勿输出值） |
| 部署脚本 | `/var/minis/workspace/personal-blog/final-deploy.py`（一键：内联数据→ESM自检→multipart→部署） |
| 站点源 | `/var/minis/workspace/personal-blog/deploy/`（6 静态文件 + functions-data.json） |
| 交接文档 | `/var/minis/workspace/personal-blog/DEPLOYMENT.md` |
| 最新部署 id | 见 `/tmp/final-deploy-id.txt`（或 GET deployments 列表取最新） |

## 3. 架构（一句话版）
静态文件走 Pages 资产存储（哈希 key 不校验内容，sha256(base64+ext)[:32] 可当 blake3 用）；
`/api/*` 走 Pages Functions，worker 代码 = 内联文章数据（functions-data.json 构建时注入）
+ **直连 CF KV REST API 做视图计数**（因新一代 Pages 后端丢弃 bundle metadata 里的 KV 绑定）。

## 4. API 契约（前端 app.js 为准，勿改）
- `GET /api/articles?limit=N[&category=X]` → `{"data":[article]}`（日期降序）
- `GET /api/articles/recent` → `[article]` 裸数组
- `GET /api/articles/:slug` → `article` 裸对象（且视图数 +1）
- `GET /api/categories` → `["字符串",...]` 字符串数组

## 5. 铁律踩坑（下次部署前必读）
1. **iSH Node 的 WASM 是 JS 假壳** → wrangler 任何网络命令全废（llhttp_alloc 崩）。一律 Python urllib / Node 内置 fetch 直打 API。
2. **`_worker.bundle` 内模块 part 的 Content-Type 必须 `application/javascript+module`**；用 `text/javascript` = 静默失败（accept 200 → deploy stage failure，无错误信息）。
3. **Pages 新代不应用 bundle 里的 KV 绑定**（env 里只有 ASSETS/CF_PAGES*）；项目级 PATCH 绑定字段被静默忽略 → 用 worker 内 KV REST 直连。
4. **国内网络 `.workers.dev` DNS 污染**（解析到 Meta IP 段）；`.pages.dev` 和 api.cloudflare.com 正常。
5. multipart 传输：Node 构造字节（`new Response(fd).blob()`）→ curl `--data-binary` + 显式 boundary 头（Node fetch 发 POST 到该端点曾报 8000096，原因未深究，curl 稳定）。
6. `POST /workers/scripts` 对 API token 405；`PUT /workers/scripts/{name}` 可隐式创建（已删，勿再建孤儿 worker）。
7. Pages 资产上传新协议：`POST /accounts/{acct}/pages/assets/upload`（JWT Bearer + JSON 数组 `[{key,value:b64,metadata:{contentType},base64:true}]` 分桶批量）。

## 6. 待办 / 下一步（按优先级）
- [ ] **P0 备份**：`deploy/` + `final-deploy.py` 在 workspace（第 3 次丢失灾区）→ 同步一份到 `/var/minis/shared/personal-blog/`
- [ ] P1 可选：CF 后台建窄 token（仅 KV Read/Write）替换内联的全权限 token
- [ ] P1 可选：`html_handling` 308 优化（articles.html→/articles，目前浏览器自动跟随无感）
- [ ] P2 可选：自定义域名绑定（PATCH /pages/projects/{name} domains）
- [ ] P2 可选：Obsidian 归档笔记（按 §二 归档规范，03-Resources/AI工具/ 放「Cloudflare Pages iSH 部署方法论」）

## 7. 会话中已清理
- 调试期孤儿 Worker `personal-blog`（Workers API 流试验品）已删除，账号恢复 2 worker + 1 KV 原状
- 调试脚本保留参考：`workers-deploy.py`（Workers API 全流程）、`gen-inner-bundle.py`（内层 multipart）
- 失败部署记录在 Pages deployments 列表（可 DELETE 清理，无副作用）
