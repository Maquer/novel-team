#!/usr/bin/env python3
"""xhs-gate.py — 小红书团队 E 系列门禁脚本 v0.2

参考：gzh-team/gate-check.py（结构移植）+ TEAM.md §3（E1-E5 判据）
覆盖：E1 证据表格式 / E2 主客观分离 + 改写建议 / E3 利益披露 / E4 贬损词 / E5 AI 人设 / 标题数字一致性
用法：
  python3 xhs-gate.py --evidence 实测数据库/e1-evidence-001.md
  python3 xhs-gate.py --article 实测数据库/04-昭断-article-001.md
  python3 xhs-gate.py --title-check "标题" "正文文件.md"
  python3 xhs-gate.py --article article.md --verbose --checklist
"""
import sys, re, json, argparse

# ─── 词表定义 ─────────────────────────────────────────────────────────────────

# E4 不可验证贬损词（小红书平台专属 + 通用）
E4_BANNED = [
    '脑残', '割韭菜', '智商税', '骗钱', '坑爹', '坑妈',
    '垃圾', '破烂', '废物', '废物利用', '狗屁', '扯淡',
    '避雷', '踩雷', '别买', '别入', '别碰',  # 部分平台可接受，留作 WARN
]

# E3 利益披露关键词（必须检测 + 位置校验）
E3_KEYWORDS = ['送测', '自费', '自购', '品牌合作', '广告', '赞助', '合作']

# E5 AI 人设检测辅助词（标记可疑第一人称句）
E5_FIRST_PERSON = ['我觉得', '我认为', '我以为', '我试了', '我用了', '我发现', '我感觉']

# 绝对化用语黑名单（E4 扩展）
ABSOLUTE_WORDS = ['最', '第一', '100%', '全网', '包治', '根治', '绝对', '一定', '必定']

# E2 改写建议模板
E2_FIX_TEMPLATES = {
    '主观感受': [
        '将「我觉得很卡」改为「C 任务输出耗时 >10s，实用性 2 分」',
        '将「体验很差」改为「对比基准差 {x}%」',
    ],
    '模糊描述': [
        '将「很快」改为具体数值（如「响应时间 <200ms」）',
        '将「很长时间」改为具体数值（如「等待 >30s」）',
    ],
    '混合句拆分': [
        '将主观感受与客观数据拆分为两句，中间用句号分隔',
        '在主观判断后添加「（个人体验，仅供参考）」标签',
    ]
}


# ─── 检测函数 ─────────────────────────────────────────────────────────────────

