# Minis 记忆栈 BEAM 类评估报告

**模式**: smart 
**时间**: 2026-09-05 00:07

## 总通过率：27/27 = 100%

## 分类结果

- **abstention**: 5/5
- **contradiction_resolution**: 3/3
- **event_ordering**: 2/2
- **information_extraction**: 5/5
- **knowledge_update**: 3/3
- **multi_session_reasoning**: 2/2
- **summarization**: 2/2
- **temporal_reasoning**: 5/5

## 详细结果

- [PASS] IE-01 (information_extraction): 检索 'pudica-memory' 应命中 2026-09-04 daily log
- [PASS] IE-02 (information_extraction): 检索 'Hermes MemoryProvider' 应命中 hermes_provider 相关条目
- [PASS] IE-03 (information_extraction): 检索 'OpenOPC Playbook' 应命中 08-24 daily log
- [PASS] IE-04 (information_extraction): 检索 'SkillForge' 应命中 08-24 daily log
- [PASS] IE-05 (information_extraction): 检索 'workspace 丢失' 应命中至少 3 个 daily log 提及
- [PASS] TR-01 (temporal_reasoning): 检索 '2026-08-24' 应命中该日 log 与跨日引用
- [PASS] TR-02 (temporal_reasoning): 检索 '2026-09-04' 应命中今日归档
- [PASS] TR-03 (temporal_reasoning): 检索 'workspace 丢失' + '08-19' 应指向特定事件
- [PASS] TR-04 (temporal_reasoning): 检索 '2026-08-20' 应命中去AI味迁移记录
- [PASS] TR-05 (temporal_reasoning): 检索 '2026-08-30' 应命中 GLOBAL.md 更新记录
- [PASS] KU-01 (knowledge_update): workspace 状态：从'丢失(08-19)'演进到'已部署 shared (08-20+)'
- [PASS] KU-02 (knowledge_update): minis-cli 从 v1.2 → v1.3.2（版本号演进）
- [PASS] KU-03 (knowledge_update): DeepSeek 模型状态：400/502/余额不足等多类错误分类
- [PASS] AB-01 (abstention): 查询不存在的领域 '区块链智能合约' 应为空或极低命中
- [PASS] AB-02 (abstention): 查询无记录的日期 '2025-01-01' 应为空
- [PASS] AB-03 (abstention): 查询个人生活细节 '家庭住址' 应为空
- [PASS] AB-04 (abstention): 查询从未涉及的编程语言 'Rust' 应为空
- [PASS] AB-05 (abstention): 查询完全不相关的名词 '米其林餐厅' 应为空
- [PASS] CR-01 (contradiction_resolution): workspace 状态出现'已部署/已丢失/待根治'多状态共存 — 检索应命中全部
- [PASS] CR-02 (contradiction_resolution): Skill 版本演进：Darwin 2.1/2.2/2.3/2.4/2.5 共存 — 检索应能取到演进链
- [PASS] CR-03 (contradiction_resolution): 模型可用/不可用分类：DeepSeek 系列从'可用'→'下线'— 状态演化链
- [PASS] EO-01 (event_ordering): 事件顺序：08-09 智能推荐器 → 08-10 记忆架构 → 08-11 Insprira → 08-12 workspace丢失治理 → 08-20 去AI味迁移
- [PASS] EO-02 (event_ordering): pudica-memory 归档事件与 2026-09-04 日期同现（跨文件时序验证）
- [PASS] MSR-01 (multi_session_reasoning): 跨多日的 OpenOPC 借鉴：从'归档'→'Playbook'→'经验档案'→'Company Mode'— 完整链条
- [PASS] MSR-02 (multi_session_reasoning): Darwin Skill 版本迭代：2.1 → 2.5 跨多日
- [PASS] SM-01 (summarization): L2 rollup 应包含 pudica-memory 归档摘要
- [PASS] SM-02 (summarization): L2 rollup 应包含 BEAM 评估引入（本次工作）
