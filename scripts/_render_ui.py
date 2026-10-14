# -*- coding: utf-8 -*-
"""《真假妈妈》风格化手机 UI 素材生成器 —— 1080x1920 竖屏 PNG
输出（03_UI素材/png/）：
  01_来电界面.png                不透明整屏
  02_转账界面.png                不透明整屏
  03_反诈预警横幅.png            不透明整屏（转账屏 + 顶部预警横幅）
  04_反诈预警96110弹窗.png       不透明整屏（转账屏压暗 + 96110 弹窗）
  05_预警横幅_透明.png           透明层（仅横幅，置顶）
  06_96110弹窗_透明.png          透明层（仅压暗 + 弹窗卡片）
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "png")
os.makedirs(OUT, exist_ok=True)

REG = "C:/Windows/Fonts/msyh.ttc"
BOLD = "C:/Windows/Fonts/msyhbd.ttc"
def F(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, size, index=0)

# ---------- 调色板 ----------
INK="#eaf0ff"; MUTED="#8ea0c0"; LINE="#22304a"; ACCENT="#3ea6ff"; GREEN="#2fbf7e"; RED="#ef4a5b"
PINK="#1a2230"; PMUTED="#8a94a6"; PLINE="#e8ecf2"; PAC="2f6bff"; PAC_HEX="#2f6bff"

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))
def hx(c):
    c=c.lstrip("#"); return tuple(int(c[i:i+2],16) for i in (0,2,4))
def vgrad(im, stops):
    d=ImageDraw.Draw(im)
    for y in range(H):
        t=y/(H-1)
        # stops: list of (pos,color)
        for i in range(len(stops)-1):
            p0,c0=stops[i]; p1,c1=stops[i+1]
            if p0<=t<=p1:
                d.line([(0,y),(W,y)], fill=lerp(hx(c0),hx(c1),(t-p0)/(p1-p0)))
                break

def ctext(d,y,txt,font,fill,x=W//2,anchor="ma"):
    d.text((x,y),txt,font=font,fill=fill,anchor=anchor)

def silhouette(d, cx, cy, r, fill):
    """通用人像剪影（不出现真人脸）"""
    d.ellipse([cx-r*0.42, cy-r*0.62, cx+r*0.42, cy-r*0.62+r*0.84], fill=fill)   # 头
    d.pieslice([cx-r*0.78, cy+r*0.05, cx+r*0.78, cy+r*1.35], 180, 360, fill=fill)  # 肩

def handset(size, color, angle):
    """手机听筒图标（旋转圆角条）"""
    im=Image.new("RGBA",(size,size),(0,0,0,0)); dd=ImageDraw.Draw(im)
    bw=int(size*0.24); bh=int(size*0.72)
    dd.rounded_rectangle([(size-bw)//2,(size-bh)//2,(size+bw)//2,(size+bh)//2],
                         radius=bw//2, fill=hx(color)+(255,), outline=None)
    return im.rotate(angle, resample=Image.BICUBIC)

# =========================================================
# 01 / 02 基础屏
# =========================================================
def render_call():
    im=Image.new("RGB",(W,H)); vgrad(im,[(0,"#1a2740"),(0.55,"#0b1220"),(1,"#070c15")])
    d=ImageDraw.Draw(im,"RGBA")
    # 状态栏
    d.text((62,62),"23:47",font=F(40),fill=hx(MUTED))
    for i in range(3):
        d.ellipse([970+i*30,74,986+i*30,90], fill=hx(MUTED)+(140,))
    # 头像脉冲圈
    cx,cy,r=540,760,140
    for rr,a in ((r+52,50),(r+96,30)):
        d.ellipse([cx-rr,cy-rr,cx+rr,cy+rr], outline=hx(ACCENT)+(a,), width=3)
    d.ellipse([cx-r,cy-r,cx+r,cy+r], fill=lerp(hx("#243553"),hx("#16213a"),0.5))
    silhouette(d,cx,cy,r*0.98,hx("#cfdcff")+(150,))
    # 文案
    ctext(d,980,"未知号码",F(74,True),hx(INK))
    ctext(d,1090,"视频通话邀请",F(40),hx(ACCENT))
    d.ellipse([398,1104,410,1116],fill=hx(ACCENT))  # 小圆点
    # 徽标
    bw=470; bx=(W-bw)//2; by=1176
    d.rounded_rectangle([bx,by,bx+bw,by+62],radius=31,outline=hx(LINE)+(255,),width=2)
    ctext(d,by+12,"对方未添加为联系人",F(28),hx(MUTED))
    # 按钮
    for bx2,col,angle,lab in ((330,RED,-42,"拒绝"),(750,GREEN,132,"接听")):
        d.ellipse([bx2-86,1580-86,bx2+86,1580+86], fill=hx(col))
        g=handset(120,"#ffffff",angle); im.paste(g,(bx2-60,1580-60),g)
        ctext(d,1690,lab,F(34),hx(MUTED),x=bx2)
    return im

def render_pay():
    im=Image.new("RGB",(W,H),hx("#f6f8fc")); d=ImageDraw.Draw(im,"RGBA")
    # 顶栏
    d.line([(78,96),(96,78),(114,96)],fill=hx(PINK),width=7)
    d.line([(96,78),(96,116)],fill=hx(PINK),width=7)
    d.text((150,66),"转账",font=F(46,True),fill=hx(PINK))
    # 风险提示条
    d.rounded_rectangle([40,168,1040,246],radius=18,fill=hx("#fff4f4"),outline=hx("#ffdcdc"),width=2)
    d.rounded_rectangle([74,200,106,232],radius=8,fill=hx("#e63946"))
    ctext(d,202,"!",F(26,True),"#ffffff",x=90)
    d.text((126,192),"风险提示：转账前请通过其他方式核实对方身份。",font=F(30),fill=hx("#c0392b"))
    # 卡片
    d.rounded_rectangle([40,300,1040,806],radius=28,fill=hx("#ffffff"))
    # 收款人
    d.rounded_rectangle([80,344,192,456],radius=56,fill=lerp(hx("#dbe4f5"),hx("#c3d2ee"),0.4))
    silhouette(d,136,400,52,hx("#7d90b3")+(255,))
    d.text((220,356),"妈妈",font=F(46,True),fill=hx(PINK))
    d.text((222,424),"收款人",font=F(28),fill=hx(PMUTED))
    d.line([(80,506),(1000,506)],fill=hx(PLINE),width=2)
    # 金额
    d.text((80,548),"转账金额",font=F(30),fill=hx(PMUTED))
    d.text((80,616),"\u00a5",font=F(58,True),fill=hx(PINK))
    d.text((150,596),"2000",font=F(104,True),fill=hx(PINK))
    d.rectangle([470,596,476,706],fill=hx(PAC_HEX))
    # 说明
    d.text((48,844),"到账时间：实时到账。请确认收款人身份无误后再操作。",font=F(28),fill=hx(PMUTED))
    # 确认按钮
    d.rounded_rectangle([40,1716,1040,1834],radius=22,fill=hx(PAC_HEX))
    ctext(d,1748,"确认转账",F(46,True),"#ffffff")
    return im

# =========================================================
# 03 横幅（转账屏 + 顶部预警横幅）
# =========================================================
def banner_layer():
    """透明层：顶部预警横幅（1080x1920）"""
    lay=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay,"RGBA")
    d.rectangle([0,0,W,150],fill=hx("#ffffff")+(255,))
    d.rectangle([0,146,W,150],fill=hx("#000000")+(30,))
    d.rounded_rectangle([40,50,96,106],radius=14,fill=hx("#e63946"))
    ctext(d,62,"!",F(40,True),"#ffffff",x=68)
    d.text((124,50),"反诈预警",font=F(30,True),fill=hx("#e63946"))
    d.text((124,92),"你正在进行的转账存在被骗风险，请立即停止",font=F(26),fill=hx("#1a2230"))
    return lay

def render_banner():
    im=render_pay().convert("RGBA")
    im.alpha_composite(banner_layer())
    return im.convert("RGB")

# =========================================================
# 04 96110 弹窗（压暗 + 卡片）
# =========================================================
def warn_layer():
    lay=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay,"RGBA")
    d.rectangle([0,0,W,H],fill=hx("#060a12")+(185,))   # 压暗
    left,right,top,bot=90,990,620,1330
    d.rounded_rectangle([left,top,right,bot],radius=34,fill=hx("#ffffff")+(255,))
    # 头部
    d.rounded_rectangle([left,top,right,top+120],radius=34,fill=hx("#e63946")+(255,))
    d.rectangle([left,top+86,right,top+120],fill=hx("#e63946")+(255,))
    d.polygon([(150,top+62),(186,top+62),(168,top+34)],fill=hx("#ffffff")+(255,))
    d.text((212,top+40),"96110 来电",font=F(46,True),fill="#ffffff")
    # 正文
    d.text((left+56,top+160),"您可能正在遭遇诈骗",font=F(48,True),fill=hx(PINK))
    body="检测到当前通话或转账存在异常，对方可能正冒充您的亲友实施诈骗。请立即挂断，并通过其他方式联系本人核实。"
    # 自动换行
    f=F(32); x0=left+56; y=top+240; maxw=(right-left)-112
    line=""
    for ch in body:
        if d.textlength(line+ch,font=f) > maxw:
            d.text((x0,y),line,font=f,fill=hx(PMUTED)); y+=48; line=ch
        else:
            line+=ch
    d.text((x0,y),line,font=f,fill=hx(PMUTED))
    # 底部按钮
    d.line([(left,top+560),(right,top+560)],fill=hx("#eef1f6"),width=2)
    d.line([(right+left)//2 - 0,top+560, (right+left)//2, bot],fill=hx("#eef1f6"),width=2)
    mid=(left+right)//2
    ctext(d,top+592,"挂断",F(42,True),hx("#e63946"),x=(left+mid)//2)
    ctext(d,top+592,"接听核实",F(42,True),hx(PAC_HEX),x=(mid+right)//2)
    return lay

def render_warn():
    im=render_pay().convert("RGBA")
    im.alpha_composite(warn_layer())
    return im.convert("RGB")

# =========================================================
# 07 / 08 回拨（呼叫中 / 通话中）
# =========================================================
def _hangup(im, d, cx, cy):
    r=86
    d.ellipse([cx-r,cy-r,cx+r,cy+r], fill=hx(RED))
    g=handset(120,"#ffffff",135); im.paste(g,(cx-60,cy-60),g)

def render_calling():
    im=Image.new("RGB",(W,H)); vgrad(im,[(0,"#16223a"),(0.6,"#0b1220"),(1,"#070c15")])
    d=ImageDraw.Draw(im,"RGBA")
    d.text((62,62),"23:48",font=F(40),fill=hx(MUTED))
    cx,cy,r=540,700,140
    d.ellipse([cx-r,cy-r,cx+r,cy+r], fill=lerp(hx("#243553"),hx("#16213a"),0.5))
    silhouette(d,cx,cy,r*0.98,hx("#cfdcff")+(150,))
    ctext(d,920,"妈妈",F(74,True),hx(INK))
    ctext(d,1032,"正在呼叫…",F(40),hx(ACCENT))
    _hangup(im,d,540,1600)
    return im

def render_incall():
    im=Image.new("RGB",(W,H)); vgrad(im,[(0,"#12243a"),(0.6,"#0b1220"),(1,"#070c15")])
    d=ImageDraw.Draw(im,"RGBA")
    d.text((62,62),"23:48",font=F(40),fill=hx(MUTED))
    cx,cy,r=540,540,108
    d.ellipse([cx-r,cy-r,cx+r,cy+r], fill=lerp(hx("#243553"),hx("#16213a"),0.5))
    silhouette(d,cx,cy,r*0.98,hx("#cfdcff")+(150,))
    ctext(d,700,"妈妈",F(66,True),hx(INK))
    ctext(d,792,"00:03",F(44),hx(GREEN))
    for bx,lab in ((330,"静音"),(540,"免提"),(750,"更多")):
        d.ellipse([bx-58,1250-58,bx+58,1250+58], fill=hx("#1a2740"))
        ctext(d,1228,lab[:1],F(40),hx(INK),x=bx)
        ctext(d,1340,lab,F(28),hx(MUTED),x=bx)
    _hangup(im,d,540,1600)
    return im

# ---------- 输出 ----------
render_call().save(os.path.join(OUT,"01_来电界面.png"),"PNG")
render_pay().save(os.path.join(OUT,"02_转账界面.png"),"PNG")
render_banner().save(os.path.join(OUT,"03_反诈预警横幅.png"),"PNG")
render_warn().save(os.path.join(OUT,"04_反诈预警96110弹窗.png"),"PNG")
render_calling().save(os.path.join(OUT,"07_回拨_呼叫中.png"),"PNG")
render_incall().save(os.path.join(OUT,"08_通话中.png"),"PNG")
banner_layer().save(os.path.join(OUT,"05_预警横幅_透明.png"),"PNG")
warn_layer().save(os.path.join(OUT,"06_96110弹窗_透明.png"),"PNG")
print("OK ->", OUT)
for fn in sorted(os.listdir(OUT)):
    p=os.path.join(OUT,fn); print("  ", fn, os.path.getsize(p)//1024, "KB")