def check_e1_evidence(evidence_file):
    """E1 实测证据格式校验（v3：按 Markdown 表格结构解析）
    
    策略：按段落分组，识别完整表格（表头 + 分隔行 + 数据行）
    """
    try:
        t = open(evidence_file).read()
    except FileNotFoundError:
        return {'PASS': False, 'error': f'文件不存在：{evidence_file}'}
    
    results = {
        'file': evidence_file,
        'entries': [],
        'summary': {}
    }
    
    # ── 按空行分割段落 ──
    paragraphs = re.split(r'\n\n+', t)
    
    for para in paragraphs:
        lines = [l for l in para.split('\n') if l.strip()]
        if not lines:
            continue
        
        # ── 检测是否为完整表格（至少 3 行且含分隔符） ──
        if not any('|' in l for l in lines):
            continue
        
        # 找分隔行（包含 ---- 或 ===）
        sep_idx = None
        for i, l in enumerate(lines):
            if re.match(r'^\|[-:\s|]+\|$', l):
                sep_idx = i
                break
        
        if sep_idx is None or sep_idx == 0:
            continue  # 不是标准表格
        
        # 提取表头和数据行
        header_line = lines[sep_idx - 1] if sep_idx > 0 else None
        data_lines = lines[sep_idx + 1:]
        
        if not header_line or len(data_lines) < 1:
            continue
        
        # 解析表头
        headers = [h.strip().lower() for h in header_line.split('|')[1:-1]]
        header_map = {h: i for i, h in enumerate(headers)}
        
        # 检测四要素列
        has_test_col = any(k in header_map for k in ['测试条件', '环境', '室温', '亮度', '系统', 'api', '接入'])
        has_data_col = any(k in header_map for k in ['数据', '结果', '评分', '得分', '分数'])
        has_reproduce_col = any(k in header_map for k in ['复现', '步骤', '方法', '操作'])
        has_sample_col = any(k in header_map for k in ['样本', '次数', '重复', 'n', '状态'])
        
        # 逐行检查数据
        for row_text in data_lines[:10]:  # 最多检查 10 行
            cells = [c.strip() for c in row_text.split('|')[1:-1]]
            if not cells or all(not c for c in cells):
                continue
            
            entry = {
                'defect': f'表格行（{len(results["entries"]) + 1}）',
                'has_test_condition': has_test_col and any(len(c) > 3 for c in cells),
                'has_data': has_data_col and any(re.search(r'\d+\.?\d*', c) for c in cells),
                'has_reproduce': has_reproduce_col and any(len(c) > 2 for c in cells),
                'has_sample_count': has_sample_col and any(re.search(r'\d+', c) for c in cells),
                'issues': [],
                'pass': True
            }
            
            if not entry['has_test_condition']:
                entry['issues'].append('缺测试条件')
                entry['pass'] = False
            if not entry['has_data']:
                entry['issues'].append('缺数据')
                entry['pass'] = False
            if not entry['has_reproduce']:
                entry['issues'].append('缺复现步骤')
                entry['pass'] = False
            if not entry['has_sample_count']:
                entry['issues'].append('缺样本数')
                entry['pass'] = False
            
            results['entries'].append(entry)
    
    # ── 汇总 ──
    if not results['entries']:
        results['summary'] = {'status': 'WARN', 'note': '未识别到标准表格，尝试章节式检查'}
        return _check_e1_chapters(evidence_file, results)
    
    passed = sum(1 for e in results['entries'] if e['pass'])
    total = len(results['entries'])
    results['summary'] = {
        'status': 'PASS' if passed == total else 'FAIL',
        'passed': passed,
        'total': total,
        'detail': f'{passed}/{total} 项通过'
    }
    return results


def _check_e1_chapters(evidence_file, results):
    """E1 章节式 fallback（当没有标准表格时）"""
    try:
        t = open(evidence_file).read()
    except FileNotFoundError:
        return results
    
    # 找所有 ## 标题块
    blocks = re.split(r'\n##\s+', t)
    blocks = [b.strip() for b in blocks if b.strip()][:10]
    
    for block in blocks:
        has_test = bool(re.search(r'测试条件|环境|室温|亮度|系统|版本', block, re.I))
        has_data = bool(re.search(r'\d+\.?\d*\s*(℃|°C|分|秒|ms|MB|GB|fps|B)', block))
        has_reproduce = bool(re.search(r'复现|步骤|方法|操作', block, re.I))
        has_sample = bool(re.search(r'样本|次数|重复|n\s*=', block, re.I))
        
        if has_test or has_data or has_reproduce:
            entry = {
                'defect': block[:50].replace('\n', ' ') + '...',
                'has_test_condition': has_test,
                'has_data': has_data,
                'has_reproduce': has_reproduce,
                'has_sample_count': has_sample,
                'issues': [],
                'pass': True
            }
            if not has_test: entry['issues'].append('缺测试条件'); entry['pass'] = False
            if not has_data: entry['issues'].append('缺数据'); entry['pass'] = False
            if not has_reproduce: entry['issues'].append('缺复现'); entry['pass'] = False
            if not has_sample: entry['issues'].append('缺样本数'); entry['pass'] = False
            
            results['entries'].append(entry)
    
    passed = sum(1 for e in results['entries'] if e['pass'])
    total = len(results['entries'])
    results['summary'] = {
        'status': 'PASS' if passed == total and total > 0 else ('WARN' if total == 0 else 'FAIL'),
        'passed': passed,
        'total': total,
        'detail': f'{passed}/{total} 项通过'
    }
    return results


