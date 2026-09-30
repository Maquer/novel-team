#!/usr/bin/env python3
"""最终部署：worker 内直接调 KV API 实现视图计数（Pages 新版不再从 bundle 应用 KV 绑定）
- /api/categories: 从文章派生（去重 + 计数）
- /api/articles: 列表 + 实时视图数
- /api/articles/:slug: 单篇 + 视图数 +1
"""
import json, os, base64, hashlib, urllib.request, urllib.error

TOKEN = os.environ['CLOUDFLARE_API_TOKEN']
ACCT = '6ddb238e2db8f43a4e974040d1437c2f'
KV_ID = '7c781ffaf51147e09d71b3f9ee4c9b3c'
BASE = f'https://api.cloudflare.com/client/v4/accounts/{ACCT}'
import os as _os
_ws_dir = '/var/minis/workspace/personal-blog/deploy'
_sh_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'deploy')
DIR = _ws_dir if _os.path.isdir(_ws_dir) else _sh_dir

data = json.load(open(f'{DIR}/functions-data.json'))

worker_code = '''// personal-blog Pages Functions（最终版）
// 视图计数：worker 内直连 Cloudflare KV API（Pages 新版不再从 bundle 应用 KV 绑定）
const data = %s;
const articles = data.articles;

const KV_BASE = 'https://api.cloudflare.com/client/v4/accounts/%s/storage/kv/namespaces/%s/values/';
const KV_TOKEN = '%s';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
    },
  });
}

async function kvGet(slug) {
  try {
    const r = await fetch(KV_BASE + 'views:' + encodeURIComponent(slug), {
      headers: { Authorization: 'Bearer ' + KV_TOKEN },
    });
    if (!r.ok) return 0;
    const v = await r.text();
    return v ? parseInt(v, 10) || 0 : 0;
  } catch {
    return 0;
  }
}

async function kvInc(slug) {
  try {
    const cur = await kvGet(slug);
    const next = cur + 1;
    await fetch(KV_BASE + 'views:' + encodeURIComponent(slug), {
      method: 'PUT',
      headers: { Authorization: 'Bearer ' + KV_TOKEN, 'Content-Type': 'text/plain' },
      body: String(next),
    });
    return next;
  } catch {
    return 0;
  }
}

// 路由
async function handleCategories(env) {
  const map = new Map();
  for (const a of articles) {
    map.set(a.category, (map.get(a.category) || 0) + 1);
  }
  return json([...map.keys()].sort());
}

async function handleArticles(env, limit, category) {
  let list = sortedArticles();
  if (category) list = list.filter((a) => a.category === category);
  if (limit > 0) list = list.slice(0, limit);
  const out = [];
  for (const a of list) {
    out.push({ ...a, views: await kvGet(a.slug) });
  }
  return json({ data: out });
}

async function handleArticle(env, slug) {
  const article = articles.find((a) => a.slug === slug);
  if (!article) return json({ error: 'not found' }, 404);
  const views = await kvInc(slug);
  return json({ ...article, views });
}

function sortedArticles() {
  return [...articles].sort((a, b) => (a.date < b.date ? 1 : -1));
}

async function handleRecent(env, limit) {
  const out = [];
  for (const a of sortedArticles().slice(0, limit)) {
    out.push({ ...a, views: await kvGet(a.slug) });
  }
  return json(out);
}

function matchRoute(url) {
  const segs = url.pathname.split('/');
  if (segs[1] === 'api') {
    if (segs.length === 3 && segs[2] === 'categories') return { h: handleCategories };
    if (segs.length === 3 && segs[2] === 'articles') {
      const limit = parseInt(url.searchParams.get('limit') || '0', 10) || 0;
      const category = url.searchParams.get('category');
      return { h: (env) => handleArticles(env, limit, category) };
    }
    if (segs.length === 4 && segs[2] === 'articles') {
      if (segs[3] === 'recent') return { h: (env) => handleRecent(env, 3) };
      return { h: (env) => handleArticle(env, decodeURIComponent(segs[3])) };
    }
  }
  return null;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) {
      const m = matchRoute(url);
      if (m) return m.h(env);
      return json({ error: 'not found' }, 404);
    }
    return env.ASSETS.fetch(request);
  },
};
''' % (
    json.dumps(data, ensure_ascii=False, indent=1),
    ACCT,
    KV_ID,
    TOKEN,
)

# 语法自检
import subprocess
with open('/tmp/final-worker.mjs', 'w') as f:
    f.write(worker_code)
r = subprocess.run(['node', '--input-type=module', '-e',
                    'import("file:///tmp/final-worker.mjs").then(m=>console.log("ESM OK:",typeof m.default)).catch(e=>{console.error("PARSE FAIL:",e.message);process.exit(1)})'],
                   capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip()[-400:])
if r.returncode != 0:
    raise SystemExit(1)


def api(method, path, body=None, raw_body=None, ct=None, jwt=None):
    h = {'Authorization': f'Bearer {jwt or TOKEN}'}
    data_b = None
    if body is not None:
        data_b = json.dumps(body).encode()
        h['Content-Type'] = 'application/json'
    if raw_body is not None:
        data_b = raw_body
        h['Content-Type'] = ct
    req = urllib.request.Request(BASE + path, data=data_b, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ---------- 资产已在 dedupe 存储（首次已上传），直接部署 ----------
files = {
    '/index.html': f'{DIR}/index.html',
    '/articles.html': f'{DIR}/articles.html',
    '/article.html': f'{DIR}/article.html',
    '/about.html': f'{DIR}/about.html',
    '/css/style.css': f'{DIR}/css/style.css',
    '/js/app.js': f'{DIR}/js/app.js',
}
manifest = {}
for path, fp in files.items():
    b = open(fp, 'rb').read()
    ext = path.rsplit('.', 1)[-1]
    manifest[path] = hashlib.sha256(base64.b64encode(b) + ext.encode()).hexdigest()[:32]

# ---------- 部署 ----------
B = 'finalblog2026'
inner = (f'--{B}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
         + json.dumps({'main_module': '_worker.mjs', 'bindings': [],
                       'compatibility_date': '2025-01-01', 'compatibility_flags': ['nodejs_compat']})
         + f'\r\n--{B}\r\nContent-Disposition: form-data; name="_worker.mjs"; filename="_worker.mjs"\r\n'
           f'Content-Type: application/javascript+module\r\n\r\n' + worker_code + f'\r\n--{B}--\r\n')
outer_B = 'outerfinal'
outer = (f'--{outer_B}\r\nContent-Disposition: form-data; name="manifest"\r\n\r\n' + json.dumps(manifest) + '\r\n'
         f'--{outer_B}\r\nContent-Disposition: form-data; name="branch"\r\n\r\nmain\r\n'
         f'--{outer_B}\r\nContent-Disposition: form-data; name="_worker.bundle"; filename="_worker.bundle"\r\n\r\n'
         + inner + f'--{outer_B}\r\nContent-Disposition: form-data; name="_routes.json"; filename="_routes.json"\r\n'
                   f'Content-Type: application/json\r\n\r\n' + json.dumps({"version": 1, "include": ["/api/*"], "exclude": []})
         + f'\r\n--{outer_B}--\r\n')
body = outer.encode()

st, out = api('POST', '/pages/projects/personal-blog/deployments', raw_body=body,
              ct=f'multipart/form-data; boundary={outer_B}')
d = json.loads(out)
dep = d.get('result', {})
print('deploy:', st, dep.get('id', json.dumps(d.get('errors'), ensure_ascii=False)[:300]))
with open('/tmp/final-deploy-id.txt', 'w') as f:
    f.write(dep.get('id', ''))
