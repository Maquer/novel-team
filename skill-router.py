#!/usr/bin/env python3
# Version: 0.1.0
"""
skill-router.py — Minis Skill 组合式路由引擎 v1.0

借鉴 SkillWeaver（arXiv 2606.18051）三阶段架构：
  Decompose → Retrieve → Compose

核心创新借鉴：
1. 语义索引层（metadata 即可，不加载全文）
2. SAD 反馈环路（初始匹配后做一致性检查）
3. 组合式 DAG（多 Skill 有序编排）

纯 Python 实现，无外部依赖。使用 TF-IDF 做语义检索，
精度低于 embedding 但 iSH 环境零依赖。

用法:
  python3 skill-router.py route "写一篇小红书笔记并配图"
  python3 skill-router.py route "帮我分析这个项目要不要做"
  python3 skill-router.py route "写文章并排好版发公众号"
  python3 skill-router.py route "把这篇文章转成抖音文案"
  python3 skill-router.py route "蒸馏费曼的思维方式"
  python3 skill-router.py route "写代码修 bug"

  python3 skill-router.py skills          # 列出所有 Skill
  python3 skill-router.py index           # 重建索引
  python3 skill-router.py test            # 单元测试
"""

import argparse
import json
import os
import re
import sys
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SKILLS_DIR = "/var/minis/skills"
REGISTRY_PATH = "/var/minis/shared/.skill-registry.json"
INDEX_PATH = "/var/minis/shared/.skill-index.json"


# ===== Tokenizer =====

STOPWORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着
没有 看 好 自己 这 他 她 它 们 那 些 什么 怎么 为什么 哪 谁 怎样
a an the of and in is it to for on with at by from as or but not be
this that these those has have had been being were would could should
""".split())

def tokenize(text):
    """中文分词（基于字符n-gram）+ 英文分词"""
    # 保留中文、英文、数字
    text = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
    tokens = []
    # 英文小写分词
    for m in re.finditer(r'[a-z0-9]+', text.lower()):
        word = m.group()
        if len(word) >= 2 and word not in STOPWORDS:
            tokens.append(word)
    # 中文2-gram
    for i in range(len(text) - 1):
        if '\u4e00' <= text[i] <= '\u9fff' and '\u4e00' <= text[i+1] <= '\u9fff':
            tokens.append(text[i:i+2])
    return [t for t in tokens if t not in STOPWORDS]


# ===== TF-IDF =====

def compute_tfidf(tokens):
    """简单 TF-IDF 权重"""
    tf = Counter(tokens)
    total = sum(tf.values())
    idf = {t: (total / (c + 1)) for t, c in tf.items()}
    return {t: tf[t] * idf[t] / max(tf.values()) if tf.values() else 1.0 for t in tf}


def cosine_sim(vec_a, vec_b):
    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in set(vec_a) | set(vec_b))
    norm_a = math.sqrt(sum(v*v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v*v for v in vec_b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


# ===== Skill 元数据加载 =====

def load_skill_meta(skill_dir):
    """从 skill 目录加载 metadata，优先 .meta.json，其次 SKILL.md frontmatter"""
    meta = {"path": skill_dir, "name": os.path.basename(skill_dir)}

    # 尝试 meta.json / skill.meta.json
    for mf in ["skill.meta.json", ".meta.json"]:
        fp = os.path.join(skill_dir, mf)
        if os.path.exists(fp):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                meta.update({k: v for k, v in d.items() if k != "path"})
                meta["_meta_source"] = mf
                break
            except Exception:
                pass

    # 从 SKILL.md frontmatter + 正文补充
    sk = os.path.join(skill_dir, "SKILL.md")
    if os.path.exists(sk):
        try:
            text = Path(sk).read_text(encoding='utf-8')
            m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', text, re.DOTALL)
            if m:
                # 逐行解析，支持 YAML block scalar (>- / |)
                fm_lines = m.group(1).split('\n')
                j = 0
                while j < len(fm_lines):
                    line = fm_lines[j]
                    if ':' in line and line.strip():
                        k, v = line.split(':', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if v in ('>-', '|'):
                            parts = []
                            j += 1
                            while j < len(fm_lines):
                                nl = fm_lines[j]
                                if nl.startswith('  ') and not nl.startswith('    '):
                                    parts.append(nl.strip())
                                    j += 1
                                elif nl.strip() == '':
                                    j += 1
                                else:
                                    break
                            v = ' '.join(parts)
                        # 跳过以 # 开头的描述（标题型而非真正描述）
                        if k == 'description' and v.strip().startswith('#'):
                            j += 1
                            continue
                        if k not in meta:
                            meta[k] = v
                    j += 1
            meta["_has_skill_md"] = True
            meta["_lines"] = len(text.split('\n'))
            meta["_size"] = len(text)

            # 如果没有 description，从正文第一段提取
            if not meta.get("description"):
                after_fm = re.sub(r'^---\s*\n.*?\n---\s*\n?', '', text, count=1, flags=re.DOTALL)
                # 跳过标题(# / ##)、引用(>)、代码块(```)、列表(-) 找真实描述
                for line in after_fm.split('\n'):
                    stripped = line.strip()
                    if (stripped and not stripped.startswith('#')
                        and not stripped.startswith('>') and not stripped.startswith('```')
                        and not stripped.startswith('-') and len(stripped) > 20
                        and not stripped.startswith('|')):
                        meta["description"] = stripped
                        break
                # 如果还是没找到，取前 3 个有效行拼接
                if not meta.get("description"):
                    lines = [l.strip() for l in after_fm.split('\n')
                             if l.strip() and not l.strip().startswith('#')
                             and not l.strip().startswith('>')
                             and not l.strip().startswith('```')]
                    meta["description"] = " ".join(lines[:5])

            # 关键词增强：从 SKILL.md 中提取触发词/适用场景
            keywords = []
            # 从表格行中提取 Trigger/适用场景 字段
            for m in re.finditer(r'\|\s*\*?\*?(?:Trigger|触发|适用场景)\*?\*?\s*\|([^|]+)', text):
                raw = m.group(1).strip()[:200]
                if raw and not raw.startswith('|'):
                    keywords.append(raw)
            # 也抓段落形式的触发说明
            for m in re.finditer(r'(?:用户说|提到|当.*?说)[。：:"]?\s*(.*?)(?=\n\n|\n##|\n---)', text):
                raw = m.group(1).strip()[:150]
                if raw and len(raw) > 10:
                    keywords.append(raw)
            if keywords:
                meta["keywords"] = " ".join(keywords)
        except Exception:
            pass

    return meta


def load_all_skills():
    """加载所有 Skill metadata"""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        print(f"Warning: {SKILLS_DIR} not found", file=sys.stderr)
        return skills

    for entry in sorted(os.listdir(SKILLS_DIR)):
        sp = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(sp):
            meta = load_skill_meta(sp)
            skills.append(meta)
    return skills


# ===== 索引构建 =====

def build_index(skills):
    """构建 TF-IDF 索引"""
    index = {"tokens": {}, "vectors": [], "meta_indices": []}
    all_tokens = set()

    # 从每个 skill 构建文本向量
    for skill in skills:
        # 组合搜索文本
        parts = []
        name = skill.get("name", "")
        if name:
            parts.append(name * 3)  # 名称权重×3

        desc = skill.get("description", "")
        if desc:
            parts.append(desc)

        tags = skill.get("tags", [])
        if tags:
            parts.append(" ".join(tags))

        # dependencies 也是相关技能线索
        deps = skill.get("dependencies", [])
        if deps:
            parts.append(" ".join(deps))

        # 额外信号
        ext_refs = skill.get("provenance", {}).get("external_refs", [])
        if ext_refs:
            parts.append(" ".join(ext_refs))

        # 关键词增强
        kw = skill.get("keywords", "")
        if kw:
            parts.append(kw)

        text = " ".join(parts)
        tokens = tokenize(text)
        vec = compute_tfidf(tokens)
        index["vectors"].append(vec)
        index["meta_indices"].append(skill["name"])
        all_tokens.update(tokens)

    index["tokens"] = sorted(all_tokens)
    index["_built_at"] = datetime.now(timezone.utc).isoformat()
    return index


def save_index(index, skills):
    """持久化索引 + Skill 元数据"""
    data = {
        "version": 1,
        "skills": skills,
        "index": index
    }
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return INDEX_PATH


def load_index():
    """加载持久化索引"""
    if not os.path.exists(INDEX_PATH):
        return None, None
    try:
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("skills", []), data.get("index", {})
    except Exception:
        return None, None


# ===== 路由核心 =====

def decompose_query(query):
    """
    将用户查询分解为原子子任务。
    用启发式规则而非 LLM（避免外部依赖）。
    支持常见的复合意图模式。
    """
    subtasks = [query.strip()]

    # 用分隔符拆分
    for sep in ['，', ',', '。', '并', '然后', '接着', '之后', '和']:
        if sep in query and len(query) > 10:
            subtasks = [s.strip() for s in re.split(sep, query) if len(s.strip()) > 2]
            break

    # 检测复合意图模式
    compound_patterns = [
        # (匹配模式, 子任务模板)
        (r'(写|创作)([^，,。并然后]*?)(并|然后|接着|再)(配|生成|设计).*(?:图|海报|封面)',
         lambda m: [f"写{m.group(2)}", f"为{m.group(2)}配图/海报"]),
        (r'(写|创作)([^，,。并然后]*?)(并|然后|接着|再)(转|转换|改编).*(?:抖音|小红书|公众号|微博)',
         lambda m: [f"写{m.group(2)}", f"将{m.group(2)}转换为{m.group(4)}"]),
        (r'(写|创作)([^，,。并然后]*?)(并|然后|接着|再)(发|发布|排版).*(?:公众号|小红书|抖音)',
         lambda m: [f"写{m.group(2)}", f"发布/排版{m.group(2)}"]),
        (r'(分析|决策|判断)(.*?)(要不要|该不该|值不值得)',
         lambda m: [f"分析{m.group(2)}", "结构化决策评估"]),
        (r'(蒸馏|提取|分析)(.*?)(思维|方法|方式)',
         lambda m: [f"蒸馏{m.group(2)}的思维方式"]),
        (r'(修|解决|排查|修一下)(.*?)(bug|问题|错误)',
         lambda m: [f"排查{m.group(2)}的代码问题"]),
        # "把 A 转成 B" 模式
        (r'把(.{2,20}?)(转|转成|转换成|改成|改写成)(.{2,20}?)(?:文案|内容|笔记|视频|脚本|文章)',
         lambda m: [f"将{m.group(1)}转换为{m.group(3)}"]),
    ]

    for pattern, template_fn in compound_patterns:
        m = re.search(pattern, query)
        if m:
            subtasks = template_fn(m)
            break

    return subtasks


def retrieve_topk(skills, index, subtasks, topk=5):
    """对每个子任务语义检索 Top-K Skill"""
    results = {}
    for i, subtask in enumerate(subtasks):
        subtokens = tokenize(subtask)
        subvec = compute_tfidf(subtokens)

        scores = []
        for j, vec in enumerate(index["vectors"]):
            sim = cosine_sim(subvec, vec)
            scores.append((sim, j))

        scores.sort(reverse=True)
        top_matches = []
        for sim, j in scores[:topk]:
            if sim > 0.05:  # 阈值过滤
                top_matches.append({
                    "name": index["meta_indices"][j],
                    "score": round(sim, 4),
                    "similarity": round(sim, 4)
                })
        results[f"subtask_{i}"] = {
            "query": subtask,
            "matches": top_matches
        }
    return results


def sad_alignment_check(skills, top_results):
    """
    SAD 对齐检查（SkillWeaver 的核心创新）。
    模拟 input-side 反馈：检查选中的 Skill 之间是否有依赖冲突或覆盖缺口。

    启发式规则：
    1. 检查选中 Skill 的 dependencies 是否也需被激活
    2. 检查子任务是否有未被覆盖的部分
    """
    alignment_notes = []
    all_matched_names = set()
    for subtask_id, result in top_results.items():
        for m in result["matches"]:
            all_matched_names.add(m["name"])

    # 构建 skill 名称→元数据映射
    skill_map = {s["name"]: s for s in skills}

    # 检查 dependency 链
    for name in list(all_matched_names):
        meta = skill_map.get(name, {})
        deps = meta.get("dependencies", [])
        for dep in deps:
            if dep in skill_map and dep not in all_matched_names:
                dep_desc = skill_map[dep].get("description", "")[:60]
                alignment_notes.append({
                    "type": "dependency_gap",
                    "skill": name,
                    "needs": dep,
                    "desc": dep_desc
                })

    return alignment_notes


def compose_dag(skills, top_results, alignment_notes, min_score=0.05):
    """
    组合 Skill DAG（有向无环图）。
    按依赖关系排序 Skill 执行顺序。
    """
    skill_map = {s["name"]: s for s in skills}

    # 收集所有被选中（去重 + 阈值过滤）的 Skill
    selected = {}
    for subtask_id, result in top_results.items():
        for m in result["matches"]:
            if m["score"] >= min_score and m["name"] not in selected:
                selected[m["name"]] = {
                    "name": m["name"],
                    "score": m["score"],
                    "subtasks": [subtask_id],
                    "deps": skill_map.get(m["name"], {}).get("dependencies", []),
                    "reason": ""
                }

    # 从 alignment_notes 补充缺失的 dependency（仅当与查询相关时）
    # 相关性判断：dependency 的 description/keywords 与子任务有 token 重叠
    all_subtask_tokens = set()
    for subtask_id, result in top_results.items():
        all_subtask_tokens.update(tokenize(result["query"]))
    for note in alignment_notes:
        if note["type"] == "dependency_gap":
            dep_name = note["needs"]
            if dep_name in skill_map and dep_name not in selected:
                dep_meta = skill_map.get(dep_name, {})
                dep_desc = dep_meta.get("description", "") + " " + dep_meta.get("keywords", "")
                dep_tokens = set(tokenize(dep_desc))
                # 至少 1 个 token 重叠才视为相关
                if dep_tokens & all_subtask_tokens:
                    selected[dep_name] = {
                        "name": dep_name,
                        "score": 0.0,
                        "subtasks": [],
                        "deps": skill_map.get(dep_name, {}).get("dependencies", []),
                        "reason": f"dependency of {note['skill']}"
                    }

    # 拓扑排序
    nodes = list(selected.keys())
    edges = []
    for name, info in selected.items():
        for dep in info["deps"]:
            if dep in selected:
                edges.append((dep, name))

    # 简单拓扑排序（Kahn 算法）
    in_degree = defaultdict(int)
    adj = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)
        in_degree[v] += 1

    queue = [n for n in nodes if in_degree[n] == 0]
    topo_order = []
    while queue:
        node = queue.pop(0)
        topo_order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 没有入度的节点（无依赖）放在最前
    for n in nodes:
        if n not in topo_order:
            topo_order.append(n)

    return topo_order, selected


# ===== 格式化输出 =====

def format_route_result(query, subtasks, top_results, topo_order, selected, alignment_notes):
    """人类可读的输出"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"🧠 用户查询: {query}")
    lines.append(f"{'='*60}")

    # Decompose
    lines.append(f"\n📋 Decompose — 分解为 {len(subtasks)} 个子任务:")
    for i, st in enumerate(subtasks, 1):
        lines.append(f"   {i}. {st}")

    # Retrieve
    lines.append(f"\n🔍 Retrieve — 语义检索 (Top-5):")
    for subtask_id, result in top_results.items():
        lines.append(f"\n   [{result['query']}]")
        if result["matches"]:
            for m in result["matches"]:
                bar = "█" * int(m["score"] * 50) + "░" * (50 - int(m["score"] * 50))
                lines.append(f"     {m['name']:<24} {bar} {m['score']:.3f}")
        else:
            lines.append(f"     (未找到匹配)")

    # SAD alignment
    if alignment_notes:
        lines.append(f"\n🔄 SAD 对齐检查:")
        for note in alignment_notes:
            lines.append(f"   ⚠️ {note['skill']} 依赖 {note['needs']}（{note['desc']}）")
            lines.append(f"      → 已自动补充到 DAG")

    # Compose
    lines.append(f"\n🧩 Compose — Skill 执行 DAG ({len(topo_order)} 个):")
    for i, name in enumerate(topo_order, 1):
        info = selected.get(name, {})
        score = info.get("score", 0)
        reason = info.get("reason", "")
        score_str = f" [{score:.3f}]" if score > 0 else " [依赖]"
        reason_str = f" ← {reason}" if reason else ""
        lines.append(f"   {i}. {name:<24}{score_str}{reason_str}")
        meta = next((s for s in load_all_skills() if s["name"] == name), {})
        desc = meta.get("description", "")
        if desc:
            lines.append(f"      └─ {desc[:80]}...")

    # DAG edges
    lines.append(f"\n   执行顺序:")
    arrows = " → ".join(topo_order)
    if len(arrows) > 80:
        # 太长就分行
        chunks = [arrows[i:i+70] for i in range(0, len(arrows), 70)]
        for c in chunks:
            lines.append(f"     {c}")
    else:
        lines.append(f"     {arrows}")

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)