# ── E1-P 数据来源可追溯（09-25 新增，#001 实检教训）─────────────────────────
# 背景：E1 旧版只校验证据表「格式」（条件/数据/复现/样本四栏齐不齐）。
# #001 的证据表自述「模拟实测数据，待真实测试验证」，四栏格式齐全 → 旧 E1 判 PASS，
# 而稿件同时以「我用 iPhone 15 Pro 实测了」第一人称发布。格式齐备 + 数据虚构
# 恰好是旧表单能放过去的形态。本函数把「数据是否声称自己真实」变成硬检查。
HARD_MOCK_MARKERS = [
    '模拟实测', '模拟数据', '虚构', '占位数据', '占位符', '示例数据', '假数据',
    '待真实测试', '未经真实测试', '尚未实测', '待实测', '尚未实测',
    'mock data', 'placeholder', 'dummy data', 'sample data', 'fabricat',
]
SOFT_MOCK_MARKERS = ['待验证', '待核实', '待补充', '待填充', 'TODO', 'TBD', '暂定']
REAL_CLAIM_PATTERNS = [
    r'我(?:在|用|于)[^。\n]{0,30}?(?:实测|测试|亲测)了',
    r'我(?:实测|亲测)了',
    r'实测(?:了)?\s*\d+\s*款',
    r'每(?:款|组)(?:测试|测)\s*\d+\s*次',
]


def check_e1_provenance(evidence_file, article_text=None):
    """E1-P 数据来源可追溯：证据表自述非真实 + 稿件声称实测 = 硬阻断"""
    out = {'file': evidence_file, 'hard': [], 'soft': [], 'claims': [],
           'summary': {'status': 'PASS', 'detail': ''}}
    try:
        ev = open(evidence_file, encoding='utf-8').read()
    except FileNotFoundError:
        out['summary'] = {'status': 'FAIL', 'detail': f'证据表文件不存在：{evidence_file}'}
        return out

    low = ev.lower()
    out['hard'] = sorted({m for m in HARD_MOCK_MARKERS if m.lower() in low})
    out['soft'] = sorted({m for m in SOFT_MOCK_MARKERS if m.lower() in low})

    if article_text:
        out['claims'] = sorted({p for p in REAL_CLAIM_PATTERNS if re.search(p, article_text)})

    if out['hard'] and out['claims']:
        out['summary'] = {'status': 'FAIL',
                          'detail': '自相矛盾：证据表自述非实测（%s），稿件却声称实测（%d 处第一人称实测叙述）'
                                    % ('、'.join(out['hard']), len(out['claims']))}
    elif out['hard']:
        out['summary'] = {'status': 'FAIL',
                          'detail': '证据表自述数据非实测：%s —— 不得作为缺点结论的证据发布' % '、'.join(out['hard'])}
    elif out['soft']:
        out['summary'] = {'status': 'WARN',
                          'detail': '证据表含未完成标记：%s，发布前需逐条确认为一手实测' % '、'.join(out['soft'])}
    else:
        out['summary'] = {'status': 'PASS', 'detail': '证据表未出现「数据非实测」自述标记'}
    return out


