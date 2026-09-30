#!/usr/bin/env python3
"""明镜(配图官) v3 · 修复 emoji 豆腐块 / 文本溢出 / 空缺版式 / 引用原文错误"""
from PIL import Image, ImageDraw, ImageFont
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_base import sanitize, _w, wrap, rr, cc, cl, save, COT_A, BODY_A

OUT = '/var/minis/attachments'
os.makedirs(OUT, exist_ok=True)

FB = '/usr/share/fonts/noto/NotoSansCJK-Bold.ttc'
FR = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'
FM = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'

def _f(path, size): return ImageFont.truetype(path, size)
title = lambda s: _f(FB, s)
body  = lambda s: _f(FR, s)
mono  = lambda s: _f(FM, s)

BG, CARD, CARD2 = '#f7f8fa', '#ffffff', '#f1f3f7'
BORDER     = '#dde1e8'
WHITE      = '#1f2430'   # 浅色主题：正文墨色
GRAY       = '#5f6b7a'
YELLOW     = '#c2610a'   # 琥珀强调色（浅色底可读）
RED        = '#d6303c'
GREEN      = '#0a8f6c'
BLUE       = '#2563eb'
PURPLE     = '#8e44ad'
CODEBG     = '#f6f8fa'
COTBG      = '#fdf3d8'
TITLEBAR   = '#fdecec'

def rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))

def canv(w,h): return Image.new('RGB',(w,h),rgb(BG))
def tap(d,x,y,text,f,color,pad=(6,3),radius=6):
    b=d.textbbox((0,0),text,font=f); tw=b[2]-b[0]; th=b[3]-b[1]
    rr(d,(x,y,x+tw+pad[0]*2,y+th+pad[1]*2),radius,rgb(color))
    d.text((x+pad[0],y+pad[1]),text,fill=rgb('#'+'0f0f1a' if False else '0f0f1a'),font=f)

