#!/usr/bin/env python3
"""
合同树前置校验工具 — v0.46.0新增，v0.50.0升级

功能：
  1. 大纲阶段预校验（轻量版合同树）
  2. 账目/线头/事实三类字段咬合检查
  3. 潜在风险点标记
  4. 校验报告生成
  5. 爽点节拍校验（v0.50.0，Progression-Architect 借鉴：L1-L4 分层+压抑上限+破冰）
  6. 兼容两种大纲结构：flat {chapters:{}} 与 volumes[] 嵌套（v0.50.0 修复）

章节节拍字段契约（写入大纲每章可选字段）：
  thrill:  "L1"|"L2"|"L3"|"L4"   本章最高爽点层级（缺省视为 L0 无正反馈）
  depress: true                  本章为压抑过渡章（无正反馈）

爽点四层（见 docs/成长经济节奏整合报告-v1.0.md）：
  L1 每章小胜利 / L2 每3-5章中收获 / L3 每卷2-3次大高潮 / L4 每卷1次格局跃迁

使用：
  python outline-precheck.py check --project projects/my-novel
  python outline-precheck.py check --project projects/my-novel --strict
  python outline-precheck.py beats --project projects/my-novel   # 只跑节拍校验
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class OutlinePrecheck:
    """大纲阶段合同树预校验"""
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.outline_file = self.project_dir / "outline" / "outline.json"
        self.world_file = self.project_dir / "world" / "world-pack.json"
        self.characters_file = self.project_dir / "characters" / "characters.json"
        
        self.outline_data = {}
        self.world_data = {}
        self.characters_data = {}
        
        self.risks = []
        self.warnings = []
        self.errors = []
    
    def load_data(self):
        """加载项目数据并归一化"""
        if self.outline_file.exists():
            self.outline_data = json.loads(self.outline_file.read_text(encoding='utf-8'))
        
        if self.world_file.exists():
            self.world_data = json.loads(self.world_file.read_text(encoding='utf-8'))
        
        if self.characters_file.exists():
            self.characters_data = json.loads(self.characters_file.read_text(encoding='utf-8'))
        
        self._normalize()
    
    def _normalize(self):
        """兼容两种大纲结构：flat chapters-dict 与 volumes 嵌套列表。
        
        归一化输出：
          self.chapters        {str(全局章号): chapter_dict}
          self.volumes         {vol_num: {"title":..., "chapter_nums":[str,...]}}
          self.foreshadowings  {id: foreshadow_dict}
        """
        self.chapters = {}
        self.volumes = {}
        
        data = self.outline_data
        if isinstance(data.get("chapters"), dict):
            self.chapters = data["chapters"]
        elif isinstance(data.get("volumes"), list):
            offset = 0
            for vi, vol in enumerate(data["volumes"], 1):
                vnum = vol.get("num", vi)
                nums = []
                for ch in vol.get("chapters", []):
                    offset += 1
                    key = str(offset)
                    ch = dict(ch)
                    ch["_volume"] = vnum
                    ch["_volume_chapter"] = ch.get("num")
                    self.chapters[key] = ch
                    nums.append(key)
                self.volumes[vnum] = {"title": vol.get("title", ""), "chapter_nums": nums}
        
        fsh = data.get("foreshadowings", {})
        if isinstance(fsh, list):
            fsh = {f.get("id", f"fs-{i}"): f for i, f in enumerate(fsh)}
        self.foreshadowings = fsh
        
        chars = self.characters_data.get("characters", {})
        if isinstance(chars, list):
            chars = {c.get("id", c.get("name", f"char-{i}")): c for i, c in enumerate(chars)}
        self.characters_map = chars
    
    def check(self, strict: bool = False) -> Dict:
        """
        执行前置校验
        
        参数：
            strict: 是否启用严格模式（错误级别升级）
        
        返回：
            校验报告
        """
        self.load_data()
        
        # 清空之前的结果
        self.risks = []
        self.warnings = []
        self.errors = []
        
        # 1. 检查大纲基本结构
        self._check_outline_structure()
        
        # 2. 检查角色与大纲的一致性
        self._check_character_outline_consistency()
        
        # 3. 检查世界设定与大纲的一致性
        self._check_world_outline_consistency()
        
        # 4. 检查伏笔与大纲的一致性
        self._check_foreshadow_outline_consistency()
        
        # 5. 检查数值一致性（防跳变）
        self._check_numerical_consistency()
        
        # 6. 爽点节拍校验（L1-L4，Progression-Architect 借鉴）
        self._check_pacing_beats()
        
        # 7. 检查潜在风险点
        self._identify_potential_risks()
        
        # 生成报告
        report = self._generate_report(strict)
        
        return report
    
    def _check_outline_structure(self):
        """检查大纲基本结构"""
        chapters = self.chapters
        
        if not chapters:
            self.warnings.append("大纲中未定义任何章节")
            return
        
        # 检查章节编号连续性
        chapter_nums = sorted([int(k) for k in chapters.keys()])
        expected_nums = list(range(1, max(chapter_nums) + 1))
        missing = set(expected_nums) - set(chapter_nums)
        
        if missing:
            self.warnings.append(f"章节编号不连续，缺失：{sorted(missing)}")
        
        # 检查章节标题
        for num, chapter in chapters.items():
            if not chapter.get("title"):
                self.errors.append(f"第{num}章缺少标题")
            
            if not chapter.get("summary"):
                self.warnings.append(f"第{num}章缺少摘要")
    
    def _check_character_outline_consistency(self):
        """检查角色与大纲的一致性"""
        characters = self.characters_map
        chapters = self.chapters
        
        # 检查大纲中引用的角色是否存在
        for num, chapter in chapters.items():
            mentioned_chars = re.findall(r"角色[：:](\w+)", chapter.get("summary", ""))
            for char_name in mentioned_chars:
                if char_name not in characters:
                    self.risks.append(f"第{num}章引用角色'{char_name}'，但该角色未定义")
    
    def _check_world_outline_consistency(self):
        """检查世界设定与大纲的一致性"""
        world = self.world_data.get("world", {})
        chapters = self.chapters
        
        # 检查大纲中引用的地点是否存在
        for num, chapter in chapters.items():
            mentioned_places = re.findall(r"地点[：:](\w+)", chapter.get("summary", ""))
            for place in mentioned_places:
                places_in_world = [p.get("name") for p in world.get("places", [])]
                if place not in places_in_world:
                    self.risks.append(f"第{num}章引用地点'{place}'，但该地点未在世界包中定义")
    
    def _check_foreshadow_outline_consistency(self):
        """检查伏笔与大纲的一致性"""
        foreshadowings = self.foreshadowings
        chapters = self.chapters
        
        # 检查伏笔的埋设和回收章节是否存在
        for fid, foreshadow in foreshadowings.items():
            planted_at = foreshadow.get("planted_at")
            payoff_at = foreshadow.get("payoff_at")
            
            if planted_at and planted_at not in chapters:
                self.errors.append(f"伏笔{fid}埋设章节{planted_at}不存在")
            
            if payoff_at and payoff_at not in chapters:
                self.warnings.append(f"伏笔{fid}回收章节{payoff_at}不存在，可能无法回收")
    
    _THRILL_ORDER = {"L0": 0, "": 0, None: 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
    
    def _thrill(self, chapter: Dict) -> int:
        """读取章节爽点层级，返回序数（L0=无标注）"""
        lv = str(chapter.get("thrill", "")).strip().upper()
        return self._THRILL_ORDER.get(lv, 0)
    
    def _check_pacing_beats(self):
        """爽点节拍校验（Progression-Architect 借鉴，规则见 law_节奏/law_爽点）
        
        章节字段：thrill=L1..L4（本章最高爽点层级）；depress=true（压抑过渡章）。
        大纲若完全未标注 thrill，跳过本校验（避免旧大纲噪音）。
        """
        chapters = self.chapters
        if not chapters:
            return
        
        tagged = [c for c in chapters.values() if str(c.get("thrill", "")).strip()]
        if not tagged:
            self.risks.append("节拍校验跳过：大纲章节均未标注 thrill（L1-L4）字段，"
                              "建议按 law_爽点_0001 四层分级标注后重跑")
            return
        
        coverage = len(tagged) / len(chapters)
        if coverage < 0.8:
            self.warnings.append(f"爽点层级标注覆盖率偏低（{len(tagged)}/{len(chapters)}），未标注章按 L0 处理")
        
        ordered = sorted(chapters.items(), key=lambda kv: int(kv[0]))
        
        # 规则1：破冰——前3章至少1章 >= L2
        first3 = [self._thrill(c) for _, c in ordered[:3]]
        if first3 and max(first3) < 2:
            self.warnings.append("破冰失败：前3章无 L2+ 中爽点，读者入坑动力不足（对齐前150字冲突/前500字金手指）")
        
        # 规则2：压抑上限——连续2章无正反馈（depress 或 L0），第3章必须 >= L2
        streak = 0
        for idx, (num, ch) in enumerate(ordered):
            no_feedback = bool(ch.get("depress")) or self._thrill(ch) == 0
            streak = streak + 1 if no_feedback else 0
            if streak >= 3:
                self.warnings.append(
                    f"压抑超限：第{ordered[idx-2][0]}-{num}章连续{streak}章无正反馈，"
                    f"规则=连续2章压抑后第3章必须爽点章（L2+）")
        
        # 规则3：里程碑间隔——连续>5章只有L1
        run, run_start = 0, None
        for num, ch in ordered:
            if self._thrill(ch) == 1:
                if run == 0:
                    run_start = num
                run += 1
                if run == 6:
                    self.warnings.append(
                        f"里程碑缺失：第{run_start}章起连续6+章仅L1，成长期应每3-5章安排1个L2+里程碑")
            else:
                run = 0
        
        # 规则4：疲劳——连续3章 L4
        run = 0
        for idx, (num, ch) in enumerate(ordered):
            run = run + 1 if self._thrill(ch) == 4 else 0
            if run == 3:
                self.warnings.append(
                    f"爽点疲劳：第{ordered[idx-2][0]}-{num}章连续3章L4顶级爽点（配额=每卷1次），高潮通胀")
                break
        
        # 规则5：卷末L4——每卷至少1个L4（仅对有卷结构且该卷>=10章时检查）
        for vnum, vol in self.volumes.items():
            nums = vol["chapter_nums"]
            if len(nums) < 10:
                continue
            levels = [self._thrill(self.chapters[n]) for n in nums]
            if max(levels) < 4 if levels else True:
                self.warnings.append(f"卷{vnum}（{vol['title']}）缺少L4格局跃迁章，卷末大高潮缺位")
    
    def _check_numerical_consistency(self):
        """检查数值一致性（防跳变）"""
        characters = self.characters_map
        chapters = self.chapters
        
        # 检查角色境界变化
        for char_id, char_data in characters.items():
            realm_history = char_data.get("realm_history", [])
            if len(realm_history) > 1:
                # 检查是否有跳变（一次突破多个境界）
                for i in range(1, len(realm_history)):
                    prev_realm = realm_history[i-1].get("realm", "")
                    curr_realm = realm_history[i].get("realm", "")
                    if prev_realm and curr_realm and prev_realm != curr_realm:
                        # 简单判断：如果境界名完全不同，可能是跳变
                        if "期" in prev_realm and "期" in curr_realm:
                            prev_level = int(re.search(r'(\d+)', prev_realm).group(1) if re.search(r'(\d+)', prev_realm) else 0)
                            curr_level = int(re.search(r'(\d+)', curr_realm).group(1) if re.search(r'(\d+)', curr_realm) else 0)
                            if curr_level - prev_level > 1:
                                self.risks.append(f"角色{char_id}境界从{prev_realm}跳到{curr_realm}，可能缺少过渡描写")
    
    def _identify_potential_risks(self):
        """识别潜在风险点"""
        chapters = self.chapters
        foreshadowings = self.foreshadowings
        
        # 检查未回收的伏笔
        unpaid_foreshadowings = [f for f in foreshadowings.values() if f.get("status") == "planted" and not f.get("payoff_at")]
        if len(unpaid_foreshadowings) > len(chapters) * 0.3:
            self.warnings.append(f"未回收伏笔比例过高（{len(unpaid_foreshadowings)}/{len(foreshadowings)}），建议检查伏笔回收计划")
        
        # 检查章节字数目标
        total_target = sum(c.get("word_count_target", 0) for c in chapters.values())
        avg_target = total_target / len(chapters) if chapters else 0
        
        if avg_target < 1500:
            self.warnings.append(f"平均章节字数目标过低（{avg_target:.0f}字），可能影响故事质量")
        elif avg_target > 3000:
            self.warnings.append(f"平均章节字数目标过高（{avg_target:.0f}字），可能影响创作效率")
    
    def _generate_report(self, strict: bool) -> Dict:
        """生成校验报告"""
        # 根据strict参数调整错误级别
        if strict:
            # 严格模式：warning升级为error
            errors = self.errors + self.warnings
            warnings = []
        else:
            errors = self.errors
            warnings = self.warnings
        
        # 计算总体状态
        if errors:
            status = "fail"
        elif warnings or self.risks:
            status = "warning"
        else:
            status = "pass"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "strict_mode": strict,
            "summary": {
                "errors": len(errors),
                "warnings": len(warnings),
                "risks": len(self.risks)
            },
            "errors": errors,
            "warnings": warnings,
            "risks": self.risks,
            "recommendations": self._generate_recommendations(errors, warnings, self.risks)
        }
    
    def _generate_recommendations(self, errors: List[str], warnings: List[str], risks: List[str]) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        if errors:
            recommendations.append("必须先解决所有错误才能继续创作")
        
        if warnings:
            recommendations.append("建议处理警告，避免后续问题")
        
        if risks:
            recommendations.append("注意潜在风险，在创作过程中留意")
        
        # 针对性建议
        for error in errors:
            if "缺少标题" in error:
                recommendations.append("为缺失标题的章节补充标题")
            elif "引用角色" in error and "未定义" in error:
                recommendations.append("在世界包中补充缺失的角色设定")
            elif "引用地点" in error and "未定义" in error:
                recommendations.append("在世界包中补充缺失的地点设定")
        
        for risk in risks:
            if "境界" in risk and "跳变" in risk:
                recommendations.append("在相关章节补充境界突破的详细描写")
            elif "伏笔" in risk and "未回收" in risk:
                recommendations.append("规划伏笔回收章节，避免烂尾")
        
        # 节拍类建议
        all_msgs = errors + warnings
        for msg in all_msgs:
            if "破冰" in msg:
                recommendations.append("前3章至少安排1个L2+中爽点（境界小成/新功法/地位提升）")
            elif "压抑超限" in msg:
                recommendations.append("连续2章压抑后第3章必须给爽点（law_节奏_0001 硬规则）")
            elif "里程碑缺失" in msg:
                recommendations.append("在连续L1段落中段插入L2+里程碑章（每3-5章1个）")
            elif "爽点疲劳" in msg:
                recommendations.append("L4顶级爽点配额=每卷1次，将多余高潮降级为L3")
            elif "L4格局跃迁" in msg:
                recommendations.append("为该卷卷末规划1个L4章（大境界突破/格局改变/真相揭示）")
        
        return recommendations


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="合同树前置校验工具")
    parser.add_argument("command", nargs="?", default="check", choices=["check", "beats"],
                        help="check=全量校验（默认）；beats=只跑爽点节拍校验")
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument("--strict", action="store_true", help="启用严格模式")
    
    args = parser.parse_args()
    
    precheck = OutlinePrecheck(args.project)
    
    if args.command == "beats":
        precheck.load_data()
        precheck._check_pacing_beats()
        result = precheck._generate_report(strict=args.strict)
    else:
        result = precheck.check(strict=args.strict)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
