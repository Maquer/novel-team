# novel-team · 小说团队 - AI 小说创作 SOP 与工具链

> ⚠️ **开源脱敏版**：本仓库已移除所有具体创作内容（角色档案、正文草稿、书名等），仅保留方法论、工具链与 SOP。
> 原始项目基于真实创作实践，脱敏后适用于任何 AI 辅助小说创作场景。

## 定位

AI 小说创作 SOP 与工具链，专注于：

- **质量门禁**：13 个检查插件，覆盖字数/AI 味/逻辑一致性/事实账本
- **编排器**：全书扫描、大纲偏离检测、账本预填
- **方法论**：女娲创作 DNA、sepia 论文借鉴、能力借鉴整合

## 技术栈

- 纯 Python 标准库
- 文件型存储（无数据库）
- 目标环境：iOS 17 OpenMinis（iSH/Alpine Linux）

## 目录结构

```
novelkit/          # 核心框架层（配置/章节模型/检查插件/编排器/数据账本）
tools/             # CLI 垫片（gate-check.py / book-scan.py 等）
config/            # 统一阈值配置（novelkit.json）
research/          # 工具调研与借鉴整合报告
docs/              # 设计文档
team/              # 团队手册与 SOP
templates/         # 模板文件
tests/             # 契约测试
```

## 快速开始

```bash
# 单章门禁（write 模式）
python3 tools/gate-check.py --novel-id my-novel --chapter-file ch1.md

# 全书扫描
python3 tools/book-scan.py --novel-id my-novel --dir chapters/

# 大纲偏离检测
python3 tools/outline-drift.py --novel-id my-novel --dir chapters/ --outline outline.md
```

环境变量 `NOVEL_TEAM_ROOT` 覆盖数据根目录。

## 阈值

- 字数：目标 2500 / 下限 1500 / 上限警告 5500
- AI 味：阻断线 15（tier_1a），警告线 13

## 开发

```bash
# 运行契约测试
python3 tests/test_contract.py

# 语法扫描
python3 /var/minis/shared/syntax-scan.py
```

## 许可

MIT — 见 LICENSE 文件
