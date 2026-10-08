# 小说团队 · 类型管理系统

> 基于91Writing动态类型管理设计，适配小说创作团队

---

## 结构

```
genre-system/
├── README.md                 # 本文件
├── genres.json               # 类型定义索引
├── presets/                  # 预设类型
│   ├── 玄幻.json
│   ├── 都市.json
│   ├── 科幻.json
│   ├── 历史.json
│   ├── 言情.json
│   └── 末日.json
└── templates/                # 类型模板
    ├── world-building.md     # 世界观模板
    └── power-system.md       # 力量体系模板
```

---

## 预设类型定义

### 1. 玄幻（xuanhuan.json）

```json
{
  "type": "玄幻",
  "short_name": "玄幻",
  "target_platform": ["起点", "番茄"],
  "demographics": {
    "age_group": "18-35岁",
    "gender": "男频为主",
    "reading_time": "碎片时间+睡前"
  },
  "core_elements": [
    "修炼体系",
    "等级升级",
    "热血战斗",
    "冒险探索"
  ],
  "popular_subgenres": [
    "东方玄幻",
    "异世大陆",
    "高武世界",
    "玄幻王朝"
  ],
  "writing_tips": [
    "修炼体系要清晰，等级划分明确",
    "主角成长要有阶段性突破",
    "战斗场面要有画面感",
    "爽点密集，节奏要快"
  ],
  "platform_notes": {
    "起点": "接受长篇，精品化路线",
    "番茄": "快节奏，前3章定生死"
  }
}
```

### 2. 都市（dushi.json）

```json
{
  "type": "都市",
  "short_name": "都市",
  "target_platform": ["起点", "番茄", "七猫"],
  "demographics": {
    "age_group": "20-40岁",
    "gender": "男频为主",
    "reading_time": "通勤+休息"
  },
  "core_elements": [
    "现代生活",
    "职场商战",
    "异能冒险",
    "社交关系"
  ],
  "popular_subgenres": [
    "都市异能",
    "都市修仙",
    "职场风云",
    "重生都市"
  ],
  "writing_tips": [
    "背景要贴近现实",
    "人物关系要复杂真实",
    "爽点要结合现实痛点",
    "节奏可稍缓，注重人物塑造"
  ],
  "platform_notes": {
    "起点": "精品化，可长篇",
    "番茄": "快节奏爽文",
    "七猫": "保底模式，稳定更新"
  }
}
```

### 3. 科幻（kehuan.json）

```json
{
  "type": "科幻",
  "short_name": "科幻",
  "target_platform": ["起点"],
  "demographics": {
    "age_group": "18-30岁",
    "gender": "男女均衡",
    "reading_time": "深度阅读时间"
  },
  "core_elements": [
    "科技设定",
    "未来想象",
    "宇宙探索",
    "文明思考"
  ],
  "popular_subgenres": [
    "星际文明",
    "赛博朋克",
    "末世科幻",
    "时间循环"
  ],
  "writing_tips": [
    "科技设定要自洽",
    "世界观要完整",
    "人性探讨是核心",
    "节奏可慢，逻辑要严"
  ],
  "platform_notes": {
    "起点": "有科幻频道，读者群体稳定"
  }
}
```

### 4. 历史（lishi.json）

```json
{
  "type": "历史",
  "short_name": "历史",
  "target_platform": ["起点"],
  "demographics": {
    "age_group": "25-45岁",
    "gender": "男频为主",
    "reading_time": "深度阅读"
  },
  "core_elements": [
    "历史考据",
    "权谋斗争",
    "战争谋略",
    "朝代兴衰"
  ],
  "popular_subgenres": [
    "穿越历史",
    "架空历史",
    "历史争霸",
    "历史种田"
  ],
  "writing_tips": [
    "历史细节要准确",
    "人物要有历史感",
    "权谋要有逻辑",
    "避免现代思维穿越"
  ],
  "platform_notes": {
    "起点": "历史频道成熟，读者挑剔但忠诚"
  }
}
```

### 5. 言情（yanqing.json）

```json
{
  "type": "言情",
  "short_name": "言情",
  "target_platform": ["晋江", "番茄"],
  "demographics": {
    "age_group": "16-30岁",
    "gender": "女频为主",
    "reading_time": "睡前+碎片时间"
  },
  "core_elements": [
    "情感发展",
    "人物关系",
    "心理描写",
    "浪漫情节"
  ],
  "popular_subgenres": [
    "现代言情",
    "古代言情",
    "校园言情",
    "霸总言情"
  ],
  "writing_tips": [
    "情感线要细腻",
    "人物要有魅力",
    "虐点要合理",
    "甜宠要自然"
  ],
  "platform_notes": {
    "晋江": "女性向龙头，影视化潜力大",
    "番茄": "快节奏甜宠"
  }
}
```

### 6. 末日（mori.md）

```json
{
  "type": "末日",
  "short_name": "末日",
  "target_platform": ["起点", "番茄"],
  "demographics": {
    "age_group": "18-35岁",
    "gender": "男频为主",
    "reading_time": "深度阅读"
  },
  "core_elements": [
    "生存危机",
    "资源争夺",
    "人性考验",
    "重建秩序"
  ],
  "popular_subgenres": [
    "丧尸末日",
    "天灾末日",
    "无限流末日",
    "末世种田"
  ],
  "writing_tips": [
    "末日氛围要营造到位",
    "人性冲突要有深度",
    "生存细节要真实",
    "希望感不能丢"
  ],
  "platform_notes": {
    "起点": "有固定读者群",
    "番茄": "2024年增速+200%的热门题材"
  }
}
```

---

## 类型选择决策树

```
选择类型
├─ 男频为主？
│   ├─ 是 → 选择题材
│   │   ├─ 喜欢升级打怪 → 玄幻
│   │   ├─ 喜欢现代背景 → 都市
│   │   ├─ 喜欢硬核设定 → 科幻
│   │   ├─ 喜欢历史考据 → 历史
│   │   └─ 喜欢生存危机 → 末日
│   └─ 否 → 选择题材
│       ├─ 喜欢情感故事 → 言情
│       ├─ 喜欢现代背景 → 都市
│       └─ 其他 → 咨询团队
└─ 确定类型
    └─ 选择平台
        ├─ 起点 → 精品化，接受长篇
        ├─ 番茄 → 快节奏，算法推荐
        ├─ 晋江 → 女性向，影视化强
        └─ 七猫 → 保底模式，新人友好
```

---

## 使用流程

### 1. 新建项目时选择类型
```bash
# 查看可用类型
ls prompt-library/genres/

# 复制类型定义
cp prompt-library/genres/{type}.json project/{novel-name}/genre.json
```

### 2. 根据类型使用模板
```bash
# 查看该类型的写作技巧
cat prompt-library/genres/{type}.json | grep -A10 "writing_tips"
```

### 3. 使用对应分类的创作工具
```bash
# 大纲生成
python tools/create-outline.py --type {type}

# 章节创作
python tools/write-chapter.py --type {type} --chapter {n}
```

---

## 版本

- v0.1.0 (2026-09-27) - 初始版本，6大类型定义
EOF

echo "类型管理系统创建完成"