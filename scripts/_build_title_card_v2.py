# -*- coding: utf-8 -*-
"""
生成片头署名卡文字层（1920x1080 RGBA 透明 PNG）—— v2 纯标题版。
标题：「"真假"妈妈」，去掉了作者署名与学校。
字体：Noto Sans SC（SIL OFL 1.1，免费且无版权争议）
用途：叠加到 未完成1.mp4 前 2 秒的"冻结首帧 + 模糊"底片上。
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, os

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "title_card_v2_1920x1080.png")

def fnt(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(weight)
    return f

# ---------- 文字定义 ----------
L2 = "\u201c\u771f\u5047\u201d\u5988\u5988"          # “真假”妈妈
L3 = "\u5168\u56fd\u9ad8\u6821\u5b89\u5168\u536b\u58eb\u7f51\u7edc\u77ed\u89c6\u9891\u4f5c\u54c1"  # 全国高校安全卫士网络短视频作品

f2 = fnt(120, "Bold")     # 标题：放大，因为只剩一行主标题
f3 = fnt(44, "Regular")   # 尾部说明：保持不变

Y2, Y3 = 452, 656
WHITE = (255, 255, 255, 255)

# ---------- 1) 文字遮罩（用于生成柔影） ----------
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)

def draw_centered(draw, text, font, y, fill):
    w = draw.textlength(text, font=font)
    draw.text(((W - w) / 2.0, y), text, font=font, fill=fill)

for t, f, y in ((L2, f2, Y2), (L3, f3, Y3)):
    draw_centered(md, t, f, y, 255)

# ---------- 2) 柔和投影 ----------
SHADOW_DY = 6
SHADOW_BLUR = 9
SHADOW_ALPHA = 170
sm = mask.transform((W, H), Image.AFFINE, (1, 0, 0, 0, 1, -SHADOW_DY), resample=Image.BILINEAR)
sm = sm.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
sm = sm.point(lambda v: int(v * SHADOW_ALPHA / 255.0))

layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
layer.putalpha(sm)

# ---------- 2b) 文字背后的淡暗色光晕（垫高对比，保留轮廓） ----------
glow = np.zeros((H, W), dtype=np.float32)
gx = (np.arange(W, dtype=np.float32) - W / 2.0) / 620.0
gy = (np.arange(H, dtype=np.float32) - 545.0) / 245.0
r2 = gx[None, :] ** 2 + gy[:, None] ** 2
glow = 0.30 * np.exp(-r2 * 1.15)
glow_img = Image.fromarray((np.clip(glow, 0, 1) * 255).astype(np.uint8), mode="L")
glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
glow_layer.putalpha(glow_img)
layer = Image.alpha_composite(layer, glow_layer)

# ---------- 3) 纯白文字 ----------
text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
layer = Image.alpha_composite(layer, text_layer)
td = ImageDraw.Draw(layer)
for t, f, y in ((L2, f2, Y2), (L3, f3, Y3)):
    draw_centered(td, t, f, y, WHITE)

# ---------- 4) 点缀 ----------
# 标题上方短横线
RULE_W, RULE_H = 120, 5
rx = (W - RULE_W) / 2.0
td.rectangle([rx, 392, rx + RULE_W, 392 + RULE_H], fill=(255, 255, 255, 235))

# 标题下方三个点（标题底约 y=592，说明行顶 y=656，取中间）
for cx in (W / 2 - 26, W / 2, W / 2 + 26):
    r = 3.5
    td.ellipse([cx - r, 622 - r, cx + r, 622 + r], fill=(255, 255, 255, 235))

# 底部收尾细线
bw, bh = 300, 2
bx = (W - bw) / 2.0
td.rectangle([bx, 772, bx + bw, 772 + bh], fill=(255, 255, 255, 120))

layer.save(OUT)

# ---------- 自检 ----------
a = np.array(layer)
alpha = a[:, :, 3]
core = alpha > 240
print("saved:", OUT)
print("size:", layer.size, "mode:", layer.mode)
print("alpha: max=%d  coverage=%.2f%%" % (alpha.max(), (alpha > 0).sum() * 100.0 / (W * H)))
if core.sum():
    print("core pixel RGB mean = (%.1f, %.1f, %.1f)  [应为 255,255,255 => 纯白]"
          % (a[:, :, 0][core].mean(), a[:, :, 1][core].mean(), a[:, :, 2][core].mean()))
