#!/usr/bin/env python3
# Version: 0.1.0
"""Fetch a file from a GitHub repo via API (raw.githubusercontent is blocked).
Usage: python3 ghf.py <owner>/<repo>/<path>[@ref]"""
import sys, json, base64, urllib.request
path = sys.argv[1]
if '@' in path and path.index('@') > path.rfind('/') + 1:
    parts = path.rsplit('@', 1)
    path, ref = parts[0], parts[1]
else:
    ref = 'main'
url = f"https://api.github.com/repos/{path.rsplit('/',1)[0]}/contents/{path.rsplit('/',1)[1]}"
# simpler: split repo/path
slash = path.find('/')
owner_repo, rel = path[:slash+1], path[slash+1:]
# wrong split; do properly
import re
m = re.match(r'^([\w.-]+)/([\w.-]+)/(.+)$', path)
if not m: sys.exit("bad path")
owner, repo, rel = m.groups()
url = f"https://api.github.com/repos/{owner}/{repo}/contents/{rel}?ref={ref}"
req = urllib.request.Request(url, headers={'Accept':'application/vnd.github+json','User-Agent':'minis'})
try:
    r = urllib.request.urlopen(req, timeout=30).read()
    d = json.loads(r)
    print(base64.b64decode(d['content']).decode())
except Exception as e:
    print(f"ERROR {e}", file=sys.stderr); sys.exit(1)
