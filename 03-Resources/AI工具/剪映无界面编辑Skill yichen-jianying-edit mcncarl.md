# 剪映无界面编辑 Skill（yichen-jianying-edit）
> `mcncarl/yichen-skills` · 4164★ · Python · 2026-02-11 → 2026-09-22 活跃
> 核心引擎：`mcncarl/jianying-headless` · 2488★ · Python+C++ · 2026-09-15 创建

## 简介
面向剪映专业版 macOS 的结构化剪辑计划→可编辑草稿→原生导出的 Agent Skill 生态。
Skill 层（公开）与引擎层（部分私有）分离：Skill 通过 SHA-256 钉住核心组件身份，
不内置官方库，需要另行检出 jianying-headless 项目并匹配本机剪映版本。
作者：逸尘（06年生，法学生+连续创业者，yichen.ai），非开源许可（个人学习+非商业）。

## 核心架构
用户请求 → edit_plan.py compile（剪辑计划编译）→ headless_draft.py build（草稿生成）
→ verify（原生保存+冷重开回读）→ export（可选，需明确请求）

已验证：视频分段/变速/多轨/画中画/字幕/线性关键帧/六类蒙版/叠化转场/滤镜/花字/音频导入/复合片段冻结导出/Hypit 工程交接（23轨/154片段案例）。

## 治理亮点
1. SHA-256 组件身份钉死（13 个核心文件全部钉 hash）
2. 版本精确匹配（剪映 11.5.0/11.4.2，应用 bundle ID+libvideoeditor hash+深度签名+Team ID）
3. 诚实边界披露（SKILL.md 明确写哪些没验/哪些被拦截）
4. Hypit 协作案例（公开 50.23秒 IG 教程交接数据）
5. ASR ledger 内容绑定（素材 hash→结果复用+防重复提交）
6. 隔离进程+权限最小化（引擎禁止网络/账号读取）

## iSH 可跑性：❌
Apple Silicon Mac 硬门槛 + C++ native codec 需编译 + 剪映 11.5.0 官方 App + Xcode CLI Tools

## 决策：归档，不装本地 skill
理由：领域错位（macOS 原生 App 自动化）+ 环境硬门槛 + 非开源许可

## P1 借鉴 5 项
1. SHA-256 组件身份钉死 → skill-eval-gate.py 加组件 hash 门禁
2. 结构化计划格式（jianying-edit-plan/v1 JSON Schema）→ AI→可执行计划场景
3. ASR ledger 内容绑定 → obsidian-distill.py / 任务队列状态管理
4. 隔离进程+权限最小化 → skill 安全设计参考
5. 诚实边界披露 → 所有 skill 加 references/limits.md 段
