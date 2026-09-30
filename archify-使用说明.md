# archify 使用说明（iSH 实战版）

> **版本** 2.17.0-dev.1 ｜ **上游** `tt-a1i/archify`（66.2k★ / MIT）
> **sourceCommit** `4011ba543` ｜ **SKILL.md SHA256** `10094272d6d1…`
> **本地路径** `/var/minis/skills/archify/`
> **本文所有命令与结论均为 2026-09-23 在 iSH + Node 22.23.2 实测**，非文档转述。

---

## 0. 一句话

给一份 JSON（或一段 Mermaid），产出**自包含可交互 HTML 技术图**：内联 SVG、明暗主题、pan/zoom、搜索、图例、PNG/JPEG/WebP/SVG/WebM 导出。核心链路是 `JSON IR → 确定性布局 → SVG → 内联 HTML`，同一份 spec 每次产出像素一致，可复验。

**它的看家本领不是"画得好看"，而是"不合格就拒绝交付"**：82 条稳定 rule code、fail-closed 诊断、冻结候选 + SHA-256 交付收据。宁可不给你图，也不给你一张线穿过节点的图。

---

## 1. iSH 上唯一的正确调用方式

**永远走包装脚本，不要裸跑 `node bin/archify.mjs`。**

```bash
# 出图（唯一入口）
/var/minis/shared/archify-render.sh render <type> <spec.json> <output.html>

# 送图前先过结构自检（0.1s，务必先跑）
python3 /var/minis/shared/archify-selfcheck.py <spec.json>

# 其它
/var/minis/shared/archify-render.sh check <output.html>      # 复验已有产物
/var/minis/shared/archify-render.sh validate <type> <spec>   # 慢，200s+
/var/minis/shared/archify-render.sh doctor                   # 环境体检
```

**为什么不能裸跑**（两条实测硬坑）：

| 坑 | 现象 | 包装做了什么 |
|---|---|---|
| `canonicalize()` → `realpathSync.native` 对 `/var/minis/**` 恒 ENOENT | 未捕获异常 exit=1，抛 `Error: ENOENT ... realpath '/var/minis/workspace'` | **spec 和产物双双中转 `/tmp`**，只在全部闸门通过后才 `cp` 回目标 |
| CLI 把子进程诊断吞掉 | 只剩 `artifact/check-failed` + `check:"unknown"` + `supportedFixes:[]`，真因丢失 | 失败时自动把 stderr 首条 `Error:` 抛到终端，不用手动翻 `$RUNDIR` |

⚠️ 第一条的边界**不只输出目录**：输入 spec 放在 `/var/minis/workspace` 同样触发。第一次出图失败就是栽在这。

**退出码**（区别于 archify 自身的，不要只看 0/非 0）：

| 码 | 含义 | 该干什么 |
|---|---|---|
| 0 | 成功，产物已就位 | — |
| 2 | 参数/环境错误 | 查 node、skill 路径、spec 是否存在 |
| **3** | **无声失败：exit=0 却没产出文件** | 退出码完全不可信；跑 `validate` 或 selfcheck |
| 4 | 超时被杀 | 调大 `ARCHIFY_RENDER_TIMEOUT`（默认 300s） |
| 5 | 渲染完但 `check` 未过 | 未验证产物留在 `$RUNDIR/unverified.html` |
| 6 | 渲染失败且无产物（exit≠0） | 报错首行已打印，照它改 |

**耗时预期**：成功 `render` 约 60–90s；`validate` 实测 **>215s**。前台直跑必撞工具超时，一律后台 + `timeout`。

---

## 2. 能画哪五类图

`architecture` 架构 ｜ `workflow` 工作流 ｜ `sequence` 时序 ｜ `dataflow` 数据流 ｜ `lifecycle` 状态生命周期

官方内置 11 个场景配方（**自带中文**，选型比记类型名有用）：

```bash
cd /var/minis/skills/archify && node bin/archify.mjs guide --lang zh
```

| 配方 | 类型 | 回答什么问题 |
|---|---|---|
| system-overview | architecture | 系统里有什么、归谁负责、彼此如何连接 |
| deployment-ownership | architecture | 每个负载跑在哪、哪些连接跨了边界 |
| agent-tool-call | workflow | Agent 如何规划、获批、执行、恢复、汇报 |
| delivery-workflow | workflow | 一次变更如何安全走到生产 |
| incident-runbook | workflow | 响应者如何发现、分诊、缓解、验证、升级 |
| api-request | sequence | 谁调用谁、顺序如何、最终返回什么 |
| async-roundtrip | sequence | 首包返回之后后台还发生什么 |
| data-lineage | dataflow | 数据从哪来、怎么变、被谁消费 |
| event-stream | dataflow | 事件经过哪些 Topic、处理器、失败路径 |
| object-lifecycle | lifecycle | 有哪些状态、什么事件触发流转 |
| deployment-lifecycle | lifecycle | 一次发布当前处于什么状态 |

