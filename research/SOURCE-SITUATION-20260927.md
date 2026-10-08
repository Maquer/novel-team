# 小说团队 · 书源现状报告

> 数据截止：2026-09-11 实测 | 更新：2026-09-27
> 来源：xbs-novel-reachable-20260911.md + good-sources-report.md

---

## 一、书源总览

### 1.1 香色闺阁书源库（sourceModelList.xbs）

| 层级 | 判定标准 | 数量 |
|------|---------|------|
| 小说类启用源 | 分类为 text | **2392** |
| L0 域名可达 | 首页 HTTP 2xx/3xx | **551** 个域名 (23.0%) |
| 🔵 L1 确认可用 | 真实搜索 + 选择器命中≥1 条 | **62** (2.6%) |
| 🟠 L2 选择器失效 | 搜索有返回但 XPath 0 命中 | **90** (3.8%) |
| ⚪ L2b 未判定 | 依赖 App 内 JS，离线无法构造 | **383** (16.0%) |
| ❌ L3 搜索失败 | 搜索接口 4xx/5xx/超时 | **213** (8.9%) |

> L1 62 源是**离线探测下限**，实际可用数可能更高（App 内 JS 执行可解决 L2b 383 源中的部分）。

### 1.2 大灰狼 good.json 书源库

| 指标 | 数量 |
|------|------|
| 总书源 | 2973 |
| 可用 (enabled) | 2952 |
| 文本类 | 2820 |
| 有声类 | 33 |
| 漫画类 | 25 |
| 文件类 | 71 |

### 1.3 可达过滤后

| 指标 | 数量 |
|------|------|
| 过滤后书源 | 1630 |
| 文本类 | 1537 |
| 有声类 | 21 |
| 漫画类 | 14 |
| 文件类 | 56 |

---

## 二、L1 确认可用书源（62 个）

### 2.1 API 类（推荐优先使用）

| 书源 | 域名 | 搜索地址 | 备注 |
|------|------|---------|------|
| 疯读小说 | fiction.fengduxiaoshuo.com | `/doReader/search_book?_tok` | ✅ API 全链路可读 (237章) |
| 🌼绾书文学 | api.wanshu.com | `/novel/search?pageSize=100&kw=` | API 响应 |
| 猫眼看书 | api.myweipin.com | `/search?keyword=` | API 响应 |
| 推书君 | pre-api.tuishujun.com | `/api/searchBook?search_value=` | API 响应 |
| 得间api | wechat.idejian.com | `/api/wechat/search/do?keyword=` | API 响应 |
| 松鹤阅读 | bookshelf.html5.qq.com | `/ajax/real/search_result?` | API 响应 |
| 唯心阅读 | weread.qq.com | `/web/search/global?` | API 响应 |

### 2.2 网页类（XPath 选择器）

| 书源 | 域名 | 搜索地址 | 备注 |
|------|------|---------|------|
| cs-万相书城 | www.wxscs.com | `/plus/search.php?q=` | 1488 条目，最高命巾 |
| ♡⃝.笔趣阁小说 | www.bi-quge.com | `/search/?searchkey=` | 100 条目 |
| 七彩小说网 | www.qicaizuowen.com | `/search/?searchkey=` | 100 条目 |
| 小说77 | www.yeduzhe.com | `/book/Search.aspx?key=` | 100 条目 |
| 笔趣阁5200 | www.b5200.net | `/modules/article/search.php` | 50 条目 |
| ♡⃝.4小说 | m.4xiaoshuo.info | `/search.php?searchkey=` | 50 条目 |
| ♡⃝.华东看书 | www.dandanwx.com | `/search.html?keyWord=` | 50 条目 |
| 看欧洲小说 | kanouzhou.com | `/search.html?keyword=` | 30 条目 |
| 若初文学网 | www.ruochu.com | `/m/search?queryString=` | 20 条目 |
| 千金小说网 | www.qianjinge.com | `/Search/` | 20 条目 |
| y-潇湘书院 | www.xxsy.net | `/search/` | 20 条目 |
| 小说阅读网 | www.readnovel.com | `/so/` | 9 条目 |

---

## 三、L2 选择器失效书源（90 个）

> 站点在线但 XPath 选择器失效，需修复规则