def check_e2_objective(article_text):
    """E2 主客观分离检测 + 改写建议
    
    要求：「我觉得」与「它发热」不得混写在同一句
    输出：失败项 + 具体改写建议
    """
    results = {
        'subjective_patterns': [],
        'objective_patterns': [],
        'mixed_sentences': [],
        'fix_suggestions': [],
        'summary': {}
    }
    
    sentences = re.split(r'[。！？；]', article_text)
    
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue
        
        has_subjective = any(p in sent for p in E5_FIRST_PERSON)
        has_objective = bool(re.search(r'\d+\.?\d*\s*(℃|°C|分|秒|ms|MB|GB|fps|帧)|发热|卡顿|延迟|耗电', sent, re.I))
        
        if has_subjective:
            results['subjective_patterns'].append({
                'sentence': sent[:50],
                'line': i + 1
            })
        if has_objective:
            results['objective_patterns'].append({
                'sentence': sent[:50],
                'line': i + 1
            })
        if has_subjective and has_objective:
            results['mixed_sentences'].append({
                'sentence': sent[:80],
                'line': i + 1,
                'issue': '主观 + 客观混写',
                'fix': E2_FIX_TEMPLATES['混合句拆分'][0]
            })
        
        # 纯主观无数据 → 给改写建议
        if has_subjective and not has_objective:
            results['fix_suggestions'].append({
                'sentence': sent[:60],
                'line': i + 1,
                'fix': E2_FIX_TEMPLATES['主观感受'][0]
            })
    
    results['summary'] = {
        'status': 'PASS' if not results['mixed_sentences'] else 'FAIL',
        'mixed_count': len(results['mixed_sentences']),
        'subjective_count': len(results['subjective_patterns']),
        'objective_count': len(results['objective_patterns']),
        'fix_count': len(results['fix_suggestions'])
    }
    return results


def check_e3_disclosure(article_text):
    """E3 利益披露检测
    
    要求：自费/送测/品牌合作 → 首图或正文前三行显著标注
    """
    lines = article_text.split('\n')
    first_lines = [l for l in lines[:10] if l.strip()]  # 前 10 行非空行
    
    results = {
        'keywords_found': [],
        'keywords_in_first_lines': [],
        'location_ok': False,
        'summary': {}
    }
    
    for kw in E3_KEYWORDS:
        if kw in article_text:
            results['keywords_found'].append(kw)
            # 检查是否在前三行
            for line in first_lines[:3]:
                if kw in line:
                    results['keywords_in_first_lines'].append(kw)
                    break
    
    # 判定：有关键词且在前三行 = PASS；有关键词但不在前三行 = WARN；无关键词 = SKIP
    if not results['keywords_found']:
        results['summary'] = {
            'status': 'SKIP',
            'note': '未检测到利益披露关键词，跳过 E3 检查'
        }
    elif len(results['keywords_in_first_lines']) == len(results['keywords_found']):
        results['location_ok'] = True
        results['summary'] = {
            'status': 'PASS',
            'note': f'所有披露关键词均在前三行：{results["keywords_in_first_lines"]}'
        }
    else:
        results['summary'] = {
            'status': 'WARN',
            'note': f'部分披露关键词不在前三行：{set(results["keywords_found"]) - set(results["keywords_in_first_lines"])}'
        }
    
    return results


def check_e4_defamatory(article_text):
    """E4 无信息量贬损检测
    
    要求：「脑残」「割韭菜」等不可验证表述
    """
    hits = [word for word in E4_BANNED if word in article_text]
    
    # 区分硬阻断（脑残/割韭菜/智商税）和软警告（避雷/踩雷）
    hard_hits = [w for w in hits if w in ['脑残', '割韭菜', '智商税', '骗钱', '坑爹', '坑妈']]
    soft_hits = [w for w in hits if w in ['避雷', '踩雷', '别买', '别入', '别碰']]
    
    return {
        'hard_hits': hard_hits,
        'soft_hits': soft_hits,
        'all_hits': hits,
        'summary': {
            'status': 'PASS' if not hard_hits else 'FAIL',
            'hard_count': len(hard_hits),
            'soft_count': len(soft_hits),
            'note': '硬阻断词需删除；软警告词可改为可验证表述'
        }
    }


