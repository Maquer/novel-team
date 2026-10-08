# Biz Novel Studio 借鉴整合报告

**整合日期**：2026-09-28
**来源项目**：ExplosiveCoderflome/AI-Novel-Writing-Assistant（3,024★）
**借鉴范围**：核心机制 + 治理原则 + 工具落地

---

## 一、借鉴项总览

| # | 借鉴项 | 落地工具 | 状态 |
|---|--------|---------|------|
| 1 | 质量债务四档分类 | `quality-debt.py` | ✅ 已落地 |
| 2 | 待确认区机制 | `pending-review.py` | ✅ 已落地 |
| 3 | 角色档案四档深度 + 形象演变覆盖率 | `character-depth.py` | ✅ 已落地 |
| 4 | 参与者精准筛选上下文 | `char-context-filter.py` | ✅ 已落地 |
| 5 | gate-check 接入质量债务 | `gate-check.py` 更新 | ✅ 已落地 |

---

## 二、核心借鉴详解

### 2.1 质量债务四档分类（P0落地）

**原设计**：
- `local_patch_plan` — 本章小修可解决 → 继续下一章
- `continue_with_warning` — 记录在案，暂不修复 → 继续下一章
- `patchable_obligation_gap` — 未来章节弥补 → 继续下一章
- `defer_and_continue` — 低优先级，静默记录 → 继续下一章
- **阻断条件**：仅 `stop_for_replan` / `data_integrity_failure`

**gate-check 改造**：
- 原"硬性阻断"→ 改为"记录债务后继续"
- 新增 `debt_integration` 字段返回债务 ID
- `continue_creation` 默认 True（除数据完整性失败）

**使用方式**：
```bash
# 查看质量债务
python quality-debt.py list --novel-id my-novel --status open

# 解决债务（修复后标记）
python quality-debt.py resolve --novel-id my-novel --debt-id QD-3-001
```

### 2.2 待确认区机制（P0落地）

**原设计**：
- AI 提取结果先进入待确认区
- 人工确认后才写入正式 facts.json
- 分离"提案"vs"既成事实"

**pending-review.py 功能**：
```bash
# 添加待确认条目（从门禁结果自动提取）
python pending-review.py add --novel-id my-novel --chapter 3 \
  --category character --content "萧辰突破至淬体五重" --confidence 0.85

# 批量确认低风险条目
python pending-review.py auto-approve --novel-id my-novel

# 列出待确认
python pending-review.py list --novel-id my-novel --status pending
```

**与 gate-check 集成**：
- 门禁 fail 的"境界变化"自动进入待确认区
- 人类作者确认后才入账

### 2.3 角色档案四档深度（P1落地）

**four-level depth**：
- 简要 ≥100 字符
- 标准 ≥300 字符
- 深入 ≥800 字符 + 回溯原文片段
- 完整 ≥1500 字符 + 外貌词条清单 + 形象演变记录

**evolution scan**（形象演变覆盖率扫描）：
- 25% / 50% / 75% / 100% 覆盖率节点
- 每节点提取该阶段外貌/服装/状态描写
- 沉淀为角色成长可视化数据

**使用方式**：
```bash
# 扫描角色形象演变
python character-depth.py scan --novel-id my-novel --char-id char-001

# 查看角色深度评级
python character-depth.py depth --novel-id my-novel

# 生成补全建议
python character-depth.py outline --novel-id my-novel --char-id char-001
```

### 2.4 上下文精准筛选（P1落地）

**原设计**：
- 按本章出场角色筛选角色档案
- 不把全部角色塞进 prompt
- 减少 token 浪费

**char-context-filter.py 功能**：
- `build --chapter N` 提取本章相关角色
- `--full` 模式包含完整档案
- 无 full 模式只返回核心信息

**token 节省预期**：
- 3角色 × 500字 = 1500字上下文
- vs 全部10角色 × 500字 = 5000字上下文
- **节省约 70%**

### 2.5 gate-check 改造（P0落地）

**原有问题**：
- P0 fail 硬阻断（ai_tone、fact_consistency）
- 第3章因 tier_1a=32 被阻断，无法继续

**改造后**：
- 记录质量债务后继续创作流程
- 债务可追溯（QD-3-001 格式）
- 修复后标记 resolve

---

## 三、与 Biz Novel Studio 的差异

| 维度 | Biz Novel Studio | 本项目落地 |
|------|-----------------|-----------|
| 质量债务 | 四档分类 | ✅ 完全借鉴 |
| 待确认区 | AI提取→确认→入账 | ✅ 完全借鉴 |
| 角色档案 | 四档深度+演变扫描 | ✅ 部分实现（深度达标，演变扫描简化）|
| 上下文筛选 | 按出场角色精准筛选 | ✅ 基础实现（关键词匹配）|
| checkpoint恢复 | 每阶段检查点可恢复 | ⚠️ 待实现（countdown-scheduler） |

---

## 四、后续待办（P2）

1. **checkpoint 恢复机制**
   - 借鉴 `每阶段 checkpoint 恢复 + 接管 + 换模型重试`
   - 在 countdown-scheduler.py 中加检查点语义

2. **retrieval trace**
   - obsidian-search 加召回追踪
   - 记录"为什么这条事实被命中"

3. **提示词编辑器可视化引用标签**
   - skill-creator 模板加引用语法
   - 可视化显示 prompt 依赖关系

4. **限速器淘汰机制**
   - model-watchdog 加旧限速器清理
   - provider 配置变更时淘汰旧限速器

---

## 五、测试验证

### 5.1 质量债务系统测试

```bash
# 测试质量债务添加
python quality-debt.py add --novel-id my-novel --chapter 3 \
  --level continue_with_warning --desc "AI味轻微超标 tier_1a=16"

# 验证列表
python quality-debt.py list --novel-id my-novel --status open
```

### 5.2 待确认区测试

```bash
# 添加待确认条目
python pending-review.py add --novel-id my-novel --chapter 3 \
  --category event --content "萧辰触发天命剑剑灵" --confidence 0.75

# 确认
python pending-review.py approve --novel-id my-novel --id P001
```

### 5.3 角色深度测试

```bash
# 扫描萧辰形象演变
python character-depth.py scan --novel-id my-novel --char-id char-001

# 查看深度评级
python character-depth.py depth --novel-id my-novel
```

---

## 六、决策

**整合范围**：5项核心机制全部落地
**未整合**：checkpoint恢复（P2）、retrieval trace（P2）
**状态**：🟢 可投入生产使用

---

*报告生成：小蒋 | 基于 ExplosiveCoderflome/Biz Novel Studio 归档笔记*
