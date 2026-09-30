# 主机/算力速记

> 更新：2026-09-21 | 用途：需要公网入口/临时算力/数据库时快速选型
> 三条来源：daily log 2026-09-14（PandaStack / my-place / ByetHost）

---

## 一句话选型

| 需求 | 首选 |
|------|------|
| 公网 Web/API（长期在线） | **PandaStack Apps**（对标 Vercel/Railway） |
| Serverless HTTP | **PandaStack Functions** |
| 托管 PG16 + pgvector | **PandaStack Databases** |
| 临时算力/无头浏览器/CLI agent | **PandaStack Sandbox** |
| 静态站 + PHP/MySQL + 可靠 cron | **my-place.us** |
| 备用 PHP 小站 | **ByetHost** |

---

## 1. PandaStack（microVM 沙箱平台）⭐ 主力

- **端点**：`https://api.pandastack.ai`
- **Workspace**：`maquer-dd52f10d`
- **凭据**：`PANDASTACK_API_KEY` 环境变量已存（2026-09-14 设置）
- **认证**：`Authorization: Bearer $PANDASTACK_API_KEY`

### 4 个产品线

| 产品 | 端点 | 特点 |
|------|------|------|
| **Sandboxes** | `/v1/sandboxes/*` | 临时算力，私有 NAT + idle TTL，**不能公网访问** |
| **Apps** | `/v1/apps/*` | git-driven + 稳定公网 URL + 自定义域名（CF）+ secrets + auto_hibernate + max_instances 扩缩 + rollback + runtime-logs SSE + metrics |
| **Functions** | `/v1/functions/*` | Serverless，`public=true` 后 `https://fn-…` 直接 HTTP invoke |
| **Databases** | `/v1/databases/*` | 托管 PG16 + pgvector，IP allowlist，PITR，branch/clone，`always_on` opt-out |

### 8 个 Sandbox 模板

| 模板 | CPU/RAM | 关键工具 |
|------|---------|---------|
| `code-interpreter` | 8/2GB | Python 3.13 + Node 24 + pandas/numpy/jupyter/playwright/openai-agents |
| `agent` | 8/2GB | claude/codex/opencode/amp/grok/gemini/copilot + ripgrep/git（8 CLI agent 全预装） |
| `browser` | 8/4GB | chromium/playwright/crawl4ai/xvfb/ffmpeg（无头浏览器） |
| `base` | 8/4GB | mise + node24/py3.12/go/bun/pnpm/yarn |
| `claude-agent` | 8/2GB | Anthropic Managed Agents 自托管 worker |
| `postgres-16` / `-4g` / `-16g` | 8/1-16GB | PG16 + pgvector + pgbouncer |

### Sandbox 快速调用

```bash
# 创建
curl -X POST https://api.pandastack.ai/v1/sandboxes \
  -H "Authorization: Bearer $PANDASTACK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template":"code-interpreter","ttl_seconds":3600}'

# 执行（exec 走 SSH 到 guest :22，root 权限）
curl -X POST https://api.pandastack.ai/v1/sandboxes/<id>/exec \
  -H "Authorization: Bearer $PANDASTACK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"cmd":"your shell command"}'

# 删除
curl -X DELETE https://api.pandastack.ai/v1/sandboxes/<id> \
  -H "Authorization: Bearer $PANDASTACK_API_KEY"
```

### Sandbox 实测（code-interpreter，2026-09-14）
- Debian 13 x86_64，kernel 5.10，8 vCPU Xeon @ 2.80GHz，2GB RAM，9.8GB 磁盘
- 启动 **109ms**（snapshot-natid，非冷启动）
- exec 通道：SSH 到 guest :22，root 全权
- 网络：Google/PyPI/npm/GitHub 全 200，DNS=1.1.1.1+8.8.8.8
- pip/npm/apt 全部可用（0.4-0.6s，有预热缓存）
- **跨 exec 持久化**：文件系统 + 后台进程都存活
- 缺：rust/cargo/go/docker/cmake/brew

### 触发场景
1. 公网 Web/API → **Apps**（不用 sandbox）
2. 无头浏览器/crawl4ai → **browser** sandbox
3. 跑 CLI agent → **agent** sandbox
4. pgvector 向量检索 → **postgres-16** sandbox 或 Databases
5. 临时算数/数据处理 → **code-interpreter** sandbox（跑完删）
6. Serverless HTTP → **Functions**

