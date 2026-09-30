#!/usr/bin/env python3
# Version: 0.1.0
"""
公众号 Web API 直推草稿箱工具 — gzh-api-push.py
==============================================
用 AppID + AppSecret 调公众号接口，实现：获取 token → 上传图片 → 推送草稿 → 读/改草稿。

环境配置（在 Minis 设置 → 环境变量 中配置）：
  WX_APPID      — 公众号 AppID（后台「设置与开发 → 基本配置」）
  WX_APPSECRET  — 公众号 AppSecret（同上，重置生成，只显示一次）

用法：
  # 测试连通性（获取 access_token）
  python3 gzh-api-push.py token

  # 上传图片到永久素材库
  python3 gzh-api-push.py upload --file /path/to/image.jpg

  # 推送草稿（从 HTML 文件创建草稿）
  python3 gzh-api-push.py push --file content.html --title "标题" --thumb /path/to/cover.jpg   # thumb 支持 media_id 或图片路径（路径自动上传）

  # 读取草稿
  python3 gzh-api-push.py get-draft --id 草稿id

  # 更新草稿（整篇覆盖，必须先读后写）
  python3 gzh-api-push.py update --id 草稿id --file content.html --title "标题"

卡点处理（对应大鸭实录 6 个坑）：
  1. AppSecret 只显示一次 — 用环境变量存储，工具不打印
  2. 40164 IP 白名单 / 48001 未认证 — token 步骤自动检测
  3. CRLF 换行符 — 读取 HTML 时自动转换
  4. 读草稿必须 POST — 工具统一用 POST
  5. 改草稿整篇覆盖 — update 步骤必须先 get-draft
  6. 标题 64 字符上限 — 工具自动截断
"""

import os, sys, json, re, mimetypes, urllib.request, urllib.error

# ─── 配置 ────────────────────────────────────────────
APPID = os.environ.get('WX_APPID', '')
APPSECRET = os.environ.get('WX_APPSECRET', '')
MAX_TITLE_LEN = 64  # 标题最大 64 字符（约 21 个汉字）
# draft/get 返回的字段远多于 draft/update 接受的范围。整篇覆盖若原样写回，
# 会因 err_code/fail/url/content_url 等只读字段触发 errcode 47001 data format error。
# 这里只放行官方文档确认可写的字段，其余丢弃。
DRAFT_UPDATE_FIELDS = (
    'title', 'author', 'digest', 'content', 'thumb_media_id',
    'content_source_url', 'pic_urls', 'pic_url', 'pic_crop_original',
    'need_open_comment', 'only_fans_can_comment',
    'need_font_fill', 'font_fill', 'show_cover',
    'need_auto_teach_related_tag', 'need_auto_read_news',
    'is_custom_title', 'is_talent_select',
    'item_show_type', 'item_link_type',
)


# ─── HTTP 基础 ────────────────────────────────────────
def _request(url, data=None, headers=None):
    """统一 HTTP 请求"""
    req_headers = {'User-Agent': 'Minis-GZH-API/1.0'}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {'err': 'HTTPError', 'code': e.code, 'body': body}


def _multipart_boundary():
    """生成 multipart 边界"""
    return '----MinisGZH' + os.urandom(8).hex()


def _build_multipart(fields, files):
    """
    构造 multipart/form-data 请求体
    fields: [(name, value), ...]
    files:  [(name, file_path), ...]
    """
    boundary = _multipart_boundary()
    parts = []
    for name, value in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')
    for name, file_path in files:
        with open(file_path, 'rb') as f:
            content = f.read()
        mime = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{os.path.basename(file_path)}"\r\nContent-Type: {mime}\r\n\r\n')
        parts.append(content.decode('latin-1') if isinstance(content, bytes) else content)
        parts.append('\r\n')
    parts.append(f'--{boundary}--\r\n')
    # 注意：decode('latin-1') 对应的编码必须是 latin-1（1:1 映射），
    # 用 utf-8 会导致二进制图片数据损坏，微信返回 40113 unsupported file type
    body = ''.join(str(p) for p in parts).encode('latin-1')
    headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
    return body, headers


# ─── API 调用 ─────────────────────────────────────────
def api_get(url):
    return _request(url)


def api_post_json(url, data):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    return _request(url, body, {'Content-Type': 'application/json'})


def api_post_file(url, fields, files):
    body, headers = _build_multipart(fields, files)
    return _request(url, body, headers)


