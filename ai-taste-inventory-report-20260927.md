# minis AI味检测工具链对比报告

> 生成时间：2026-09-27 | 覆盖范围：全部 AI味相关技能、脚本、门禁、规则 | 实测文章：11篇

---

## 一、工具链全景图

| 工具 | 路径 | 团队 | 来源 | 规则数 | 定位 |
|------|------|------|------|--------|------|
| **humanizer-check.py** | `/var/minis/shared/humanizer-check/` | gzh-team | lieflat 11条实测规则 | 11条规则+3条v1保留 | 通用非虚构（主渠道） |
| **novel-humanizer.py** | `/var/minis/shared/novel-team/tools/` | novel-team | lieflat 11条 + Novel-Creator 7大类 | 11+7=18类检测 | 小说专用（含lieflat） |
| **anti-ai-12.py** | `/var/minis/shared/novel-team/tools/` | novel-team | NovelCraft + 51mazi | 12条场景纪律 | 小说创作纪律（非检测） |
| **gate-H14-check.py** | `/var/minis/shared/gzh-team/` | gzh-team | 封装 humanizer-check | 三档硬判据 | gzh发布前AI味门禁 |
| **gate-G7-check.py** | `/var/minis/shared/gzh-team/` | gzh-team | 引用审核结论中的分数 | 复用 | gzh发布前复合门禁 |
| **gate-check.py（gzh）** | `/var/minis/shared/gzh-team/` | gzh-team | 纯脚本计数 | 9词BANNED+4词META | gzh基础字数/段落/禁用词门禁 |
| **gate-check.py（novel）** | `/var/minis/shared/novel-team/tools/` | novel-team | 六门禁框架，子调用 novel-humanizer | 8项门禁 | novel章节综合门禁 |
| **train-check.py** | `/var/minis/shared/gzh-team/training/` | gzh-team | 集成 humanizer-check | 10项能力考核 | 岗位能力考核 |
| **bao-kuai-xie-zuo/SKILL.md** | `/var/minis/skills/bao-kuai-xie-zuo/` | 通用 | 引用 humanizer-check | 2档阈值+红线 | 写作时内嵌提醒 |
| **gzh-fa-qian-jian-cha/SKILL.md** | `/var/minis/skills/gzh-fa-qian-jian-cha/` | gzh | 引用 gate-H14 | 三档门槛 | 发布前检查清单 |

---

## 二、核心发现：两套 lieflat 实现存在系统性评分偏差

### 2.1 差异根源：规则3（相邻句结构同款）实现完全不同

| 维度 | humanizer-check.py | novel-humanizer.py |
|------|-------------------|-------------------|
| 句法骨架比对 | **结构签名归一化**：把每段连续中文替换为`C{字数}`标记，再比对完整骨架 | **粗匹配**：只比逗号数量和长度比例，不比对语法结构 |
| 误报容忍 | 低（表格行、列表项因结构不同不匹配） | 高（表格行因逗号和长度近似被大量命中） |
| 对 Markdown 表格的鲁棒性 | ✅ 不受影响 | ❌ 大量误报 |

**实测证据**（ai-tool-comparison 正文）：
- `humanizer-check`：规则3命中 **0 处**（表格行结构签名不同，未误判）
- `novel-humanizer`：规则3命中 **7 处**（表格行仅比逗点数+长度，大量误判）

### 2.2 其他次要差异

| 差异点 | humanizer-check | novel-humanizer |
|--------|----------------|----------------|
| Markdown 预处理 | 保留，直接检测 | 先 strip 标题和列表标记，暴露更多文本给规则 |
| 规则4b（em dash密度） | ✅ 有（5‰/10‰双阈值） | ❌ 缺失 |
| v1保留规则（A5/A8/A14） | ✅ 有（标注未验证） | ❌ 缺失 |
| Novel-Creator 7大类 | ❌ 无 | ✅ 有（小说专用词汇库） |
| Tier 1A/1B 分层 | ✅ 有（1B×0.3权重） | ✅ 有（同架构） |

### 2.3 结果：对同一篇文章，两工具评分差异巨大

| 文章 | humanizer-check | novel-humanizer | 差异 |
|------|----------------|----------------|------|
| ai-tool-comparison | **4** 🟢极轻 | **16** 🔴明显 | +12 |
| ai-tone-evidence | **5** 🟢极轻 | **39** 🚨严重 | +34 |
| self-validation | **4** 🟢极轻 | **28** 🚨严重 | +24 |
| asc-skill-gov-v2 | **18** 🔴明显 | **37** 🚨严重 | +19 |
| asc-skill-gov-v1 | **17** 🔴明显 | **43** 🚨严重 | +26 |
| ai-academic-integrity | **14** 🟡轻微 | **26** 🔴明显 | +12 |
| app-slop | **13** 🟡轻微 | **31** 🚨严重 | +18 |
| skill-ecosystem-2017 | **21** 🔴明显 | **43** 🚨严重 | +22 |
| skill-ecosystem-20260920 | **6** 🟡轻微 | **10** 🔴明显 | +4 |
| system-over-willpower | **10** 🟡轻微 | **28** 🚨严重 | +18 |
| wanganzhou | **16** 🔴明显 | **25** 🔴明显 | +9 |

