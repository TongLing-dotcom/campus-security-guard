# -*- coding: utf-8 -*-
"""
生成片头署名卡文字层（1920x1080 RGBA 透明 PNG）。
字体：Noto Sans SC（SIL OFL 1.1，免费且无版权争议）
用途：叠加到 未完成1.mp4 前 2 秒的"冻结首帧 + 模糊"底图上。
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, os

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work", "title_card_1920x1080.png")

def fnt(size, weight):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(weight)
    return f

# ---------- 文字定义 ----------
L1 = "作者  曹家洋"
L2 = "河南财经政法大学"
L3 = "全国高校安全卫士网络短视频作品"

f1 = fnt(88, "Bold")
f2 = fnt(58, "Regular")
f3 = fnt(44, "Regular")

Y1, Y2, Y3 = 374, 514, 620
WHITE = (255, 255, 255, 255)

# ---------- 1) 文字遮罩（用于生成柔影） ----------
mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(mask)

def draw_centered(draw, text, font, y, fill):
    w = draw.textlength(text, font=font)
    draw.text(((W - w) / 2.0, y), text, font=font, fill=fill)

for t, f, y in ((L1, f1, Y1), (L2, f2, Y2), (L3, f3, Y3)):
    draw_centered(md, t, f, y, 255)

# ---------- 2) 柔和投影：遮罩 -> 下移 -> 高斯模糊 ----------
SHADOW_DY = 5
SHADOW_BLUR = 7
SHADOW_ALPHA = 165
sm = mask.transform((W, H), Image.AFFINE, (1, 0, 0, 0, 1, -SHADOW_DY), resample=Image.BILINEAR)
sm = sm.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
sm = sm.point(lambda v: int(v * SHADOW_ALPHA / 255.0))

layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
layer.putalpha(sm)                                  # 黑色 #000 带 alpha => 柔影

# ---------- 2b) 文字背后的淡暗色光晕（垫高对比，仍保留画面轮廓） ----------
glow = np.zeros((H, W), dtype=np.float32)
gx = (np.arange(W, dtype=np.float32) - W / 2.0) / 620.0
gy = (np.arange(H, dtype=np.float32) - 525.0) / 235.0
r2 = gx[None, :] ** 2 + gy[:, None] ** 2
glow = 0.30 * np.exp(-r2 * 1.15)                    # 峰值 alpha ~76/255，边缘归零
glow_img = Image.fromarray((np.clip(glow, 0, 1) * 255).astype(np.uint8), mode="L")
glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
glow_layer.putalpha(glow_img)
layer = Image.alpha_composite(layer, glow_layer)

# ---------- 3) 纯白文字叠在柔影与光晕之上 ----------
text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
layer = Image.alpha_composite(layer, text_layer)
td = ImageDraw.Draw(layer)
for t, f, y in ((L1, f1, Y1), (L2, f2, Y2), (L3, f3, Y3)):
    draw_centered(td, t, f, y, WHITE)

# ---------- 4) 点缀 ----------
# 上方短横线
RULE_W, RULE_H = 108, 5
rx = (W - RULE_W) / 2.0
td.rectangle([rx, 318, rx + RULE_W, 318 + RULE_H], fill=(255, 255, 255, 235))

# 第2、3行之间：基线省略点（第2行底约 584，第3行顶 620）
for cx in (W / 2 - 26, W / 2, W / 2 + 26):
    r = 3.5
    td.ellipse([cx - r, 600 - r, cx + r, 600 + r], fill=(255, 255, 255, 235))

# 下方收尾细线（与第三行文字留出间距）
bw, bh = 300, 2
bx = (W - bw) / 2.0
td.rectangle([bx, 736, bx + bw, 736 + bh], fill=(255, 255, 255, 120))

layer.save(OUT)

# ---------- 自检 ----------
a = np.array(layer)
alpha = a[:, :, 3]
core = alpha > 240                      # 实心文字区域
print("saved:", OUT)
print("size:", layer.size, "mode:", layer.mode)
print("alpha: max=%d  coverage=%.2f%%" % (alpha.max(), (alpha > 0).sum() * 100.0 / (W * H)))
if core.sum():
    r = a[:, :, 0][core].mean(); g = a[:, :, 1][core].mean(); b = a[:, :, 2][core].mean()
    print("core pixel RGB mean = (%.1f, %.1f, %.1f)  [应为 255,255,255 => 纯白]" % (r, g, b))