# ===== 命令接口 =====

def cmd_route(args):
    skills = args.skills if hasattr(args, 'skills') and args.skills else []
    index = args.index if hasattr(args, 'index') and args.index else {}

    if not skills or not index:
        print("错误: 索引为空，请先运行 skill-router.py index")
        return

    query = args.query

    # 1. Decompose
    subtasks = decompose_query(query)

    # 2. Retrieve
    top_results = retrieve_topk(skills, index, subtasks, topk=args.topk)

    # 3. SAD alignment
    alignment_notes = sad_alignment_check(skills, top_results)

    # 4. Compose DAG
    topo_order, selected = compose_dag(skills, top_results, alignment_notes)

    result = format_route_result(query, subtasks, top_results, topo_order, selected, alignment_notes)
    print(result)

    # 同时输出 JSON
    json_out = {
        "query": query,
        "subtasks": subtasks,
        "top_results": top_results,
        "alignment_notes": alignment_notes,
        "dag": {
            "order": topo_order,
            "selected": {k: {"score": v.get("score",0), "subtasks": v.get("subtasks",[]),
                              "deps": v.get("deps",[])}
                         for k,v in selected.items()}
        }
    }
    with open(os.path.join("/tmp", "skill-route.json"), 'w', encoding='utf-8') as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2)