---

## 3. spec 骨架与字段真名

```jsonc
{
  "schema_version": 1,          // 必填
  "diagram_type": "architecture", // 必填
  "meta": {                       // 必填，required: ["title"]
    "title": "标题",
    "locale": "zh-CN",            // ← 真名 locale，不是 language
    "quality_profile": "standard",// standard | showcase
    "animation": "none",          // trace | none
    "visual_preset": "classic",   // classic|signal-flow|blueprint|editorial
    "viewBox": [1080, 720]
  },
  "layout": { "mode": "grid", "origin": [38,70], "cols": 5,
              "cellW": 138, "cellH": 68, "gapX": 76, "gapY": 100 },
  "components": [ { "id":"a", "type":"backend", "label":"A",
                    "sublabel":"说明", "row":0, "col":0 } ],   // required: id,type,label
  "connections": [ { "id":"e1", "from":"a", "to":"b", "label":"调用" } ], // required: from,to
  "cards": [ { "dot":"cyan", "title":"…", "items":["…"] } ]
}
```

**枚举值（写错直接拒）**

- `component.type`：`frontend backend database cloud security messagebus external`
- `connection.variant`：`default emphasis security dashed`
- `connection.route`：`auto straight orthogonal-h orthogonal-v`
- `card.dot`：`cyan emerald violet amber rose orange slate`
- `meta.locale`：`en zh-CN`

⚠️ **每一层都是 `additionalProperties: false`**。多一个键就整份拒绝——包括你以为存在的 `meta.language`（真名 `locale`）。这是 selfcheck 存在的首要理由。

---

## 4. 出图一次过的 5 条硬规则

前 3 条来自 `references/authoring-contract.md`「Executable geometry rules」，后 2 条是本页实测补充。2026-09-23 出第一张图连撞 6 轮，全在这 5 条上。

### ① 每条边只连相邻格

> 官方原文：`An edge crossing an unrelated opaque node is always a hard failure, independent of quality profile.`

边穿过无关节点是**无条件硬失败**，`showcase` 也救不了。`quality_profile` 只影响路由节奏（每段 ≥8px、内部段 ≥16px），不影响这条。

- grid 布局下 `row/col` 曼哈顿距离 > 1 的边，大概率被判穿节点（selfcheck 会 WARN）
- 分叉节点放中间：`A→B` 和 `A→C` 要同时成立，把 **声明者放中间**（`distill(0) sched(1) worker(2)`），别放两端
- 跨层节点对只能靠 `via` 走通道，成本高；优先考虑规则 ④

### ② 间距公式：clear gap 不是中心距

> 官方原文：`Spacing recommendations mean clear gap between boxes, not center distance.`

```
clear gap > label 遮罩宽 + 8px 呼吸位
label 遮罩宽 ≈ 6.5px × ASCII units + 13px
CJK 汉字按 2 units 计
```

**代入实测验证过**（同一份 spec 两次渲染）：

| gapX | 4 字中文标签需要 | 结果 |
|---|---|---|
| 44px | 6.5×8+13+8 = **72px** | ❌ `Label overlaps component` |
| 76px | 72px | ✅ rc=0 |

水平边看 `gapX`，垂直边看 `gapY`。**中文标签按 12px/字估算太乐观，一律按公式算。**

### ③ 标签拥挤只许挪，不许删

> 官方原文：`Relationship labels are semantic data… Deleting it is not a spacing repair.`

修复顺序（官方 `Repair order`，一级一级来，**一次只应用一个诊断控制**）：

1. schema / `quality_profile` 错误
2. 节点重叠、越界
3. 边穿节点、端点方向
4. 交叉、歧义走廊、贴边、路由节奏
5. 标签压节点 → 标签互相压 → 标签压路由

第 5 级内部顺序：**先挪**（`labelAt` 诊断给了点就直接用，别自己估；否则 `labelDx`/`labelDy`/`labelSegment`）→ **再调路由或间距** → **最后才缩短措辞且必须保语义**。只有"两端点已完全隐含、且不含协议/动作/方向/同步异步/跨边界机制"的标签才可省略，且要说明为何冗余。

（本页作者第 6 轮曾用"删 label"糊过去，属于违规修法，已按契约改回 `label` + `labelDy: 26` 重渲染通过。）