| 书源 | 域名 | HTTP | 可能原因 |
|------|------|-----:|---------|
| 🌼冷门小说 | www.lengleng.cc | 200 | 站点改版，选择器过期 |
| ∰总监小说 | www.lexuntimes.com | 200 | 同上 |
| 言情小说阁 | www.xianqihaotianmi.org | 200 | 同上 |
| 〽️橘色书院 | www.juseshuyuan.com | 200 | 同上 |
| 书海阁 | m.shuhaige.net | 200 | 移动端结构变化 |
| x-完本神站 | www.xiaoshuowanben.com | 200 | 同上 |
| 格格党51 | m.51ggd.com | 200 | 同上 |
| FZ-说说520 | www.shuquta.com | 200 | 同上 |
| 📖衍墨轩小说 | m.ymxw.net | 200 | 同上 |
| 🌼酷匠小说 | m.kujiang.com | 200 | 同上 |
| ... | ... | ... | 共 90 个 |

---

## 四、失效原因分布（1707 个域名）

| 结果 | 域名数 | 占比 | 说明 |
|------|-------:|------|------|
| ConnectionError | 685 | 40.1% | DNS失败/连接被拒（站已死） |
| 200 | 548 | 32.1% | 正常 |
| timeout | 330 | 19.3% | 连接超时（被墙/CDN不通/站慢） |
| 403 | 72 | 4.2% | 反爬拦截(Cloudflare等) |
| 404 | 24 | 1.4% | 首页路径已变 |
| 521 | 13 | 0.8% | CDN 回源挂 |
| SSLError | 9 | 0.5% | 证书异常 |
| 503 | 6 | 0.4% | 服务不可用 |
| 530 | 5 | 0.3% | DNS/CDN 配置错 |
| 502 | 4 | 0.2% | 网关错误 |

---

## 五、全链路实测（62→6）

> 搜索→详情→目录→正文，逐跳真实请求

| 结果 | 数量 |
|------|-----:|
| ✅ 全链路可读 | 6 |
| 🟢 目录通、正文未取到 | 7 |
| 🟡 详情页通、目录规则失效 | 7 |
| 🔷 API 源（另测） | 12 |
| ⚪ 详情链接依赖 @js | 25 |
| ⚠️ 复测超时 | 6 |

### 全链路可读的 6 个源

| 书源 | 章节数 | 正文字数 |
|------|------:|--------:|
| 小说阅读网无分类 | 1071 | 9917 |
| 小说77 | 2433 | 1089 |
| 看欧洲小说 | 432 | 2470 |
| ♡⃝.笔趣阁小说 | 29 | 3207 |
| y-潇湘书院 | 9 | 6782 |
| 疯读小说（API） | 237 | 正文走 App 内链路 |

---

## 六、关键技术约束

### 6.1 iSH 环境限制

| 约束 | 影响 | 替代方案 |
|------|------|---------|
| GitHub 间歇性 403 | 拉取源码不稳定 | 用 github-raw.sh (API + base64) |
| PyPI 缺 aarch64 wheel | 部分包无法 pip 安装 | 用 `apk add py3-*` |
| 网络并发上限 12 | 高并发探测会瘫 | 控制并发 ≤12 |
| workspace 多次丢失 | 脚本可能丢失 | 核心工具放 `shared/` |

### 6.2 书源格式约束

| 约束 | 说明 |
|------|------|
| GBK/Big5 编码 | 中文站多用 GBK，必须自动检测 charset |
| `@js` 解析器 | 大量书源的 `detailUrl`/`chapterList` 写在 `@js:` 里，离线不可执行 |
| 移动端站点多 | 多数书源是 m. 开头的移动端站点 |

---

## 七、下一步行动

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 重建 probe_stage{A,D,E,F}.py | P0 | 从 daily log 恢复探测工具链 |
| 2 | 编写书源管理器原型 | P0 | 维护 xbs 库 + 健康检测 |
| 3 | 对 L2 90 个源做规则修复 | P1 | 修复失效 XPath |
| 4 | 对 L2b 383 个源做 App 内实测 | P2 | 需在 xbs App 内手动验证 |
| 5 | 制定公版书判断标准 | P1 | 版权合规前置 |

---

> 本报告由 搜韵 维护，每次书源库更新后重新运行探测并刷新。
