# 小说团队 · 提示词模板库

> 基于91Writing提示词模板格式定制，适配小说创作团队工作流

---

## 结构

```
prompt-library/
├── README.md                  # 本文件
├── prompts.json               # 提示词模板索引
├── categories/                # 按分类存储
│   ├── outline.md             # 大纲生成
│   ├── chapter.md             # 章节创作
│   ├── character.md           # 角色设计
│   ├── worldbuilding.md       # 世界观
│   └── polish.md              # 润色优化
└── examples/                  # 示例模板
    └── prompts-example.json   # 参考91Writing格式
```

---

## 使用说明

### 1. 查找模板
```bash
grep -n "标题" prompt-library/prompts.json
```

### 2. 使用模板
```bash
# 读取完整模板
cat prompt-library/categories/outline.md
```

### 3. 自定义模板
编辑对应分类文件，替换变量：
- `{小说类型}` - 填入题材（玄幻/都市/科幻等）
- `{主角姓名}` - 填入主角名字
- `{世界设定}` - 填入世界观描述

---

## 分类说明

| 分类 | 用途 | 变量数量 |
|------|------|---------|
| outline | 大纲生成 | 6-8个 |
| chapter | 章节创作 | 4-6个 |
| character | 角色设计 | 5-7个 |
| worldbuilding | 世界观 | 3-5个 |
| polish | 润色优化 | 2-3个 |

---

## 版本

- v0.1.0 (2026-09-27) - 初始版本，参考91Writing格式