### ④ 画不清的关系，交给卡片文字

跨层"回读"类关系（配置注入、启动自检、缓存回填……）画成线几乎必穿节点。架构图**清晰优先于关系穷尽**——放进 `cards` 用文字承载，比强行塞 `via` 绕行更诚实也可读。

### ⑤ 送图前先跑 selfcheck

archify 自己的 `validate` 要 200s+，而 `render` 出错可能零诊断。未知字段、悬空引用、枚举非法、格子冲突、矩形重叠这些**确定性结构问题**交给 0.1s 的自检：

```bash
python3 /var/minis/shared/archify-selfcheck.py spec.json
# 改脚本后先跑反向断言样本，rc 必须 = 1：
python3 /var/minis/shared/archify-selfcheck.py /var/minis/shared/archify-selfcheck.badcase.json
```

---

## 5. 排障对照表

| 报错 / 现象 | 根因 | 修法 |
|---|---|---|
| `exit=0` 且**没有产物**（rc=3） | archify 无声失败，退出码不可信 | 跑 selfcheck；再看 `$RUNDIR/stderr.clean.log` |
| `must NOT have additional properties {"additionalProperty":"language"}` | 字段真名是 `locale`；或手滑写了不存在的键 | 每层 `additionalProperties:false`，按 §3 白名单删/改名 |
| `Error: ENOENT … realpath '/var/minis/…'` | 裸跑了，或 spec 在 minis 挂载下 | 必须走 wrapper（它把 spec+产物都中转 `/tmp`） |
| `[clean-flow/edge-through-node] … crosses component "x"` | 边穿过无关节点 | 只连相邻格；或声明者移到中间；或关系交给cards |
| `Label "x" overlaps component "y"` | clear gap < 遮罩宽+8px | `labelDy`／加大 `gapX/gapY`／缩措辞，**不要删标签** |
| 只剩 `artifact/check-failed` + `supportedFixes:[]` | CLI 丢弃了子进程诊断 | wrapper 已抛 stderr 首行；仍不够则直跑 `renderers/<type>/render-*.mjs` 取 stderr |
| 前台跑没反应/超时 | `validate` >215s，`render` 60–90s | `nohup` 后台 + `timeout`，或调 `ARCHIFY_*_TIMEOUT` |

---

## 6. 它能验什么、验不了什么

**能验（82 条 rule code 全部覆盖这里）**：几何合法性、边穿越、标签遮罩碰撞、路由节奏、schema、模式放置、交付物完整性、字节级交付收据。

**验不了**：**图说得对不对**。零条规则检查语义正确性——组件划分、命名、因果、抽象层次，全都无人把关。仓库自己用 `engineering/*` 命名承认这是可选语义层。唯一的语义验证是 CI 用真实 Chrome + ffmpeg 逐帧比对**导出动画**，也只覆盖动画不覆盖内容。

> 结论：**语义唯一闸门是人眼看**。没做视觉审查就报"图已验证"，只到布局层，不许升级为"内容正确"。

**iSH 已知不可用**：`visual-check`（需真实浏览器）、`--open` / `preview` 的自动打开、依赖 headless Chrome 的导出。PNG 预览可用浏览器全页截图代替。

---

## 7. 官方文档索引（本地，无需联网）

| 文件 | 用途 | 什么时候读 |
|---|---|---|
| `SKILL.md`（16.4KB） | 主指令 + 硬约束清单 | 首次接手 |
| `references/authoring-contract.md`（14.2KB） | **: 字段枚举、间距数学、几何修复顺序、仓库取证** | 卡在布局/间距时（本文 §4 的出处） |
| `references/delivery-contract.md`（9.6KB） | 交付收据、冻结候选、SHA-256 | 要做正式交付 |
| `schemas/README.md`（11.5KB） | 五类图的 schema 说明 | 手写 spec |
| `references/viewer-runtime.md`（4.2KB） | Share Cards / 运行时 | 用户要分享卡 |
| `renderers/<type>/README.md` | 各类型专属规则（workflow 10.4KB 最厚） | 该类型反复失败 |
| `examples/*.json`（15 份） | 可直接抄的真 spec | 起手 |
| `node bin/archify.mjs guide --lang zh` | 11 场景选型 | 不知道用哪类图 |

**上游文档**：`tt-a1i/archify` 的 `README.md` / `docs/authoring-cookbook.zh-CN.md` / `ROADMAP.md`。取文件走 `api.github.com`（iSH 下 `raw.githubusercontent.com` 不通）。