**结论**：`novel-humanizer` 的 lieflat 部分比 `humanizer-check` 系统性高出 **12~34分**，主要差在规则3的匹配灵敏度。

---

## 三、各工具定位与边界对比

### 3.1 humanizer-check.py（gzh-team 主工具）

- **适用体裁**：公众号非虚构（评测/教程/政策解读/复盘）
- **规则来源**：lieflat-less-ai-tone（300篇AI样本/117.9万汉字/5模型）
- **核心优势**：白名单式改写，只改命中处，不润色不重组
- **误报控制**：结构签名归一化 + Tier 1A/1B分层 + 「不作为改写理由」负面用例表
- **已知局限**：缺少 em dash 密度检测（规则4b是额外加分项）；v1保留的3条规则未经验证

### 3.2 novel-humanizer.py（novel-team 主工具）

- **适用体裁**：小说/叙事（含 lieflat 通用规则）
- **额外规则**：NC AI高频词汇（63词）+ 弱化副词（12词）+ 意义膨胀（15词）+ 通用结论套话 + 论文式段落开头 + 正式语体入侵 + 排比三连
- **问题**：规则3过于敏感，对 Markdown 表格/列表产生大量误报；score = 16 的文章被判「明显AI味」，但 humanizer-check 判「极轻」且内容质量确实可用
- **建议**：对非小说体裁（公众号正文），应使用 humanizer-check 而非 novel-humanizer

### 3.3 anti-ai-12.py（novel-team 创作纪律）

- **定位不同**：不是"检测器"，是「写前自检清单」——12条场景纪律（眼前有事/视角细节/对白做事/设定后置...）
- **检测能力**：极低。所有11篇文章只命中 1~2/12 条（全部命中的是"反乒乓链"，但正则几乎不可能真正匹配）
- **价值**：创作指导，不是质量门禁。与 humanizer-check/novel-humanizer 不冲突，定位不同
- **自定义禁词**：`.blacklist.json` 支持团队级扩展（默认15词：首先/其次/不禁/仿佛...）

### 3.4 gate-H14-check.py（gzh 发布门禁）

- **封装 humanizer-check**，直接调 subprocess 取分数
- **三档判定**：≤5 PASS / 6-15 WARN（重写≥50%）/ >25 FAIL（推倒重写）
- **双模式**：`solo`（默认，只给参考分不卡关）/ `strict`（硬判定）
- **与 humanizer-check 自身评分一致**（同阈值 ≤5/≤15/≤25）

### 3.5 gate-G7-check.py（gzh 发布前复合门禁）

- 调用 `--review` 参数读取审核结论中的 AI味分数（不直接调 humanizer）
- 九项检查：标题字数/封面尺寸/金句数量/防盗链/互动钩子/**AI味分数**/OCR中文/后台预览/AI声明/24h pre-mortem
- AI味项依赖人工填写的审核结论，非自动检测

### 3.6 train-check.py（gzh 岗位能力考核）

- 集成 humanizer-check，输出 `H14 AI味` 项
- **双模式**：solo（达标=None，SKIP）/ strict（达标=score≤5）
- 考核10项：H8字数/H9段落/H10结构/H14 AI味/禁用词/元话语/标题策略/AI声明/金句密度/紧迫诱导词

### 3.7 bao-kuai-xie-zuo SKILL.md（写作引擎）

- 在技能描述中**硬编码阈值**：AI味>16 分→大幅改写；>25 分→推倒重写
- **与 humanizer-check 实测阈值不一致**：humanizer 的 ≥16 分档是「🔴明显AI味」，但 skill 里写的是>16触发大幅改写（与 H14 WARN 档重叠但更严格）
- 实际调用：`python3 /var/minis/shared/humanizer-check/humanizer-check.py < 文章.txt`

### 3.8 gzh-fa-qian-jian-cha SKILL.md（发布前检查）

- 依赖 gate-H14 报告，引用审核结论中的 AI味分数
- 触发词：「发布前检查」「发前检查」「这篇能发吗」

---

## 四、阈值不一致问题（P0级）

### 4.1 同一 humanizer-check 输出，三路解读不同

