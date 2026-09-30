#!/usr/bin/env python3
# Version: 0.1.0
"""
Knowledge Visualizer — 交互式知识图谱可视化器（P1，零依赖版）

纯 HTML/CSS/JS，无外部 CDN 依赖。使用 SVG 绘制节点图，
右侧并排 Markdown 阅读器。支持搜索、过滤、标签高亮。

用法：
    python3 knowledge-visualizer.py                 # 生成 /var/minis/shared/knowledge-graph.html
    python3 knowledge-visualizer.py --output /path  # 指定输出路径
"""

import json, os, argparse

KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
DEFAULT_OUTPUT = "/var/minis/shared/knowledge-graph.html"

TYPE_COLORS = {
    "concept": "#4A90D9",
    "memory": "#6C5CE7",
    "tool": "#00B894",
    "skill": "#FDCB6E",
    "decision": "#E17055",
    "reference": "#A29BFE",
    "insight": "#00CEC9",
    "preference": "#FFEAA7",
    "general": "#B2BEC3",
    "active": "#00B894",
    "draft": "#B2BEC3",
    "stale": "#E17055",
    "deprecated": "#636E72",
    "approved": "#00B894",
    "pending": "#FDCB6E",
}

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Minis 第二大脑 — 知识图谱</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; height: 100vh; overflow: hidden; }
#app { display: flex; height: 100vh; }
#sidebar { width: 300px; background: #161b22; border-right: 1px solid #30363d; display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0; }
#sidebar-header { padding: 14px; border-bottom: 1px solid #30363d; }
#sidebar-header h1 { font-size: 14px; color: #58a6ff; margin-bottom: 8px; }
#search-box { width: 100%; padding: 7px 10px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 13px; outline: none; }
#search-box:focus { border-color: #58a6ff; }
#filters { padding: 10px 14px; border-bottom: 1px solid #30363d; }
#filters h3 { font-size: 10px; color: #8b949e; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.filter-group { display: flex; flex-wrap: wrap; gap: 3px; }
.filter-btn { padding: 2px 7px; font-size: 11px; border-radius: 4px; border: 1px solid #30363d; background: #21262d; color: #8b949e; cursor: pointer; transition: all 0.15s; }
.filter-btn:hover { border-color: #58a6ff; color: #c9d1d9; }
.filter-btn.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
#card-list { flex: 1; overflow-y: auto; }
#card-list::-webkit-scrollbar { width: 5px; }
#card-list::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
.card-item { padding: 8px 14px; border-bottom: 1px solid #21262d; cursor: pointer; transition: background 0.15s; }
.card-item:hover { background: #21262d; }
.card-item.active { background: #1c3a5f; border-left: 3px solid #58a6ff; }
.card-item-title { font-size: 12px; color: #c9d1d9; margin-bottom: 3px; display: flex; align-items: center; gap: 6px; }
.card-item-meta { font-size: 10px; color: #8b949e; }
.card-item .type-badge { font-size: 9px; padding: 1px 5px; border-radius: 3px; background: #21262d; color: #8b949e; }
.stale-badge { background: #f85149 !important; color: #fff !important; }
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
#stats-bar { padding: 6px 14px; border-bottom: 1px solid #21262d; font-size: 11px; color: #8b949e; display: flex; gap: 14px; flex-wrap: wrap; }
#graph-area { flex: 1; position: relative; overflow: hidden; min-height: 300px; }
#graph-canvas { width: 100%; height: 100%; display: block; }
#graph-canvas:active { cursor: grabbing; }
#viewer-panel { height: 0; background: #161b22; border-top: 1px solid #30363d; overflow: hidden; transition: height 0.3s ease; display: flex; }
#viewer-panel.open { height: 42%; }
#viewer-content { flex: 1; overflow-y: auto; padding: 16px; }
#viewer-content::-webkit-scrollbar { width: 5px; }
#viewer-content::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
#viewer-content h1 { font-size: 18px; margin-bottom: 10px; }
#viewer-content h2 { font-size: 15px; margin: 14px 0 6px; color: #58a6ff; }
#viewer-content h3 { font-size: 13px; margin: 10px 0 4px; color: #c9d1d9; }
#viewer-content blockquote { border-left: 3px solid #58a6ff; padding-left: 10px; margin: 6px 0; color: #8b949e; font-style: italic; font-size: 13px; }
#viewer-content ul, #viewer-content ol { margin: 6px 0; padding-left: 18px; }
#viewer-content li { margin: 3px 0; font-size: 13px; }
#viewer-content hr { border: none; border-top: 1px solid #30363d; margin: 12px 0; }
#viewer-content p { margin: 6px 0; line-height: 1.55; font-size: 13px; }
#viewer-content strong { color: #f0f6fc; }
#viewer-content code { background: #21262d; padding: 1px 5px; border-radius: 3px; font-size: 12px; color: #f2cc60; }
#viewer-meta { padding: 10px 16px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 10px; font-size: 12px; color: #8b949e; }
#viewer-close { cursor: pointer; font-size: 18px; color: #8b949e; padding: 0 6px; user-select: none; }
#viewer-close:hover { color: #c9d1d9; }
.legend { position: absolute; bottom: 10px; right: 10px; background: rgba(22,27,34,0.92); border: 1px solid #30363d; border-radius: 8px; padding: 6px 10px; font-size: 10px; display: flex; gap: 10px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 7px; height: 7px; border-radius: 50%; }
#empty-state { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; color: #484f58; }
#empty-state h2 { font-size: 15px; margin-bottom: 6px; }
#empty-state p { font-size: 12px; }
</style>
</head>
<body>
<div id="app">
<div id="sidebar">
    <div id="sidebar-header">
        <h1>🧠 Minis 第二大脑</h1>
        <input id="search-box" type="text" placeholder="搜索卡片标题、标签、主张...">
    </div>
    <div id="filters">
        <h3>类型过滤</h3>
        <div class="filter-group" id="type-filters"></div>
    </div>
    <div id="card-list"></div>
</div>
<div id="main">
    <div id="stats-bar"></div>
    <div id="graph-area">
        <svg id="graph-canvas"></svg>
        <div id="empty-state"><h2>📊 知识图谱</h2><p>点击左侧卡片或图中节点查看详情</p></div>
        <div class="legend" id="legend"></div>
    </div>
    <div id="viewer-panel">
        <div id="viewer-meta">
            <span id="viewer-close">✕</span>
            <span id="viewer-title"></span>
            <span style="flex:1"></span>
            <span id="viewer-evidence"></span>
        </div>
        <div id="viewer-content"></div>
    </div>
</div>
</div>
<script>
const GRAPH_DATA = {nodes: %%NODES%%, edges: %%EDGES%%};
const CARDS = %%CARDS_JSON%%;

let activeCard = null;
let activeFilter = 'all';
let searchTerm = '';

// ── Graph layout ──
const svgCanvas = document.getElementById('graph-canvas');
const emptyState = document.getElementById('empty-state');
let offsetX = 0, offsetY = 0, isDragging = false, dragNode = null;
let layoutX = 0, layoutY = 0;
const NODE_RADIUS = 18;
const REPULSION = 18000;
const ATTRACTION = 0.005;
const CENTER_PULL = 0.0008;
const DAMPING = 0.9;
const MAX_VEL = 5;

// Initialize node positions
let nodePositions = {};
let nodeVelocities = {};
let layoutWidth = 500, layoutHeight = 500;

function initLayout() {
    let w = window.innerWidth || document.documentElement.clientWidth || 390;
    let h = window.innerHeight || document.documentElement.clientHeight || 844;
    // 减去侧边栏和头部
    const sidebarW = w < 600 ? 200 : 300;
    const headerH = 60;
    // 至少保证 280×400 的绘图区，确保节点能散开
    layoutWidth = Math.max(w - sidebarW, 280);
    layoutHeight = Math.max(h - headerH, 400);
    // 设置 SVG 尺寸
    svgCanvas.setAttribute('width', layoutWidth);
    svgCanvas.setAttribute('height', layoutHeight);
    svgCanvas.setAttribute('viewBox', `0 0 ${layoutWidth} ${layoutHeight}`);
    svgCanvas.style.width = layoutWidth + 'px';
    svgCanvas.style.height = layoutHeight + 'px';
    GRAPH_DATA.nodes.forEach(n => {
        nodePositions[n.id] = {
            x: layoutWidth / 2 + (Math.random() - 0.5) * layoutWidth * 0.7,
            y: layoutHeight / 2 + (Math.random() - 0.5) * layoutHeight * 0.7,
        };
        nodeVelocities[n.id] = {vx: 0, vy: 0};
    });
}

function updateLayoutSize() {
    const ga = document.getElementById('graph-area');
    layoutWidth = ga.offsetWidth || 300;
    layoutHeight = ga.offsetHeight || 300;
    layoutWidth = Math.max(layoutWidth, 300);
    layoutHeight = Math.max(layoutHeight, 300);
}

window.addEventListener('resize', () => { updateLayoutSize(); renderGraph(); });

function simulate() {
    const nodes = GRAPH_DATA.nodes;
    const edges = GRAPH_DATA.edges;

    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
            const a = nodePositions[nodes[i].id];
            const b = nodePositions[nodes[j].id];
            let dx = a.x - b.x, dy = a.y - b.y;
            let dist = Math.sqrt(dx*dx + dy*dy) || 1;
            let force = REPULSION / (dist * dist);
            let fx = (dx / dist) * force;
            let fy = (dy / dist) * force;
            nodeVelocities[nodes[i].id].vx += fx;
            nodeVelocities[nodes[i].id].vy += fy;
            nodeVelocities[nodes[j].id].vx -= fx;
            nodeVelocities[nodes[j].id].vy -= fy;
        }
    }

    // Attraction along edges
    edges.forEach(e => {
        const a = nodePositions[e.from];
        const b = nodePositions[e.to];
        if (!a || !b) return;
        let dx = b.x - a.x, dy = b.y - a.y;
        let dist = Math.sqrt(dx*dx + dy*dy) || 1;
        let force = dist * ATTRACTION;
        let fx = (dx / dist) * force;
        let fy = (dy / dist) * force;
        nodeVelocities[e.from].vx += fx;
        nodeVelocities[e.from].vy += fy;
        nodeVelocities[e.to].vx -= fx;
        nodeVelocities[e.to].vy -= fy;
    });

    // Center pull + velocity + position update
    nodes.forEach(n => {
        const pos = nodePositions[n.id];
        const vel = nodeVelocities[n.id];
        vel.vx += (layoutWidth / 2 - pos.x) * CENTER_PULL;
        vel.vy += (layoutHeight / 2 - pos.y) * CENTER_PULL;
        vel.vx *= DAMPING;
        vel.vy *= DAMPING;
        vel.vx = Math.max(-MAX_VEL, Math.min(MAX_VEL, vel.vx));
        vel.vy = Math.max(-MAX_VEL, Math.min(MAX_VEL, vel.vy));
        pos.x += vel.vx;
        pos.y += vel.vy;
    });
}

function renderGraph() {
    const nodes = GRAPH_DATA.nodes;
    const edges = GRAPH_DATA.edges;
    let svg = '';

    // Edges (limit to 50 to avoid rendering bloat)
    const limitedEdges = edges.slice(0, 50);
    limitedEdges.forEach(e => {
        const a = nodePositions[e.from];
        const b = nodePositions[e.to];
        if (!a || !b) return;
        const visible = !e.hidden;
        if (!visible) return;
        svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#30363d" stroke-width="0.5" opacity="0.4"/>`;
    });

    // Nodes
    nodes.forEach(n => {
        const pos = nodePositions[n.id];
        if (!pos) return;
        const color = (n.color && n.color.background) || '#4A90D9';
        const size = n.size || 14;
        svg += `<circle cx="${pos.x}" cy="${pos.y}" r="${size}" fill="${color}" fill-opacity="0.85" stroke="${color}" stroke-width="1" data-id="${n.id}" style="cursor:pointer">`;
        svg += `<title>${n.tooltip || n.label}</title></circle>`;
        // Label
        svg += `<text x="${pos.x}" y="${pos.y + size + 10}" text-anchor="middle" font-size="8" fill="#8b949e" style="pointer-events:none">${n.label.substring(0,12)}</text>`;
    });

    svgCanvas.innerHTML = svg;

    // Click handlers
    svgCanvas.querySelectorAll('circle[data-id]').forEach(circle => {
        circle.addEventListener('click', () => selectCard(circle.getAttribute('data-id')));
    });
}

// Mouse drag
svgCanvas.addEventListener('mousedown', e => {
    const target = e.target;
    if (target.tagName === 'circle' && target.getAttribute('data-id')) {
        dragNode = target.getAttribute('data-id');
        isDragging = true;
        e.preventDefault();
    }
});
svgCanvas.addEventListener('mousemove', e => {
    if (isDragging && dragNode) {
        const rect = svgCanvas.getBoundingClientRect();
        const x = (e.clientX - rect.left - offsetX);
        const y = (e.clientY - rect.top - offsetY);
        if (nodePositions[dragNode]) {
            nodePositions[dragNode].x = x;
            nodePositions[dragNode].y = y;
            nodeVelocities[dragNode].vx = 0;
            nodeVelocities[dragNode].vy = 0;
        }
    }
});
svgCanvas.addEventListener('mouseup', () => { isDragging = false; dragNode = null; });
svgCanvas.addEventListener('mouseleave', () => { isDragging = false; dragNode = null; });

function startAnimation() {
    // 同步模拟力导向（120 步，节点更散开），确保后台标签页也能渲染
    initLayout();
    for (let i = 0; i < 120; i++) {
        simulate();
    }
    renderGraph();
    if (GRAPH_DATA.nodes.length > 0 && emptyState) {
        emptyState.style.display = 'none';
    }
}

// ── Card list & viewer ──
function selectCard(cardId) {
    activeCard = CARDS.find(c => c.id === cardId);
    if (!activeCard) return;
    document.querySelectorAll('.card-item').forEach(el => el.classList.remove('active'));
    const item = document.getElementById('card-' + cardId);
    if (item) item.classList.add('active');
    const panel = document.getElementById('viewer-panel');
    panel.classList.add('open');
    document.getElementById('viewer-title').textContent = activeCard.title;
    document.getElementById('viewer-evidence').textContent = activeCard.evidence_status || '';
    const body = activeCard.body || '';
    const viewer = document.getElementById('viewer-content');
    // Simple markdown rendering
    let html = body
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
        .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
        .replace(/(\*\*(.+?)\*\*)/g, '<strong>$2</strong>')
        .replace(/(`(.+?)`)/g, '<code>$2</code>')
        .replace(/^---$/gm, '<hr>')
        .replace(/\n\n/g, '<br>')
        .replace(/\n/g, '<br>');
    viewer.innerHTML = html;
}

function closeViewer() {
    document.getElementById('viewer-panel').classList.remove('open');
    document.querySelectorAll('.card-item').forEach(el => el.classList.remove('active'));
    activeCard = null;
}

function filterByType(type) {
    if (activeFilter === type) { activeFilter = 'all'; document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); return; }
    activeFilter = type;
    document.querySelectorAll('.filter-btn').forEach(b => { b.classList.toggle('active', b.dataset.type === type); });
    updateCardList();
}

function updateCardList() {
    const list = document.getElementById('card-list');
    list.innerHTML = '';
    const filtered = Object.values(CARDS).filter(c => {
        if (activeFilter !== 'all' && c.type !== activeFilter) return false;
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            return c.title.toLowerCase().includes(term) || (c.tags || []).some(t => t.toLowerCase().includes(term)) || (c.claims || []).some(cl => cl.toLowerCase().includes(term));
        }
        return true;
    });
    filtered.sort((a, b) => a.title.localeCompare(b.title));
    filtered.forEach(c => {
        const div = document.createElement('div');
        div.className = 'card-item';
        div.id = 'card-' + c.id;
        div.onclick = () => selectCard(c.id);
        const staleBadge = c.evidence_stale ? '<span class="type-badge stale-badge">⚠️</span>' : '';
        div.innerHTML = '<div class="card-item-title">' + staleBadge + '<span>' + c.title.substring(0, 30) + '</span></div><div class="card-item-meta">' + c.type + ' · ' + (c.tags || []).slice(0,3).join(' · ') + '</div>';
        list.appendChild(div);
    });
}

function initFilters() {
    const types = [...new Set(Object.values(CARDS).map(c => c.type))].sort();
    const container = document.getElementById('type-filters');
    const allBtn = document.createElement('button');
    allBtn.className = 'filter-btn active';
    allBtn.dataset.type = 'all';
    allBtn.textContent = '全部';
    allBtn.onclick = () => filterByType('all');
    container.appendChild(allBtn);
    types.forEach(t => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.dataset.type = t;
        btn.textContent = t;
        btn.onclick = () => filterByType(t);
        container.appendChild(btn);
    });
}

function initStats() {
    const cards = Object.values(CARDS);
    const staleCount = cards.filter(c => c.evidence_stale).length;
    const typeCounts = {};
    cards.forEach(c => { typeCounts[c.type] = (typeCounts[c.type] || 0) + 1; });
    const typeStr = Object.entries(typeCounts).map(([k,v]) => `${k}:${v}`).join(' · ');
    document.getElementById('stats-bar').innerHTML = `<span>📊 ${cards.length} 张卡片</span><span>${typeStr}</span><span>${staleCount ? '⚠️ ' + staleCount + ' 张过期' : '✅ 全部有效'}</span>`;
}

function initLegend() {
    const legend = document.getElementById('legend');
    const items = [
        {color: '#4A90D9', label: 'Concept'},
        {color: '#00B894', label: 'Tool'},
        {color: '#6C5CE7', label: 'Memory'},
        {color: '#E17055', label: 'Stale'},
    ];
    legend.innerHTML = items.map(li => `<span class="legend-item"><span class="legend-dot" style="background:${li.color}"></span>${li.label}</span>`).join('');
}

document.getElementById('search-box').addEventListener('input', e => { searchTerm = e.target.value; updateCardList(); });
document.getElementById('viewer-close').addEventListener('click', closeViewer);

initLegend();
initFilters();
updateCardList();
initStats();
startAnimation();
</script>
</body>
</html>"""


def _get_type_color(card_type, status, evidence_stale):
    if evidence_stale:
        return "#E17055"
    return TYPE_COLORS.get(card_type, "#4A90D9")


def build_graph_data(cards):
    """构建可视化器所需的图数据。"""
    nodes = []
    edges = []

    tag_to_cards = {}
    for card in cards:
        for tag in card.get('tags', []):
            tag_to_cards.setdefault(tag, []).append(card['id'])

    for card in cards:
        card_type = card.get('type', 'general')
        evidence_stale = card.get('evidence', {}).get('stale', False)
        color = _get_type_color(card_type, card.get('status'), evidence_stale)
        title = card.get('title', '')
        score = card.get('score', 10)
        size = max(10, min(28, score // 3 + 8))

        nodes.append({
            "id": card['id'],
            "label": title[:25] + ('...' if len(title) > 25 else ''),
            "group": card_type,
            "color": {"background": color, "border": color, "highlight": {"background": color, "border": "#fff"}},
            "size": size,
            "tooltip": f"{card_type} · score:{score} · {'⚠️ STALE' if evidence_stale else '✅'}",
        })

    seen_edges = set()
    for tag, card_ids in tag_to_cards.items():
        if len(card_ids) < 2:
            continue
        for i in range(len(card_ids)):
            for j in range(i + 1, len(card_ids)):
                edge_key = (card_ids[i], card_ids[j])
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({"from": card_ids[i], "to": card_ids[j], "label": tag[:6], "width": 0.5})

    return nodes, edges


def build_cards_json(cards):
    """构建卡片详情的 JSON 数据。"""
    result = {}
    for card in cards:
        body_parts = [f"# {card.get('icon', '')} {card.get('title', '')}"]
        body_parts.append('')

        l0 = card.get('l0_abstract', '')
        if l0:
            body_parts.append(f"> {l0}")
            body_parts.append('')

        l1 = card.get('l1_overview', '')
        if l1:
            body_parts.append('## 概览')
            body_parts.append(l1[:600])
            body_parts.append('')

        claims = card.get('claims', [])
        if claims:
            body_parts.append('## 核心主张')
            for c in claims[:10]:
                body_parts.append(f'- {c}')
            body_parts.append('')

        tags = card.get('tags', [])
        if tags:
            body_parts.append(f'**标签：** ' + ', '.join(f'`{t}`' for t in tags[:10]))
            body_parts.append('')

        evidence = card.get('evidence', {})
        if evidence:
            body_parts.append('## 证据')
            if evidence.get('file_missing'):
                body_parts.append('⚠️ 源文件已丢失')
            else:
                body_parts.append(f'来源：`{evidence.get("source_path", "")}`')
                body_parts.append(f'哈希：`{evidence.get("source_hash", "")[:16]}...`')
                body_parts.append(f'捕获时间：{evidence.get("captured_at", "")[:19]}')
                if evidence.get('stale'):
                    body_parts.append(f'⚠️ 过期原因：{evidence.get("stale_reason", "")}')
                    body_parts.append(f'过期时间：{evidence.get("stale_at", "")[:19]}')
            body_parts.append('')

        score = card.get('score')
        status = card.get('status', '')
        evidence_stale = evidence.get('stale', False)
        body_parts.append(f'_类型：{card.get("type_label", "")} | 状态：{status} | 评分：{score} | 来源：{card.get("source", "")}_')

        result[card['id']] = {
            "id": card['id'],
            "title": card.get('title', ''),
            "type": card.get('type', 'general'),
            "tags": tags,
            "claims": claims,
            "body": '\n'.join(body_parts),
            "evidence_status": '✅ 有效' if not evidence_stale else '⚠️ 过期',
            "evidence_stale": evidence_stale,
        }

    return result


def generate_html(output_path=DEFAULT_OUTPUT):
    """生成知识图谱 HTML 页面。"""
    if not os.path.exists(KNOWLEDGE_STORE):
        return {"error": "knowledge-store not found"}

    store = json.load(open(KNOWLEDGE_STORE, 'r', encoding='utf-8'))
    cards = store.get('cards', [])

    if not cards:
        return {"error": "no cards found"}

    nodes, edges = build_graph_data(cards)
    cards_json = build_cards_json(cards)

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    cards_json_str = json.dumps(cards_json, ensure_ascii=False)

    html_content = HTML_TEMPLATE.replace('%%NODES%%', nodes_json).replace('%%EDGES%%', edges_json).replace('%%CARDS_JSON%%', cards_json_str)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return {
        "output": output_path,
        "cards": len(cards),
        "nodes": len(nodes),
        "edges": len(edges),
    }


def main():
    parser = argparse.ArgumentParser(description='知识图谱可视化器（零依赖）')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出 HTML 路径')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    result = generate_html(output_path=args.output)

    if 'error' in result:
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"❌ {result['error']}")
        return

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    r = result
    print(f"📊 知识图谱可视化器已生成")
    print(f"  输出: {r['output']}")
    print(f"  节点: {r['nodes']} | 边: {r['edges']} | 卡片: {r['cards']}")


if __name__ == '__main__':
    main()
