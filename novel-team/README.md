# novel-assistant-v2 · 小说写作助手 v2

纯 Python 标准库、文件型存储的小说写作质量门禁与事实账本工具链。
无数据库、无常驻服务，目标运行环境：iOS 17 OpenMinis（iSH/Alpine）。

这是 v1（`novel-team` 上帝对象脚本集）的架构升级版：
`novelkit/` 提供可复用的库（配置 / 章节模型 / 检查插件 / 编排器 / 数据账本），
`tools/` 只保留 CLI 兼容垫片（参数、输出、退出码与 v1 一致）。

## 目录结构

```
novelkit/
  core/        # config / chapter / results / log / resolve（配置、章节模型、结果、日志、路径解析）
  checks/      # 13 个门禁检查插件（@register 即插即用）
  pipeline/    # orchestrator（编排）/ review（审核状态机）/ cache（文件 hash 缓存）
               # book_scan（全书扫描）/ outline_drift（大纲偏离）/ ledger_prefill（账本预填）
  outline/     # 大纲解析器（markdown / JSON）
  stores/      # FactStore（事实账本）/ DebtStore（质量债务）/ WorldStore（世界包只读）
tools/         # CLI 垫片：gate-check.py / book-scan.py / outline-drift.py / ledger-prefill.py …
config/        # novelkit.json（全部阈值集中于此）
tests/         # tests/test_contract.py（契约测试）
```

## 快速开始

```bash
# 单章门禁（write 模式）
python3 tools/gate-check.py --novel-id my-novel --chapter-file ch1.md

# 全书扫描
python3 tools/book-scan.py --novel-id my-novel --dir chapters/

# 大纲偏离检测
python3 tools/outline-drift.py --novel-id my-novel --dir chapters/ --outline outline.md

# 从大纲预填事实账本
python3 tools/ledger-prefill.py --novel-id my-novel --outline outline.md
```

环境变量 `NOVEL_TEAM_ROOT` 覆盖数据根目录（默认 `/var/minis/shared/novel-team`）。

## 阈值（config/novelkit.json）

- 字数：目标 2500 / 下限 1500 / 上限警告 5500
- AI 味：阻断线 15（`tier_1a`），警告线 13

## 设计文档

见 `docs/设计文档-20260930.md`（v2 架构设计、插件契约、Phase 0–4 记录）。

## 许可

私有项目，保留所有权利。