def cmd_skills(args):
    skills = load_all_skills()
    print(f"\n{'Skill':<24} {'描述':<60} {'依赖数':<6}")
    print("-" * 95)
    for s in skills:
        deps = s.get("dependencies", [])
        desc = s.get("description", "")[:58]
        print(f"{s['name']:<24} {desc:<60} {len(deps):<6}")


def cmd_index(args):
    skills = load_all_skills()
    print(f"扫描到 {len(skills)} 个 Skill...")
    index = build_index(skills)
    path = save_index(index, skills)
    print(f"索引已保存: {path} ({len(index['tokens'])} 个唯一 tokens)")


def cmd_test(args):
    """内置测试"""
    print("🧪 Skill Router 单元测试\n")

    # Test 1: tokenize
    t = tokenize("写一篇小红书笔记")
    assert len(t) >= 3, f"tokenize failed: {t}"
    print("  ✅ tokenize 正常")

    # Test 2: cosine_sim
    v1 = compute_tfidf(tokenize("写小红书笔记"))
    v2 = compute_tfidf(tokenize("创作小红书文案"))
    sim = cosine_sim(v1, v2)
    assert sim > 0.0, f"cosine_sim failed: {sim}"
    print(f"  ✅ cosine_sim = {sim:.4f}")

    # Test 3: build_index
    skills = load_all_skills()
    if skills:
        idx = build_index(skills)
        assert len(idx["vectors"]) == len(skills)
        print(f"  ✅ build_index ({len(skills)} skills)")

        # Test 4: retrieve
        results = retrieve_topk(skills, idx, ["写小红书笔记"], topk=3)
        assert results["subtask_0"]["matches"], "no matches"
        best = results["subtask_0"]["matches"][0]["name"]
        print(f"  ✅ retrieve: '写小红书笔记' → top1 = {best}")

        # Test 5: decompose
        subs = decompose_query("写文章并配图")
        assert len(subs) == 2, f"decompose: {subs}"
        print(f"  ✅ decompose: '写文章并配图' → {subs}")

        # Test 6: compose
        _, selected = compose_dag(skills, results, [])
        print(f"  ✅ compose: {len(selected)} 个 Skill 入选")

    print("\n所有测试通过 ✅")


# ===== Main =====

def main():
    parser = argparse.ArgumentParser(description="SkillWeaver-inspired Minis Skill Router")
    sub = parser.add_subparsers(dest="command")

    # route
    p_route = sub.add_parser("route", help="路由用户查询到 Skill DAG")
    p_route.add_argument("query", help="用户查询")
    p_route.add_argument("--topk", type=int, default=5)

    # skills
    sub.add_parser("skills", help="列出所有 Skill")

    # index
    sub.add_parser("index", help="重建 Skill 索引")

    # test
    sub.add_parser("test", help="运行单元测试")

    args = parser.parse_args()

    if args.command == "route":
        skills, idx = load_index()
        if skills is None:
            cmd_index(args)
            skills, idx = load_index()
        args.skills = skills
        args.index = idx
        cmd_route(args)
    elif args.command == "skills":
        cmd_skills(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
