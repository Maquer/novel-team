#!/usr/bin/env python3
"""明镜(配图官) 公共基础模块 — gen2/gen3 共用的绘图工具函数（无主题色依赖）"""
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTCollection as _TTC
import os

OUT = '/var/minis/attachments'
os.makedirs(OUT, exist_ok=True)

FB = '/usr/share/fonts/noto/NotoSansCJK-Bold.ttc'
FR = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'
FM = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'

def _f(path, size): return ImageFont.truetype(path, size)
title = lambda s: _f(FB, s)
body  = lambda s: _f(FR, s)
mono  = lambda s: _f(FM, s)

# ── emoji / 不支持字形清理 ─────────────────────────────
_EMOJI_SUB = {'✅':'推荐','❌':'淘汰','⬜':'未测','⚠️':'注意：','⚠':'注意：','🔴':'','✨':'','❤':'','😭':'','🧸':'','🫂':'','📦':'','👇':'','💬':'','💕':'','🥹':'','🔥':'','🚗':'','📸':'','☕':'','🥤':'','👌':'','🥰':'','💪':'','💦':'','🌍':'','🛒':'','😍':'','🙀':''}
_tc = _TTC(FR)
_CMAP = set(_tc.fonts[0].getBestCmap().keys())
def sanitize(s):
    for k,v in _EMOJI_SUB.items(): s = s.replace(k,v)
    out=[]
    for ch in s:
        o=ord(ch)
        if o <= 0x7F:
            out.append(ch); continue
        if o in _CMAP:
            out.append(ch); continue
    return ''.join(out)

# ── 自动换行（按像素宽度）──────────────────────────────
def _w(d, text, f):
    try: return d.textlength(text, font=f)
    except Exception: return f.getbbox(text)[2]
def wrap(d, text, f, maxw):
    lines=[]
    for para in sanitize(text).split('\n'):
        if not para.strip(): lines.append(''); continue
        cur=''
        for ch in para:
            if _w(d, cur+ch, f) <= maxw: cur+=ch
            else: lines.append(cur); cur=ch
        lines.append(cur)
    return lines

def rr(d,xy,r,fill,outline=None,width=1):
    x0,y0,x1,y1=xy; R=r
    d.rectangle([x0+R,y0,x1-R,y1],fill=fill)
    d.rectangle([x0,y0+R,x1,y1-R],fill=fill)
    for bbox,a1,a2 in [([x0,y0,x0+2*R,y0+2*R],180,270),([x1-2*R,y0,x1,y0+2*R],270,360),
                       ([x0,y1-2*R,x0+2*R,y1],90,180),([x1-2*R,y1-2*R,x1,y1],0,90)]:
        d.pieslice(bbox,a1,a2,fill=fill)
    if outline:
        for bbox,a1,a2 in [([x0,y0,x0+2*R,y0+2*R],180,270),([x1-2*R,y0,x1,y0+2*R],270,360),
                           ([x0,y1-2*R,x0+2*R,y1],90,180),([x1-2*R,y1-2*R,x1,y1],0,90)]:
            d.arc(bbox,a1,a2,fill=outline,width=width)
        d.line([x0+R,y0,x1-R,y0],fill=outline,width=width); d.line([x0+R,y1,x1-R,y1],fill=outline,width=width)
        d.line([x0,y0+R,x0,y1-R],fill=outline,width=width); d.line([x1,y0+R,x1,y1-R],fill=outline,width=width)
def cc(d,cx,y,text,f,color):  # 居中
    b=d.textbbox((0,0),text,font=f); w=b[2]-b[0]
    d.text((cx-w//2,y),text,fill=color,font=f)
def cl(d,x,y,text,f,color):  # 左对齐
    d.text((x,y),text,fill=color,font=f)
def save(img,name):
    img.save(os.path.join(OUT,name),'PNG')
    print('ok', name, os.path.getsize(os.path.join(OUT,name))//1024,'KB')

# ── 公共数据（各版本共用）──────────────────────────────
COT_A = """好的，我需要帮用户写一条小红书种草笔记，主题是保温杯。要求是200字左右，要有emoji，口语化，用第一人称，还要结尾有问题互动。让我想想怎么组织内容。

用户之前让我写过行李牌的内容，现在需要的是保温杯的推荐。用户是商家，所以语气要活泼热情，突出产品特点。结构上需要吸引人，带点种草的感觉。

我得确保字数控制在200字左右，emoji用得当。口语化的话，可以用“兄弟姐妹们”这样的称呼，增加亲近感。结尾要有个问题，让读者互动，比如“你们最喜欢哪个款式？”之类的。"""

BODY_A = """✨保温杯私藏秘诀✨

姐妹们！这个保温杯真的绝了😭保温性能超绝，饭团、咖啡都能喝上班喝水不凉！外壳软糯得像握个毛绒球🧸倒杯水都不心疼～拿在手上就超安心💕

悄悄说它的小细节：喷墨哑光防指纹✨磨砂手感超级舒服🫂微薄设计不占地方📦放在办公桌都得被夸~

真正的好杯子还得自己得熟用哦❤️不知道的姐妹可以试试这几款👇

你们最喜欢哪个款式呀？或者有什么保温杯推荐也可以告诉我呀~💬"""