#!/usr/bin/env python3
"""明镜(配图官) v4 · 统一 1080×1440 (3:4) 竖版，适合小红书连滑"""
from PIL import Image, ImageDraw, ImageFont
import os
from fontTools.ttLib import TTCollection as _TTC

W, H = 1080, 1440
OUT = '/var/minis/attachments'
os.makedirs(OUT, exist_ok=True)

FB = '/usr/share/fonts/noto/NotoSansCJK-Bold.ttc'
FR = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'
def _f(p, s): return ImageFont.truetype(p, s)
title = lambda s: _f(FB, s)
body  = lambda s: _f(FR, s)
mono  = lambda s: _f(FR, s)

BG='#f7f8fa'; CARD='#ffffff'; CARD2='#f1f3f7'; BORDER='#dde1e8'
INK='#1f2430'; GRAY='#5f6b7a'; AMBER='#c2610a'; RED='#d6303c'
GREEN='#0a8f6c'; BLUE='#2563eb'; PURPLE='#8e44ad'
CODEBG='#f6f8fa'; COTBG='#fdf3d8'; COTINK='#92400e'
def rgb(h):
    h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))

_EMOJI_SUB={'✅':'推荐','❌':'淘汰','⬜':'未测','⚠️':'注意：','⚠':'注意：'}
_tc=_TTC(FR); _CMAP=set(_tc.fonts[0].getBestCmap().keys())
def sanitize(s):
    for k,v in _EMOJI_SUB.items(): s=s.replace(k,v)
    return ''.join(c for c in s if ord(c)<=0x7F or ord(c) in _CMAP)

def _w(d,t,f):
    try: return d.textlength(t,font=f)
    except Exception: return f.getbbox(t)[2]
def wrap(d,text,f,maxw):
    lines=[]
    for para in sanitize(text).split('\n'):
        if not para.strip(): lines.append(''); continue
        cur=''
        for ch in para:
            if _w(d,cur+ch,f)<=maxw: cur+=ch
            else: lines.append(cur); cur=ch
        lines.append(cur)
    return lines

