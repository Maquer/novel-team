# CONTEXT — 会话切换摘要（2026-09-25）

> 换模型/新会话时先读此文件，对齐状态后再动手。

## 当前任务进度

### 公众号（gzh-team）
| 稿件 | 日期 | 状态 | 下一步 |
|------|------|------|--------|
| ai-tool-comparison | 09-28 | ✅ 草稿就绪 | humanizer 14分人工审阅 + 价格核实 + 手动发布 |
| ai-writing | 09-27 | ✅ 草稿就绪 | 直接发布（humanizer 11分达标） |
| app-slop | 储备 | ✅ 完成 | 第三篇发布候选 |

### 小红书（xhs-team）
| 阶段 | 状态 |
|------|------|
| #001 首发 | ⏳ 待发布（方向：AI效率手册） |
| #002 AI周报30天实测 | 紧随 #001 后启动 |
| 赛道调研 | ✅ 完成，已出报告 |

### Web Portal
- 已上线：https://minis.maquer.eu.org
- 组件：web-portal.py + portal-daemon.sh + Cloudflare Tunnel

---

## 关键决策记录

1. **公众号方向校准**：工具实测型 > 政策解读型（wanganzhou 1阅读教训）
2. **Slogan**：「野路实测，笔记为证：留下能用的」（已落地到首尾图生成器）
3. **小红书画像**：最敢写缺点的AI评测号 → 差异化：真实场景锚定 + 缺点优先 + 有条件结论

---

## 待用户决策（HANDOFF §6）

1. 🔴 ① 公众号后台「账号健康」标签状态
2. 🟡 ② 补后台截图（画像区/送达人数/粉丝总数）
3. 🟡 ③ ai-tool-comparison humanizer 14分是否通过人工审阅放行

---

## 技术备忘

- **iSH 坑**：file_write 中文长内容可能 stub 化，写完后必须 `wc -c` + `grep -c CONTEXT OFFLOADED` 验证
- **模型**：主 deepseek-v4-flash / 备用 Radeon Cloud DeepSeek-V4-Flash
- **countdown-scheduler**：会话启动需 `check --catchup` 补跑积压

---

**最后更新**：2026-09-25 17:05
**下次对齐**：换模型/新会话时读此文件 → 复述状态 → 确认后再继续