def check_e5_ai_persona(article_text):
    """E5 AI 虚假人设检测
    
    要求：第一人称叙述中的经历必须可验证（时间/地点/对象/场景）
    """
    sentences = re.split(r'[。！？]', article_text)
    
    results = {
        'suspicious_sentences': [],
        'verified_sentences': [],
        'summary': {}
    }
    
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue
        
        # 检测第一人称句
        if any(p in sent for p in E5_FIRST_PERSON):
            # 检查是否有可验证细节
            has_time = bool(re.search(r'\d{4}年|\d{1,2}月|\d{1,2}日|昨天|今天|上周|本月', sent))
            has_place = bool(re.search(r'在|北京|上海|广州|深圳|家里|公司|店里', sent))
            has_object = bool(re.search(r'用户|商家|客户|朋友|同事', sent))
            has_scene = bool(re.search(r'场景|任务|工作|使用|操作|打开', sent))
            
            if not (has_time or has_place or has_object or has_scene):
                results['suspicious_sentences'].append({
                    'sentence': sent[:60],
                    'line': i + 1,
                    'issue': '第一人称句无可验证细节',
                    'fix': '补充具体时间/地点/对象/场景描述，或删除第一人称'
                })
            else:
                results['verified_sentences'].append({
                    'sentence': sent[:60],
                    'line': i + 1
                })
    
    results['summary'] = {
        'status': 'PASS' if not results['suspicious_sentences'] else 'FAIL',
        'suspicious_count': len(results['suspicious_sentences']),
        'verified_count': len(results['verified_sentences']),
        'note': 'FAIL 项需退回昭断改写（删第一人称或补充可验证细节）'
    }
    return results


def check_title_number_consistency(article_text, title=None):
    """标题数字一致性检查（防止标题偏差）
    
    示例：标题「测 5 款」→ 正文实际测了 4 款 → FAIL
    """
    # 提取标题中的数字
    title_numbers = re.findall(r'(\d+)\s*[款个种套组]', title or '')
    # 提取正文中的数量词
    body_numbers = re.findall(r'(\d+)\s*[款个种套组台部]', article_text)
    
    # 简单对比：标题数字是否在正文数字中出现
    issues = []
    for tn in title_numbers:
        if tn not in body_numbers:
            issues.append(f'标题数字「{tn}」在正文中未找到对应')
    
    return {
        'title_numbers': title_numbers,
        'body_numbers': body_numbers,
        'issues': issues,
        'summary': {
            'status': 'PASS' if not issues else 'FAIL',
            'note': '标题数字与正文不一致，需秉裁裁定'
        }
    }


def check_absolute_words(article_text):
    """绝对化用语检测（扩展 E4）"""
    hits = [word for word in ABSOLUTE_WORDS if word in article_text]
    return {
        'hits': list(set(hits)),
        'summary': {
            'status': 'PASS' if not hits else 'WARN',
            'note': '绝对化用语需改为可验证表述'
        }
    }


def check_title_only(title, body_file=None):
    """标题专项检查（--title-check 专用）
    
    检测：字数、绝对化用语、数字一致性（如果提供正文）
    """
    results = {
        'title': title,
        'char_count': len(title),
        'issues': []
    }
    
    # 字数检测（小红书标题 ≤20 字）
    if len(title) > 20:
        results['issues'].append(f'标题过长（{len(title)} 字，建议 ≤20 字）')
    
    # 绝对化用语检测
    abs_hits = [w for w in ABSOLUTE_WORDS if w in title]
    if abs_hits:
        results['issues'].append(f'标题含绝对化用语：{abs_hits}')
    
    # 数字一致性（如果有正文文件）
    if body_file:
        try:
            with open(body_file) as f:
                body = f.read()
            title_numbers = re.findall(r'(\d+)\s*[款个种套组]', title)
            body_numbers = re.findall(r'(\d+)\s*[款个种套组台部]', body)
            for tn in title_numbers:
                if tn not in body_numbers:
                    results['issues'].append(f'标题数字「{tn}」与正文不一致')
        except FileNotFoundError:
            results['issues'].append(f'正文文件不存在：{body_file}')
    
    results['summary'] = {
        'status': 'PASS' if not results['issues'] else 'FAIL',
        'issues': results['issues']
    }
    return results


# ─── 主逻辑 ───────────────────────────────────────────────────────────────────

