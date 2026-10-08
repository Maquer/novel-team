#!/usr/bin/env python3
"""
文风蒸馏器 style-distiller

借鉴：awesome-novel-agent (modoojunko/awesome-novel-agent, 778★) style-distiller
核心：量化文风参数（句长/对话占比/形容词密度等），归档后增量校准，越写越贴合风格

量化维度：
1. 平均句长（汉字数/句子数）
2. 对话占比（对话字数/总字数）
3. 形容词密度（形容词数/千字）
4. 动作描写密度（动作词数/千字）
5. 感官描写密度（感官词数/千字）
6. 段落平均长度
7. 句长变异系数（标准差/均值）
8. 短句占比（<10字的句子比例）
9. 长句占比（>30字的句子比例）
10. 对话句平均长度

用法：
  python3 style-distiller.py distill --novel-id <id> --sample <file>  # 蒸馏样本文风
  python3 style-distiller.py profile --novel-id <id>                  # 查看文风主卡
  python3 style-distiller.py compare --novel-id <id> --chapter <N> --content <file>  # 对比文风
  python3 style-distiller.py calibrate --novel-id <id> --chapter <N>  # 增量校准
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime


class StyleDistiller:
    """文风蒸馏+增量校准系统"""

    # 量化参数定义
    DIMENSIONS = [
        "avg_sentence_length",      # 平均句长
        "dialogue_ratio",            # 对话占比
        "adjective_density",         # 形容词密度（/千字）
        "action_density",            # 动作描写密度（/千字）
        "sensory_density",           # 感官描写密度（/千字）
        "avg_paragraph_length",     # 段落平均长度
        "sentence_length_cv",       # 句长变异系数
        "short_sentence_ratio",     # 短句占比（<10字）
        "long_sentence_ratio",      # 长句占比（>30字）
        "dialogue_avg_length",      # 对话句平均长度
    ]

    # 形容词模式（简化）
    ADJECTIVE_PATTERNS = [
        r'美丽', r'漂亮', r'英俊', r'丑陋', r'高大', r'矮小',
        r'明亮', r'阴暗', r'温暖', r'寒冷', r'柔和', r'刺眼',
        r'沉重', r'轻盈', r'缓慢', r'迅速', r'安静', r'嘈杂',
        r'古老', r'崭新', r'破旧', r'华丽', r'朴素', r'精致',
        r'巨大的', r'微小的', r'宽阔的', r'狭窄的',
        r'冰冷的', r'炽热的', r'锋利的', '钝重的',
        r'苍白的', r'通红的', r'漆黑的', r'雪白的',
    ]

    # 动作描写模式
    ACTION_PATTERNS = [
        r'走|跑|跳|蹲|站|坐|躺|转|退|冲|扑|抓|握|推|拉|踢|打|挥|举|放|扔',
        r'抬头|低头|回头|侧头|点头|摇头',
        r'睁眼|闭眼|眨眼|瞪|瞥|凝视',
        r'微笑|大笑|苦笑|冷笑|皱眉|蹙眉',
        r'深呼吸|叹气|喘|呼吸',
    ]

    # 感官描写模式
    SENSORY_PATTERNS = [
        r'看到|看见|望去|映入眼帘|目光',
        r'听到|听见|声音|响|鸣|轰',
        r'闻到|气味|香味|臭味|腥味',
        r'尝到|味道|苦|甜|酸|辣|咸',
        r'摸到|触感|冰凉|滚烫|粗糙|光滑',
        r'感到|感觉|一阵.*涌上',
    ]

    def __init__(self, novel_id: str = None, project_root: str = None):
        self.novel_id = novel_id
        self.root = Path(project_root or f"novels/{novel_id}")
        self.profile_file = self.root / ".style-profile.json"
        self.history_file = self.root / ".style-versions.json"

    def distill(self, sample_text: str, source: str = "sample") -> dict:
        """蒸馏样本文风——提取量化参数"""
        params = self._extract_params(sample_text)

        profile = self._load_profile()
        if not profile:
            # 首次蒸馏——创建主卡
            profile = {
                "novel_id": self.novel_id,
                "created_at": datetime.now().isoformat(),
                "main_card": params,
                "scene_cards": {},  # 分场景风格卡
                "version": 1,
                "calibration_history": [],
            }
        else:
            # 增量校准——合并到主卡
            profile["main_card"] = self._merge_params(
                profile["main_card"], params, weight=0.3
            )
            profile["version"] += 1

        profile["last_updated"] = datetime.now().isoformat()
        profile["last_source"] = source

        self._save_profile(profile)

        # 保存版本快照
        self._save_version_snapshot(params, source)

        return {
            "success": True,
            "version": profile["version"],
            "params": params,
            "main_card": profile["main_card"],
        }

    def _extract_params(self, text: str) -> dict:
        """提取量化参数"""
        # 清理
        clean = re.sub(r'^#.*$', '', text, flags=re.MULTILINE)  # 去标题
        clean_text = re.sub(r'[\s\n\r\t]', '', clean)  # 纯文本
        total_chars = len(clean_text)
        if total_chars == 0:
            return {d: 0 for d in self.DIMENSIONS}

        # 句子分割
        sentences = [s for s in re.split(r'[。！？]', clean) if s.strip()]
        sentence_count = max(1, len(sentences))

        # 段落
        paragraphs = [p for p in clean.split('\n') if p.strip()]
        para_count = max(1, len(paragraphs))

        # 句长
        sentence_lengths = [len(re.sub(r'[\s]', '', s)) for s in sentences]
        avg_sent_len = sum(sentence_lengths) / sentence_count
        variance = sum((l - avg_sent_len) ** 2 for l in sentence_lengths) / sentence_count
        std_sent_len = variance ** 0.5
        cv_sent_len = std_sent_len / avg_sent_len if avg_sent_len > 0 else 0

        # 短句/长句占比
        short_count = sum(1 for l in sentence_lengths if l < 10)
        long_count = sum(1 for l in sentence_lengths if l > 30)

        # 对话
        dialogues = re.findall(r'"([^"]+)"|「([^」]+)」', clean)
        dlg_texts = [d[0] or d[1] for d in dialogues if (d[0] or d[1])]
        dlg_chars = sum(len(d) for d in dlg_texts)
        dialogue_ratio = dlg_chars / total_chars if total_chars > 0 else 0
        dlg_avg_len = (sum(len(d) for d in dlg_texts) / len(dlg_texts)) if dlg_texts else 0

        # 形容词密度
        adj_count = 0
        for pat in self.ADJECTIVE_PATTERNS:
            adj_count += len(re.findall(pat, clean))
        adj_density = adj_count / (total_chars / 1000) if total_chars > 0 else 0

        # 动作描写密度
        action_count = 0
        for pat in self.ACTION_PATTERNS:
            action_count += len(re.findall(pat, clean))
        action_density = action_count / (total_chars / 1000) if total_chars > 0 else 0

        # 感官描写密度
        sensory_count = 0
        for pat in self.SENSORY_PATTERNS:
            sensory_count += len(re.findall(pat, clean))
        sensory_density = sensory_count / (total_chars / 1000) if total_chars > 0 else 0

        # 段落长度
        para_lengths = [len(re.sub(r'[\s]', '', p)) for p in paragraphs]
        avg_para_len = sum(para_lengths) / para_count if para_count > 0 else 0

        return {
            "avg_sentence_length": round(avg_sent_len, 1),
            "dialogue_ratio": round(dialogue_ratio, 3),
            "adjective_density": round(adj_density, 1),
            "action_density": round(action_density, 1),
            "sensory_density": round(sensory_density, 1),
            "avg_paragraph_length": round(avg_para_len, 1),
            "sentence_length_cv": round(cv_sent_len, 3),
            "short_sentence_ratio": round(short_count / sentence_count, 3),
            "long_sentence_ratio": round(long_count / sentence_count, 3),
            "dialogue_avg_length": round(dlg_avg_len, 1),
        }

    def _merge_params(self, old: dict, new: dict, weight: float = 0.3) -> dict:
        """增量校准——新旧参数加权合并"""
        merged = {}
        for key in self.DIMENSIONS:
            old_val = old.get(key, 0)
            new_val = new.get(key, 0)
            merged[key] = round(old_val * (1 - weight) + new_val * weight, 3)
        return merged

    def compare(self, content: str) -> dict:
        """对比当前文本与文风主卡的偏差"""
        current = self._extract_params(content)
        profile = self._load_profile()
        if not profile:
            return {"success": False, "error": "无文风主卡，请先蒸馏"}

        main_card = profile["main_card"]
        deviations = {}
        for key in self.DIMENSIONS:
            target = main_card.get(key, 0)
            actual = current.get(key, 0)
            if target > 0:
                dev = abs(actual - target) / target
            else:
                dev = 0 if actual == 0 else 1
            deviations[key] = round(dev, 3)

        # 总偏差
        avg_dev = sum(deviations.values()) / len(deviations)
        match_score = round(max(0, 1 - avg_dev) * 100, 1)

        return {
            "success": True,
            "match_score": match_score,
            "avg_deviation": round(avg_dev, 3),
            "deviations": deviations,
            "current": current,
            "target": main_card,
            "level": "high" if match_score >= 80 else "medium" if match_score >= 60 else "low",
        }

    def calibrate(self, chapter: int, content: str) -> dict:
        """增量校准——用新章节内容更新文风主卡"""
        result = self.distill(content, source=f"chapter_{chapter}")
        result["calibration"] = True
        result["chapter"] = chapter
        return result

    def get_profile(self) -> dict:
        """查看文风主卡"""
        profile = self._load_profile()
        if not profile:
            return {"success": False, "error": "无文风主卡"}
        return {
            "success": True,
            "version": profile["version"],
            "main_card": profile["main_card"],
            "scene_cards": profile.get("scene_cards", {}),
            "last_updated": profile.get("last_updated", ""),
            "calibration_count": len(profile.get("calibration_history", [])),
        }

    def _load_profile(self):
        if self.profile_file.exists():
            return json.loads(self.profile_file.read_text(encoding="utf-8"))
        return None

    def _save_profile(self, profile):
        self.profile_file.parent.mkdir(parents=True, exist_ok=True)
        self.profile_file.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _save_version_snapshot(self, params, source):
        versions = []
        if self.history_file.exists():
            versions = json.loads(self.history_file.read_text(encoding="utf-8"))
        versions.append({
            "version": len(versions) + 1,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "params": params,
        })
        self.history_file.write_text(
            json.dumps(versions, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="文风蒸馏器")
    parser.add_argument("--novel-id", default=None)
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="cmd")

    p_distill = sub.add_parser("distill", help="蒸馏样本文风")
    p_distill.add_argument("--sample", required=True, help="样本文件路径")

    p_compare = sub.add_parser("compare", help="对比文风")
    p_compare.add_argument("--content", required=True, help="对比文件路径")

    p_calibrate = sub.add_parser("calibrate", help="增量校准")
    p_calibrate.add_argument("--chapter", type=int, required=True)
    p_calibrate.add_argument("--content", required=True)

    sub.add_parser("profile", help="查看文风主卡")

    args = parser.parse_args()
    sd = StyleDistiller(args.novel_id, args.project_root)

    if args.cmd == "distill":
        text = Path(args.sample).read_text(encoding="utf-8")
        result = sd.distill(text, source="manual")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "compare":
        text = Path(args.content).read_text(encoding="utf-8")
        result = sd.compare(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "calibrate":
        text = Path(args.content).read_text(encoding="utf-8")
        result = sd.calibrate(args.chapter, text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "profile":
        result = sd.get_profile()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
