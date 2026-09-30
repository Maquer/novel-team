#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
novel-analyzer.py — 小说章节五维分析器

借鉴 Panda-995/ai-writing-assistant（妙笔生花）的核心设计：
  - Schema-Driven JSON 输出（使用 Agnes AI 或 OpenRouter）
  - 五维评分：文笔/剧情连贯/代入感/新意/节奏
  - 纠错与优化建议（语法/错字/文笔/标点四类）
  - 逻辑树结构可视化数据
  - 章节标题吸引力分析
  - 全文润色版本

API 配置：优先使用 AGNES_API_KEY，其次 OPENROUTER_API_KEY
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import httpx

DEFAULT_CONFIG = {
    "agnes": {
        "base_url": "https://apihub.agnes-ai.com/v1",
        "model": "agnes-3.0-flash",
        "max_tokens": 8192,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "z-ai/glm-5.3-flash",
        "max_tokens": 8192,
    }
}


def get_api_key(provider):
    return os.environ.get(f"{provider.upper()}_API_KEY", "")


def get_available_provider():
    if get_api_key("agnes"):
        return "agnes", DEFAULT_CONFIG["agnes"]
    if get_api_key("openrouter"):
        return "openrouter", DEFAULT_CONFIG["openrouter"]
    return None, None


@dataclass
class ArticleScores:
    total: int = 0
    writing: int = 0
    plot_coherence: int = 0
    immersion: int = 0
    novelty: int = 0
    rhythm: int = 0


@dataclass
class Correction:
    original: str
    suggestion: str
    reason: str
    type: str
    location_snippet: str = ""


@dataclass
class TitleAnalysis:
    score: int = 0
    retention_potential: str = "Low"
    critique: str = ""
    suggestions: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class StructureNode:
    name: str
    type: str
    description: str = ""
    children: List["StructureNode"] = field(default_factory=list)


@dataclass
class AnalysisResult:
    scores: ArticleScores = field(default_factory=ArticleScores)
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    corrections: List[Correction] = field(default_factory=list)
    title_analysis: TitleAnalysis = field(default_factory=TitleAnalysis)
    structure: Optional[StructureNode] = None
    polished_content: str = ""
    tone_analysis: str = ""

    def to_dict(self):
        return {
            "scores": asdict(self.scores),
            "summary": self.summary,
            "keywords": self.keywords,
            "corrections": [asdict(c) for c in self.corrections],
            "title_analysis": asdict(self.title_analysis),
            "structure": asdict(self.structure) if self.structure else None,
            "polished_content": self.polished_content,
            "tone_analysis": self.tone_analysis,
        }

    def to_markdown(self):
        s = self.scores
        lines = [
            "# \u7ae0\u8282\u5206\u6790\u62a5\u544a", "",
            f"## \u7efc\u5408\u8bc4\u5206: **{s.total}/100**", "",
            "| \u7ef4\u5ea6 | \u5f97\u5206 | \u7b49\u7ea7 |",
            "|------|------|------|",
            f"| \u6587\u7b14 | {s.writing} | {grade(s.writing)} |",
            f"| \u5267\u60c5\u8fde\u8d2f | {s.plot_coherence} | {grade(s.plot_coherence)} |",
            f"| \u4ee3\u5165\u611f | {s.immersion} | {grade(s.immersion)} |",
            f"| \u65b0\u610f | {s.novelty} | {grade(s.novelty)} |",
            f"| \u8282\u594f | {s.rhythm} | {grade(s.rhythm)} |",
            "", "## \u6458\u8981", self.summary, "",
        ]
        if self.keywords:
            lines += ["## \u5173\u952e\u8bcd", " ".join(f"`{k}`" for k in self.keywords), ""]
        if self.tone_analysis:
            lines += ["## \u60c5\u7eea\u57fa\u8c03", self.tone_analysis, ""]
        if self.corrections:
            lines += ["## \u7ea0\u9519\u4e0e\u5efa\u8bae", ""]
            for i, c in enumerate(self.corrections[:15], 1):
                lines += [
                    f"**{i}. [{c.type}]** {c.reason}",
                    f"> \u539f\u6587\uff1a`{c.original}`",
                    f"> \u5efa\u8bae\uff1a`{c.suggestion}`",
                ]
                if c.location_snippet:
                    lines.append(f"> \u4f4d\u7f6e\uff1a...{c.location_snippet}...")
                lines.append("")
        if self.title_analysis:
            ta = self.title_analysis
            lines += [
                "## \u7ae0\u8282\u6807\u9898\u5206\u6790",
                f"- \u8bc4\u5206\uff1a{ta.score}/100",
                f"- \u7559\u5b58\u6f5c\u529b\uff1a{ta.retention_potential}",
                f"- \u8bca\u65ad\uff1a{ta.critique}",
            ]
            if ta.suggestions:
                lines += ["- \u4f18\u5316\u5efa\u8bae\uff1a"] + [f"  - {sug}" for sug in ta.suggestions]
            if ta.examples:
                lines += ["- \u63a8\u8350\u6807\u9898\uff1a"] + [f"  - {ex}" for ex in ta.examples]
            lines.append("")
        if self.structure:
            lines += ["## \u903b\u8f91\u7ed3\u6784", self._format_structure(self.structure, 0), ""]
        if self.polished_content:
            lines += ["## \u6da6\u8272\u540e\u5168\u6587", self.polished_content]
        return "\n".join(lines)

    def _format_structure(self, node, indent):
        lines = []
        prefix = "  " * indent
        emoji_map = {
            "root": "\U0001F4D6", "chapter_theme": "\U0001F3AF",
            "plot_point": "\u26A1", "detail": "\U0001F4DD",
            "description": "\U0001F3A8", "cliffhanger": "\u2753",
        }
        emoji = emoji_map.get(node.type, "\u2022")
        lines.append(f"{prefix}- {emoji} **{node.name}**")
        if node.description:
            lines.append(f"{prefix}  \u63cf\u8ff0\uff1a{node.description}")
        for child in node.children:
            lines.extend(self._format_structure(child, indent + 1))
        return "\n".join(lines)