# ─── 命令实现 ─────────────────────────────────────────
def cmd_token(args=None):
    """获取 access_token — 同时检测 40164/48001 错误"""
    if not APPID or not APPSECRET:
        print("❌ 缺少 WX_APPID 或 WX_APPSECRET 环境变量")
        print("   请在 Minis 设置 → 环境变量 中配置")
        sys.exit(1)
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}"
    resp = api_get(url)
    if 'access_token' in resp:
        print(json.dumps({'status': 'ok', 'access_token': resp['access_token'], 'expires_in': resp.get('expires_in', 7200)}, ensure_ascii=False, indent=2))
    else:
        errcode = resp.get('errcode', -1)
        errmsg = resp.get('errmsg', '')
        if errcode == 40164:
            print(f"❌ 错误 {errcode}: IP 不在白名单")
            print(f"   请前往「基本配置 → IP 白名单」，添加当前服务器 IP")
            print(f"   详细信息: {errmsg}")
        elif errcode == 48001:
            print(f"❌ 错误 {errcode}: 公众号未认证")
            print(f"   个人订阅号无法使用 API，请先完成认证")
            print(f"   详细信息: {errmsg}")
        else:
            print(f"❌ 获取 token 失败: {json.dumps(resp, ensure_ascii=False)}")
        sys.exit(1)


