# Nexus-Lore 借鉴落地报告 v1.0

**来源**：[diosmentiras/Nexus-Lore](https://github.com/diosmentiras/Nexus-Lore)（87★/MIT/2026-06-26→2026-09-27 活跃）
**借鉴日期**：2026-09-28
**状态**：已落地（nexus-lint.py + 整合进世界包治理）

---

## 一、项目定位

> 设定即数据（Lore as Data）——自托管世界观构建终端，面向长篇创作、跑团与共享世界。

**与天命项目的关系**：高度互补。Nexus-Lore 是世界层管理工具（多世界隔离、结构化 Lore、时间线、3D 关系图），天命当前是章节创作层。两者结合 = 完整叙事系统。

---

## 二、借鉴清单

### ✅ 已落地（P0）

| 借鉴项 | Nexus-Lore 原实现 | 天命落地方式 | 状态 |
|--------|-----------------|------------|------|
| **Lore Linter 规则集** | 5 条确定性规则 + 可持久化问题 | `nexus-lint.py` 新增 6 条规则（N1-N6） | ✅ 已部署 |
| **Chronicle 时间线** | `date_order` 稳定排序，不依赖字符串字典序 | `nexus-lint.py timeline` 子命令 | ✅ 已部署 |
| **关系图可视化** | Three.js 3D 球状网络 | `nexus-lint.py graph` 文本版（iSH 可用） | ✅ 已部署 |
| **死后行动语境豁免** | 支持 archive/flashback/memorial 等语境 | DEATH_CONTEXT_EXEMPT 表 | ✅ 已部署 |
| **问题持久化 + 严重级筛选** | issues 数组带 severity，可定位/修复/重新打开 | `check` 输出按 error/warning/info 分组 | ✅ 已部署 |
| **实体解析（名字→ID）** | resolve_entity 通过别名回退 | `resolve_entity()` 方法 | ✅ 已部署 |

### 🔜 待借鉴（P1，Mac 部署后启用）

| 借鉴项 | 说明 | 触发条件 |
|--------|------|---------|
| **多世界隔离** | 当前 `玄天大陆.json` 单一世界，可扩展到多宇宙 | 需要跨世界引用时 |
| **Ollama AI 抽取** | 从文章正文自动抽取实体/事件/关系 | 有 Mac 部署后接 Ollama |
| **3D Nexus 关系图** | Three.js 球状网络，支持节点类型/关系类型过滤 | 需要 Web 预览时 |
| **来源归档** | 保留原文链接/正文/状态/分析摘要 | 有外部参考资料需归档时 |
| **JSON 备份 + 世界管理** | 导出/导入/删除世界 | 需要版本管理时 |

### ❌ 不借鉴（领域错位）

| 项 | 原因 |
|----|------|
| 前端 Nuxt 4 / Vue 3 | iSH 无法运行，Mac 部署走浏览器 |
| Docker Compose | iSH 无 Docker，macOS 直接跑 Python |
| FastAPI + SQLAlchemy | 重后端，当前 JSON+Python 已够用 |
| CI/CD GitHub Actions | iSH 环境限制 |

---

## 三、新增规则详解

### N1: broken_relation — 关系目标不存在
```python
# 示例：萧辰 → nonexistent_entity
{
  "rule": "broken_relation",
  "severity": "error",
  "entry_id": "char_萧辰_0001",
  "message": "关系目标不存在: 萧辰 → nonexistent_entity",
  "fix": "补上目标条目，或把 to 改成它的名字/别名"
}
```

### N2: temporal_inversion — date_start > date_end
```python
# 示例：某事件开始日期晚于结束日期
{
  "rule": "temporal_inversion",
  "severity": "error",
  "entry_id": "event_xxx",
  "message": "时间倒置: 某事件 (start=2026-12-01 > end=2026-06-01)",
  "fix": "检查 date_start 和 date_end，或改为 only_date 字段"
}
```

### N4: death_after_action_v2 — 死后行动（带语境豁免）
```python
DEATH_CONTEXT_EXEMPT = {"archive", "flashback", "memorial", "回忆", "纪念", "传说"}

# 示例：血煞老祖已死，但 content 中有"领导"关键词且无 context 豁免
{
  "rule": "death_after_action_v2",
  "severity": "error",
  "entry_id": "figure_血煞老祖_0001",
  "message": "实体已死亡但仍参与活动: 血煞老祖 (caused)",
  "fix": "核对时间线，或设置 context: memorial/flashback/archive"
}
```

### N5: self_reference — 实体引用自身
```python
# 示例：某实体 relations 中 to 指向自己
{
  "rule": "self_reference",
  "severity": "warning",
  "entry_id": "figure_xxx",
  "message": "实体自引用: 某某 → 自身",
  "fix": "检查是否是笔误，或改为 'self' 表示自我关系"
}
```

### N6: empty_relation_type — 关系缺少 type 字段
```python
# 示例：relations 数组中有条目但无 type 和 to/target
{
  "rule": "empty_relation_type",
  "severity": "info",
  "entry_id": "figure_xxx",
  "message": "关系 #1 缺少 type 和 to/target 字段: 某某",
  "fix": "补上 type（如 associate/alliance/participated）和 to（目标ID）"
}
```

---

## 四、自动补全关系（2026-09-28 执行）

### 4.1 应用结果

| 指标 | 变更前 | 变更后 |
|------|--------|--------|
| 孤立实体 | 66 个 | **16 个**（-76%） |
| 新增关系 | 0 | **47 条** |
| 错误 | 0 | 0 |
| 警告 | 0 | 0 |

### 4.2 关系类型分布

| 关系类型 | 数量 | 说明 |
|---------|------|------|
| `part_of` | 10 | 境界→修炼体系 |
| `belongs_to` | 8 | 地点→宗门 |
| `taught_by` | 6 | 功法→宗门 |
| `supplied_by` | 7 | 物品→来源势力 |
| `details_of` | 4 | 详细条目→主实体 |
| `related_to` | 4 | 秘辛→关联实体 |
| `foreshadows` | 3 | 伏笔→关联实体 |
| `member_of` | 2 | 人物→所属宗门 |
| `enforced_by` | 2 | 规矩→制定者 |
| `affects` | 1 | 事件→影响世界 |

### 4.3 剩余孤立实体（16 个）

需要手动补充或等待后续剧情展开时再连接：

- **万剑剑冢、万剑剑冢·深处** — 天剑山脉禁地，待剧情触发
- **寒渊秘境、毒瘴谷、沉船墓** — 三大秘境，待探索剧情
- **妖兽、剑灵** — 通用类别，待具体实例
- **剑齿虎、炎蛇、蛟、风刃鹰、影魔** — 具体妖兽，待首次登场
- **event_天裂之劫_真相、secret_上古剑圣_详细** — 历史秘辛，待揭秘
- **寒铁** — 特产物资，待交易剧情
- **武力值量化体系** — 可并入修炼体系详细条目

---

## 五、集成到现有工作流

### 4.1 单次检查
```bash
python3 /var/minis/shared/novel-team/tools/nexus-lint.py --world "玄天大陆" check
```

### 4.2 JSON 输出（CI 集成）
```bash
python3 /var/minis/shared/novel-team/tools/nexus-lint.py --world "玄天大陆" check --json > issues.json
```

### 4.3 时间线视图
```bash
python3 /var/minis/shared/novel-team/tools/nexus-lint.py --world "玄天大陆" timeline
```

### 4.4 关系图（文本版）
```bash
python3 /var/minis/shared/novel-team/tools/nexus-lint.py --world "玄天大陆" graph
```

### 4.5 整合进 world-pack.py 流程
```python
# 在 world-pack.py 的 check_consistency() 中追加调用
from nexus_lint import WorldPack as NexusPack

def check_all(world_name):
    pack = WorldPack(world_name)
    nexus = NexusPack(world_name)
    
    # 运行 nexus-lint 新规则
    new_issues = nexus.full_check()
    
    # 合并现有 rules
    existing_issues = pack.check_consistency()
    
    # 合并去重
    all_issues = new_issues + existing_issues
    
    # 保存
    pack.data["issues"] = all_issues
    pack._save()
    
    return all_issues
```

---

## 五、当前检查报告（玄天大陆）

| 指标 | 数值 |
|------|------|
| 实体总数 | 87 |
| 有关系的实体 | 16/87（18%） |
| 孤立实体 | 71（需补充关系） |
| 错误（error） | 0 |
| 警告（warning） | 0 |
| 提示（info） | 66（全部 orphan） |

**结论**：当前无阻断级问题，主要问题是**孤立实体过多**（71/87 = 82%）。

---

## 六、后续建议

1. **优先补充关系**：把 71 个孤立实体与已有实体建立关系（特别是 figure ↔ org、place ↔ region）
2. **添加时间信息**：在 `when` 字段补充 `date_start`/`date_end`，启用 Chronicle 时间线
3. **Mac 部署 Nexus-Lore**：需要 Web 界面和 3D 关系图时，在 Mac 上部署
4. **AI 抽取**：接入 Ollama 从章节草稿自动抽取实体/事件

---

## 七、文件清单

| 文件 | 大小 | 说明 |
|------|------|------|
| `tools/nexus-lint.py` | 23.6KB | 新世界包一致性检查器（6 条新规则 + 兼容现有规则） |
| `docs/nexus-lore-integration-v1.0.md` | 本文件 | 借鉴落地报告 |
