"""novelkit/pipeline/review.py — 章节审核状态机（方案C+）。

v2 Phase 2：由 tools/gate-check.py 的 GateChecker 审核状态机方法移植，
逻辑逐行保真。状态文件：<project>/.novel/tracking/review-ch<NNN>.json。
"""

import json
import time
from typing import Dict, Optional

from novelkit.core.resolve import resolve


class ReviewStateMachine:
    """章节审核状态机：未初始化 → 待审核 → 已审核 / 审核驳回。"""

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        # BUG 10 修复（v1）：修前在 __init__ 里 mkdir → 构造函数有文件系统副作用，
        # 仅实例化即把已删除的项目目录"复活"。现惰性创建。
        self.status_dir = resolve(novel_id).root_dir / ".novel/tracking"

    def get_review_status(self, chapter_num: int) -> Dict:
        """获取章节审核状态。"""
        status_file = self.status_dir / f"review-ch{chapter_num:03d}.json"
        if not status_file.exists():
            return {
                "chapter": chapter_num,
                "status": "未初始化",
                "triggered_at": None,
                "no_feedback_rounds": 0,
                "reviewer_comment": None,
            }
        return json.loads(status_file.read_text(encoding='utf-8'))

    def set_review_status(self, chapter_num: int, status: str,
                          comment: Optional[str] = None):
        """设置章节审核状态。"""
        status_file = self.status_dir / f"review-ch{chapter_num:03d}.json"
        self.status_dir.mkdir(parents=True, exist_ok=True)  # 惰性创建（BUG 10）
        data = {
            "chapter": chapter_num,
            "status": status,
            "triggered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "no_feedback_rounds": 0,
            "reviewer_comment": comment,
        }
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def trigger_review(self, chapter_num: int) -> Dict:
        """触发审核（创作完成 → 待审核）。"""
        status = self.get_review_status(chapter_num)
        if status["status"] == "待审核":
            return {"success": False, "chapter": chapter_num,
                    "message": f"第{chapter_num}章已在待审核队列中"}
        if status["status"] == "已审核":
            return {"success": False, "chapter": chapter_num,
                    "message": f"第{chapter_num}章已完成审核，无需重复触发"}

        self.set_review_status(chapter_num, "待审核")
        return {"success": True, "chapter": chapter_num,
                "message": f"第{chapter_num}章已加入审核队列"}

    def auto_approve(self, chapter_num: int) -> Dict:
        """自动通过（连续3轮无反馈 → 已审核）。"""
        status = self.get_review_status(chapter_num)
        if status["status"] != "待审核":
            return {"success": False, "chapter": chapter_num,
                    "message": f"第{chapter_num}章不在待审核状态"}

        # 检查是否达到3轮无反馈阈值
        if status.get("no_feedback_rounds", 0) < 3:
            return {"success": False, "chapter": chapter_num,
                    "message": f"第{chapter_num}章仅无反馈{status.get('no_feedback_rounds', 0)}轮，需达到3轮"}

        self.set_review_status(chapter_num, "已审核", comment="连续3轮无反馈，默认通过")
        return {"success": True, "chapter": chapter_num,
                "message": f"第{chapter_num}章审核默认通过（连续3轮无反馈）"}

    def reject_review(self, chapter_num: int, reason: str) -> Dict:
        """驳回审核（审核发现重大问题 → 审核驳回）。"""
        status = self.get_review_status(chapter_num)
        if status["status"] != "待审核":
            return {"success": False, "chapter": chapter_num,
                    "message": f"第{chapter_num}章不在待审核状态"}

        self.set_review_status(chapter_num, "审核驳回", comment=reason)
        return {"success": True, "chapter": chapter_num,
                "message": f"第{chapter_num}章审核驳回：{reason}"}

    def increment_no_feedback(self, chapter_num: int) -> Dict:
        """增加无反馈轮次（每次调用后无回复时增加）。"""
        status = self.get_review_status(chapter_num)
        if status["status"] != "待审核":
            return {"chapter": chapter_num, "rounds": 0, "should_auto_approve": False}

        rounds = status.get("no_feedback_rounds", 0) + 1
        status_file = self.status_dir / f"review-ch{chapter_num:03d}.json"
        self.status_dir.mkdir(parents=True, exist_ok=True)  # 惰性创建（BUG 10）
        data = json.loads(status_file.read_text(encoding='utf-8'))
        data["no_feedback_rounds"] = rounds
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

        return {
            "chapter": chapter_num,
            "rounds": rounds,
            "should_auto_approve": rounds >= 3,
        }

    def get_block_status(self, chapter_num: int) -> Dict:
        """检查章节是否阻塞下一章创作。"""
        status = self.get_review_status(chapter_num)
        if status["status"] == "待审核":
            return {
                "blocked": True,
                "reason": f"第{chapter_num}章处于待审核状态，需等待审核结果或连续3轮无反馈自动通过",
                "status": "待审核",
            }
        if status["status"] == "审核驳回":
            return {
                "blocked": True,
                "reason": f"第{chapter_num}章审核驳回，需回炉修改后重新提交",
                "status": "审核驳回",
            }
        return {
            "blocked": False,
            "reason": None,
            "status": status["status"],
        }
