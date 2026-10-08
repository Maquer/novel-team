# 事实账本 (Fact Ledger) · 使用指南

> 借鉴 StoryForge 四层记忆系统，实现轻量级Python版本

---

## 一、设计理念

### 1.1 四层记忆系统

```
正文（Chapter）
    ↓ 提取
事实账本（Facts）
    ↓ 结构化
状态追踪（States）
    ↓ 汇总
摘要系统（Summaries）
    ↓ 索引
检索系统（Index）
```

### 1.2 核心原则

1. **事实独立于正文**：从正文中提取已确认的事实，存储为独立数据
2. **版本保护**：正文变化使旧候选失效，需要重新验证
3. **三层摘要**：章节/卷/全局，帮助快速定位
4. **关键词索引**：支持模糊搜索相关事实

---

## 二、快速开始

### 2.1 添加事实

```bash
# 基本用法
python3 tools/fact-ledger.py add-fact \
  --project-id my-novel \
  --type 人物 \
  --content "主角林动获得神秘玉佩，内含空间" \
  --chapter 1 \
  --tags "林动,玉佩,金手指"

# 常见类型
--type 人物      # 人物相关事实
--type 物品      # 物品、道具、能力
--type 事件      # 重要事件、转折点
--type 地点      # 场景、地点、环境
--type 关系      # 人物关系、情感线
```

### 2.2 更新状态

```bash
# 更新人物状态
python3 tools/fact-ledger.py update-state \
  --project-id my-novel \
  --type 人物 \
  --entity "林动" \
  --key "境界" \
  --value "淬体境三重" \
  --chapter 1

# 常用状态键
境界、修为、生命值、心情、持有物品、当前位置、关系状态
```

### 2.3 查看状态

```bash
# 列出所有状态
python3 tools/fact-ledger.py list-states --project-id my-novel

# 查询特定状态
python3 tools/fact-ledger.py get-state \
  --project-id my-novel \
  --type 人物 \
  --entity "林动" \
  --key "境界"
```

### 2.4 搜索事实

```bash
# 关键词搜索
python3 tools/fact-ledger.py search \
  --project-id my-novel \
  --query "林动 玉佩"
```

### 2.5 生成报告

```bash
python3 tools/fact-ledger.py report --project-id my-novel
```

---

## 三、工作流程

### 3.1 章节创作后

```bash
# 1. 提取新事实
python3 tools/fact-ledger.py add-fact --chapter N ...

# 2. 更新人物/物品状态
python3 tools/fact-ledger.py update-state --chapter N ...

# 3. 添加章节摘要
python3 tools/fact-ledger.py add-summary \
  --type chapter \
  --from-chapter N \
  --to-chapter N \
  --content "本章摘要内容..."
```

### 3.2 修改已发布章节

```bash
# 1. 使后续事实失效
python3 tools/fact-ledger.py check-stale --chapter M

# 2. 重新验证相关事实
python3 tools/fact-ledger.py list-facts --type 人物

# 3. 验证确认后
python3 tools/fact-ledger.py verify-fact --fact-id xxx
```

### 3.3 卷完成后

```bash
# 添加卷摘要
python3 tools/fact-ledger.py add-summary \
  --type volume \
  --from-chapter 1 \
  --to-chapter 50 \
  --content "第一卷摘要..."
```

---

## 四、数据模型

### 4.1 事实（Fact）

```json
{
  "id": "project_0001",
  "type": "人物",
  "content": "主角林动获得神秘玉佩",
  "source_chapter": 1,
  "confidence": 1.0,
  "tags": ["林动", "玉佩"],
  "created_at": "2026-09-27T09:00:00+08:00",
  "verified": true,
  "hash": "a1b2c3d4e5f6g7h8"
}
```

### 4.2 状态（State）

```json
{
  "history": [
    {
      "chapter": 1,
      "key": "境界",
      "old_value": null,
      "new_value": "淬体境三重",
      "timestamp": "..."
    }
  ],
  "current": {
    "境界": "淬体境三重",
    "持有物品": ["神秘玉佩"]
  }
}
```

### 4.3 摘要（Summary）

```json
{
  "id": "project_chapter_0001",
  "type": "chapter",
  "content": "本章摘要...",
  "source_chapters": [1],
  "hash_original": null,
  "hash_summary": "x1y2z3..."
}
```

---

## 五、与SOP整合

### 5.1 创作阶段嵌入

在现有七阶段流程中，**第5阶段（章节创作）**后增加记忆更新步骤：

```
章节创作 → 事实提取 → 状态更新 → 摘要生成 → 索引更新
```

### 5.2 章后整理模板

每次写完一章，执行：

```bash
# 1. 检查是否需要失效旧事实
python3 tools/fact-ledger.py check-stale --chapter N

# 2. 添加新事实（根据章节内容）
python3 tools/fact-ledger.py add-fact --chapter N --content "..."

# 3. 更新状态（如有变化）
python3 tools/fact-ledger.py update-state --chapter N --entity "..."

# 4. 生成章节摘要
python3 tools/fact-ledger.py add-summary --type chapter --from-chapter N --to-chapter N --content "..."
```

### 5.3 连续性检查

写作前查询相关事实：

```bash
# 查询某人物当前状态
python3 tools/fact-ledger.py get-state --type 人物 --entity "林动" --key "境界"

# 查询相关事实
python3 tools/fact-ledger.py search --query "林动 玉佩"
```

---

## 六、进阶用法

### 6.1 置信度管理

对于AI生成的待确认事实，设置较低置信度：

```bash
--confidence 0.7  # AI生成，待确认
--confidence 1.0  # 作者确认，可信
```

### 6.2 标签系统

使用标签进行多维度分类：

```bash
--tags "林动,主角,成长线"
--tags "玉佩,金手指,辅助"
```

### 6.3 失效机制

当修改已发布章节时：

```bash
# 失效第N章之后的所有未验证事实
python3 tools/fact-ledger.py check-stale --chapter N
```

---

## 七、文件结构

```
novel-team/ledger/
├── facts.json          # 事实账本
├── states.json         # 状态追踪
├── summaries.json      # 摘要系统
└── index.json          # 检索索引
```

---

## 八、版本记录

- v0.1.0 (2026-09-27) - 初始版本，借鉴StoryForge记忆系统