### 未验证
- Apps 完整部署流程（git push → deploy → 公网 URL）
- Functions public=true 后的 HTTP invoke
- postgres-16 + pgvector 向量查询
- 订阅/计费方案（有 Stripe billing endpoint）
- Sandbox `persistent: true` 参数实际行为

---

## 2. my-place.us（备用外部主机）

- **主机商**：my-place.us（底层 MyOwnFreeHost / iFastNet 免费共享主机）
- **域名**：`loong.my-place.us` → 185.27.134.135
- **控制面板**：https://cpanel.my-place.us（nginx+PHPSESSID）
- **MySQL**：sql101.my-place.us
- **FTP**：ftp.my-place.us
- **用户名**：`mp_42909509`（**密码用户自管，不在小蒋这**）
- **配置**：5GB NVMe、流量不限、ZeroSSL DV 证书（有效期至 2026-12-01）
- **连通性实测（09-14）**：DNS ✅ / 80 openresty 200 ✅ / 443 TLS ✅ / cPanel 200 ✅

### 能力边界（共享主机，非 VPS）
| ✅ 能做 | ❌ 不能做 |
|--------|--------|
| PHP/MySQL 网站、静态站、WordPress | root/管理员权限 |
| cPanel 服务器端 cron（app 死也跑） | Docker/容器 |
| 邮件、FTP 文件传输 | 任意端口监听、长驻后台服务 |
| jailshell（受限 SSH） | 编译大型软件、装系统包 |

### 与 iSH 互补关系
- iSH 短板：无公网、app 杀即停、无数据库、cron 不可靠
- 这台补上：**公网入口 + 24h 在线 + MySQL + 服务器端 cron**
- 组合模式：iSH 生成内容/抓数据 → 推到主机托管；cron 定时任务放主机

### 触发场景
1. 需要公网可达的网页/API 入口
2. 需要可靠的定时任务（不依赖 iSH 存活）
3. 需要 MySQL 数据库后端
4. 需要给 iSH 处理结果找个 24h 在线的托管地

### 不适用
- 常驻爬虫/监控代理（没 root/不能长驻进程）
- 自建 API 服务长时间跑（共享主机限进程时长）
- Docker/编译类需求

### 交互入口
[Login to cPanel/FTP](minis://open_terminal?init_command=curl%20-u%20mp_42909509%20https://cpanel.my-place.us)

---

## 3. ByetHost（免费主机，备用）

- **平台**：byethost24.com（共享虚拟主机）
- **控制面板**：cpanel.byethost24.com
- **用户名**：`b24_42909561`（密码用户自管）
- **网站**：loong.byethost24.com
- **MySQL**：sql112.byethost24.com
- **FTP**：ftp.byethost24.com

### 能力边界
- ✅ PHP + MySQL、静态文件托管、FTP 上传、cPanel 管理
- ❌ 无 SSH/root、无 Python/Node、无后台进程、无自定义端口
- **不能当 VPS 用**

---

## 三台对比

| 维度 | PandaStack | my-place.us | ByetHost |
|------|-----------|-------------|----------|
| 类型 | microVM 沙箱 + Apps/Functions/Databases | 共享主机 | 共享主机 |
| Root 权限 | Sandbox 内 root，Apps 走 git | jailshell 受限 | 无 |
| 公网入口 | Apps 稳定 URL / Functions HTTP | ✅ | ✅ |
| 数据库 | PG16 + pgvector（托管） | MySQL | MySQL |
| Cron | Apps 有 runtime | cPanel cron ✅ | cPanel cron |
| 长驻进程 | Apps ✅ / Sandbox ❌ TTL | ❌ | ❌ |
| Python/Node | ✅ | ❌ | ❌ |
| Docker | ❌ | ❌ | ❌ |
| 存储 | Sandbox 9.8GB | 5GB NVMe | 未查 |
| 凭据位置 | 环境变量 `PANDASTACK_API_KEY` | 用户密码管理器 | 用户密码管理器 |

---

## 凭据安全约定

- PandaStack API Key 在环境变量（小蒋可读取调用）
- my-place.us / ByetHost **密码用户自管**，小蒋不存，需要时用 [交互式终端](minis://open_terminal) 手动输入
