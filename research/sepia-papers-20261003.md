# sepia 引用论文库 — 去AI味理论基础

> 来源：sepia (Nanako0129/sepia) research/ 目录
> 归档时间：2026-10-03
> 核心论文：StoryScope (arXiv:2604.03136) — 61,608 篇故事，叙事结构特征检测 AI 准确率 93.2%

## 核心论文

### 1. StoryScope — 叙事结构检测 AI 小说（93.2% 准确率）
- **arXiv**: [2604.03136](https://arxiv.org/abs/2604.03136)
- **作者**: Russell et al., 2026
- **数据**: 61,608 篇故事（人类 + 5 个前沿 LLM）
- **核心发现**:
  - 仅用叙事结构特征（不看用词），分类器检测 AI 准确率 **93.2% macro-F1**
  - LAMP 编辑条件（人类编辑改写表层风格后），检测率只从 95.5% 降到 93.9%
  - **词句改写对降检测率几乎无效**
- **AI 破绽（叙事结构层）**:
  - 主题由叙述者直接解释
  - 单一因果链过于整洁
  - 情绪仅通过身体感觉描写
  - 无真实世界参照
  - 无读者意识
  - 线性时间无闪回
  - 结尾靠主角成长和接纳解决
- **对 sepia 的指导**: 三层修复协议——叙事架构→话语流→表面风格

### 2. LAMP — 人类编辑改写效果测量
- **arXiv**: [2409.14509](https://arxiv.org/abs/2409.14509)
- **会议**: CHI 2025
- **核心**: 测量人类编辑对 AI 文本表层风格的改写效果
- **对 sepia 的指导**: 证明词句层改写几乎无效

### 3. Measuring AI Slop — AI 垃圾内容测量
- **arXiv**: [2509.19163](https://arxiv.org/abs/2509.19163)
- **核心**: 测量 AI 生成的低质量内容特征
- **对 sepia 的指导**: 专业文档的去AI味规则

### 4. Reinhart et al. — AI 文本检测
- **arXiv**: [2410.16107](https://arxiv.org/abs/2410.16107)
- **会议**: PNAS 2025

### 5. Russell et al. — AI 叙事检测
- **arXiv**: [2501.15654](https://arxiv.org/abs/2501.15654)
- **会议**: ACL 2025

### 6. NarraBench — 叙事基准
- **arXiv**: [2510.09869](https://arxiv.org/abs/2510.09869)

### 7. Echoes in AI — AI 文本中的回声
- **arXiv**: [2501.00273](https://arxiv.org/abs/2501.00273)
- **会议**: PNAS 2025

### 8. QUDsim — 问题-回答相似度
- **arXiv**: [2504.09373](https://arxiv.org/abs/2504.09373)
- **会议**: COLM 2025

### 9. Beguš — AI 生成文本的语言学分析
- **arXiv**: [2310.12902](https://arxiv.org/abs/2310.12902)
- **年份**: 2024

### 10. Beyond Checkmate — 超越棋盘
- **arXiv**: [2501.19301](https://arxiv.org/abs/2501.19301)
- **会议**: EMNLP 2025

### 11. Nonaka & Perry — 创造性写作中的认知
- **arXiv**: [2510.18932](https://arxiv.org/abs/2510.18932)
- **年份**: 2025

### 12. Chakrabarty et al. — AI 创意写作的局限
- **arXiv**: [2510.13939](https://arxiv.org/abs/2510.13939)
- **年份**: 2026

### 13. Shan, Lee & Hao — AI 写作的风格
- **arXiv**: [2608.27855](https://arxiv.org/abs/2608.27855)
- **年份**: 2026

### 14. Rohrbacher et al. — 叙事结构分析
- **arXiv**: [2609.02482](https://arxiv.org/abs/2609.02482)
- **年份**: 2026

### 15. Sourati et al. — AI 文本分类
- **arXiv**: [2502.11266](https://arxiv.org/abs/2502.11266)
- **年份**: 2026

## 补充论文

### SLOPSHAPE-2026 — 公司博客 AI 检测（98.0% 准确率）
- **arXiv**: [2609.15369](https://arxiv.org/abs/2609.15369)
- **数据**: 2,250 篇公司博客 vs 11,250 篇 AI 镜像
- **核心**: 仅用结构特征分离准确率 **98.0% macro-F1**
- **AI 特征描述**: "tidy and self-announcing"（整洁且自宣告）
- **注意**: 此论文特征是 LLM-scored，测试的是原始和模型自改写文本，非人类编辑后的

## 核心结论

1. **词句改写无效**：StoryScope 证明人类编辑改完词句后检测率只降 1.6 个百分点（95.5%→93.9%）
2. **叙事结构才是破绽**：仅看叙事结构（不看用词），准确率 93.2%
3. **专业文档同样适用**：SLOPSHAPE 证明公司博客结构特征检测 98.0%
4. **减规则治假**：sepia 原则——calibrate to human distribution, select 3-5 moves per story and leave slack
5. **每篇只选 3-5 个手法**：应用所有规则 = 新的 AI 指纹