def grade(score):
    if score >= 90: return "\U0001F7E2 \u4f18\u79c0"
    if score >= 75: return "\U0001F7E1 \u826f\u597d"
    if score >= 60: return "\U0001F7E0 \u53ca\u683c"
    return "\U0001F534 \u5f85\u6539\u8fdb"


PROMPT_TEMPLATE = """\
\u4f60\u662f\u4e00\u4f4d\u8d44\u6df1\u7f51\u7edc\u5c0f\u8bf4\u7f16\u8f91\uff0c\u8bf7\u5bf9\u4ee5\u4e0b\u7ae0\u8282\u8fdb\u884c\u5206\u6790\u3002

\u7ae0\u8282\u6807\u9898\uff1a{title}
\u7ae0\u8282\u6b63\u6587\uff1a
{content}

\u8bf7\u5b8c\u6210\uff1a
1. \u4e94\u7ef4\u8bc4\u5206\uff080-100\uff09\uff1atotal/writing/plot_coherence/immersion/novelty/rhythm
2. summary\uff1a\u6458\u8981
3. keywords\uff1a5-7\u4e2a\u5173\u952e\u8bcd
4. corrections\uff1a\u7ea0\u9519\u5217\u8868\uff08original/suggestion/reason/type/location_snippet\uff09
5. title_analysis\uff1ascore/retention_potential/critique/suggestions/examples
6. structure\uff1a\u903b\u8f91\u6811\uff08name/type/description/children\uff09
7. polished_content\uff1a\u6da6\u8272\u5168\u6587
8. tone_analysis\uff1a\u60c5\u7eea\u57fa\u8c03

JSON\u7ed3\u6784\uff1a
{{"scores":{{"total":int,"writing":int,"plot_coherence":int,"immersion":int,"novelty":int,"rhythm":int}},"summary":"string","keywords":["string"],"corrections":[{{"original":"string","suggestion":"string","reason":"string","type":"grammar|typo|style|punctuation","location_snippet":"string"}}],"title_analysis":{{"score":int,"retention_potential":"High|Medium|Low","critique":"string","suggestions":["string"],"examples":["string"]}},,"structure":{{"name":"string","type":"root|chapter_theme|plot_point|detail|description|cliffhanger","description":"string","children":[]}},"polished_content":"string","tone_analysis":"string"}}

\u6ce8\u610f\uff1a\u4e25\u683cJSON\u8f93\u51fa\uff0c\u4e0d\u8981\u5305\u542b\u4efb\u4f55\u989d\u5916\u6587\u5b57\u6216markdown\u3002
"""


def call_api(prompt, provider, config):
    api_key = get_api_key(provider)
    if not api_key:
        raise RuntimeError(f"\u672a\u627e\u5230 {provider} API \u5bc6\u94a5")

    base_url = config["base_url"].rstrip("/")
    model = config["model"]
    max_tokens = config.get("max_tokens", 8192)

    if provider == "agnes":
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.3}
    else:
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://minis.app", "X-Title": "Novel Analyzer"}
        data = {"model": model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "max_tokens": max_tokens, "temperature": 0.3}

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=data, headers=headers)
        resp.raise_for_status()
        return resp.text


