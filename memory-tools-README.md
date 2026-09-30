# Minis 记忆工具使用指南

> 存放于 `/var/minis/shared/`，不受 workspace 丢失影响。

## 📋 工具总览

| 工具 | 文件名 | 用途 |
|------|--------|------|
| 系统健康检查 | `minis-dashboard.sh` | 一键查看记忆/Skill/工作区/集成状态 |
| 快速捕捉 | `minis-capture.sh` | 闪念→daily log + Obsidian Inbox |
| L2 周报 | `memory-l2-rollup.py` | 自动扫描 daily log → 生成周报 |
| 知识关联 | `memory-knowledge-link.py` | 跨笔记话题分析 + L3 晋升建议 |
| 工作区备份 | `workspace-backup.sh` | workspace → shared 自动备份 |
| **Obsidian 检索** | `obsidian-search.py` | 扫描 Obsidian 笔记，自然语言触发搜索 |
| **Obsidian 同步** | `obsidian-sync.sh` | Minis ↔ Obsidian 双向同步管道 |
| **搜索热度追踪** | `obsidian-analytics.py` | 记录搜索行为，分析命中/点击率，生成调优建议 |
| **自动标签提取** | `obsidian-tag.py` | 扫描笔记 → 提取/建议标签，检测一致性 |
| **知识图谱构建** | `obsidian-graph.py` | 解析 `[[wiki-link]]`，构建知识网络，找孤立笔记/中心节点 |
| **交叉验证** | `obsidian-crossq.py` | 对知识网络做交叉提问，发现矛盾/缺口/单向引用 |
| **知识蒸馏** | `obsidian-distill.py` | 对话/笔记→知识卡片→Skill骨架的自动化转化 |
| **学习轨迹** | `obsidian-learn.py` | 记录学习进度、能力雷达、复习提醒 |
| **认知盲区** | `obsidian-blindspot.py` | 基于图谱发现孤立集群/浅涉领域/推荐探索方向 |
| **训练 Agent** | `second-brain-train.sh` | 每次对话执行一轮全量训练步，写入 Obsidian 训练日志 |
| **训练脉冲** | `second-brain-pulse.sh` | 轻量训练步（<3秒），快速采样关键指标+异常检测 |
| **卡片审核归档** | `obsidian-distill.py --review / --approve` | 审核→批准→自动归档到对应 PARA 目录 |
| **自动学习管道** | `obsidian-auto-learn.py` | 扫描新/修改笔记→蒸馏→自动批准→归档→升级等级 |
| **健康仪表盘** | `second-brain-dashboard.py` | 健康分+图谱+搜索+卡片+能力雷达+扣分项 |
| 别名 | `minis-aliases.sh` | 一键加载所有快捷命令 |

## 🚀 快速开始

```bash
# 1. 加载别名（可选，加载后 minis 直接可用）
source /var/minis/shared/minis-aliases.sh

# 2. 查看 CLI 帮助
minis --help

# 3. 搜索知识库
minis search --query "AI编程"

# 4. 查看系统状态
minis dashboard

# 5. 快速捕捉
minis capture -t 想法 "今天想到了 XXX"

# 6. 生成 L2 周报
minis rollup --days 7

# 7. 第二大脑训练
minis train

# 8. 全量评分
minis audit
```

## 🎯 minis-cli 统一入口（v1.0.0）

所有工具通过 `minis <命令> [参数]` 统一调用，分组如下：

| 命令 | 说明 | 示例 |
|------|------|------|
| **search** | 知识检索 | `minis search --query "AI" --tier 0` |
| **distill** | 知识卡片蒸馏 | `minis distill --pending` |
| **graph** | 知识图谱 | `minis graph --stats` |
| **crossq** | 交叉验证 | `minis crossq --report` |
| **blindspot** | 认知盲区 | `minis blindspot --gaps` |
| **tag** | 标签提取 | `minis tag --audit` |
| **analytics** | 搜索分析 | `minis analytics --stats` |
| **learn** | 学习轨迹 | `minis learn --add "AI编程" "基础"` |
| **sync** | Obsidian 同步 | `minis sync --status` |
| **tiering** | 分层处理 | `minis tiering --backfill` |
| **registry** | Skill 注册表 | `minis registry scan` |
| **eval** | Skill 评测 | `minis eval report` |
| **migrate** | Skill 迁移 | `minis migrate` |
| **lifecycle** | Skill 生命周期 | `minis lifecycle --stats` |
| **duel** | 红蓝军对弈 | `minis duel probe-banks skill-name list` |
| **train** | 训练流水线 | `minis train` |
| **pulse** | 训练脉冲 | `minis pulse` |
| **dashboard** | 健康仪表盘 | `minis dashboard` |
| **feedback** | 反馈层 | `minis feedback --stats` |
| **commit** | Session 提交 | `minis commit --days 1` |
| **auto-learn** | 自动学习 | `minis auto-learn --dry-run` |
| **nuwa** | 女娲蒸馏 | `minis nuwa --distill "费曼"` |
| **rollup** | L2 周报 | `minis rollup --days 7` |
| **link** | 知识关联 | `minis link --obsidian` |
| **capture** | 闪念捕捉 | `minis capture -t 想法 "内容"` |
| **friction** | 摩擦度评分 | `minis friction --score 1` |
| **backup** | 工作区备份 | `minis backup` |
| **audit** | 全量评分 | `minis audit` |
| **config** | 设置管理 | `minis config get providers` |
| **mcp** | MCP 管理 | `minis mcp ping second-brain` |
| **model** | 模型调用 | `minis model list` |
| **session** | 会话管理 | `minis session list` |