# ═══════════════ 图1 Core 证据（原文忠实）═══════════════
def chart1():
    W,H=1200,1120
    img=canv(W,H); d=ImageDraw.Draw(img)
    # 顶部红条区域
    rr(d,(28,22,W-28,96),14,rgb(TITLEBAR),rgb(RED),2)
    cl(d,52,40,'截图 2 ·【核心证据】MiniCPM 把思考过程原样吐给用户',title(24),rgb(RED))
    cl(d,52,74,'模型原始输出  Prompt A 种草任务 · 共 1267 字节 · 未做任何修饰',body(14),rgb(GRAY))
    # 代码面板
    px0,py0,px1,py1=40,120,W-40,700
    rr(d,(px0,py0,px1,py1),10,rgb(CODEBG),'#b6c8e0',2)
    # CoT 高亮底
    cot_y0=py0+52
    cot_lines=wrap(d,COT_A,mono(16),px1-px0-56)
    cot_h=len(cot_lines)*24+16
    d.rectangle([px0,py0+42,px1,cot_y0+cot_h],fill=rgb(COTBG))
    # 标题
    mon=mono(15)
    cl(d,px0+20,py0+14,'输出前段 — chain-of-thought 推理过程（模型自言自语）',mon,rgb('#1d4ed8'))
    # CoT 行
    y=cot_y0+8
    for ln in cot_lines:
        if ln=='': y+=18; continue
        cl(d,px0+24,y,ln,mono(16),rgb('#92400e'))
        y+=24
    # 分隔 + 正文标注
    y+=6
    d.line([px0+20,y,px1-20,y],fill='#d0d7de',width=1)
    y+=26
    cl(d,px0+20,y,'[正文输出 — 正常文章]',mon,rgb('#1d4ed8'))
    y+=22
    bbody=wrap(d,BODY_A,mono(15),px1-px0-56)
    for ln in bbody[:6]:
        cl(d,px0+24,y,ln,mono(15),rgb(WHITE)); y+=22
    # 对比卡
    cards=[('在其后 3 款（DeepSeek / Qwen / MiMo）','相同 Prompt','推理过程被抑制，直接返回成品',rgb(GREEN)),
           ('MiniCPM5-2B（面壁）','API 通道','用户看到的是思考过程，不是可直接发布的内容',rgb(RED))]
    for i,(a,b,c,col) in enumerate(cards):
        yc=760+i*150
        rr(d,(50,yc,W-50,yc+138),12,rgb(CARD),col,2)
        cl(d,78,yc+18,a,body(20),rgb(WHITE))
        cl(d,78,yc+52,b+'  →  '+c,   body(17),col)
    cc(d,W//2,H-44,'数据源：api-responses/MiniCPM面壁_A_retry.txt · 2026-09-24 · via Radeon Cloud',body(13),rgb(GRAY))
    save(img,'chart01-mincpm-cot-v3.png')

# ═══════════════ 图2 评分总览 ═══════════════
def chart2():
    W,H=1200,760
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,36,'评分总览（4维度 × 4任务，满分 80）',title(26),rgb(WHITE))
    hs=['模型','准确性','自然度','完整度','实用性','总分','结论']
    xs=[60,235,395,555,715,875,1040]
    for x,h in zip(xs,hs): cc(d,x,92,h,title(17),rgb(YELLOW))
    rows=[
        ('Qwen 通义','18','19','18','16','72','推荐',rgb(GREEN)),
        ('MiMo 小米','18','19','18','16','72','推荐',rgb(GREEN)),
        ('DeepSeek','17','18','17','16','69','推荐',rgb(BLUE)),
        ('MiniCPM 面壁','13','13','14','11','51','淘汰',rgb(RED)),
        ('GLM 智谱','—','—','—','—','—','未测',rgb(GRAY)),
    ]
    for i,(name,a,b,c,sc,tot,ver,col) in enumerate(rows):
        y=138+i*96
        rr(d,(40,y,W-40,y+84),8,rgb(CARD if i%2==0 else CARD2),'#e2e5ea',1)
        cl(d,70,y+28,name,body(19),rgb(WHITE))
        for x,v,isbold,vc in zip(xs[1:],[a,b,c,sc,tot],[False]*4+[True],[rgb(WHITE)]*4+[col]):
            cc(d,x,y+30,v,title(19) if isbold else body(18),vc)
        cc(d,xs[6],y+30,ver,title(18),col)
    cc(d,W//2,H-56,'均值 66 分 ｜ MiniCPM 差距 −15 分 ｜ 淘汰线：总分 < 均值 且 某任务实用性 ≤ 2',body(15),rgb(GRAY))
    cc(d,W//2,H-30,'数据源：e1-evidence-001.md · 2026-09-24',body(13),rgb(GRAY))
    save(img,'chart02-score-table-v3.png')

# ═══════════════ 图3 Prompt A 4列对比 ═══════════════
def chart3():
    W=1300
    cols=[
        ('DeepSeek','19 分 · 612B',rgb(BLUE),
         '用了三个月的保温杯，真心想安利给全世界！\n早上倒的热水，下午喝还是烫嘴的程度，保温效果真的绝了！杯身磨砂质感，握着超舒服，而且完全不沾指纹。\n最戳我的是它的杯盖，一键弹开+安全锁，单手操作超方便，通勤路上喝水不用手忙脚乱。\n容量400ml刚好够我半天，放包里也不重，颜值还高，奶茶色越看越喜欢。\n现在每天喝水频率都变高了，连同事都被种草问链接。\n姐妹们，你们选保温杯最看重啥？是颜值还是保温时长？评论区聊聊'),
        ('Qwen 通义','19 分 · 589B',rgb(BLUE),
         '姐妹们，我真的被这个保温杯拿捏了\n以前冬天喝热水，没一会儿就凉了，后来随手入手了这个保温杯，结果直接爱上！保温效果很惊喜，早上倒的热水到下午还是温温的，泡咖啡、泡茶也很合适。\n杯子颜值也很能打，简单干净，放办公桌上看着都舒服。密封性也OK，放包里不怕漏水。最关键是一点不显重，随手带出门很方便。\n冬天真的不能没有它，感觉随时都有热乎乎的水喝。你们平时买保温杯最看重保温、颜值还是便携呀？'),
        ('MiMo 小米','19 分 · 529B',rgb(BLUE),
         '冬天的命真的是保温杯给的！\n之前随便买个杯子，一小时就凉透，直到换了这款保温杯，直接真香。早上倒的热水，下午打开还烫嘴，保温力我愿称之为「卷王」\n颜值也戳我，奶fufu的颜色，拿在手里像个配饰，拍照超上镜。杯口大好清洗，装咖啡不串味，单手开盖开车党狂喜\n重点是不重！放包里不占地，通勤党狠狠爱住\n姐妹们冬天都用什么保温杯呀？评论区一起抄作业'),
        ('MiniCPM 面壁','13 分 · 1267B',rgb(RED),
         '好的，我需要帮用户写一条小红书种草笔记……让我想想怎么组织内容。\n（此处为 CoT 推理过程）\n用户是商家，所以语气要活泼热情，突出产品特点。\n（此处为 CoT 推理过程）\n—— 正文分隔 ——\n保温杯私藏秘诀\n姐妹们！这个保温杯真的绝了\u200b\n保温性能超绝，饭团、咖啡都能喝上班喝水不凉！\n外壳软糯得像握个毛绒球。\n真正的好杯子还得自己得熟用哦。\n你们最喜欢哪个款式呀？'),
    ]
    colw=(W-50)//4
    hy=[0]*4; cbs=[]
    _tmp = ImageDraw.Draw(canv(10,10))  # throwaway for text wrapping
    for i,(name,meta,col,text) in enumerate(cols):
        x0=25+i*colw; x1=x0+colw-12
        mon=11
        lines=wrap(_tmp,text,body(mon),x1-x0-36)
        boxh=len(lines)*20+10
        hy[i]=245+boxh
        cbs.append((x0,x1,110,225,name,meta,col,boxh,lines))
    H=max(hy)+80
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,36,'截图 3 · Prompt A 种草 · 4 款输出对比',title(24),rgb(WHITE))
    cc(d,W//2,76,'「用一句话安利保温杯，200字左右，口语化，第一人称，结尾提问互动」',body(14),rgb(GRAY))
    for x0,x1,y0,y1,name,meta,col,boxh,lines in cbs:
        rr(d,(x0+4,y0,x1,y1),10,rgb(CARD),col,1 if col!=rgb(RED) else 2)
        cl(d,x0+16,y0+12,name,title(19),col)
        cl(d,x0+16,y0+46,meta,body(14),rgb(GRAY))
        yy=y1+16
        for ln in lines:
            iscot = ('CoT' in ln) or ('此处为' in ln) or ('用户是商家' in ln) or ('让我想想' in ln)
            c = rgb('#92400e') if iscot else rgb(WHITE)
            cl(d,x0+14,yy,ln,body(mon),c)
            yy+=20
    cc(d,W//2,H-30,'MiniCPM 输出 1267B，约 60% 篇幅是 CoT 推理过程；其余 3 款直接返回可用文案（约 550B）',body(13),rgb(GRAY))
    save(img,'chart03-a-compare-v3.png')

# ═══════════════ 图4 Prompt C 逻辑 ═══════════════
def chart4():
    W,H=1200,780
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,32,'截图 4 · Prompt C 逻辑推理 · 单独验证谁在说真话',title(24),rgb(WHITE))
    rr(d,(50,72,W-50,126),10,rgb('#e8f1fb'),rgb(BLUE),2)
    cc(d,W//2,94,'已知：甲说“乙在说谎”，乙说“丙在说谎”，丙说“甲乙都在说谎” → 谁在说真话？',body(17),rgb(WHITE))
    rows=[
        ('DeepSeek（943B）', '结论：乙说真话', '推理链逐步排除矛盾，验证完整', rgb(BLUE)),
        ('Qwen 通义（1106B）', '结论：乙说真话', '反证法穷举，严格验证', rgb(GREEN)),
        ('MiMo 小米（936B）', '结论：乙说真话', '三种假设逐一验证，格式最清晰', rgb(GREEN)),
        ('MiniCPM（4019B）', '结论：乙说真话', '但结论淹没在 4 倍长度的 CoT 推理里，输出被截断', rgb(RED)),
    ]
    for i,(name,con,note,col) in enumerate(rows):
        y=150+i*140
        rr(d,(50,y,W-50,y+126),10,rgb(CARD),col,2)
        cl(d,80,y+16,name,title(20),col)
        cl(d,80,y+52,con,body(18),rgb(YELLOW))
        cl(d,80,y+82,note,body(15),rgb(GRAY))
    cc(d,W//2,H-34,'4 款结论一致，但 MiniCPM 输出 4019B = 其他 3 款（约 1000B）的 4 倍，因 CoT 反复推演',body(13),rgb(GRAY))
    save(img,'chart04-c-compare-v3.png')

# ═══════════════ 图5 Prompt D 润色 ═══════════════
def chart5():
    W,H=1200,860
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,30,'截图 5 · Prompt D 润色 · 全模型共同短板',title(24),rgb(WHITE))
    rr(d,(50,68,W-50,120),10,rgb('#fef6e0'),rgb(YELLOW),2)
    cc(d,W//2,88,'原始输入（27 字）：「该产品在续航方面表现优异，能够满足用户全天候使用需求，值得推荐。」',body(16),rgb(YELLOW))
    rows=[
        ('DeepSeek（102B）','这产品续航真的顶，充一次电能用一整天，完全不耽误事儿，挺值得入手的。','信息损失：全天候 → 一整天，但口语化自然',rgb(BLUE)),
        ('Qwen 通义（83B）','这款产品的续航挺给力的，从早用到晚基本没问题，很推荐。','过度简化，丢失“值得推荐”的力度',rgb(BLUE)),
        ('MiMo 小米（90B）','这款产品续航真的很给力，从早用到晚完全没问题，挺值得推荐的。','几乎无损，但仍偏简',rgb(BLUE)),
        ('MiniCPM（926B）','需要考虑……我可以这样改写：“这款产品在续航上真的很不错，差不多能撑一整天用来用，确实值得推荐。”（前有 CoT 推理）','CoT 膨胀，输出 926B = 原始输入的 34 倍',rgb(RED)),
    ]
    for i,(name,outp,note,col) in enumerate(rows):
        y=140+i*170
        rr(d,(50,y,W-50,y+156),10,rgb(CARD),col,2)
        cl(d,80,y+14,name,title(19),col)
        cl(d,80,y+48,'输出：'+outp,body(15),rgb(WHITE))
        cl(d,80,y+120,note,body(15),rgb(YELLOW))
    cc(d,W//2,H-34,'4 款润色均丢失细节或过度简化；MiniCPM 因 CoT 膨胀最严重，实用性给 3 分以下',body(13),rgb(GRAY))
    save(img,'chart05-d-compare-v3.png')

# ═══════════════ 图6 柱状图 + 图7 GLM + 图8 耗时 ═══════════════
def chart6():
    W,H=1000,600
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,26,'总分对比（满分 80）',title(24),rgb(WHITE))
    data=[('Qwen 通义',72,rgb(GREEN)),('MiMo 小米',72,rgb(GREEN)),('DeepSeek',69,rgb(BLUE)),('MiniCPM',51,rgb(RED))]
    base=H-100; scale=(H-250)/80
    d.line([(50,base-66*scale),(W-50,base-66*scale)],fill=rgb(YELLOW),width=2)
    cl(d,W-210,base-66*scale-22,'均值 66',body(13),rgb(YELLOW))
    bw=120;gap=60;x0=110
    for i,(n,s,col) in enumerate(data):
        x=x0+i*(bw+gap); bh=s*scale
        rr(d,(x,base-bh,x+bw,base),6,col)
        cc(d,x+bw//2,base-bh-26,str(s),title(24),col)
        cc(d,x+bw//2,base+14,n,body(17),rgb(WHITE))
    cc(d,W//2,H-60,'数据源：e1-evidence-001.md · 2026-09-24 丨 MiniCPM 因 CoT 拖累全面低分',body(13),rgb(GRAY))
    save(img,'chart06-bar-chart-v3.png')

def chart7():
    W,H=1000,520
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,34,'截图 7 · GLM-5.3-Flash 失败记录（本轮未测）',title(23),rgb(RED))
    lines=['{','  "action": "run",','  "error": {','    "code": "internal_error",',
           '    "message": "Provider error: [402] This request requires more credits,','    or fewer max_tokens. You requested up to 4096 tokens, but ..."},',
           '  "ok": false,','  "timestamp": "2026-09-24T09:10:11+08:00",','  "tool": "minis-model-use"','}']
    rr(d,(60,80,W-60,360),10,rgb(CODEBG),rgb(RED),2)
    for i,l in enumerate(lines):
        cl(d,84,100+i*28, l, mono(15), rgb('#92400e') if '[402]' in l else rgb(RED))
    cl(d,84,380,'说明：OpenRouter free tier credits 不足，max_tokens=4096 触发 402。降到 500 仍间歇失败，故 4 任务全未测。',body(15),rgb(GRAY))
    cc(d,W//2,H-36,'本轮 GLM 未测，不纳入评分对比（TIP：可选加图，说明为何只有 4 款）',body(13),rgb(GRAY))
    save(img,'chart07-glm-error-v3.png')

def chart8():
    W,H=1100,660
    img=canv(W,H); d=ImageDraw.Draw(img)
    cc(d,W//2,28,'截图 6（可选）· API 调用耗时对比（秒）',title(23),rgb(WHITE))
    tasks=['A 种草','B 长文','C 逻辑','D 润色']
    dset={'DeepSeek':[9.2,None,13.8,2.7],'Qwen 通义':[13.3,36.8,None,9.4],
          'MiMo 小米':[9.1,37.7,50.8,3.2],'MiniCPM':[2.8,8.0,37.0,20.4]}
    cmap={'DeepSeek':rgb(BLUE),'Qwen 通义':rgb(GREEN),'MiMo 小米':rgb(PURPLE),'MiniCPM':rgb(RED)}
    base=H-110; scale=(H-240)/52
    gw=200; gap=72; gx0=60
    for ti,t in enumerate(tasks):
        gx=gx0+ti*(gw+gap)
        cc(d,gx+gw//2,70,t,title(18),rgb(WHITE))
        for mi,(name,vals) in enumerate(dset.items()):
            v=vals[ti]; bw=gw//4
            bx=gx+mi*bw+6
            if v is None:
                cc(d,bx+(bw-12)//2,base-14,'超时',body(13),rgb(GRAY)); continue
            bh=v*scale
            rr(d,(bx,base-bh,bx+bw-12,base),4,cmap[name])
            cc(d,bx+(bw-12)//2,base-bh-16,f'{v:.1f}',body(12),cmap[name])
    lx=110
    for n,col in cmap.items():
        rr(d,(lx,base+16,lx+22,base+36),4,col)
        cl(d,lx+30,base+18,n,body(14),rgb(WHITE)); lx+=150
    cc(d,W//2,H-40,'B 长文 DeepSeek/Qwen 超时（60s 上限），标记为「超时」；MiniCPM 最快但质量最低',body(13),rgb(GRAY))
    save(img,'chart08-timing-v3.png')

# ═══════════════ 图9 封面（3:4）═══════════════
def chart9():
    W,H=1080,1200
    img=canv(W,H); d=ImageDraw.Draw(img)
    rr(d,(40,50,W-40,390),20,rgb(CARD),rgb(RED),3)
    cc(d,W//2,90,'AI 写小红书笔记',title(64),rgb(WHITE))
    cc(d,W//2,196,'4 款国产模型 1 款淘汰',title(48),rgb(RED))
    cc(d,W//2,282,'MiniCPM 的 CoT 泄露踩坑实录',title(30),rgb(YELLOW))
    d.line([(110,336),(W-110,336)],fill=rgb(BORDER),width=2)
    cc(d,W//2,348,'自费测评 · 无品牌合作 · 全证据可复现',body(22),rgb(GRAY))
    scores=[('Qwen 通义',72,rgb(GREEN)),('MiMo 小米',72,rgb(GREEN)),('DeepSeek',69,rgb(BLUE)),('MiniCPM',51,rgb(RED))]
    y0=440; rowh=130; barh=46; maxw=560; barx0=340
    for i,(n,s,col) in enumerate(scores):
        y=y0+i*rowh
        cl(d,100,y+4,n,title(34),rgb(WHITE))
        bw=int(maxw*s/80)
        rr(d,(barx0,y,barx0+maxw,y+barh),8,rgb('#e9ecf1'))
        rr(d,(barx0,y,barx0+bw,y+barh),8,col)
        cl(d,barx0+maxw+44,y-2,f'{s}',title(40),col)
    endy=y0+4*rowh-40
    d.line([(110,920),(W-110,920)],fill=rgb(BORDER),width=2)
    cl(d,100,955,'推荐：',title(32),rgb(GREEN))
    cl(d,290,958,'MiMo / Qwen（72 分）',body(30),rgb(WHITE))
    cl(d,100,1030,'淘汰：',title(32),rgb(RED))
    cl(d,290,1033,'MiniCPM（51 分，CoT 泄露）',body(30),rgb(WHITE))
    cc(d,W//2,1125,'#AI写作 #AI工具 #国产大模型 #API实测 #踩坑',body(26),rgb(GRAY))
    save(img,'chart09-cover-v3.png')

if __name__=='__main__':
    chart1(); chart2(); chart3(); chart4(); chart5()
    chart6(); chart7(); chart8(); chart9()
    print('all done')