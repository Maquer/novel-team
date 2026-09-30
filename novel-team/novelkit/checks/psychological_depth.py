# Version: 2.1.0
"""心理描写深度检测插件（v2 Phase 2：防直白/流水账/写剧本感）。

P2 建议级，不阻断。核心洞察（来自用户反馈「文章直白、像写剧本、全是短篇」）：
AI 生成小说最常见的心理描写缺陷是「作者跳出来总结」——用「他想/她觉得/他意识到」
直接告诉读者角色心理，而不是通过生理反应/环境投射/回忆闪回间接展现。

规则分类：
  A. 直白心理词：「他想/她觉得/他意识到/他明白/他感到」→ 建议改为间接展现
  B. 缺心理展现：含强情绪词（怒/惊/悲/喜/慌）但无生理/环境细节 → 建议补描写
  C. 情绪词堆砌：一段内重复使用同一情绪词 → 建议差异化表达

依据：写作指南《Show, Don't Tell》+ 用户实测反馈
"""

import re

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity


# A 类：直白心理动词（告诉而非展现）
# 建议：修改为生理反应/动作/环境投射/回忆闪回
DIRECT_THINK_PATTERNS = [
    (re.compile(r"他[们]?想[到]?[^。；\n]{0,8}[，,]?\s*就是"), "直白心理『他想…就是』"),
    (re.compile(r"她[们]?想[到]?[^。；\n]{0,8}[，,]?\s*就是"), "直白心理『她想…就是』"),
    (re.compile(r"他[们]?觉得[^。；\n]{0,15}[，,]"), "直白『他觉得』"),
    (re.compile(r"她[们]?觉得[^。；\n]{0,15}[，,]"), "直白『她觉得』"),
    (re.compile(r"他[们]?意识[到到]?[^。；\n]{0,10}"), "直白『他意识到』"),
    (re.compile(r"她[们]?意识[到到]?[^。；\n]{0,10}"), "直白『她意识到』"),
    (re.compile(r"他[们]?明白[了否]?[^。；\n]{0,8}"), "直白『他明白』"),
    (re.compile(r"她[们]?明白[了否]?[^。；\n]{0,8}"), "直白『她明白』"),
    (re.compile(r"他[们]?心中[^。；\n]{0,20}[，,]"), "直白『他心中…』"),
    (re.compile(r"她[们]?心中[^。；\n]{0,20}[，,]"), "直白『她心中…』"),
    (re.compile(r"他[们]?暗自[^。；\n]{0,15}"), "直白『他暗自…』"),
    (re.compile(r"她[们]?暗自[^。；\n]{0,15}"), "直白『她暗自…』"),
    (re.compile(r"暗[中自]?里[^。；\n]{0,15}"), "直白『暗地里…』"),
]

# B 类：强情绪词出现但周边无生理/环境细节
# 检测「情绪词±5字内」是否有关联的生理动词或环境描写
EMOTION_WORDS = ["怒", "惊", "悲", "喜", "慌", "惧", "恨", "痛", "悲", "愤",
                 "恐惧", "愤怒", "惊喜", "悲痛", "慌乱", "仇恨", "痛苦", "悲伤"]
# 生理反应信号（暗示情绪，不直接说）
PHYSIOLOGICAL_SIGNALS = [
    r"手[指颤|发抖|紧握|攥紧|微微发抖|不受控制]",
    r"心[跳加快|一沉|猛地一跳|口收紧]",
    r"呼吸[一滞|变急|骤然放缓]",
    r"脊[背发凉|背上]']",
    r"瞳孔[收缩|骤缩|猛地放大]",
    r"喉[结滚动|头微动]",
    r"脸色[一白|骤变|惨白]",
    r"指尖[发麻|发凉]",
    r"膝盖[发软|一软]",
    r"拳头[攥紧|握紧]",
    r"眼神[一凝|暗变|微沉]",
    r"眉[梢微挑|尖紧蹙|头微皱]",
]

# C 类：同一段落内重复情绪描写
REPEAT_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,4}[，,。]", re.MULTILINE)


@register
class PsychologicalDepthCheck:
    """心理描写深度检测（P2 建议级，不阻断）——09-30 新增。"""

    name = "psychological_depth"
    default_severity = Severity.ADVICE

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        content = chapter.body
        details = []

        # A 类：直白心理词
        a_hits = self._check_direct_thinking(content)
        details.extend(a_hits)

        # B 类：有情绪词但无生理/环境细节
        b_hits = self._check_missing_physiological(content)
        details.extend(b_hits)

        # C 类：同段落重复情绪词
        c_hits = self._check_repetition(content)
        details.extend(c_hits)

        raw = {"status": "pass", "details": details,
               "a_direct": len(a_hits), "b_missing": len(b_hits), "c_repeat": len(c_hits)}

        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}.get(
            "fail" if details else "pass", CheckStatus.PASS)

        return CheckResult(
            check=self.name,
            status=status,
            severity=self.default_severity,
            details=details,
            raw=raw,
        )

    def _check_direct_thinking(self, text: str) -> list:
        """A类：检测直白心理动词，返回建议列表"""
        results = []
        for pat, label in DIRECT_THINK_PATTERNS:
            matches = pat.findall(text)
            if matches:
                # 取前2个具体位置
                for m in pat.finditer(text):
                    snippet = text[max(0, m.start()-5):m.end()+15]
                    results.append(f"{label} → {snippet.strip()}（建议：改为动作/表情/环境间接展现）")
                    if len(results) - len(matches) >= 2:  # 每模式最多2条
                        break
                if len(results) >= 6:  # 全局上限
                    break
        return results[:6]  # 最多6条

    def _check_missing_physiological(self, text: str) -> list:
        """B类：检测有情绪词但无生理/环境细节的段落"""
        # 按段落切分
        paragraphs = re.split(r'\n\s*\n', text)
        results = []
        phys_re = [re.compile(p) for p in PHYSIOLOGICAL_SIGNALS]

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) < 20:
                continue
            # 检查是否包含强情绪词
            has_emotion = any(ew in para for ew in EMOTION_WORDS)
            if not has_emotion:
                continue
            # 检查是否包含生理反应信号
            has_physio = any(p.search(para) for p in phys_re)
            if not has_physio:
                # 情绪词存在但无生理描写 → 建议补充
                snippet = para[:80].replace('\n', ' ')
                results.append(
                    f"第{i+1}段含情绪词但无生理细节 → {snippet}（建议：加『手紧攥/心跳加速/呼吸一滞』等）")
                if len(results) >= 3:
                    break
        return results

    def _check_repetition(self, text: str) -> list:
        """C类：同段落重复情绪描写"""
        paragraphs = re.split(r'\n\s*\n', text)
        results = []
        for para in paragraphs:
            para = para.strip()
            if len(para) < 30:
                continue
            # 统计同义情绪词出现次数
            emotion_count = sum(para.count(ew) for ew in EMOTION_WORDS)
            if emotion_count >= 3:
                results.append(
                    f"段落内情绪词重复{emotion_count}次（{EMOTION_WORDS[:5]}）→ 建议差异化表达")
                if len(results) >= 2:
                    break
        return results