| 来源 | ≤5分 | 6-15分 | 16-25分 | >25分 |
|------|------|--------|---------|-------|
| humanizer-check.py 自身输出 | 🟢 极轻 | 🟡 轻微 | 🔴 明显 | 🚨 严重，建议重写 |
| gate-H14-check.py（solo模式） | PASS | WARN | WARN | FAIL |
| gate-H14-check.py（strict模式） | PASS | WARN | WARN | FAIL |
| train-check.py（solo模式） | 达标=None（SKIP） | 达标=None（SKIP） | 达标=None（SKIP） | 达标=None（SKIP） |
| train-check.py（strict模式） | 达标=True | 达标=False | 达标=False | 达标=False |
| bao-kuai-xie-zuo SKILL.md | — | 重写≥50% | 推倒重写 | 未定义 |

**问题**：`train-check.py` solo 模式下 H14 永远 SKIP（达标=None），相当于门禁失效；strict 模式才走硬判定，但文档默认是 solo。

### 4.2 novel-humanizer vs humanizer-check 不可互转

同一篇文章，humanizer-check=4（PASS），novel-humanizer=16（FAIL）。**不存在简单的分差换算系数**，因为规则3的匹配逻辑根本不同。

---

## 五、跨工具覆盖盲区

| 检测项 | humanizer | novel-humanizer | anti-ai-12 | gate-H14 | gate-G7 | gate-check(gzh) |
|--------|-----------|-----------------|------------|----------|---------|-----------------|
| 翻案腔（不是…而是） | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 顿号罗列过密 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 相邻句结构同款 | ✅（精确） | ✅（粗糙） | ❌ | ❌ | ❌ | ❌ |
| 破折号滥用 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| em dash密度 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 冒号滥用 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 序数词当小标题 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 拟人化喻体 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 数据被概括盖掉 | ✅(1B) | ✅(1B) | ❌ | ❌ | ❌ | ❌ |
| 禁用起手式 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 翻译腔（5种） | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 段首零主语评论 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| AI高频词汇（63词） | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 弱化副词泛滥 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 意义膨胀 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 反乒乓链（对话节奏） | ❌ | ❌ | ✅（弱） | ❌ | ❌ | ❌ |
| 冷开场/硬结尾 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 紧迫感诱导词 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅（URGENCY）|
| 元话语污染 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅（META）|
| 禁用过渡词 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅（BANNED）|

**空白区域**：
1. **em dash密度**（novel-humanizer 缺失）——Markdown文章常见
2. **紧迫感诱导词**（humanizer/novel-humanizer 缺失）——仅 gate-check 覆盖
3. **反乒乓链/冷开场/硬结尾**（仅 anti-ai-12 覆盖）——小说专用
4. **跨工具统一报告**——无，每次只能跑一个工具

---

## 六、建议

### P0：解决阈值不一致

1. **统一 score 口径**：所有门禁（gate-H14/train-check/bao-kuai-xie-zuo）统一引用 `humanizer-check.py` 的官方分档（≤5/≤15/≤25），不要自创阈值
2. **明确 solo vs strict 默认值**：`train-check.py` 的 solo 模式 H14 永远 SKIP，建议改为 strict 默认，或文档里明确写"solo=参考，strict=门禁"
3. **bao-kuai-xie-zuo 阈值对齐**：当前写">16分大幅改写"，与 humanizer-check 的"16-25分=🔴明显AI味"重叠但更严，建议统一用 ≤5/≤15/≤25 三档

### P1：工具定位清晰化

4. **gzh 稿件用 humanizer-check**，不要在 gzh 流程里引入 novel-humanizer（规则3误报率高）
5. **novel 稿件用 novel-humanizer**，但规则3需要降低灵敏度（加结构签名校验）
6. **anti-ai-12 定位为创作纪律**，不是门禁，不要和 humanizer-check 混用

### P2：补齐空白

7. **em dash密度检测**从 humanizer-check 移植到 novel-humanizer（或新建独立检测）
8. **跨工具统一入口**：一个脚本同时跑三个工具，输出合并报告（方便对比）
9. **阈值校准**：用历史已发文章做基线，重新标定 humanizer-check 的三档阈值（当前 ≤5/≤15/≤25 是基于 lieflat 语料，但与团队实际标准可能有偏差）

---

## 七、快速对照表（下次遇到AI味问题先看这个）

| 场景 | 用哪个工具 | 阈值 |
|------|-----------|------|
| 公众号正文检测 | `humanizer-check.py` | ≤5放行 / 6-15重写 / >25推倒 |
| 小说章节检测 | `novel-humanizer.py` | 同左，但注意规则3误报 |
| 创作前自检（小说） | `anti-ai-12.py preview` | 12条纪律，逐条对照 |
| 发布前AI味门禁 | `gate-H14-check.py --mode strict` | 三档硬判定 |
| 综合能力考核 | `train-check.py --mode strict` | H14纳入10项能力分母 |
| 写作时实时提示 | `bao-kuai-xie-zuo` 内嵌提醒 | 触发即告警 |

---

*报告生成：小蒋 | 数据截止：2026-09-27*