def cmd_upload(args):
    """上传图片到永久素材库"""
    token_resp = cmd_token_get()
    token = token_resp['access_token']
    file_path = args.get('--file')
    if not file_path:
        print("❌ 缺少 --file 参数", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(file_path):
        print(f"❌ 文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
    resp = api_post_file(url, fields=[], files=[('media', file_path)])
    if 'media_id' in resp:
        print(f"✅ 图片上传成功")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return resp
    print(f"❌ 图片上传失败: {json.dumps(resp, ensure_ascii=False)}", file=sys.stderr)
    sys.exit(1)


def cmd_push(args):
    """推送草稿到草稿箱"""
    token = cmd_token_get()['access_token']
    html_file = args.get('--file')
    if not html_file:
        print("❌ 缺少 --file 参数（HTML 文件路径）")
        sys.exit(1)
    if not os.path.isfile(html_file):
        print(f"❌ 文件不存在: {html_file}")
        sys.exit(1)

    # 卡点 3：CRLF 换行符 → 自动转换
    with open(html_file, 'rb') as f:
        raw = f.read()
    content = raw.decode('utf-8-sig')
    content = content.replace('\r\n', '\n')

    # 提取正文内容（去掉 <html><head> 包装，只保留 body 内容）
    body = extract_body(content)
    # 清洗：移除 <h1> 标题和末尾 --- 分割线
    body = clean_body(body)
    if not body:
        print("❌ 无法从 HTML 中提取正文内容")
        sys.exit(1)

    title = args.get('--title', '')
    if title:
        title = title[:MAX_TITLE_LEN]  # 卡点 6：标题上限
    else:
        title = extract_title(content)[:MAX_TITLE_LEN]

    author = args.get('--author', '')
    digest = args.get('--digest', '')
    if not digest:
        digest = extract_body_text(body, 100)

    thumb_media_id = args.get('--thumb', '')

    # 卡点 1 补强：--thumb 传的是文件路径时自动 upload 拿 media_id
    if thumb_media_id and (thumb_media_id.endswith(('.jpg','.jpeg','.png','.webp','.gif','.JPG','.JPEG','.PNG','.WEBP','.GIF'))
        or os.path.isfile(thumb_media_id)):
        print(f"   --thumb 是文件路径，自动上传拿 media_id …")
        up_args = {'--file': thumb_media_id}
        up = cmd_upload(up_args)
        thumb_media_id = up.get('media_id','')
        if not thumb_media_id:
            print("❌ 封面自动上传失败，请手动 upload 后重推")
            sys.exit(1)
        print(f"   封面 media_id: {thumb_media_id}")

    article = {
        "title": title,
        "content": body,
    }
    if author:
        article["author"] = author
    if digest:
        article["digest"] = digest
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    data = {"articles": [article]}
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    resp = api_post_json(url, data)
    if 'media_id' in resp:
        print(f"✅ 草稿推送成功")
        print(f"   草稿 ID: {resp['media_id']}")
        print(f"   标题: {title}")
    else:
        print(f"❌ 草稿推送失败: {json.dumps(resp, ensure_ascii=False)}")
        sys.exit(1)


def cmd_get_draft(args):
    """读取草稿（必须用 POST — 卡点 4）"""
    token = cmd_token_get()['access_token']
    draft_id = args.get('--id')
    if not draft_id:
        print("❌ 缺少 --id 参数（草稿 media_id）")
        sys.exit(1)
    data = {"media_id": draft_id}
    url = f"https://api.weixin.qq.com/cgi-bin/draft/get?access_token={token}"
    resp = api_post_json(url, data)
    if 'news_item' in resp or 'articles' in resp:
        print(f"✅ 读取草稿成功")
        items = resp.get('news_item') or resp.get('articles', [])
        for i, item in enumerate(items):
            print(f"  [{i}] 标题: {item.get('title', '')}")
            print(f"       作者: {item.get('author', '')}")
            print(f"       摘要: {item.get('digest', '')}")
            print(f"       字数: {len(item.get('content', ''))}")
            if item.get('thumb_media_id'):
                print(f"       封面: {item['thumb_media_id']}")
    else:
        print(f"❌ 读取草稿失败: {json.dumps(resp, ensure_ascii=False)}")
        sys.exit(1)


def cmd_update(args):
    """更新草稿 — 整篇覆盖（卡点 5），必须先 get-draft 再 update"""
    token = cmd_token_get()['access_token']
    draft_id = args.get('--id')
    if not draft_id:
        print("❌ 缺少 --id 参数")
        sys.exit(1)

    # 先读取原草稿
    print("→ 读取原草稿...")
    data = {"media_id": draft_id}
    url_get = f"https://api.weixin.qq.com/cgi-bin/draft/get?access_token={token}"
    orig = api_post_json(url_get, data)

    orig_items = orig.get('news_item') or orig.get('articles', [])
    if not orig_items:
        print(f"❌ 读取原草稿失败: {json.dumps(orig, ensure_ascii=False)}")
        sys.exit(1)

    # 只保留 draft/update 可写字段，避免把 draft/get 的只读字段写回触发 47001
    original = {k: v for k, v in orig_items[0].items() if k in DRAFT_UPDATE_FIELDS}

    html_file = args.get('--file')
    if html_file and os.path.isfile(html_file):
        with open(html_file, 'rb') as f:
            raw = f.read()
        content = raw.decode('utf-8-sig').replace('\r\n', '\n')
        body = extract_body(content)
        if body:
            original['content'] = body

    if args.get('--title'):
        original['title'] = args['--title'][:MAX_TITLE_LEN]
    if args.get('--author'):
        original['author'] = args['--author']
    if args.get('--digest'):
        original['digest'] = args['--digest']
    if args.get('--thumb'):
        original['thumb_media_id'] = args['--thumb']

    # 确保 thumb_media_id 存在（公众号要求）
    if 'thumb_media_id' not in original:
        print("⚠️ 草稿缺少 thumb_media_id，更新可能失败")

    update_data = {"media_id": draft_id, "articles": [original]}
    url_update = f"https://api.weixin.qq.com/cgi-bin/draft/update?access_token={token}"
    resp = api_post_json(url_update, update_data)
    if resp.get('errcode', -1) == 0:
        print(f"✅ 草稿更新成功: {draft_id}")
    else:
        print(f"❌ 草稿更新失败: {json.dumps(resp, ensure_ascii=False)}")
        sys.exit(1)


# ─── 辅助函数 ─────────────────────────────────────────
def cmd_token_get():
    """获取 token（静默版，不打印）"""
    if not APPID or not APPSECRET:
        print("❌ 缺少 WX_APPID 或 WX_APPSECRET 环境变量")
        sys.exit(1)
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}"
    resp = api_get(url)
    if 'access_token' not in resp:
        errcode = resp.get('errcode', -1)
        if errcode == 40164:
            print("❌ IP 不在白名单，请添加")
        elif errcode == 48001:
            print("❌ 公众号未认证")
        else:
            print(f"❌ token 失败: {json.dumps(resp, ensure_ascii=False)}")
        sys.exit(1)
    return resp


def extract_body(html):
    """从完整 HTML 中提取 <body> 内容"""
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # 没有 <body> 标签，返回原文
    return html.strip()


def clean_body(body):
    """推送前清洗：移除 <h1> 标题（文章标题已通过 --title 指定）和末尾 --- 分割线"""
    # 移除 <h1> 标题
    body = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', body, flags=re.DOTALL | re.IGNORECASE)
    # 移除末尾 <p>---</p> 分割线
    body = re.sub(r'<p>\s*---+\s*</p>\s*$', '', body, flags=re.DOTALL | re.IGNORECASE)
    # 移除纯文本 --- 分割线（如果有的话）
    body = re.sub(r'\n---\s*$', '', body)
    return body.strip()


def extract_title(html):
    """从 HTML 中提取 <title> 或 <h1> 内容"""
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return ''


def extract_body_text(html, max_len=100):
    """提取 HTML 纯文本，截断到 max_len"""
    text = re.sub(r'<[^>]+>', '', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


# ─── CLI 入口 ─────────────────────────────────────────
def parse_args(argv):
    args = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith('--'):
            key = argv[i]
            if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                args[key] = argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            args.setdefault('_positional', []).append(argv[i])
            i += 1
    return args


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('--help', '-h', 'help'):
        print(__doc__)
        print("\n可用命令: token / upload / push / get-draft / update")
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    cmd = sys.argv[1]
    args = parse_args(sys.argv[2:])

    commands = {
        'token': cmd_token,
        'upload': cmd_upload,
        'push': cmd_push,
        'get-draft': cmd_get_draft,
        'update': cmd_update,
    }

    handler = commands.get(cmd)
    if handler:
        handler(args)
    else:
        print(f"❌ 未知命令: {cmd}")
        print(f"   可用: {', '.join(commands.keys())}")
        sys.exit(1)


if __name__ == '__main__':
    main()