def parse_json_response(raw_resp):
    try:
        resp_data = json.loads(raw_resp)
        content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content:
            return parse_json_content(content)
    except (json.JSONDecodeError, KeyError):
        pass

    cleaned = raw_resp.strip()
    if cleaned.startswith("{"):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    m = re.search(r'\{.*\}', raw_resp, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Failed to extract valid JSON from response", raw_resp, 0)


def parse_json_content(content):
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    return json.loads(cleaned)


def build_result(data):
    scores_data = data.get("scores", {})
    scores = ArticleScores(
        total=scores_data.get("total", 0),
        writing=scores_data.get("writing", scores_data.get("readability", 0)),
        plot_coherence=scores_data.get("plot_coherence", scores_data.get("logic", 0)),
        immersion=scores_data.get("immersion", scores_data.get("emotion", 0)),
        novelty=scores_data.get("novelty", scores_data.get("creativity", 0)),
        rhythm=scores_data.get("rhythm", 0),
    )

    corrections = []
    for c in data.get("corrections", []):
        corrections.append(Correction(
            original=c.get("original", ""),
            suggestion=c.get("suggestion", ""),
            reason=c.get("reason", ""),
            type=c.get("type", "style"),
            location_snippet=c.get("location_snippet", ""),
        ))

    ta_data = data.get("title_analysis", {})
    retention = ta_data.get("retention_potential", ta_data.get("viralPotential", "Low"))
    title_analysis = TitleAnalysis(
        score=ta_data.get("score", 0),
        retention_potential=retention,
        critique=ta_data.get("critique", ""),
        suggestions=ta_data.get("suggestions", []),
        examples=ta_data.get("examples", []),
    )

    def build_node(node_data):
        children = [build_node(c) for c in node_data.get("children", [])]
        return StructureNode(
            name=node_data.get("name", ""),
            type=node_data.get("type", "detail"),
            description=node_data.get("description", ""),
            children=children,
        )

    structure = None
    struct_data = data.get("structure")
    if struct_data:
        structure = build_node(struct_data)

    return AnalysisResult(
        scores=scores,
        summary=data.get("summary", ""),
        keywords=data.get("keywords", []),
        corrections=corrections,
        title_analysis=title_analysis,
        structure=structure,
        polished_content=data.get("polished_content", ""),
        tone_analysis=data.get("tone_analysis", ""),
    )


def analyze_chapter(title, content, model=None, json_output=False):
    if model:
        if any(kw in model.lower() for kw in ["glm", "qwen", "deepseek"]):
            provider, config = "openrouter", DEFAULT_CONFIG["openrouter"]
            config["model"] = model
        else:
            provider, config = "agnes", DEFAULT_CONFIG["agnes"]
            config["model"] = model
    else:
        provider, config = get_available_provider()
        if not provider:
            raise RuntimeError("\u6ca1\u6709\u53ef\u7528\u7684 API \u5bc6\u94a5\uff0c\u8bf7\u8bbe\u7f6e AGNES_API_KEY \u6216 OPENROUTER_API_KEY")

    prompt = PROMPT_TEMPLATE.format(title=title or "\u65e0\u6807\u9898", content=content)

    print(f"\U0001F504 \u6b63\u5728\u8c03\u7528 {provider} ({config['model']}) \u5206\u6790\u7ae0\u8282...", file=sys.stderr)
    raw_resp = call_api(prompt, provider, config)

    try:
        data = parse_json_response(raw_resp)
    except json.JSONDecodeError as e:
        print(f"\u274c JSON \u89e3\u6790\u5931\u8d25: {e}", file=sys.stderr)
        print(f"\u539f\u59cb\u54cd\u5e94\u524d500\u5b57: {raw_resp[:500]}", file=sys.stderr)
        raise

    return build_result(data)


def main():
    parser = argparse.ArgumentParser(description="\u5c0f\u8bf4\u7ae0\u8282\u4e94\u7ef4\u5206\u6790\u5668")
    parser.add_argument("--text", "-t", help="\u7ae0\u8282\u6b63\u6587\u6587\u672c")
    parser.add_argument("--title", default="", help="\u7ae0\u8282\u6807\u9898")
    parser.add_argument("--file", "-f", help="\u7ae0\u8282 Markdown \u6587\u4ef6\u8def\u5f84")
    parser.add_argument("--model", "-m", default=None, help="\u6307\u5b9a\u6a21\u578b")
    parser.add_argument("--json", "-j", action="store_true", help="\u4ee5 JSON \u683c\u5f0f\u8f93\u51fa")
    args = parser.parse_args()

    if not args.text and not args.file:
        parser.error("\u8bf7\u63d0\u4f9b --text \u6216 --file")

    try:
        if args.file:
            path = Path(args.file)
            if not path.exists():
                print(f"\u274c \u6587\u4ef6\u4e0d\u5b58\u5728: {args.file}", file=sys.stderr)
                sys.exit(1)
            text = path.read_text(encoding="utf-8")
            title = args.title
            if not title and text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].strip().split("\n"):
                        m = re.match(r"^title:\s*(.+)$", line.strip())
                        if m:
                            title = m.group(1).strip().strip('"').strip("'")
                            break
            if not title:
                title = path.stem
        else:
            text = args.text
            title = args.title or "\u65e0\u6807\u9898"

        result = analyze_chapter(title, text, model=args.model, json_output=args.json)

        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(result.to_markdown())

    except httpx.HTTPStatusError as e:
        print(f"\u274c API \u8bf7\u6c42\u5931\u8d25: {e.response.status_code} - {e.response.text[:200]}", file=sys.stderr)
        sys.exit(2)
    except RuntimeError as e:
        print(f"\u274c {e}", file=sys.stderr)
        sys.exit(3)
    except json.JSONDecodeError as e:
        print(f"\u274c JSON \u89e3\u6790\u5931\u8d25: {e}", file=sys.stderr)
        sys.exit(4)
    except Exception as e:
        print(f"\u274c \u9519\u8bef: {e}", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    main()