> 所有别名均映射到 `minis <命令>`，加载 `minis-aliases.sh` 后可直接使用 `minis-*` 快捷方式。

## 📊 记忆架构（三层）

```
L1 (Daily Logs)     → /var/minis/memory/YYYY-MM-DD.md
     ↓ 自动 rollup
L2 (Weekly Summaries) → /var/minis/memory/L2-weekly-summaries.md
     ↓ 人工审查晋升
L3 (Knowledge Graph)  → /var/minis/memory/L3-knowledge-graph.md
     ↓ 稳定知识沉淀
GLOBAL.md              → /var/minis/memory/GLOBAL.md
```

## 🔄 定期维护（Apple Shortcuts）

> ⚠️ iSH 不支持 cron，定时任务请用 Apple Shortcuts 自动化。

推荐设置：
- **每日**：运行 `m-dashboard` 查看状态
- **每周日**：运行 `m-mem-rollup` 生成周报 + `m-mem-link` 分析关联
- **每月初**：运行 `m-backup` 备份工作区
- **按需**：运行 `m-capture` 随时捕捉闪念

## 🔧 高级用法

### 记忆查询
```bash
python3 /var/minis/shared/memory-l2-rollup.py --query "DeepSeek" --days 30
```

### L2 周报导出
```bash
python3 /var/minis/shared/memory-l2-rollup.py --days 7 --output /tmp/weekly-report.md
```

### 知识关联深度分析
```bash
python3 /var/minis/shared/memory-knowledge-link.py --days 30 --obsidian
```

### 工作区恢复
```bash
bash /var/minis/shared/workspace-backup.sh --restore
```

## 🧠 第二大脑 — Obsidian 检索与同步

> 自然语言触发 Obsidian 知识库检索，双向同步 Minis 记忆到 Obsidian 归档。

### 自然语言检索（对话触发）

在对话中用自然语言触发检索，无需记命令：

```
"Obsidian 里AI工具的笔记"
"知识库搜一下公众号的文章"
"笔记里找一下编程相关"
"搜一下AI编程"
```

内部自动解析触发词 + 提取关键词 + 猜测文件夹 → 执行搜索。

### 命令行用法

```bash
# 直接搜索
python3 /var/minis/shared/obsidian-search.py --query "AI编程" --folder "03-Resources"

# 列出 Obsidian 目录结构
python3 /var/minis/shared/obsidian-search.py --list-folders

# 自然语言意图检测（调试用）
python3 /var/minis/shared/obsidian-search.py --detect "搜一下XX"
```

### 双向同步

```bash
# Minis daily log → Obsidian 归档
bash /var/minis/shared/obsidian-sync.sh

# 指定日期同步
bash /var/minis/shared/obsidian-sync.sh --date 2026-08-21

# 检查同步状态
bash /var/minis/shared/obsidian-sync.sh --status
```

**写回规则：**

| Minis 类型 | Obsidian 目标 | 触发时机 |
|---|---|---|
| daily log | `04-Archives/Minis-Memory/YYYY-MM-DD.md` | 按需/每日 |
| AI 工具归档 | `03-Resources/AI工具/` | 已实现 |
| 闪念/想法 | `00-Inbox/` | `minis-capture.sh` |

> 📌 核心工具：`obsidian-search.py`（检索引擎 + 意图识别）和 `obsidian-sync.sh`（双向同步管道）均存放于 `/var/minis/shared/`，不受 workspace 丢失影响。

## 🧬 自我进化层

三个模块让 Obsidian 知识体系持续学习、自动优化：

### 搜索热度追踪
```bash
# 记录一次搜索（对话系统调用）
python3 /var/minis/shared/obsidian-analytics.py --log "AI编程" --folder "03-Resources"

# 查看搜索统计
python3 /var/minis/shared/obsidian-analytics.py --stats

# 查看热门笔记
python3 /var/minis/shared/obsidian-analytics.py --trending

# 生成调优建议
python3 /var/minis/shared/obsidian-analytics.py --suggest
```

