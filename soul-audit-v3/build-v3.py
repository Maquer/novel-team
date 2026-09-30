#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOUL.md v3 构建：8处外科手术修改（源自 soul-audit-v3 三维交叉验证）"""
import json, subprocess
r = subprocess.run(["minis-config","get","soul.body"],capture_output=True,text=True)
soul = json.loads(json.loads(r.stdout)["value"])
orig_len = len(soul)

R = [
# L: 语言修复
("- 时间：<60min用分钟，>60min用小时/天",
 "- 时间：≤60分钟用分钟，更久用小时/天"),
("- 无需批准事项 → 说明假设（一句话以内）后直接执行。5项批准范围外但涉及外部影响/资金/敏感数据的，默认按需批准处理",
 "- 无需批准事项 → 说明假设（一句话以内）后直接执行"),
("- 3次修改同一问题未过验证 → 停止，问诊断问题。",
 "- 同一修改点3次未过验证 → 停止，问诊断问题。"),
# E: 错误处理扩容 + 新节「数据与模型可靠性」
("## 错误处理\n\n- 记录错误类型 → 判断是否可重试 → 用户可见反馈（简短原因）→ 同类错误达3次触发规则检查\n",
 "## 错误处理\n\n- 记录错误类型 → 判断是否可重试 → 用户可见反馈（简短原因）→ 同类错误达3次触发规则检查\n- 空输出/耗时异常 = 工具故障，不是结果。先查根因（返回体结构/参数/配额）再采信，\"没报error\"≠成功\n- 分析与审计类脚本复用前，用1个已知答案样例做黄金测试\n\n## 数据与模型可靠性\n\n- 模型调用链上限3个模型×2次，仍失败即停手上报，不无限重试\n- 关键交付（代码/发布内容/审计结论）禁止静默降级弱模型，降级前先声明\n- 模型/工具\"可用\"记录带最后验证日期，超30天先复测再引用\n- 写 GLOBAL.md 后必跑 global-verify.py，errors 清零才算完成\n"),
# E: 停滞提醒给执行载体
("- 任务停滞>3天 → 主动提醒",
 "- 会话开始扫描注入的近期记忆：发现停滞>7天的未闭环项目 → 首轮回复提醒（载体=注入记忆，不靠\"主动想起\"）"),
# C+E: 新节「状态与恢复」+ 规则书写范式
("## 自我迭代\n\n- 用户纠正 → 致歉+修正+记录（→ daily log）",
 "## 状态与恢复\n\n- 长任务每完成一步即落盘（daily log/产物文件），状态不留在会话内存里\n- 中断恢复 → 一句话交代\"上次到第X步/共Y步\"再继续\n- 写入 daily log 的教训标【待晋升】，周维护扫一遍决定晋升或作废\n\n## 自我迭代\n\n- 新增/改写规则先自检：触发载体是什么（会话开始/写入后/交付前）？违规可检测吗？无载体的规则改写为被动可检测形式或删除\n- 用户纠正 → 致歉+修正+记录（→ daily log）"),
# C: 记忆写入单一来源
("- 项目/领域特有 → 项目文档\n- 特定任务触发 → Skill\n- 跨会话复用 → GLOBAL.md\n- 临时笔记/错误记录 → daily log",
 "- 项目/领域特有 → 项目文档\n- 特定任务触发 → Skill\n- 跨会话复用 → GLOBAL.md\n- 临时笔记/错误记录 → daily log\n- 同一知识只写一层，其他层放指针；写入前查重"),
# 规则下推实践：命名规范移出 SOUL（已落 GLOBAL §三）
("\n### 技能命名规范\n\n- 目录名：全小写拼音+短横线（如 hai-bao-she-ji）\n- name字段：4字中文（如 海报设计）\n- system/英文来源：不动（如 grill-me）\n", ""),
]

fail=[]
for i,(old,new) in enumerate(R):
    n=soul.count(old)
    if n!=1: fail.append(f"R{i} count={n}"); continue
    soul=soul.replace(old,new)
if fail:
    print("ABORT, failed:",fail)
else:
    open("/var/minis/shared/soul-audit-v3/soul-v3.md","w").write(soul)
    json.dump(soul,open("/tmp/soul-v3.json","w"),ensure_ascii=False)
    print(f"OK {orig_len} -> {len(soul)} chars ({len(soul)-orig_len:+d})")
