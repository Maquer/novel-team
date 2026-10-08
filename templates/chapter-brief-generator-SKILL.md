---
name: chapter-brief-generator
version: "0.1.0"
description: "单章细纲生成器——根据世界包逻辑+角色档案+五卷大纲，生成每章的写作指令。输出为 markdown 格式的 chapter-brief.md，供创作岗直接读取。"
minis_url: minis://shared/novel-team/tools/chapter-brief-generator.py
created: 2026-09-30
---

# 单章细纲生成器

## 用途

将 Phase 4 的全卷细纲（`vol-001-brief.yaml`）展开为每章的写作指令（`ch-{N}-brief.md`）。

## 输入

| 文件 | 路径 | 说明 |
|------|------|------|
| 全卷细纲 | `outline/vol-{N}-brief.yaml` | 已定义的卷级细纲 |
| 世界核心逻辑 | `world/core-logic.md` | Phase 3 产出 |
| 世界包数据 | `world/world-pack.json` | 结构化数据 |
| 角色档案 | `characters/*.json` | 出场角色信息 |
| 前情提要 | `chapters/ch{N-1}.md` | 上一章正文（Ch1 时为空） |

## 输出

```
outline/
├── vol-001-brief.yaml          # 全卷细纲（输入）
├── ch-001-brief.md             # 第1章细纲（输出）
├── ch-002-brief.md             # 第2章细纲（输出）
└── ...
```

## 单章细纲格式

```markdown
# 第{N}章细纲：《{标题}》

> 生成日期：{date}
> 所属卷：{volume}（Ch{start}-{end}）
> 爽点层级：L{N}
> 字数目标：{word_count}（2000-3000）

## 基础信息
- **章节**：{N}
- **标题**：{title}
- **场景**：{location}
- **时长**：{time_span}
- **出场角色**：{roles}

## 出场角色详情
| 角色 | 境界 | 在场理由 | 本章变化 | 禁忌 |
|------|------|---------|---------|------|
| {name} | {realm} | {reason} | {change} | {forbidden} |

## 核心冲突
{一段话描述本章核心冲突}

## 爽点设计
- **层级**：L{N}
- **压抑点**：{什么让读者不舒服？}
- **释放点**：{什么让读者痛快？}
- **余韵**：{释放后留什么？}

## 信息揭示
- **读者知道**：{本章揭示的新信息}
- **角色知道**：{各角色的认知状态}
- **信息差**：{制造悬念的信息差}

## 章末钩子
{让读者点下一章的具体悬念，≤50字}

## 世界包约束
| 约束类型 | 具体内容 | 违反后果 |
|---------|---------|---------|
| 境界匹配 | {规则} | P0 阻断 |
| 资源限制 | {规则} | P1 警告 |
| 知情边界 | {规则} | P0 阻断 |

## 写作禁忌
- {禁忌1}
- {禁忌2}
- {禁忌3}

## 场景过渡要求
- **上一章结尾**：{上章最后一句/情绪}
- **本章开头衔接**：{过渡方式}
- **切换点**：{哪里需要过渡桥段}

## 创作指令
{给 LLM 的具体写作要求，基于以上所有信息}
```

## 使用方法

```bash
# 生成第 N 章细纲
python3 tools/chapter-brief-generator.py \
  --project helper-creator \
  --chapter {N} \
  --output outline/ch-{N:03d}-brief.md

# 批量生成第一卷全部细纲
python3 tools/chapter-brief-generator.py \
  --project helper-creator \
  --volume 1 \
  --batch
```

## 约束继承规则

从世界包自动继承的约束（无需手动填写）：

1. **境界匹配**：从 `core-logic.md` 提取当前卷的境界范围
2. **资源限制**：从 `world-pack.json` 提取角色可接触的资源
3. **知情边界**：从前章内容提取"读者已知" + "角色已知"
4. **写作铁律**：时间体系、过渡要求从 `world-bible.md` 第六节提取

## 与 gate-check 的对接

`chapter-brief.md` 中的"世界包约束"字段将被 `gate-check.py` 读取：
- `境界匹配` → `fact_consistency.py` 检查
- `资源限制` → `forbidden_words.py` 检查越级物品
- `知情边界` → `info-boundary.py` 检查信息穿帮
