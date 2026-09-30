#!/usr/bin/env python3
# Version: 0.1.0
"""
知识网络交叉验证 — 从 Obsidian 知识图谱中找有 wiki-link 关联的笔记对，
提取双方核心主张/声明，交叉比对发现矛盾、缺口、未验证内容。

用法:
    python3 obsidian-crossq.py                       # 全量交叉验证
    python3 obsidian-crossq.py --from "水果采购"       # 验证某节点及其引用者
    python3 obsidian-crossq.py --topic "水果采购"      # 验证某话题的跨笔记一致性
    python3 obsidian-crossq.py --report              # 生成完整报告 Markdown
"""

import argparse
import os
import re
import json
from pathlib import Path
from collections import defaultdict

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
WIKI_RE = re.compile(r'\[\[([^\]]+)\]\]')

# 提取主张的关键词模式
CLAIM_PATTERNS = [
    re.compile(r'(?:认为|指出|提出|发现|总结|结论|核心|主张|定义|原理)[，：:](.{5,80})'),
    re.compile(r'(?:不是|不等于|不能|不能|不能|不应|无法|不可能|不适合)[，：:]?(.{5,80})'),
    re.compile(r'(?:注意|警告|提醒|风险|陷阱|坑|问题|bug|漏洞|缺陷)[：:]?(.{5,80})'),
    re.compile(r'^>\s*\*\*(.{5,80})\*\*'),
    re.compile(r'^- \*\*(.{5,80})\*\*'),
]


def read_file(rel_path):
    """读取 Obsidian 文件内容。"""
    full = os.path.join(OBSIDIAN_ROOT, rel_path)
    try:
        return open(full, 'r', encoding='utf-8', errors='replace').read()
    except (OSError, PermissionError):
        return None


def extract_claims(content, source_name=""):
    """从内容中提取关键主张/声明。"""
    claims = []
    lines = content.split('\n')

    for line in lines:
        line = line.strip()
        for pat in CLAIM_PATTERNS:
            m = pat.search(line)
            if m:
                claim = m.group(1).strip()
                claims.append(claim)
                break

        # 提取标题作为核心主张
        if line.startswith('# ') and not line.startswith('##'):
            claims.append(line[2:].strip())

    # 从 YAML front matter 提取摘要
    in_front = False
    summary = ""
    for line in lines:
        if line.strip() == '---':
            in_front = not in_front
            continue
        if in_front:
            if line.strip().startswith('summary:') or line.strip().startswith('description:'):
                summary = line.split(':', 1)[1].strip().strip('"')
                if summary:
                    claims.insert(0, summary)

    return claims[:10]  # 最多10条


