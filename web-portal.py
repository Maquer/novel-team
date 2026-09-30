#!/usr/bin/env python3
# Version: 0.1.0
"""
Minis Web Portal - 稳定版
使用 SimpleHTTPRequestHandler + API 路由
"""
import json, os, sys, re, subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path

SHARED_DIR = "/var/minis/shared"
MEMORY_DIR = "/var/minis/memory"
GZH_TEAM_DIR = f"{SHARED_DIR}/gzh-team"
API_PREFIX = "/api/"

class PortalHandler(SimpleHTTPRequestHandler):
    """基于 SimpleHTTPRequestHandler 的门户服务器"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SHARED_DIR, **kwargs)
    
    def log_message(self, format, *args):
        pass  # 静默
    
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API 路由
        if path == '/api/dashboard':
            return self.api_dashboard()
        elif path == '/api/search':
            return self.api_search(parsed)
        elif path == '/api/daily-logs':
            return self.api_daily_logs(parsed)
        elif path == '/api/gzh-team':
            return self.api_gzh_team(parsed)
        elif path == '/api/skills':
            return self.api_skills()
        elif path == '/api/health':
            return self.send_json({'status': 'ok', 'time': datetime.now().isoformat()})
        
        # 静态文件 — 交给父类
        return super().do_GET()
    
    def api_dashboard(self):
        try:
            mem_dir = Path(MEMORY_DIR)
            logs = list(mem_dir.glob('2026-*.md'))
            has_l2 = (mem_dir / 'L2-weekly-summaries.md').exists()
            has_l3 = (mem_dir / 'L3-knowledge-graph.md').exists()
            has_global = (mem_dir / 'GLOBAL.md').exists()
            has_soul = (mem_dir / 'SOUL.md').exists()
            
            ws = Path('/var/minis/workspace')
            ws_count = len(list(ws.iterdir())) if ws.exists() else 0
            
            shared = Path(SHARED_DIR)
            shared_count = len(list(shared.iterdir())) if shared.exists() else 0
            
            skills_dir = Path('/var/minis/skills')
            skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir() and (d / 'SKILL.md').exists()) if skills_dir.exists() else 0
            
            return self.send_json({
                'memory': {'daily_logs': len(logs), 'l2_weekly': '✅' if has_l2 else '❌',
                           'l3_graph': '✅' if has_l3 else '❌', 'global': '✅' if has_global else '❌',
                           'soul': '✅' if has_soul else '❌'},
                'workspace': {'status': '✅' if ws_count > 0 else '⚠️ 为空', 'file_count': ws_count},
                'shared': {'file_count': shared_count, 'size_mb': round(shared_count * 5 / 1024, 1)},
                'skills': {'count': skill_count},
                'tunnel': {'status': 'online', 'url': 'https://minis.maquer.eu.org'},
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
    
    def api_search(self, parsed):
        params = parse_qs(parsed.query)
        query = params.get('q', [''])[0]
        folder = params.get('folder', [None])[0]
        top = int(params.get('top', [10])[0])
        
        if not query:
            return self.send_json({'error': '请输入搜索关键词', 'results': []})
        
        # URL decode
        try:
            query = query.encode('latin-1').decode('utf-8')
        except:
            pass
        
        cmd = ['python3', '/var/minis/shared/obsidian-search.py', '--query', query, '--top', str(top), '--json']
        if folder:
            cmd.extend(['--folder', folder])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                return self.send_json(json.loads(result.stdout))
            else:
                return self.send_json({'error': result.stderr[:500], 'results': []})
        except subprocess.TimeoutExpired:
            return self.send_json({'error': '搜索超时，请尝试更简单的关键词', 'results': []})
        except Exception as e:
            return self.send_json({'error': str(e), 'results': []})
    
    def api_daily_logs(self, parsed):
        params = parse_qs(parsed.query)
        limit = int(params.get('limit', [7])[0])
        
        logs = []
        mem_dir = Path(MEMORY_DIR)
        for f in mem_dir.glob('2026-*.md'):
            try:
                stat = f.stat()
                with open(f, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                lines = content.split('\n')
                preview = ''
                for line in lines:
                    line = line.strip()
                    if line.startswith('<!--') or line.startswith('-->') or not line:
                        continue
                    preview = line[:200]
                    break
                logs.append({
                    'filename': f.name,
                    'date': f.stem,
                    'content_preview': preview,
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except:
                pass
        
        logs.sort(key=lambda x: x['date'], reverse=True)
        return self.send_json({'logs': logs[:limit], 'total': len(logs)})
    
    def api_gzh_team(self, parsed):
        params = parse_qs(parsed.query)
        path_str = params.get('path', [''])[0]
        path_list = [p for p in path_str.split('/') if p]
        
        base = Path(GZH_TEAM_DIR)
        current = base
        for part in path_list:
            current = current / part
        
        if not current.exists():
            return self.send_json({'error': '路径不存在'}, 404)
        
        if current.is_file():
            with open(current, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.send_json({'type': 'file', 'path': str(current), 'content': content})
        
        items = []
        for item in sorted(current.iterdir()):
            if item.is_dir():
                item_type = 'directory'
            elif item.suffix in ['.md', '.html']:
                item_type = 'document'
            else:
                item_type = 'other'
            items.append({
                'name': item.name,
                'type': item_type,
                'is_dir': item.is_dir(),
                'size': item.stat().st_size if item.is_file() else None
            })
        
        return self.send_json({'type': 'directory', 'path': str(current), 'items': items})
    
    def api_skills(self):
        skills = []
        skills_dir = Path('/var/minis/skills')
        for d in sorted(skills_dir.iterdir()):
            skill_file = d / 'SKILL.md'
            if skill_file.exists():
                meta_file = d / 'skill.meta.json'
                meta = {}
                if meta_file.exists():
                    try:
                        with open(meta_file, 'r') as f:
                            meta = json.load(f)
                    except:
                        pass
                name = meta.get('name', d.name)
                triggers = meta.get('triggers', [])
                skills.append({
                    'name': d.name,
                    'display_name': name,
                    'triggers': triggers,
                    'path': str(d.relative_to(Path('/var/minis'))),
                    'size': skill_file.stat().st_size
                })
        return self.send_json({'skills': skills})


def main():
    port = int(os.environ.get('PORT', 8765))
    server = ThreadingHTTPServer(('0.0.0.0', port), PortalHandler)
    print(f'Minis Web Portal on 0.0.0.0:{port}', flush=True)
    print('URL: https://minis.maquer.eu.org', flush=True)
    server.serve_forever()

if __name__ == '__main__':
    main()
