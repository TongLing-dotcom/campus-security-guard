# -*- coding: utf-8 -*-
"""
《真假妈妈》片尾定格卡 —— 横屏 1920x1080 文字层（RGBA 透明 PNG）
排版沿用 03_UI素材/_render_ui_v8.py 中 12_片尾警示语底板 的视觉语言，
但按横屏重新排布（原版是 1080x1920 竖屏，直接放大到横屏会让 AI 标识被裁掉）。

输出：_work/endcard_1920x1080.png （透明层，叠在冻结帧上）
字体：Noto Sans SC（SIL OFL 1.1，免费无版权争议）
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "endcard_1920x1080.png")

def F(size, weight="Regular"):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(weight)
    return f

INK   = (242, 246, 255, 255)   # 主文案 近白
THEME = (159, 196, 255, 255)   # 主题句 冷蓝
MUTED = (142, 160, 192, 255)   # AI 声明 灰蓝

img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img, "RGBA")

def ctext(y, txt, font, fill):
    w = d.textlength(txt, font=font)
    d.text(((W - w) / 2.0, y), txt, font=font, fill=fill)

# ---------- 主警示语（两行，最大） ----------
f_main = F(112, "Bold")
main_lines = ["眼见未必真，", "转账先核实"]
y = 250
for ln in main_lines:
    ctext(y, ln, f_main, INK)
    y += 148

# ---------- 分隔细线 ----------
y += 34
d.line([(W/2 - 190, y), (W/2 + 190, y)], fill=(255, 255, 255, 90), width=3)
y += 46

# ---------- 主题句（次大） ----------
ctext(y, "涵育网络素养  共建清朗空间", F(56, "Bold"), THEME)

# ---------- AI 标识 + 声明（置底并排居中） ----------
def ai_badge(size=66):
    """圆角方框 + A/I 字形，与 _render_ui_v8.py 的风格一致但重绘为横屏用尺寸"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im, "RGBA")
    r = int(size * 0.24)
    stroke = max(3, size // 15)
    col = (234, 241, 255, 235)
    dd.rounded_rectangle([stroke, stroke, size-stroke-1, size-stroke-1],
                         radius=r, outline=col, width=stroke)
    lx0, lx1 = int(size*0.17), int(size*0.40)
    ly0, ly1 = int(size*0.31), int(size*0.70)
    mid = (lx0+lx1)//2
    dd.line([(lx0, ly1), (mid, ly0)], fill=col, width=stroke)
    dd.line([(mid, ly0), (lx1, ly1)], fill=col, width=stroke)
    cy = ly0 + int((ly1-ly0)*0.62)
    dd.line([(lx0 + int((lx1-lx0)*0.22), cy), (lx1 - int((lx1-lx0)*0.22), cy)], fill=col, width=stroke)
    ix = int(size*0.68)
    dd.line([(ix, ly0), (ix, ly1)], fill=col, width=stroke)
    return im

f_dec = F(38, "Regular")
decl = "本作品为AI辅助制作"
bsz, gap = 66, 20
tw = d.textlength(decl, font=f_dec)
total = bsz + gap + tw
x0 = (W - total) / 2.0
by = 950
badge = ai_badge(bsz)
img.paste(badge, (int(x0), int(by - 8)), badge)
d.text((int(x0 + bsz + gap), by + 2), decl, font=f_dec, fill=MUTED)

img.save(OUT)
print("saved:", OUT)
print("size:", img.size, "mode:", img.mode)
import numpy as np
a = np.array(img)[:, :, 3]
print("alpha coverage: %.2f%%" % ((a > 0).sum() * 100.0 / (W * H)))