def cross_validate(source_path, target_path):
    """对一对有 wiki-link 关系的笔记做交叉验证。"""
    src_content = read_file(source_path)
    tgt_content = read_file(target_path)

    if not src_content or not tgt_content:
        return {
            "pair": f"{source_path} ↔ {target_path}",
            "errors": ["文件读取失败"],
        }

    # 双方互提的主张
    src_claims = extract_claims(src_content, source_path)
    tgt_claims = extract_claims(tgt_content, target_path)

    src_title = Path(source_path).stem
    tgt_title = Path(target_path).stem

    # 找交叉点：双方都提到了同一话题
    src_text_lower = src_content.lower()
    tgt_text_lower = tgt_content.lower()

    # 1) 提取共同关键词
    src_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,4}', src_content))
    tgt_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,4}', tgt_content))
    common_keywords = src_keywords & tgt_keywords
    # 过滤停用词
    stop = {'的', '了', '是', '在', '和', '与', '及', '或', '有', '这', '那', '它',
            '都', '也', '还', '就', '又', '很', '更', '最', '一个', '一种', '一些'}
    common_keywords = {w for w in common_keywords if w not in stop and len(w) >= 2}

    # 2) 检查引用是否"空转"（引用了但没实质展开）
    # 在 source 中搜 target 标题关键词
    tgt_words = re.findall(r'[\u4e00-\u9fff]{2,}', tgt_title)
    src_mentions = sum(src_content.count(w) for w in tgt_words)
    tgt_mentions = sum(tgt_content.count(w) for w in tgt_words if w != tgt_words[0])

    # 3) 检查 target 是否反向引用了 source
    src_words = re.findall(r'[\u4e00-\u9fff]{2,}', src_title)
    tgt_back_ref = any(w in tgt_content for w in src_words[:3] if w)

    issues = []

    # 检测引用空转
    if src_mentions == 1 and '[[wiki-link]]' in src_content and tgt_back_ref:
        pass  # 正常引用
    elif src_mentions <= 2 and len(tgt_content) > 500:
        issues.append(f"⚠️ 弱引用：{src_title} 引用了 {tgt_title}，但仅在文中提及 {src_mentions} 次，未做深入展开。")

    # 检测反向引用缺失
    if not tgt_back_ref and src_mentions > 2:
        issues.append(f"🔗 单向引用：{src_title} → {tgt_title}，但 {tgt_title} 没有反向引用 {src_title}。建议补充反向链接以形成知识闭环。")

    # 检测主题交集
    if common_keywords:
        top_common = sorted(common_keywords, key=len, reverse=True)[:5]
        issues.append(f"💡 共同关键词（{len(common_keywords)} 个）：{'、'.join(top_common)}。两篇笔记在同一主题上有交集。")
    else:
        issues.append(f"🤔 无明显共同关键词。{src_title} 和 {tgt_title} 的主题交集较小，引用动机可能为索引/导航。")

    return {
        "pair": f"{source_path} ↔ {target_path}",
        "src_title": src_title,
        "tgt_title": tgt_title,
        "src_claims": src_claims[:3],
        "tgt_claims": tgt_claims[:3],
        "common_keywords": sorted(common_keywords)[:5],
        "issues": issues,
    }


def validate_topic(topic: str, top_n: int = 8):
    """验证一个话题下所有相关笔记的一致性。"""
    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        return []

    # 找包含该话题关键词的所有笔记
    related = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md') or fname.startswith('.'):
                continue
            full = os.path.join(dirpath, fname)
            try:
                content = open(full, 'r', encoding='utf-8', errors='replace').read()
            except:
                continue
            rel = os.path.relpath(full, root)
            if topic in content:
                count = content.count(topic)
                related.append((rel, count, content))

    if not related:
        return [{"topic": topic, "error": f"未找到包含「{topic}」的笔记"}]

    # 提取每个笔记对该话题的主张
    findings = []
    for path, count, content in sorted(related, key=lambda x: x[1], reverse=True):
        claims = extract_claims(content)
        findings.append({
            "path": path,
            "mentions": count,
            "title": Path(path).stem,
            "claims": [c for c in claims if topic in c or any(
                w in c for w in re.findall(r'[\u4e00-\u9fff]{2,4}', topic)
            )][:3],
        })

    # 检测矛盾：不同笔记对同一话题的说法是否冲突
    contradictions = []
    all_claims_by_path = {f["path"]: f["claims"] for f in findings}

    # 简化矛盾检测：如果有笔记说 X 好，另一个说 X 不好
    for i, fi in enumerate(findings):
        for j, fj in enumerate(findings):
            if i >= j:
                continue
            # 找相互否定的表达
            neg_words = ['不是', '不能', '不适合', '无法', '不可能', '不应该', '不应']
            pos_words = ['是', '适合', '可以', '能', '可能', '应该', '推荐', '建议', '最优', '最好']
            for c1 in all_claims_by_path[fi["path"]]:
                for c2 in all_claims_by_path[fj["path"]]:
                    if any(nw in c1 and pw in c2 for nw in neg_words for pw in pos_words):
                        contradictions.append({
                            "between": f"{fi['title']} vs {fj['title']}",
                            "conflict": f"「{c1[:40]}」 vs 「{c2[:40]}」"
                        })

    return {
        "topic": topic,
        "related_count": len(findings),
        "top_notes": findings[:top_n],
        "contradictions": contradictions[:5],
    }


def build_graph():
    """构建简化版 wiki-link 图。"""
    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        return {}
    graph = defaultdict(set)
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md') or fname.startswith('.'):
                continue
            full = os.path.join(dirpath, fname)
            try:
                content = open(full, 'r', encoding='utf-8', errors='replace').read()
            except:
                continue
            source = os.path.relpath(full, root)
            for link in WIKI_RE.findall(content):
                target = link.split('|')[0].strip()
                if target and target != source:
                    # 解析目标文件的相对路径
                    target_rel = os.path.join(os.path.dirname(source), target)
                    # 尝试找到目标文件的实际路径
                    graph[source].add(target_rel)
    return graph