def new():
    img=Image.new('RGB',(W,H),rgb(BG)); return img,ImageDraw.Draw(img)
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
def cc(d,cx,y,t,f,c):
    b=d.textbbox((0,0),t,font=f); d.text((cx-(b[2]-b[0])//2,y),t,fill=c,font=f)
def cl(d,x,y,t,f,c): d.text((x,y),t,fill=c,font=f)
def footer(d,t): cc(d,W//2,1396,t,body(20),rgb(GRAY))
def save(img,name):
    p=os.path.join(OUT,name); img.save(p,'PNG')
    print('ok',name,os.path.getsize(p)//1024,'KB')
_tmp=ImageDraw.Draw(Image.new('RGB',(10,10)))

# ═══════════ 图1 CoT 核心证据 ═══════════
COT_A="""好的，我需要帮用户写一条小红书种草笔记，主题是保温杯。要求是200字左右，要有emoji，口语化，用第一人称，还要结尾有问题互动。让我想想怎么组织内容。

用户之前让我写过行李牌的内容，现在需要的是保温杯的推荐。用户是商家，所以语气要活泼热情，突出产品特点。结构上需要吸引人，带点种草的感觉。

我得确保字数控制在200字左右，emoji用得当。口语化的话，可以用“兄弟姐妹们”这样的称呼，增加亲近感。结尾要有个问题，让读者互动，比如“你们最喜欢哪个款式？”之类的。"""
BODY_A="""保温杯私藏秘诀

姐妹们！这个保温杯真的绝了！保温性能超绝，饭团、咖啡都能喝上班喝水不凉！外壳软糯得像握个毛绒球，倒杯水都不心疼～拿在手上就超安心

悄悄说它的小细节：喷墨哑光防指纹，磨砂手感超级舒服，微薄设计不占地方，放在办公桌都得被夸~

你们最喜欢哪个款式呀？"""

def chart1():
    img,d=new()
    rr(d,(40,50,1040,168),14,rgb('#fdecec'),rgb(RED),2)
    cl(d,70,70,'截图 2 ·【核心证据】MiniCPM 把思考过程原样吐给用户',title(29),rgb(RED))
    cl(d,70,120,'模型原始输出 · Prompt A 种草任务 · 共 1267 字节 · 未做任何修饰',body(21),rgb(GRAY))
    x0,x1=40,1040; py=190
    cot=wrap(d,COT_A,mono(24),x1-x0-64)
    bod=wrap(d,BODY_A,mono(22),x1-x0-64)
    ph=64+len(cot)*36+120+len(bod)*34+30
    rr(d,(x0,py,x1,py+ph),10,rgb(CODEBG),'#b6c8e0',2)
    y=py+18
    cl(d,x0+28,y,'输出前段 — chain-of-thought 推理过程（模型自言自语）',body(22),rgb(BLUE))
    coty=py+62
    d.rectangle([x0,coty,x1,coty+len(cot)*36+20],fill=rgb(COTBG))
    y=coty+10
    for ln in cot:
        if ln=='': y+=18; continue
        cl(d,x0+32,y,ln,mono(24),rgb(COTINK)); y+=36
    y=coty+len(cot)*36+20+14
    d.line([x0+28,y,x1-28,y],fill=rgb(BORDER),width=2); y+=16
    cl(d,x0+28,y,'[正文输出 — 正常文章]',body(22),rgb(BLUE)); y+=44
    for ln in bod:
        if ln=='': y+=16; continue
        cl(d,x0+32,y,ln,mono(22),rgb(INK)); y+=34
    cy=py+ph+26
    for t1,t2,col in [('在其后 3 款（DeepSeek / Qwen / MiMo）','相同 Prompt → 推理过程被抑制，直接返回成品',rgb(GREEN)),
                      ('MiniCPM5-2B（面壁）','API 通道 → 用户看到的是思考过程，不是可直接发布的内容',rgb(RED))]:
        rr(d,(40,cy,1040,cy+118),12,rgb(CARD),col,2)
        cl(d,68,cy+16,t1,title(26),rgb(INK))
        cl(d,68,cy+66,t2,body(22),col)
        cy+=134
    footer(d,'数据源：api-responses/MiniCPM面壁_A_retry.txt · 2026-09-24 · via Radeon Cloud')
    save(img,'chart01-mincpm-cot-v4.png')

# ═══════════ 图2 评分总览 ═══════════
def chart2():
    img,d=new()
    cc(d,W//2,70,'评分总览',title(46),rgb(INK))
    cc(d,W//2,150,'4 维度 × 4 任务 · 满分 80',body(26),rgb(GRAY))
    hs=['模型','准确性','自然度','完整度','实用性','总分','结论']
    xs=[150,352,486,620,754,880,985]
    for x,h in zip(xs,hs): cc(d,x,250,h,title(25),rgb(AMBER))
    rows=[('Qwen 通义','18','19','18','16','72','推荐',rgb(GREEN)),
          ('MiMo 小米','18','19','18','16','72','推荐',rgb(GREEN)),
          ('DeepSeek','17','18','17','16','69','推荐',rgb(BLUE)),
          ('MiniCPM 面壁','13','13','14','11','51','淘汰',rgb(RED)),
          ('GLM 智谱','—','—','—','—','—','未测',rgb(GRAY))]
    for i,(name,a,b,c,sc,tot,ver,col) in enumerate(rows):
        y=310+i*195
        rr(d,(40,y,1040,y+172),10,rgb(CARD if i%2==0 else CARD2),rgb(BORDER),1)
        cl(d,84,y+62,name,body(32),rgb(INK))
        for x,v in zip(xs[1:5],[a,b,c,sc]): cc(d,x,y+66,v,body(30),rgb(INK))
        cc(d,xs[5],y+62,tot,title(34),col)
        cc(d,xs[6],y+66,ver,title(27),col)
    cc(d,W//2,1330,'均值 66 分 ｜ MiniCPM 差距 −15 分 ｜ 淘汰线：总分 < 均值 且 某任务实用性 ≤ 2',body(23),rgb(GRAY))
    footer(d,'数据源：e1-evidence-001.md · 2026-09-24')
    save(img,'chart02-score-table-v4.png')

# ═══════════ 图3 Prompt A 2×2 ═══════════
def chart3():
    cols=[('DeepSeek','19 分 · 612B',rgb(BLUE),
      '用了三个月的保温杯，真心想安利给全世界！\n早上倒的热水，下午喝还是烫嘴的程度，保温效果真的绝了！杯身磨砂质感，握着超舒服，而且完全不沾指纹。\n最戳我的是它的杯盖，一键弹开+安全锁，单手操作超方便，通勤路上喝水不用手忙脚乱。\n容量400ml刚好够我半天，放包里也不重，颜值还高，奶茶色越看越喜欢。\n姐妹们，你们选保温杯最看重啥？评论区聊聊'),
     ('Qwen 通义','19 分 · 589B',rgb(BLUE),
      '姐妹们，我真的被这个保温杯拿捏了\n以前冬天喝热水，没一会儿就凉了，后来随手入手了这个保温杯，结果直接爱上！保温效果很惊喜，早上倒的热水到下午还是温温的，泡咖啡、泡茶也很合适。\n杯子颜值也很能打，简单干净，放办公桌上看着都舒服。密封性也OK，放包里不怕漏水。\n你们平时买保温杯最看重保温、颜值还是便携呀？'),
     ('MiMo 小米','19 分 · 529B',rgb(BLUE),
      '冬天的命真的是保温杯给的！\n之前随便买个杯子，一小时就凉透，直到换了这款保温杯，直接真香。早上倒的热水，下午打开还烫嘴，保温力我愿称之为「卷王」\n颜值也戳我，奶fufu的颜色，拿在手里像个配饰，拍照超上镜。\n重点是不重！放包里不占地，通勤党狠狠爱住\n姐妹们冬天都用什么保温杯呀？评论区一起抄作业'),
     ('MiniCPM 面壁','13 分 · 1267B',rgb(RED),
      '好的，我需要帮用户写一条小红书种草笔记……让我想想怎么组织内容。\n（此处为 CoT 推理过程）\n用户是商家，所以语气要活泼热情，突出产品特点。\n（此处为 CoT 推理过程）\n—— 正文分隔 ——\n保温杯私藏秘诀\n姐妹们！这个保温杯真的绝了\n保温性能超绝，饭团、咖啡都能喝上班喝水不凉！\n真正的好杯子还得自己得熟用哦。\n你们最喜欢哪个款式呀？')]
    img,d=new()
    cc(d,W//2,56,'截图 3 · Prompt A 种草 · 4 款输出对比',title(36),rgb(INK))
    cc(d,W//2,122,'「用一句话安利保温杯，200字左右，口语化，第一人称，结尾提问互动」',body(22),rgb(GRAY))
    grid=[(30,170),(545,170),(30,740),(545,740)]
    for (gx,gy),(name,meta,col,text) in zip(grid,cols):
        cw,ch=455,550 if gy<400 else 540
        rr(d,(gx,gy,gx+cw,gy+ch),12,rgb(CARD),col,2)
        cl(d,gx+22,gy+16,name,title(26),col)
        cl(d,gx+22,gy+56,meta,body(18),rgb(GRAY))
        lines=wrap(d,text,body(18),cw-44)
        y=gy+96
        for ln in lines:
            iscot=('CoT' in ln) or ('此处为' in ln) or ('用户是商家' in ln) or ('让我想想' in ln)
            if ln=='': y+=10; continue
            cl(d,gx+22,y,ln,body(18),rgb(COTINK) if iscot else rgb(INK)); y+=27
    cc(d,W//2,1330,'MiniCPM 输出 1267B，约 60% 篇幅是 CoT 推理过程',title(24),rgb(RED))
    footer(d,'其余 3 款直接返回可用文案（约 550B）· 数据源：api-responses/ · 2026-09-24')
    save(img,'chart03-a-compare-v4.png')

# ═══════════ 图4 Prompt C 逻辑 ═══════════
def chart4():
    img,d=new()
    cc(d,W//2,60,'截图 4 · Prompt C 逻辑推理',title(38),rgb(INK))
    cc(d,W//2,128,'单独验证谁在说真话',body(24),rgb(GRAY))
    q='已知：甲说“乙在说谎”，乙说“丙在说谎”，丙说“甲乙都在说谎” → 谁在说真话？'
    ql=wrap(d,q,body(24),900)
    rr(d,(40,170,1040,170+len(ql)*38+36),10,rgb('#e8f1fb'),rgb(BLUE),2)
    y=188
    for ln in ql: cc(d,W//2,y,ln,body(24),rgb(INK)); y+=38
    y0=170+len(ql)*38+36+28
    rows=[('DeepSeek（943B）','结论：乙说真话','推理链逐步排除矛盾，验证完整',rgb(BLUE)),
          ('Qwen 通义（1106B）','结论：乙说真话','反证法穷举，严格验证',rgb(GREEN)),
          ('MiMo 小米（936B）','结论：乙说真话','三种假设逐一验证，格式最清晰',rgb(GREEN)),
          ('MiniCPM（4019B）','结论：乙说真话','但结论淹没在 4 倍长度的 CoT 推理里，输出被截断',rgb(RED))]
    for i,(name,con,note,col) in enumerate(rows):
        y=y0+i*225
        rr(d,(40,y,1040,y+205),12,rgb(CARD),col,2)
        cl(d,72,y+22,name,title(28),col)
        cl(d,72,y+76,con,body(26),rgb(AMBER))
        nl=wrap(d,note,body(22),900); yy=y+126
        for ln in nl: cl(d,72,yy,ln,body(22),rgb(GRAY)); yy+=32
    footer(d,'4 款结论一致，但 MiniCPM 输出 = 其他 3 款的 4 倍，因 CoT 反复推演')
    save(img,'chart04-c-compare-v4.png')

# ═══════════ 图5 Prompt D 润色 ═══════════
def chart5():
    img,d=new()
    cc(d,W//2,56,'截图 5 · Prompt D 润色 · 全模型共同短板',title(34),rgb(INK))
    q='原始输入（27 字）：「该产品在续航方面表现优异，能够满足用户全天候使用需求，值得推荐。」'
    ql=wrap(d,q,body(23),880)
    y=120
    rr(d,(40,y,1040,y+len(ql)*36+32),10,rgb('#fef6e0'),rgb(AMBER),2)
    yy=y+16
    for ln in ql: cc(d,W//2,yy,ln,body(23),rgb(AMBER)); yy+=36
    y0=y+len(ql)*36+32+26
    rows=[('DeepSeek（102B）','这产品续航真的顶，充一次电能用一整天，完全不耽误事儿，挺值得入手的。','信息损失：全天候 → 一整天，但口语化自然',rgb(BLUE)),
          ('Qwen 通义（83B）','这款产品的续航挺给力的，从早用到晚基本没问题，很推荐。','过度简化，丢失“值得推荐”的力度',rgb(BLUE)),
          ('MiMo 小米（90B）','这款产品续航真的很给力，从早用到晚完全没问题，挺值得推荐的。','几乎无损，但仍偏简',rgb(BLUE)),
          ('MiniCPM（926B）','需要考虑……我可以这样改写：“这款产品在续航上真的很不错，差不多能撑一整天用来用，确实值得推荐。”（前有 CoT 推理）','CoT 膨胀，输出 926B = 原始输入的 34 倍',rgb(RED))]
    for i,(name,outp,note,col) in enumerate(rows):
        y=y0+i*245
        rr(d,(40,y,1040,y+225),12,rgb(CARD),col,2)
        cl(d,72,y+18,name,title(26),col)
        ol=wrap(d,'输出：'+outp,body(22),920)
        yy=y+70
        for ln in ol[:3]: cl(d,72,yy,ln,body(22),rgb(INK)); yy+=34
        cl(d,72,y+182,note,body(21),rgb(AMBER))
    footer(d,'4 款润色均丢失细节或过度简化；MiniCPM 因 CoT 膨胀最严重')
    save(img,'chart05-d-compare-v4.png')

# ═══════════ 图6 柱状图（竖版）═══════════
def chart6():
    img,d=new()
    cc(d,W//2,70,'总分对比',title(46),rgb(INK))
    cc(d,W//2,150,'满分 80 · 均值线 66',body(26),rgb(GRAY))
    data=[('Qwen 通义',72,rgb(GREEN)),('MiMo 小米',72,rgb(GREEN)),('DeepSeek',69,rgb(BLUE)),('MiniCPM',51,rgb(RED))]
    base=1230; sc=800/80.0
    avg_y=base-int(66*sc)
    d.line([(50,avg_y),(1030,avg_y)],fill=rgb(AMBER),width=3)
    cl(d,858,avg_y-40,'均值 66',body(22),rgb(AMBER))
    bw=190; gap=60; x0=95
    for i,(n,s,col) in enumerate(data):
        x=x0+i*(bw+gap); bh=int(s*sc)
        rr(d,(x,base-bh,x+bw,base),10,col)
        cc(d,x+bw//2,base-bh-70,str(s),title(46),col)
        cc(d,x+bw//2,base+22,n,body(28),rgb(INK))
    footer(d,'数据源：e1-evidence-001.md · 2026-09-24 ｜ MiniCPM 因 CoT 拖累全面低分')
    save(img,'chart06-bar-chart-v4.png')

# ═══════════ 图7 GLM 失败记录 ═══════════
def chart7():
    img,d=new()
    cc(d,W//2,64,'截图 7 · GLM-5.3-Flash 失败记录',title(36),rgb(RED))
    cc(d,W//2,132,'本轮未测 · 如实记录',body(24),rgb(GRAY))
    lines=['{','  "action": "run",','  "error": {','    "code": "internal_error",',
           '    "message": "Provider error: [402]','     This request requires more credits,','     or fewer max_tokens. You requested','     up to 4096 tokens, but ..."},',
           '  "ok": false,','  "timestamp": "2026-09-24T09:10:11+08:00",','  "tool": "minis-model-use"','}']
    ph=len(lines)*50+50
    rr(d,(40,180,1040,180+ph),12,rgb(CODEBG),rgb(RED),2)
    y=205
    for l in lines:
        cl(d,72,y,l,mono(24),rgb(COTINK) if '[402]' in l else rgb(RED)); y+=50
    ny=180+ph+30
    for ln in wrap(d,'说明：OpenRouter free tier credits 不足，max_tokens=4096 触发 402。降到 500 仍间歇失败，故 4 任务全未测。',body(24),940):
        cl(d,70,ny,ln,body(24),rgb(GRAY)); ny+=38
    cc(d,W//2,ny+20,'本轮 GLM 未测，不纳入评分对比（说明为何只有 4 款）',title(24),rgb(INK))
    footer(d,'数据源：minis-model-use 调用日志 · 2026-09-24')
    save(img,'chart07-glm-error-v4.png')

# ═══════════ 图8 耗时（按任务分行）═══════════
def chart8():
    img,d=new()
    cc(d,W//2,54,'截图 6（可选）· API 调用耗时对比',title(34),rgb(INK))
    lg=[('DeepSeek',rgb(BLUE)),('Qwen 通义',rgb(GREEN)),('MiMo 小米',rgb(PURPLE)),('MiniCPM',rgb(RED))]
    lx=110
    for n,col in lg:
        rr(d,(lx,116,lx+26,142),5,col)
        cl(d,lx+36,116,n,body(23),rgb(INK)); lx+=230
    tasks={'A 种草':{'DeepSeek':9.2,'Qwen 通义':13.3,'MiMo 小米':9.1,'MiniCPM':2.8},
           'B 长文':{'DeepSeek':None,'Qwen 通义':36.8,'MiMo 小米':37.7,'MiniCPM':8.0},
           'C 逻辑':{'DeepSeek':13.8,'Qwen 通义':None,'MiMo 小米':50.8,'MiniCPM':37.0},
           'D 润色':{'DeepSeek':2.7,'Qwen 通义':9.4,'MiMo 小米':3.2,'MiniCPM':20.4}}
    sc=16.0; y=200
    for t,vals in tasks.items():
        rr(d,(40,y,1040,y+248),12,rgb(CARD),rgb(BORDER),1)
        cl(d,72,y+18,t,title(28),rgb(INK))
        yy=y+72
        for name,v in vals.items():
            col=dict(lg)[name]
            if v is None:
                cl(d,76,yy,'超时（60s 上限）',body(22),rgb(GRAY))
            else:
                bw=int(v*sc)
                rr(d,(76,yy,76+bw,yy+40),6,col)
                cl(d,96+bw,yy+4,f'{v:.1f}s',title(22),col)
            yy+=46
        y+=278
    footer(d,'MiniCPM 多数任务最快，但质量最低（B 长文最快却最不可用）')
    save(img,'chart08-timing-v4.png')

# ═══════════ 图9 封面（3:4 统一）═══════════
def chart9():
    img,d=new()
    rr(d,(40,60,1040,540),20,rgb(CARD),rgb(RED),3)
    cc(d,W//2,110,'AI 写小红书笔记',title(58),rgb(INK))
    cc(d,W//2,220,'4 款国产模型 1 款淘汰',title(44),rgb(RED))
    cc(d,W//2,310,'MiniCPM 的 CoT 泄露踩坑实录',title(30),rgb(AMBER))
    d.line([(110,390),(970,390)],fill=rgb(BORDER),width=2)
    cc(d,W//2,420,'自费测评 · 无品牌合作 · 全证据可复现',body(24),rgb(GRAY))
    scores=[('Qwen 通义',72,rgb(GREEN)),('MiMo 小米',72,rgb(GREEN)),('DeepSeek',69,rgb(BLUE)),('MiniCPM',51,rgb(RED))]
    y0=600; rowh=150; barx0=380; maxw=480; barh=52
    for i,(n,s,col) in enumerate(scores):
        y=y0+i*rowh
        cl(d,90,y+4,n,title(34),rgb(INK))
        rr(d,(barx0,y,barx0+maxw,y+barh),9,rgb('#e9ecf1'))
        rr(d,(barx0,y,barx0+int(maxw*s/80),y+barh),9,col)
        cl(d,barx0+maxw+36,y+1,f'{s}',title(38),col)
    d.line([(110,1240),(970,1240)],fill=rgb(BORDER),width=2)
    cl(d,100,1275,'推荐：',title(30),rgb(GREEN))
    cl(d,280,1278,'MiMo / Qwen（72 分）',body(28),rgb(INK))
    cl(d,100,1345,'淘汰：',title(30),rgb(RED))
    cl(d,280,1348,'MiniCPM（51 分，CoT 泄露）',body(28),rgb(INK))
    cc(d,W//2,1410,'#AI写作 #AI工具 #国产大模型 #API实测 #踩坑',body(22),rgb(GRAY))
    save(img,'chart09-cover-v4.png')

if __name__=='__main__':
    for f in (chart1,chart2,chart3,chart4,chart5,chart6,chart7,chart8,chart9):
        f()
    print('all done')
