#!/usr/bin/env python3
# Version: 0.1.0
"""
Minis Web Portal API Server
提供搜索、仪表盘、日报、GZH团队等 REST API 端点
"""
import json
import os
import sys
import re
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import subprocess
from pathlib import Path

SHARED_DIR = "/var/minis/shared"
MEMORY_DIR = "/var/minis/memory"
GZH_TEAM_DIR = f"{SHARED_DIR}/gzh-team"

class MinisHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass  # 静默日志
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        # API 端点
        if path == '/api/search':
            query = params.get('q', [''])[0]
            folder = params.get('folder', [None])[0]
            top = int(params.get('top', [10])[0])
            return self.handle_search(query, folder, top)
        
        elif path == '/api/dashboard':
            return self.handle_dashboard()
        
        elif path == '/api/daily-logs':
            limit = int(params.get('limit', [7])[0])
            return self.handle_daily_logs(limit)
        
        elif path == '/api/gzh-team':
            path_list = params.get('path', [''])[0].split('/')
            return self.handle_gzh_team(path_list)
        
        elif path == '/api/obsidian-folders':
            return self.handle_obsidian_folders()
        
        elif path == '/api/skills':
            return self.handle_skills()

        elif path == '/api/scheduler-catchup':
            return self.handle_scheduler_catchup()
        
        # 静态文件 — 统一从 shared/ 目录提供
        if path == '/':
            return self.serve_file('index.html')
        
        # 尝试从 shared/ 目录直接提供文件
        rel_path = path.lstrip('/')
        if rel_path:
            return self.serve_file(rel_path)
    
    def handle_search(self, query, folder, top):
        """执行 Obsidian 搜索"""
        if not query:
            return self.send_json({'error': '请输入搜索关键词', 'results': []})
        
        # URL decode query
        try:
            query = query.encode('latin-1').decode('utf-8')
        except:
            pass
        
        cmd = ['python3', '/var/minis/shared/obsidian-search.py', '--query', query, '--top', str(top), '--json']
        if folder:
            cmd.extend(['--folder', folder])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return self.send_json(data)
            else:
                return self.send_json({'error': result.stderr, 'results': []})
        except Exception as e:
            return self.send_json({'error': str(e), 'results': []})
    
    def handle_dashboard(self):
        """返回系统健康数据"""
        # 记忆系统
        memory_count = len(list(Path(MEMORY_DIR).glob('2026-*.md')))
        has_l2 = os.path.exists(f"{MEMORY_DIR}/L2-weekly-summaries.md")
        has_l3 = os.path.exists(f"{MEMORY_DIR}/L3-knowledge-graph.md")
        has_global = os.path.exists(f"{MEMORY_DIR}/GLOBAL.md")
        has_soul = os.path.exists(f"{MEMORY_DIR}/SOUL.md")
        
        # 工作区
        ws_files = list(Path('/var/minis/workspace').glob('**/*')) if Path('/var/minis/workspace').exists() else []
        ws_count = sum(1 for f in ws_files if f.is_file())
        
        # 共享区
        shared_files = list(Path(SHARED_DIR).glob('**/*')) if Path(SHARED_DIR).exists() else []
        shared_count = sum(1 for f in shared_files if f.is_file())
        
        # Skill 系统
        skills_dir = Path('/var/minis/skills')
        skill_count = 0
        if skills_dir.exists():
            skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir() and (d / 'SKILL.md').exists())
        
        # 隧道状态（不调用子进程，避免阻塞）
        tunnel_status = 'online'  # 如果能访问到这里，隧道就是在线的
        
        return self.send_json({
            'memory': {
                'daily_logs': memory_count,
                'l2_weekly': '✅' if has_l2 else '❌',
                'l3_graph': '✅' if has_l3 else '❌',
                'global': '✅' if has_global else '❌',
                'soul': '✅' if has_soul else '❌'
            },
            'workspace': {
                'status': '✅' if ws_count > 0 else '⚠️ 为空',
                'file_count': ws_count
            },
            'shared': {
                'file_count': shared_count,
                'size_mb': round(shared_count * 5 / 1024, 1)  # 估算
            },
            'skills': {
                'count': skill_count
            },
            'tunnel': {
                'status': tunnel_status,
                'url': 'https://minis.maquer.eu.org'
            },
            'timestamp': datetime.now().isoformat()
        })
    
    def handle_daily_logs(self, limit):
        """返回最近的 daily logs"""
        logs = []
        mem_dir = Path(MEMORY_DIR)
        
        for f in mem_dir.glob('2026-*.md'):
            try:
                stat = f.stat()
                with open(f, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                    # 提取日期（文件名本身就是日期）
                    date = f.stem  # e.g. 2026-09-25
                    # 提取第一段有意义的内容
                    lines = content.split('\n')
                    preview = ''
                    for line in lines:
                        line = line.strip()
                        # 跳过 HTML 注释和空行
                        if line.startswith('<!--') or line.startswith('-->') or not line:
                            continue
                        # 找到第一个标题或内容行
                        preview = line[:200]
                        break
                
                logs.append({
                    'filename': f.name,
                    'date': date,
                    'content_preview': preview,
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except:
                pass
        
        logs.sort(key=lambda x: x['date'], reverse=True)
        return self.send_json({'logs': logs[:limit], 'total': len(logs)})
    
    def handle_gzh_team(self, path_list):
        """返回 GZH 团队目录结构"""
        base = Path(GZH_TEAM_DIR)
        current = base
        
        for part in path_list:
            if part:
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
    
    def handle_obsidian_folders(self):
        """返回 Obsidian 目录结构"""
        vault_dir = Path('/var/minis/mounts/loong')
        if not vault_dir.exists():
            return self.send_json({'error': 'Obsidian vault 未挂载'})
        
        folders = []
        for item in sorted(vault_dir.iterdir()):
            if item.is_dir():
                count = sum(1 for _ in item.rglob('*.md'))
                folders.append({
                    'name': item.name,
                    'path': str(item.relative_to(vault_dir)),
                    'note_count': count
                })
        
        return self.send_json({'folders': folders})
    
    def handle_scheduler_catchup(self):
        """触发 countdown-scheduler check --catchup（由 Apple Shortcuts 调用）"""
        import tempfile, shlex
        # 后台运行，不阻塞 HTTP 响应
        log_dir = "/var/minis/shared/.scheduler/logs"
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = os.path.join(log_dir, f"shortcut-catchup-{ts}.log")
        cmd = ["python3", "/var/minis/shared/countdown-scheduler.py", "check", "--catchup"]
        try:
            with open(log_file, "w") as lf:
                proc = subprocess.Popen(
                    cmd, stdout=lf, stderr=subprocess.STDOUT, text=True
                )
            return self.send_json({
                "status": "started",
                "pid": proc.pid,
                "log": log_file,
                "message": f"catchup 已启动 (pid={proc.pid})，结果写入 {log_file}"
            })
        except Exception as e:
            return self.send_json({"status": "error", "error": str(e)}, 500)

    def handle_skills(self):
        """返回 Skill 列表"""
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
                
                with open(skill_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 提取基本信息
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
    
    def serve_file(self, filename):
        """提供 HTML 或任意静态文件"""
        try:
            # 安全检查：防止路径穿越
            filepath = os.path.normpath(os.path.join(SHARED_DIR, filename))
            if not filepath.startswith(SHARED_DIR):
                self.send_json({'error': '非法路径'}, 403)
                return
            
            if not os.path.isfile(filepath):
                self.send_json({'error': '文件不存在'}, 404)
                return
            
            # 根据扩展名设置 Content-Type
            ext = os.path.splitext(filepath)[1].lower()
            ct = {
                '.html': 'text/html; charset=utf-8',
                '.css': 'text/css; charset=utf-8',
                '.js': 'application/javascript',
                '.json': 'application/json',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml',
                '.md': 'text/markdown; charset=utf-8',
                '.txt': 'text/plain; charset=utf-8',
            }.get(ext, 'application/octet-stream')
            
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def serve_file_static(self, filepath):
        """提供静态文件"""
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_json({'error': '文件不存在'}, 404)


def main():
    port = int(os.environ.get('PORT', 8765))
    server = ThreadingHTTPServer(('0.0.0.0', port), MinisHandler)
    print(f'Minis Web Portal running on 0.0.0.0:{port}', flush=True)
    print(f'Open https://minis.maquer.eu.org to access the portal', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