def full_scan(top_pairs: int = 8):
    """全量交叉验证：选取被引用最多的笔记与其引用者做交叉验证。"""
    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        return []

    # 收集所有文件映射
    all_files = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith('.md') and not fname.startswith('.'):
                rel = os.path.relpath(os.path.join(dirpath, fname), root)
                all_files[rel] = Path(rel).stem

    def resolve_target(target_name):
        """解析 wiki-link 目标名到实际文件路径。"""
        # 精确匹配文件名 stem
        for rel, stem in all_files.items():
            if stem == target_name:
                return rel
        # 模糊匹配
        for rel in all_files:
            if target_name in rel:
                return rel
        return None

    # 统计被引用关系
    citations = defaultdict(list)
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md') or fname.startswith('.'):
                continue
            full = os.path.join(dirpath, fname)
            try:
                content = open(full, 'r', encoding='utf-8', errors='replace').read()
            except:
                continue
            source = os.path.relpath(full, root)
            for link in WIKI_RE.findall(content):
                target = link.split('|')[0].strip()
                if target and target != source:
                    citations[target].append(source)

    # 选被引用最多的目标
    top_targets = sorted(citations.items(), key=lambda x: len(x[1]), reverse=True)[:top_pairs]

    results = []
    seen_pairs = set()
    for target_name, sources in top_targets:
        target_path = resolve_target(target_name)
        if not target_path:
            continue
        for source in sources[:2]:
            pair_key = (source, target_path)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            result = cross_validate(source, target_path)
            if "pair" in result and "errors" not in result:
                results.append(result)
            if len(results) >= top_pairs:
                break

    return results