### 自动标签提取
```bash
# 扫描单个文件
python3 /var/minis/shared/obsidian-tag.py --scan "03-Resources/AI工具/README.md"

# 审计：找出所有缺标签的笔记
python3 /var/minis/shared/obsidian-tag.py --audit

# 应用建议标签（带备份）
python3 /var/minis/shared/obsidian-tag.py --apply "03-Resources/AI工具/README.md"
```

### 知识图谱
```bash
# 图谱统计
python3 /var/minis/shared/obsidian-graph.py --stats

# 中心节点（被引用最多的笔记）
python3 /var/minis/shared/obsidian-graph.py --hubs

# 孤立笔记（需要添加链接的）
python3 /var/minis/shared/obsidian-graph.py --isolated

# 找两个主题之间的路径
python3 /var/minis/shared/obsidian-graph.py --path --from "AI工具" --to "编程"

# 导出为 Obsidian Markdown
python3 /var/minis/shared/obsidian-graph.py --export
```

### 交叉验证
```bash
# 全量验证（基于 wiki-link 引用关系）
python3 /var/minis/shared/obsidian-crossq.py

# 验证某个话题的跨笔记一致性
python3 /var/minis/shared/obsidian-crossq.py --topic "AI工具"

# 生成完整报告
python3 /var/minis/shared/obsidian-crossq.py --report
```

## 🚀 学习能力提升

三个模块补全知识能力与学习能力的衔接：

### 知识蒸馏
```bash
# 从文本蒸馏知识卡片
python3 /var/minis/shared/obsidian-distill.py --distill "文本内容"

# 从文件蒸馏
python3 /var/minis/shared/obsidian-distill.py --distill-file "03-Resources/AI工具/README.md"

# 批量处理 Inbox 待蒸馏文件
python3 /var/minis/shared/obsidian-distill.py --batch

# 查看待审核知识卡片
python3 /var/minis/shared/obsidian-distill.py --pending

# 从知识卡片生成 Skill 骨架
python3 /var/minis/shared/obsidian-distill.py --skill-from "卡片标题"
```

### 学习轨迹追踪
```bash
# 记录学习
python3 /var/minis/shared/obsidian-learn.py --add "AI编程" "掌握基础知识"

# 更新等级（1-5）
python3 /var/minis/shared/obsidian-learn.py --update "AI编程" --level 2

# 查看状态
python3 /var/minis/shared/obsidian-learn.py --status

# 能力雷达
python3 /var/minis/shared/obsidian-learn.py --radar

# 复习提醒
python3 /var/minis/shared/obsidian-learn.py --review

# 学习统计
python3 /var/minis/shared/obsidian-learn.py --stats
```

### 认知盲区检测
```bash
# 全量扫描
python3 /var/minis/shared/obsidian-blindspot.py --scan

# 发现认知差距（被频繁提及但无专门笔记的概念）
python3 /var/minis/shared/obsidian-blindspot.py --gaps

# 发现孤立集群（同目录但无内部链接的笔记组）
python3 /var/minis/shared/obsidian-blindspot.py --clusters

# 推荐探索方向（相邻可能）
python3 /var/minis/shared/obsidian-blindspot.py --adjacent

# 生成完整报告
python3 /var/minis/shared/obsidian-blindspot.py --report
```

## 🧠 训练层

### 全量训练步
```bash
bash /var/minis/shared/second-brain-train.sh
```
每次对话执行一轮全量训练，结果写入 `04-Archives/Training/training-YYYY-MM-DD.md`

### 轻量训练脉冲（<3秒）
```bash
bash /var/minis/shared/second-brain-pulse.sh
```
快速采样关键指标，发现问题时主动通知。适合每次对话后自动触发。

### 自动学习管道
```bash
# 自动扫描新/修改笔记，蒸馏知识卡片，自动批准并归档
python3 /var/minis/shared/obsidian-auto-learn.py

# 强制重新扫描全部笔记
python3 /var/minis/shared/obsidian-auto-learn.py --force

# 仅预览，不写入
python3 /var/minis/shared/obsidian-auto-learn.py --dry-run

# JSON 输出（供程序调用）
python3 /var/minis/shared/obsidian-auto-learn.py --json
```
**评分规则：** 主张数×8 + 文本长度÷20 + wiki-link×5 + 标题关键词 + 20基础分，满分100。评分≥80自动批准归档，<80待人工审核。

### 健康仪表盘
```bash
python3 /var/minis/shared/second-brain-dashboard.py
```
显示健康分、图谱统计、搜索统计、知识卡片数、学习等级、扣分项、能力雷达 Top 5。