def run_gate(args):
    """门禁主执行器"""
    # 自动推断模式
    mode = 'evidence' if args.evidence else ('title' if args.title_check else ('article' if args.article else None))
    if not mode:
        print('错误：请指定 --evidence、--article 或 --title-check')
        return 1
    
    all_results = {
        'mode': mode,
        'file': args.evidence or args.article or args.title_check,
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'checks': {}
    }
    
    # ── 模式分支 ──
    if mode == 'evidence':
        # E 证据表模式：E1 格式 + E1-P 来源可追溯
        r = check_e1_evidence(args.evidence)
        all_results['checks']['E1'] = r
        rp = check_e1_provenance(args.evidence, args.article and open(args.article, encoding='utf-8').read())
        all_results['checks']['E1-P'] = rp
        stats = [r['summary']['status'], rp['summary']['status']]
        worst = 'FAIL' if 'FAIL' in stats else ('WARN' if 'WARN' in stats else 'PASS')
        all_results['summary'] = {
            'status': worst,
            'detail': 'E1：%s ｜ E1-P：%s' % (r['summary'].get('detail', ''), rp['summary']['detail']),
        }
    
    elif mode == 'title':
        # 标题专项检查模式
        r = check_title_only(args.title_check, args.body)
        all_results['checks']['标题检查'] = r
        all_results['summary'] = r['summary']
    
    elif mode == 'article':
        # E 文章审查模式：跑 E2-E5 + 标题检测
        with open(args.article) as f:
            text = f.read()
        
        # 提取标题（第一个 # 或 ## 后的内容）
        title_match = re.search(r'^#{1,2}\s*(.+)$', text, re.M)
        title = title_match.group(1).strip() if title_match else ''
        
        all_results['checks']['E2'] = check_e2_objective(text)
        all_results['checks']['E3'] = check_e3_disclosure(text)
        all_results['checks']['E4'] = check_e4_defamatory(text)
        all_results['checks']['E5'] = check_e5_ai_persona(text)
        all_results['checks']['标题一致性'] = check_title_number_consistency(text, title)
        all_results['checks']['绝对化用语'] = check_absolute_words(text)
        
        # 汇总
        fails = [k for k, v in all_results['checks'].items() if v['summary']['status'] == 'FAIL']
        warns = [k for k, v in all_results['checks'].items() if v['summary']['status'] == 'WARN']
        all_results['summary'] = {
            'status': 'FAIL' if fails else ('WARN' if warns else 'PASS'),
            'fails': fails,
            'warns': warns,
            'note': 'FAIL 项需修完再发；WARN 项建议优化'
        }
    
    # ── 输出 ──
    print('\n=== 门禁检测结果 ===\n')
    print(json.dumps(all_results['summary'], ensure_ascii=False, indent=2))
    
    if args.verbose:
        print('\n=== 详细检查结果 ===\n')
        for check_name, result in all_results['checks'].items():
            print(f'\n【{check_name}】')
            if 'entries' in result:
                for e in result['entries']:
                    status = '✅' if e['pass'] else '❌'
                    name = e['defect'][:40] + '...' if len(e['defect']) > 40 else e['defect']
                    print(f'  {status} {name}')
                    if e['issues']:
                        print(f'     问题：{", ".join(e["issues"])}')
            elif 'mixed_sentences' in result:
                if result['mixed_sentences']:
                    for ms in result['mixed_sentences']:
                        print(f'  ❌ 第 {ms["line"]} 句：{ms["sentence"][:50]}...')
                        print(f'     建议：{ms.get("fix", "拆分为主观句和客观句")}')
                else:
                    print(f'  ✅ 无主客观混写')
                if result['fix_suggestions']:
                    print(f'\n  💡 改写建议（共 {len(result["fix_suggestions"])} 条）:')
                    for fs in result['fix_suggestions'][:3]:  # 最多显示 3 条
                        print(f'     第 {fs["line"]} 行：{fs["fix"]}')
            elif 'keywords_found' in result:
                print(f'  状态：{result["summary"]["status"]}')
                print(f'  发现关键词：{result["keywords_found"] or "无"}')
                print(f'  前三行已披露：{result["keywords_in_first_lines"] or "否"}')
                print(f'  备注：{result["summary"]["note"]}')
            elif 'hard_hits' in result:
                if result['hard_hits']:
                    print(f'  ❌ 硬阻断词：{result["hard_hits"]}')
                if result['soft_hits']:
                    print(f'  ⚠️ 软警告词：{result["soft_hits"]}')
                print(f'  备注：{result["summary"]["note"]}')
            elif 'suspicious_sentences' in result:
                if result['suspicious_sentences']:
                    for ss in result['suspicious_sentences']:
                        print(f'  ❌ 第 {ss["line"]} 句：{ss["sentence"][:50]}...')
                        print(f'     问题：{ss["issue"]}')
                        print(f'     建议：{ss.get("fix", "补充可验证细节")}')
                else:
                    print(f'  ✅ 所有第一人称句均有可验证细节')
                print(f'  备注：{result["summary"]["note"]}')
            elif 'issues' in result and 'title_numbers' in result:
                if result['issues']:
                    for issue in result['issues']:
                        print(f'  ❌ {issue}')
                else:
                    print(f'  ✅ 标题数字与正文一致')
                print(f'  标题数字：{result["title_numbers"]}')
                print(f'  正文数字：{result["body_numbers"]}')
            elif 'hits' in result:
                if result['hits']:
                    print(f'  ⚠️ 绝对化用语：{result["hits"]}')
                else:
                    print(f'  ✅ 无绝对化用语')
            elif 'char_count' in result:
                # 标题专项检查输出
                print(f'  标题：「{result['title']}」')
                print(f'  字数：{result['char_count']} 字', end='')
                if result['char_count'] > 20:
                    print(f' ⚠️ 超 20 字限制')
                else:
                    print(' ✅')
                if result['issues']:
                    for issue in result['issues']:
                        print(f'  ❌ {issue}')
                else:
                    print(f'  ✅ 标题格式合规')
    
    # ── Checklist 模式 ──
    if args.checklist:
        print('\n=== Checklist 执行记录 ===\n')
        checklist_records = []
        
        # E1 检查
        if 'E1' in all_results['checks']:
            e1 = all_results['checks']['E1']
            status = e1['summary']['status']
            detail = e1['summary'].get('detail', '')
            checklist_records.append(f'S3-1 E1 实证表：{status}（{detail}）')
        
        # E2-E5 检查
        for check_name, result in all_results['checks'].items():
            if check_name in ['E2', 'E3', 'E4', 'E5']:
                status = result['summary']['status']
                checklist_records.append(f'S6-{["E2", "E3", "E4", "E5"].index(check_name) + 1} {check_name}门禁：{status}')
        
        for rec in checklist_records:
            print(f'  ✅ {rec}')
        
        print(f'\nChecklist 完成：{len(checklist_records)} 项已检查')
    
    # ── 最终判定 ──
    final_status = all_results['summary']['status']
    print(f'\n=== 门禁判定：{final_status} ===')
    if final_status == 'FAIL':
        print('❌ 有 FAIL 项，需修完再复检')
    elif final_status == 'WARN':
        print('⚠️ 有 WARN 项，建议优化后发布')
    else:
        print('✅ 全项通过，可进入下一环节')
    
    return 0 if final_status != 'FAIL' else 1


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='xhs-gate.py — 小红书团队 E 系列门禁脚本')
    parser.add_argument('--evidence', help='E1 证据表文件路径')
    parser.add_argument('--article', help='文章文件路径（跑 E2-E5）')
    parser.add_argument('--title-check', metavar='TITLE', help='标题专项检查（输入标题文本）')
    parser.add_argument('--body', metavar='FILE', help='与 --title-check 配合，提供正文文件路径')
    parser.add_argument('--verbose', action='store_true', help='输出详细检查结果')
    parser.add_argument('--checklist', action='store_true', help='输出 Checklist 执行记录')
    
    args = parser.parse_args()
    
    if not args.evidence and not args.article and not args.title_check:
        print('错误：请指定 --evidence、--article 或 --title-check')
        sys.exit(1)
    
    if args.title_check and not args.body:
        print('错误：--title-check 需配合 --body 指定正文文件')
        sys.exit(1)
    
    sys.exit(run_gate(args))