def extract_context_snippets(content, keywords, window=120, max_per_file=3):
    """从笔记中提取包含关键词的上下文片段。"""
    snippets = []
    for line in content.split('\n'):
        for kw in keywords:
            if kw in line:
                idx = line.find(kw)
                start = max(0, idx - window // 2)
                end = min(len(line), idx + len(kw) + window // 2)
                snippet = line[start:end].strip()
                if snippet:
                    snippets.append(snippet)
                    break
        if len(snippets) >= max_per_file:
            break
    return snippets


def save_reflect_card(question, synthesis, hits):
    """把 reflect 结果存成一张知识卡片。"""
    import datetime
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    sources = "\n".join(
        f"- [[{Path(h['path']).stem}]] ({h['date'] or '无日期'}) — 命中 {h['score']} 次"
        for h in hits
    )
    card = f"""---
type: reflect
question: "{question}"
created: {ts}
sources: {len(hits)}
model: reflect-minimal
---

# Reflect：{question}

> 合成于 {ts} | 最小验证版 reflect | 素材 {len(hits)} 篇

## 合成结论

{synthesis}

## 检索来源

{sources}
"""
    out_path = f"/var/minis/shared/reflect-{ts[:10].replace('-', '')}.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(card)
    print(f"\n💾 卡片已保存: {out_path}")


def reflect(question, top_n=8, save=False, model="sensenova-6.8-flash-lite"):
    """最小验证版 reflect：检索相关主张 → LLM 合成推理。

    不依赖向量检索，复用 crossq 的关键词检索 + 主张提取，
    调 minis-model-use 做一次合成推理，验证 reflect 概念有无增量。
    """
    import subprocess
    import tempfile

    root = Path(OBSIDIAN_ROOT)
    if not root.exists():
        print("❌ Obsidian 根目录不存在")
        return

    # 从问题提取关键词（中文 2-4 字 + 英文 token）
    kws = set(re.findall(r'[\u4e00-\u9fff]{2,4}', question))
    stop = {'的', '了', '是', '在', '和', '与', '及', '或', '有', '这', '那',
            '都', '也', '还', '就', '又', '很', '更', '最', '一个', '一种',
            '一些', '哪些', '什么', '怎么', '为什么', '如何', '我们', '你们',
            '我', '你', '他', '她', '它', '之间', '变化', '理解', '有哪些',
            '带来', '可以', '应该', '这样'}
    kws = {w for w in kws if w not in stop and len(w) >= 2}
    kws |= set(re.findall(r'[A-Za-z][A-Za-z0-9.]{2,}', question))

    if not kws:
        print("❌ 无法从问题提取有效关键词")
        return

    # 扫所有笔记，找包含关键词的
    hits = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith('.md') or fname.startswith('.'):
                continue
            full = os.path.join(dirpath, fname)
            try:
                content = open(full, 'r', encoding='utf-8', errors='replace').read()
            except (OSError, PermissionError):
                continue
            score = sum(content.count(k) for k in kws)
            if score == 0:
                continue
            rel = os.path.relpath(full, root)
            m = re.search(r'(\d{4}-\d{2}-\d{2})', rel)
            date = m.group(1) if m else ""
            claims = extract_claims(content)
            relevant_claims = [c for c in claims if any(k in c for k in kws)]
            snippets = extract_context_snippets(content, kws, max_per_file=3)
            hits.append({
                "path": rel,
                "date": date,
                "score": score,
                "claims": relevant_claims[:3],
                "snippets": snippets,
            })

    hits.sort(key=lambda x: x["score"], reverse=True)
    hits = hits[:top_n]

    if not hits:
        print(f"❌ 未找到与问题相关的笔记。关键词：{', '.join(sorted(kws))}")
        return

    # 构造证据
    evidence = []
    for i, h in enumerate(hits, 1):
        date_str = f"（{h['date']}）" if h["date"] else "（无日期）"
        evidence.append(f"## 片段 {i}：{h['path']}{date_str}")
        if h["claims"]:
            evidence.append("主张：")
            for c in h["claims"]:
                evidence.append(f"  - {c}")
        if h["snippets"]:
            evidence.append("上下文：")
            for s in h["snippets"]:
                evidence.append(f"  > {s}")
        evidence.append("")

    evidence_text = "\n".join(evidence)

    system_prompt = (
        "你是一个记忆合成推理引擎。你会收到从用户知识库检索到的记忆片段（笔记主张+上下文），"
        "每条带有来源文件和日期。你的任务：\n"
        "1. 基于这些片段回答用户的问题\n"
        "2. 识别片段之间的矛盾或张力，明确指出哪些说法冲突\n"
        "3. 按时间线梳理用户对该话题理解的演化（哪些先、哪些后、是否修正）\n"
        "4. 区分【事实】（片段直接陈述）与【推断】（你合成的结论）\n"
        "5. 片段不足以回答时，明确说「证据不足」并指出缺什么\n"
        "用简洁中文输出，结构化。不要编造片段里没有的事实。"
    )

    user_prompt = f"""# 用户问题
{question}

# 检索到的记忆片段（共 {len(hits)} 篇，按关键词命中数排序）
{evidence_text}

# 请基于以上片段合成回答
"""

    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                     encoding='utf-8') as pf:
        pf.write(user_prompt)
        prompt_file = pf.name

    print(f"🔍 检索到 {len(hits)} 篇相关笔记，关键词：{', '.join(sorted(kws))}")
    print(f"🤖 调用 {model} 合成中...\n")

    try:
        result = subprocess.run(
            ["minis-model-use", "run", "--model", model,
             "--prompt-file", prompt_file, "--system", system_prompt,
             "--max-tokens", "2048", "--temperature", "0.3"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            print(f"❌ 模型调用失败：{result.stderr[:300]}")
            return
        synthesis = ""
        try:
            payload = json.loads(result.stdout)
            synthesis = payload.get("data", {}).get("output_text", "").strip()
        except json.JSONDecodeError:
            synthesis = result.stdout.strip()
        if not synthesis:
            print("❌ 模型未返回内容（该模型可能不支持 output_text 捕获）")
            return
    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass

    print("=" * 50)
    print("🧠 合成结论")
    print("=" * 50)
    print(synthesis)

    if save:
        save_reflect_card(question, synthesis, hits)


def main():
    parser = argparse.ArgumentParser(description='Obsidian 知识网络交叉验证')
    parser.add_argument('--from', dest='from_node', help='验证某节点与其引用者')
    parser.add_argument('--topic', '-t', help='验证某话题的跨笔记一致性')
    parser.add_argument('--report', '-r', action='store_true', help='生成完整报告')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    parser.add_argument('--top', type=int, default=8, help='验证对数上限')
    parser.add_argument('--reflect', dest='reflect_q',
                        help='合成推理：基于知识库回答问题')
    parser.add_argument('--save', action='store_true',
                        help='reflect 结果存成卡片')
    parser.add_argument('--model', default='sensenova-6.8-flash-lite', help='合成用模型')

    args = parser.parse_args()

    if args.reflect_q:
        reflect(args.reflect_q, top_n=args.top, save=args.save,
                model=args.model)
        return

    if args.topic:
        result = validate_topic(args.topic)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_topic_report(result)
        return

    if args.from_node:
        root = Path(OBSIDIAN_ROOT)
        target = None
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if Path(fname).stem == args.from_node or args.from_node in fname:
                    target = os.path.relpath(full, root)
                    break
            if target:
                break
        if target:
            result = cross_validate(
                f"02-Areas/认知思考/{args.from_node}.md" if "框架" in args.from_node else target,
                target
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print_pair_report(result)
        else:
            print(f"❌ 未找到节点: {args.from_node}")
        return

    # 默认：全量扫描
    results = full_scan(args.top)
    if args.report:
        export_report(results)
    elif args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print_pair_report(r, verbose=False)


def print_pair_report(result, verbose=True):
    if "errors" in result:
        print(f"❌ {result['pair']}: {', '.join(result['errors'])}")
        return
    print(f"\n{'═'*50}")
    print(f"🔍 {result['src_title']} → {result['tgt_title']}")
    print(f"   📍 {result['pair']}")
    if verbose and result.get('src_claims'):
        print(f"   💬 {result['src_title']} 主张: {result['src_claims'][0][:60]}")
    if verbose and result.get('tgt_claims'):
        print(f"   💬 {result['tgt_title']} 主张: {result['tgt_claims'][0][:60]}")
    if result.get('common_keywords'):
        print(f"   🔗 共同关键词: {', '.join(result['common_keywords'])}")
    for issue in result.get('issues', []):
        print(f"   {issue}")


def print_topic_report(result):
    print(f"\n📊 话题交叉验证：「{result['topic']}」")
    print(f"   关联笔记：{result['related_count']} 篇\n")
    for f in result.get('top_notes', []):
        claims = f.get('claims', [])
        claim_text = f"{claims[0][:50]}" if claims else "（无明确主张）"
        print(f"   📄 {f['title']} ({f['mentions']} 次提及)")
        print(f"      {claim_text}")
    if result.get('contradictions'):
        print(f"\n   ⚠️ 发现 {len(result['contradictions'])} 处潜在矛盾:")
        for c in result['contradictions'][:3]:
            print(f"      {c['between']}")
            print(f"      {c['conflict']}")
    else:
        print(f"\n   ✅ 未发现明显矛盾，各笔记说法一致。")


def export_report(results):
    lines = [
        "# 知识网络交叉验证报告",
        f"> 自动生成于 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 概览",
        f"- **验证对数：** {len(results)} 对",
        "- **方法：** 基于 wiki-link 引用关系，提取双方核心主张交叉比对",
        "",
        "## 验证详情",
    ]

    for r in results:
        if "errors" in r:
            lines.append(f"### ❌ {r['pair']}")
            lines.append(f"  {', '.join(r['errors'])}")
            continue
        lines.append(f"### {r['src_title']} → {r['tgt_title']}")
        lines.append(f"**共同关键词：** {', '.join(r.get('common_keywords', []))}")
        if r.get('src_claims'):
            lines.append(f"**{r['src_title']} 主张：** {r['src_claims'][0][:80]}")
        if r.get('tgt_claims'):
            lines.append(f"**{r['tgt_title']} 主张：** {r['tgt_claims'][0][:80]}")
        for issue in r.get('issues', []):
            lines.append(f"- {issue}")
        lines.append("")

    out_path = "/var/minis/shared/obsidian-crossq-report.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"✅ 报告已导出: {out_path}")


if __name__ == '__main__':
    main()