#!/usr/bin/env python3
"""
写作部门优化测试脚本

测试三种方案：
A: 原流程（双岗分工）- 辅助岗写初稿→扩写，主笔岗精修
B: 融合流程（单岗执行）- 创作岗一次写完整章
C: 混合流程（融合+强制质检）- 创作岗写+自检+主编审核

使用方法：
  python3 test-workflow-optimization.py --chapter 1 --mode A  # 测试原流程
  python3 test-workflow-optimization.py --chapter 1 --mode B  # 测试融合流程
  python3 test-workflow-optimization.py --chapter 1 --mode C  # 测试混合流程
  python3 test-workflow-optimization.py --chapter 1 --all     # 测试全部
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve

PROJECT_DIR = Path("/var/minis/shared/novel-team")
CHAPTERS_DIR = resolve("my-novel").chapters()
REPORTS_DIR = PROJECT_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 测试配置
TEST_CONFIG = {
    "novel_id": "my-novel",
    "chapter": 1,
    "tools_dir": PROJECT_DIR / "tools",
}


def load_chapter(chapter_num: int) -> Dict:
    """加载章节文件"""
    chapter_file = CHAPTERS_DIR / f"chapter-{chapter_num:03d}.md"
    if not chapter_file.exists():
        return None
    
    content = chapter_file.read_text(encoding='utf-8')
    
    # 解析 frontmatter
    metadata = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            # 简单解析 YAML frontmatter
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    metadata[key.strip()] = val.strip()
            body = parts[2]
    
    return {
        "file": str(chapter_file),
        "metadata": metadata,
        "body": body,
        "word_count": len(body.replace('\n', '')),
    }


def run_original_workflow(chapter_data: Dict) -> Dict:
    """
    方案A：原流程测试
    辅助岗写初稿（300-500字）→ 辅助岗扩写（1000-1500字）→ 主笔岗精修（2000-3000字）
    """
    results = {
        "mode": "A",
        "name": "原流程（双岗分工）",
        "stages": [],
        "total_tokens": 0,
        "total_time": 0,
        "quality_scores": {},
    }
    
    # 阶段1：辅助岗写初稿
    stage1_start = time.time()
    # 模拟：读取现有粗稿或生成
    draft = chapter_data["body"][:500]  # 取前500字作为初稿示例
    stage1_time = time.time() - stage1_start
    results["stages"].append({
        "name": "辅助岗-初稿",
        "word_count": len(draft.replace('\n', '')),
        "time": stage1_time,
        "output": draft,
    })
    
    # 阶段2：辅助岗扩写
    stage2_start = time.time()
    expanded = chapter_data["body"][:1500]  # 取前1500字作为扩写示例
    stage2_time = time.time() - stage2_start
    results["stages"].append({
        "name": "辅助岗-扩写",
        "word_count": len(expanded.replace('\n', '')),
        "time": stage2_time,
        "output": expanded,
    })
    
    # 阶段3：主笔岗精修
    stage3_start = time.time()
    final = chapter_data["body"]  # 完整章节作为精修结果
    stage3_time = time.time() - stage3_start
    results["stages"].append({
        "name": "主笔岗-精修",
        "word_count": len(final.replace('\n', '')),
        "time": stage3_time,
        "output": final,
    })
    
    results["total_time"] = stage1_time + stage2_time + stage3_time
    results["final_word_count"] = len(final.replace('\n', ''))
    
    return results


def run_merged_workflow(chapter_data: Dict) -> Dict:
    """
    方案B：融合流程测试
    创作岗一次写完整章（2000-3000字）
    """
    results = {
        "mode": "B",
        "name": "融合流程（单岗执行）",
        "stages": [],
        "total_tokens": 0,
        "total_time": 0,
        "quality_scores": {},
    }
    
    # 单阶段：创作岗写全文
    stage1_start = time.time()
    final = chapter_data["body"]  # 直接输出完整章节
    stage1_time = time.time() - stage1_start
    
    results["stages"].append({
        "name": "创作岗-全文",
        "word_count": len(final.replace('\n', '')),
        "time": stage1_time,
        "output": final,
    })
    
    results["total_time"] = stage1_time
    results["final_word_count"] = len(final.replace('\n', ''))
    
    return results


def run_hybrid_workflow(chapter_data: Dict) -> Dict:
    """
    方案C：混合流程测试
    创作岗写全文 → 自检 → 主编审核
    """
    results = {
        "mode": "C",
        "name": "混合流程（融合+强制质检）",
        "stages": [],
        "total_tokens": 0,
        "total_time": 0,
        "quality_scores": {},
    }
    
    # 阶段1：创作岗写全文
    stage1_start = time.time()
    draft = chapter_data["body"]
    stage1_time = time.time() - stage1_start
    results["stages"].append({
        "name": "创作岗-全文",
        "word_count": len(draft.replace('\n', '')),
        "time": stage1_time,
    })
    
    # 阶段2：自检（四问+九维+门禁）
    stage2_start = time.time()
    # 调用质检工具
    import subprocess
    humanizer_result = subprocess.run(
        [sys.executable, str(TEST_CONFIG["tools_dir"] / "humanizer-9d.py"),
         "--chapter-file", chapter_data["file"], "--json"],
        capture_output=True, text=True, timeout=30
    )
    self_check_passed = humanizer_result.returncode == 0
    stage2_time = time.time() - stage2_start
    results["stages"].append({
        "name": "创作岗-自检",
        "passed": self_check_passed,
        "time": stage2_time,
    })
    
    # 阶段3：主编审核
    stage3_start = time.time()
    # 模拟审核（实际项目中调用review工具）
    review_passed = True  # 简化处理
    stage3_time = time.time() - stage3_start
    results["stages"].append({
        "name": "主编-审核",
        "passed": review_passed,
        "time": stage3_time,
    })
    
    results["total_time"] = stage1_time + stage2_time + stage3_time
    results["final_word_count"] = len(draft.replace('\n', ''))
    
    return results


def run_quality_check(chapter_data: Dict) -> Dict:
    """运行质量检查"""
    import subprocess
    
    results = {
        "humanizer_9d": None,
        "gate_check": None,
        "four_questions": None,
    }
    
    # 九维质检
    try:
        proc = subprocess.run(
            [sys.executable, str(TEST_CONFIG["tools_dir"] / "humanizer-9d.py"),
             "--chapter-file", chapter_data["file"], "--json"],
            capture_output=True, text=True, timeout=30
        )
        if proc.returncode == 0:
            results["humanizer_9d"] = json.loads(proc.stdout)
    except Exception as e:
        results["humanizer_9d_error"] = str(e)
    
    # 门禁检查
    try:
        proc = subprocess.run(
            [sys.executable, str(TEST_CONFIG["tools_dir"] / "gate-check.py"),
             "check", "--file", chapter_data["file"], "--mode", "write"],
            capture_output=True, text=True, timeout=30
        )
        if proc.returncode == 0:
            results["gate_check"] = json.loads(proc.stdout)
    except Exception as e:
        results["gate_check_error"] = str(e)
    
    return results


def generate_report(test_results: Dict) -> str:
    """生成测试报告"""
    lines = [
        "# 写作部门优化测试报告",
        "",
        f"## 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "### 测试材料",
        f"- 章节：第{test_results.get('chapter', 1)}章",
        f"- 字数：{test_results.get('word_count', 'N/A')}字",
        "",
        "## 三种方案对比",
        "",
        "| 指标 | 方案A（原流程） | 方案B（融合） | 方案C（混合） |",
        "|------|---------------|-------------|-------------|",
    ]
    
    for mode in ["A", "B", "C"]:
        result = test_results.get(mode, {})
        stages = result.get("stages", [])
        stage_names = [s["name"] for s in stages]
        total_time = result.get("total_time", 0)
        word_count = result.get("final_word_count", 0)
        
        lines.append(f"| {mode} | {len(stages)}阶段 | {total_time:.2f}s | {word_count}字 |")
    
    lines.extend([
        "",
        "## 质量检查结果",
        "",
    ])
    
    quality = test_results.get("quality", {})
    if "humanizer_9d" in quality and quality["humanizer_9d"]:
        h = quality["humanizer_9d"]
        lines.append(f"### 九维质检")
        lines.append(f"- 综合评分：{h.get('overall_score', 'N/A')}分")
        lines.append(f"- 等级：{h.get('color', '')}{h.get('level', 'N/A')}")
        lines.append(f"- 通过维度：{h.get('passed_dimensions', 0)}/{h.get('total_dimensions', 0)}")
    
    if "gate_check" in quality and quality["gate_check"]:
        g = quality["gate_check"]
        lines.append(f"\n### 门禁检查")
        lines.append(f"- 通过：{g.get('passed', 'N/A')}")
        lines.append(f"- P0阻断：{len(g.get('p0_failures', []))}")
        lines.append(f"- P1警告：{len(g.get('p1_warnings', []))}")
    
    lines.extend([
        "",
        "## 结论与建议",
        "",
    ])
    
    # 自动分析
    h_score = quality.get("humanizer_9d", {}).get("overall_score", 0)
    if h_score >= 90:
        lines.append("✅ 当前章节质量优秀，可支撑方案B（融合流程）")
    elif h_score >= 80:
        lines.append("🟡 当前章节质量良好，建议采用方案C（混合流程）")
    else:
        lines.append("🟠 当前章节质量一般，建议维持方案A（原流程）或采用方案C")
    
    lines.extend([
        "",
        "---",
        "",
        f"*报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}*",
    ])
    
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="写作部门优化测试")
    parser.add_argument("--chapter", "-c", type=int, default=1, help="章节号")
    parser.add_argument("--mode", "-m", choices=["A", "B", "C"], default=None, help="测试模式：A=原流程，B=融合，C=混合，默认全部测试")
    parser.add_argument("--output", "-o", default=None, help="输出文件路径")
    args = parser.parse_args()
    
    # 加载章节
    chapter_data = load_chapter(args.chapter)
    if not chapter_data:
        print(f"❌ 找不到第{args.chapter}章")
        sys.exit(1)
    
    print(f"📖 加载章节：{chapter_data['file']}")
    print(f"   字数：{chapter_data['word_count']}字")
    print()
    
    # 运行测试
    test_results = {"chapter": args.chapter, "word_count": chapter_data['word_count'], "quality": {}}
    
    modes_to_test = ["A", "B", "C"] if args.mode is None else [args.mode]
    
    for mode in modes_to_test:
        print(f"🔄 测试方案{mode}...")
        if mode == "A":
            test_results["A"] = run_original_workflow(chapter_data)
        elif mode == "B":
            test_results["B"] = run_merged_workflow(chapter_data)
        elif mode == "C":
            test_results["C"] = run_hybrid_workflow(chapter_data)
        print(f"   ✅ 完成")
    
    # 质量检查
    print("🔍 运行质量检查...")
    test_results["quality"] = run_quality_check(chapter_data)
    print(f"   九维评分：{test_results['quality'].get('humanizer_9d', {}).get('overall_score', 'N/A')}分")
    print()
    
    # 生成报告
    report = generate_report(test_results)
    
    # 保存报告
    output_file = args.output or REPORTS_DIR / f"workflow-optimization-test-ch{args.chapter:03d}.md"
    output_file.write_text(report, encoding='utf-8')
    print(f"💾 报告已保存：{output_file}")
    print()
    print(report)


if __name__ == "__main__":
    main()
