# Hypit 声明式视频编排引擎
> https://github.com/hypit-ai/hypit · ⭐ 15730 · 2026-07-29 创建 · v0.2.13

## 简介
用 AI agent（Claude Code/Codex）操控的声明式视频生成引擎。输入参考视频，agent 自动生成完整工作流：素材、字幕、B-roll、特效，支持 1 命令出 100 个变体，成本约 $1/次。核心是一个叫 **SVML**（hypit Video Markup Language）的声明式视频编排 DSL。

## 核心原理
- **SVML DSL**：类似 SVG/SSML 的 XML 风格标记语言，用 `<script>` / `<text:Value>` / `<seedance:generate>` 描述视频结构，而非命令式代码
- **组件即包**：122 个 `@hypit/*` npm 包，每个包一个能力（seedance 视频生成 / caption 字幕 / ranking 排行榜 / whisperx 语音对齐），可插拔组合
- **词级锚定**：字幕和特效绑定到"词"而非"时间戳"，改写文案自动重排时序
- **模板→变体**：一份 reference.svml → 换 host/B-roll/文案/语言 → 100 个独立视频，共用未变部分
- **渲染层**：64 个 headless Chromium 并发渲染，不依赖 GPU，本地出片
- **Agent 入口**：`npx skills add hypit-ai/hypit -g` 安装 Skill，Claude Code/Codex 通过 Skill 读项目、调 API、出片

## 示例（ranking-football）
```xml
<?svml using="@hypit/markup@1"?>
<script id="story">
  <ronaldo>
    <HOST>Ronaldo is <D | Dee> tier...</HOST>
  </ronaldo>
  <messi>
    <HOST>Messi? Man won...</HOST>
  </messi>
</script>
<seedance:generate source="./images/messi.jpg" prompt="Messi celebrating..." />
<caption:fine source="@hypit/whisperx@1" sync="story" />
<render:hyperframes concurrency="64" />
```
三个 clone 变体：换 narrato（banana cat）、反转排名（Ronaldo S tier）、替换人物（tech founders）。

## 架构亮点
1. **SVML 是 SSML 的视频版**——声明"要什么"，engine 决定"怎么做"，agent 只写声明
2. **组件可单独替换**——换 host 不动字幕，换字幕不动 B-roll（对齐 watermarks-remover `/capabilities` 模式）
3. **成本透明**——README 明确写"generation models are optional"，纯前端渲染零 API 费用
4. **官方 Skill 即安装入口**——不是 GitHub repo 复制，是标准 `npx skills add`，与我的 Vercel Skills 生态兼容
5. **Agent 协作模式**——agent 读项目文件 + 调 API + 出片，但用户负责审片和导出（人机分工清晰）

## 许可证
**修改版 Apache 2.0**（不是标准 Apache）：
- ✅ 允许：自用、企业内网、单租户部署、商业工作
- ❌ 禁止：多租户 SaaS（向第三方提供 Hypit 功能）、付费转售
- ⚠️ 贡献者条款：contributor 代码可用于商业（含云端业务），作者可调 stricter
- 🔒 LOGO 和版权信息不可移除

## iSH 适用性
❌ **完全不可用**：Node.js 22.15+ 硬门槛（iSH 是 22.23 勉强够，但 pnpm + 122 包 + Chromium 渲染 iSH 跑不了）+ 需要 GPU 级视频 API（Seedance/GPT Image 等）+ 需要外部模型服务付费

## 决策
**归档不装本地**。领域错位（视频生成 vs 我的内容生产+知识管理）+ iSH 环境不满足 + 会加重 P0 无语料清单（122 包 36MB）。

## P1 借鉴 8 项
1. **SVML 声明式 DSL 模式** → 我任何"流程编排"场景可借鉴（把"命令式步骤"改成"声明式结构"）
2. **组件即 npm 包** → 我的 skill 生态可拆成更细粒度的 `@minis/*` 包（当前 skill 是单体大文件）
3. **词级锚定（word-level）** → gzh 排版工具字幕/特效与文案绑定，改写不重排
4. **成本透明报价** → 每次 render 输出费用明细（对齐 my-place 账单模式）
5. **Agent 职责边界** → agent 读项目+调 API+出片，**用户审片+导出**（人机分工写进 README，我不缺这个意识但可以写进 skill 文档）
6. **官方 Skill 安装入口** → `npx skills add` 标准化（对齐 Vercel Skills 生态，我的 `minis-cli hub install` 可借鉴）
7. **并发渲染调度** → 64 进程并行（我的 `render-hyperframes` 模式，对齐 archify 的 `concurrency` 参数）
8. **模板→变体流水线** → 一个 source → N 个 clone（对齐 re-souo-ju-he 的"一选题多平台分发"模式，但这里是同一平台多变体）

## 相关
- TrendRadar（09-22 归档）：同类"AI 内容生产"赛道，但 TrendRadar 是热点聚合+通知，Hypit 是视频生成引擎，无直接竞争
- archify（已装）：同为"声明式→渲染"模式，但 archify 是静态图，Hypit 是视频，互补
- MiniCPM CoT 泄露（#001 今日）：同属"AI 生成内容"，Hypit 是生成工具，我是内容生产者，无直接关系
