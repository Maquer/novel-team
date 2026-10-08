#!/usr/bin/env python3
"""
training-system.py — 团队培训系统

功能：
  1. 加载培训配置
  2. 执行技能训练
  3. 进行能力考核
  4. 记录培训档案
  5. 生成培训报告

使用：
  python training-system.py train --role director
  python training-system.py assess --role lead_writer
  python training-system.py report
  python training-system.py certify --role editor --level 1
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class TrainingRecord:
    """培训记录"""
    record_id: str
    member_id: str
    role: str
    skill: str
    start_time: str
    end_time: str
    duration_minutes: int
    score: int
    status: str  # completed/failed/ongoing
    feedback: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TrainingSystem:
    """培训系统"""
    
    def __init__(self, base_path: str = "team"):
        self.base_path = Path(base_path)
        self.members_file = self.base_path / "members.json"
        self.skills_file = self.base_path / "skills-config.json"
        self.training_file = self.base_path / "training-records.json"
        
        self.members = self._load_json(self.members_file)
        self.skills = self._load_json(self.skills_file)
        self.training = self._load_json(self.training_file)
    
    def _load_json(self, path: Path) -> Dict:
        """加载JSON文件"""
        if path.exists():
            return json.loads(path.read_text())
        return {}
    
    def _save_json(self, path: Path, data: Dict):
        """保存JSON文件"""
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def get_member(self, role: str) -> Optional[Dict]:
        """获取成员"""
        for member in self.members.get("members", []):
            if member["role"] == role:
                return member
        return None
    
    def get_training_program(self, role: str) -> Optional[Dict]:
        """获取培训计划"""
        return self.training.get("training_programs", {}).get(role)
    
    def train_skill(self, role: str, skill: str) -> Dict:
        """训练单个技能"""
        member = self.get_member(role)
        if not member:
            return {"error": f"未找到角色 {role} 的成员"}
        
        skill_def = self.skills.get("skill_definitions", {}).get(skill)
        if not skill_def:
            return {"error": f"未找到技能 {skill} 的定义"}
        
        # 模拟训练过程
        start_time = datetime.now()
        print(f"🎓 开始训练 {member['name']} 的 {skill} 技能...")
        
        # 执行训练（模拟）
        time.sleep(0.5)
        
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        
        # 模拟考核
        score = self._simulate_assessment(role, skill)
        status = "completed" if score >= 70 else "failed"
        
        # 记录培训
        record = {
            "record_id": f"train-{int(time.time())}",
            "member_id": member["id"],
            "role": role,
            "skill": skill,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": max(duration, 1),
            "score": score,
            "status": status,
            "feedback": f"得分{score}分，{'通过' if status == 'completed' else '需重新训练'}"
        }
        
        # 保存记录
        if "records" not in self.training:
            self.training["records"] = []
        if not isinstance(self.training["records"], list):
            self.training["records"] = []
        self.training["records"].append(record)
        
        # 更新成员状态
        if "skills" not in member:
            member["skills"] = []
        member["skills"].append({
            "skill": skill,
            "score": score,
            "status": status,
            "trained_at": end_time.isoformat(),
        })
        
        self._save_json(self.members_file, self.members)
        self._save_json(self.training_file, self.training)
        
        return {
            "member": member["name"],
            "skill": skill,
            "score": score,
            "status": status,
            "duration_minutes": record.duration_minutes,
        }
    
    def _simulate_assessment(self, role: str, skill: str) -> int:
        """模拟考核（根据角色和技能给出不同分数）"""
        # 基础分数
        base_scores = {
            "director": 85,
            "lead_writer": 90,
            "writer": 80,
            "world_builder": 88,
            "outline_designer": 87,
            "editor": 92,
            "style_optimizer": 85,
            "analyst": 83,
        }
        
        # 技能难度调整
        skill_difficulty = {
            "context-manager": 0,
            "plot-analyzer": 5,
            "plot-simulation-v2": 8,
            "wordcount-check": -5,
            "world-pack": 3,
            "world-init": 2,
            "fact-snapshot": 6,
            "story-graph": 4,
            "rag-enhanced": 7,
            "outline": 3,
            "outline-builder": 4,
            "foreshadow-service": 5,
            "contract-tree": 6,
            "gate-check": 7,
            "guard-v6": 8,
            "fact-ledger": 5,
            "decide-trigger": 4,
            "anti-ai-12": 6,
            "novel-humanizer": 7,
            "fusion-engine": 8,
            "batch-replace": -3,
            "merge-chapters": -2,
            "clean_commas": -5,
            "inject_punctuation": -4,
            "preference-memory": 3,
            "timeline": 2,
            "llm-integrator": 6,
            "knowledge-base": 5,
            "team-manager": 4,
            "capability-evaluator": 6,
        }
        
        base = base_scores.get(role, 80)
        adjustment = skill_difficulty.get(skill, 0)
        
        # 添加随机波动
        import random
        noise = random.randint(-5, 5)
        
        score = max(0, min(100, base + adjustment + noise))
        return score
    
    def train_all_skills(self, role: str) -> Dict:
        """训练角色的所有技能"""
        member = self.get_member(role)
        if not member:
            return {"error": f"未找到角色 {role} 的成员"}
        
        results = []
        for skill in member.get("skills", []):
            result = self.train_skill(role, skill)
            results.append(result)
        
        return {
            "role": role,
            "member_name": member["name"],
            "total_skills": len(results),
            "passed": sum(1 for r in results if r["status"] == "completed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "results": results,
        }
    
    def assess_member(self, role: str) -> Dict:
        """评估成员"""
        member = self.get_member(role)
        if not member:
            return {"error": f"未找到角色 {role} 的成员"}
        
        # 计算平均分数
        trained_skills = member.get("skills", [])
        if not trained_skills or not isinstance(trained_skills, list):
            return {
                "member": member["name"],
                "role": role,
                "status": "not_trained",
                "avg_score": 0,
                "skills_count": 0,
            }
        
        scores = [s["score"] for s in trained_skills if isinstance(s, dict)]
        avg_score = sum(scores) / len(scores)
        
        # 判断认证级别
        certification_level = 0
        if avg_score >= 90:
            certification_level = 3  # 专家
        elif avg_score >= 80:
            certification_level = 2  # 资深
        elif avg_score >= 70:
            certification_level = 1  # 初级
        
        return {
            "member": member["name"],
            "role": role,
            "status": "certified" if certification_level > 0 else "not_certified",
            "avg_score": round(avg_score, 1),
            "certification_level": certification_level,
            "skills_count": len(scores),
            "skills": trained_skills,
        }
    
    def generate_report(self) -> str:
        """生成培训报告"""
        lines = []
        lines.append("# 团队培训报告")
        lines.append("")
        lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 总体统计
        total_members = len(self.members.get("members", []))
        total_records = len(self.training.get("records", []))
        
        lines.append("## 一、总体统计")
        lines.append("")
        lines.append(f"- 团队成员：{total_members}人")
        lines.append(f"- 培训记录：{total_records}条")
        lines.append("")
        
        # 成员状态
        lines.append("## 二、成员培训状态")
        lines.append("")
        lines.append("| 姓名 | 角色 | 已培训技能 | 平均分 | 认证级别 |")
        lines.append("|------|------|-----------|--------|---------|")
        
        for member in self.members.get("members", []):
            role = member["role"]
            trained_skills = member.get("skills", [])
            skills_count = len(trained_skills)
            
            if trained_skills:
                avg_score = sum(s["score"] for s in trained_skills) / skills_count
                if avg_score >= 90:
                    level = "🟢 专家"
                elif avg_score >= 80:
                    level = "🟡 资深"
                elif avg_score >= 70:
                    level = "🔵 初级"
                else:
                    level = "⚪ 未认证"
            else:
                avg_score = 0
                level = "⚪ 未培训"
            
            lines.append(f"| {member['name']} | {role} | {skills_count} | {avg_score:.1f} | {level} |")
        
        lines.append("")
        
        # 技能掌握情况
        lines.append("## 三、技能掌握情况")
        lines.append("")
        
        all_skills = set()
        for member in self.members.get("members", []):
            member_skills = member.get("skills", [])
            if isinstance(member_skills, list):
                for s in member_skills:
                    if isinstance(s, dict) and "skill" in s:
                        all_skills.add(s["skill"])
        
        for skill in sorted(all_skills):
            passed = 0
            total = 0
            for member in self.members.get("members", []):
                member_skills = member.get("skills", [])
                if isinstance(member_skills, list):
                    for s in member_skills:
                        if isinstance(s, dict) and s.get("skill") == skill:
                            total += 1
                            if s.get("status") == "completed":
                                passed += 1
            lines.append(f"- **{skill}**: {passed}/{total} 通过")
        
        lines.append("")
        
        # 待培训技能
        pending = []
        for member in self.members.get("members", []):
            role = member["role"]
            program = self.get_training_program(role)
            if program:
                for module in program.get("modules", []):
                    skill = module["module"]
                    already_trained = False
                    member_skills = member.get("skills", [])
                    if isinstance(member_skills, list):
                        for s in member_skills:
                            if isinstance(s, dict) and s.get("skill") == skill:
                                already_trained = True
                                break
                    if not already_trained:
                        pending.append((member["name"], role, skill))
        
        if pending:
            lines.append("## 四、待培训技能")
            lines.append("")
            for name, role, skill in pending[:10]:
                lines.append(f"- {name} ({role}): {skill}")
            if len(pending) > 10:
                lines.append(f"... 还有 {len(pending)-10} 项")
            lines.append("")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="团队培训系统")
    parser.add_argument("--base", "-b", default="team", help="基础目录")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # train
    train_parser = subparsers.add_parser("train", help="培训技能")
    train_parser.add_argument("--role", "-r", required=True, help="角色")
    train_parser.add_argument("--skill", "-s", help="指定技能（不指定则训练全部）")
    
    # assess
    assess_parser = subparsers.add_parser("assess", help="评估成员")
    assess_parser.add_argument("--role", "-r", required=True, help="角色")
    
    # report
    report_parser = subparsers.add_parser("report", help="生成报告")
    report_parser.add_argument("--output", "-o", help="输出文件")
    
    args = parser.parse_args()
    
    system = TrainingSystem(args.base)
    
    if args.command == "train":
        if args.skill:
            result = system.train_skill(args.role, args.skill)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            result = system.train_all_skills(args.role)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "assess":
        result = system.assess_member(args.role)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "report":
        report = system.generate_report()
        if args.output:
            Path(args.output).write_text(report)
            print(f"✅ 报告已保存: {args.output}")
        else:
            print(report)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
