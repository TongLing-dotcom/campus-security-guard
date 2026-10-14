# -*- coding: utf-8 -*-
"""《真假妈妈》v8 片尾卡与回拨面板素材生成器 —— 1080x1920 竖屏 PNG
输出（03_UI素材/png/）：
  09_回拨三入口面板.png        联系人"妈妈" + 电话/微信/短信 三入口（镜6）
  10_片尾对照底版_左冷.png     左半对照画框（冷蓝，留手部窗口）+ 标注"差点转出去"
  11_片尾对照底版_右暖.png     右半对照画框（暖调，留手部窗口）+ 标注"多打一个电话"
  12_片尾警示语底板.png        纯黑底 + 主警示语 + 主题字 + AI声明（8c 定格终态）
  13_AI标识_透明.png           透明 AI 徽标（圆角方 + AI 字样），可复用/叠在声明旁
  14_片尾对照_合成示意.png     左右并置的一张合成预览（供剪映参考构图）

字体：思源黑体优先（若本机已装），退化为雅黑以保证出图；
       ★成片请务必使用第十章列出的免费商用字体。
"""
import os, math
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "png")
os.makedirs(OUT, exist_ok=True)

# ---- 字体：优先免费商用字体 ----
CAND_REG = [
    "C:/Windows/Fonts/SourceHanSansSC-Regular.otf",
    "C:/Windows/Fonts/SourceHanSansCN-Regular.otf",
    "C:/Windows/Fonts/AlibabaPuHuiTi-3-55-Regular.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]
CAND_BLD = [
    "C:/Windows/Fonts/SourceHanSansSC-Bold.otf",
    "C:/Windows/Fonts/SourceHanSansCN-Bold.otf",
    "C:/Windows/Fonts/AlibabaPuHuiTi-3-85-Bold.ttf",
    "C:/Windows/Fonts/msyhbd.ttc",
]
def _pick(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(paths)
REG_PATH, BLD_PATH = _pick(CAND_REG), _pick(CAND_BLD)
def F(size, bold=False):
    return ImageFont.truetype(BLD_PATH if bold else REG_PATH, size, index=0)

# ---------- 工具 ----------
def hx(c):
    c = c.lstrip("#"); return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))
def vgrad(im, stops):
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y/(H-1)
        for i in range(len(stops)-1):
            p0, c0 = stops[i]; p1, c1 = stops[i+1]
            if p0 <= t <= p1:
                d.line([(0, y), (W, y)], fill=lerp(hx(c0), hx(c1), (t-p0)/(p1-p0)))
                break
def ctext(d, y, txt, font, fill, x=W//2, anchor="ma"):
    d.text((x, y), txt, font=font, fill=fill, anchor=anchor)
def wrap(d, txt, font, maxw):
    lines, line = [], ""
    for ch in txt:
        if d.textlength(line+ch, font=font) > maxw:
            lines.append(line); line = ch
        else:
            line += ch
    if line: lines.append(line)
    return lines

INK = "#f2f6ff"; MUTED = "#8ea0c0"; SUB = "#aab6cc"
COLD = "#5b8fd6"; WARM = "#f0a35e"; RED = "#e63946"; GREEN = "#2fbf7e"

# =========================================================
# 13 AI 标识（透明，圆角方形 + AI 字样）
# =========================================================
def render_ai_badge(size=200):
    """AI 徽标：圆角方框 + 'A'+'I'（手工描边，任何尺寸都清晰）"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    r = int(size*0.24)
    stroke = max(3, size//30)
    col = hx("#eaf1ff")+(245,)
    d.rounded_rectangle([stroke, stroke, size-stroke-1, size-stroke-1], radius=r,
                        outline=col, width=stroke)
    # --- A：左斜 / 右斜 / 横杠 ---
    lx0, lx1 = int(size*0.17), int(size*0.40)
    ly_top, ly_bot = int(size*0.31), int(size*0.70)
    mid = (lx0+lx1)//2
    d.line([(lx0, ly_bot), (mid, ly_top)], fill=col, width=stroke)   # 左斜
    d.line([(mid, ly_top), (lx1, ly_bot)], fill=col, width=stroke)   # 右斜
    cross_y = ly_top + int((ly_bot-ly_top)*0.62)                     # 横杠靠下 1/3
    d.line([(lx0 + int((lx1-lx0)*0.22), cross_y),
            (lx1 - int((lx1-lx0)*0.22), cross_y)], fill=col, width=stroke)
    # --- I ---
    ix = int(size*0.68)
    d.line([(ix, ly_top), (ix, ly_bot)], fill=col, width=stroke)
    return im

# =========================================================
# 09 回拨三入口面板（镜6）
# =========================================================
def render_callback_panel():
    im = Image.new("RGB", (W, H))
    vgrad(im, [(0, "#16223a"), (0.55, "#0b1220"), (1, "#070c15")])
    d = ImageDraw.Draw(im, "RGBA")
    d.text((62, 62), "23:48", font=F(40), fill=hx(MUTED))
    for i in range(3):
        d.ellipse([970+i*30, 74, 986+i*30, 90], fill=hx(MUTED)+(140,))

    # 联系人卡片
    cx, cy, r = 540, 470, 120
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=lerp(hx("#243553"), hx("#16213a"), 0.5))
    # 通用人像剪影
    d.ellipse([cx-r*0.42, cy-r*0.62, cx+r*0.42, cy-r*0.62+r*0.84], fill=hx("#cfdcff")+(150,))
    d.pieslice([cx-r*0.78, cy+r*0.05, cx+r*0.78, cy+r*1.35], 180, 360, fill=hx("#cfdcff")+(150,))
    ctext(d, 660, "妈妈", F(76, True), hx(INK))
    ctext(d, 772, "选择联系方式", F(34), hx(MUTED))

    # 三入口面板
    pb = 940
    d.rounded_rectangle([70, pb, 1010, pb+560], radius=36, fill=hx("#141e30")+(255,))
    d.line([(70, pb+186), (1010, pb+186)], fill=hx("#22304a"), width=2)
    d.line([(70, pb+374), (1010, pb+374)], fill=hx("#22304a"), width=2)

    entries = [
        ("电话", "直接拨号 · 最可靠", GREEN, "tel"),
        ("微信", "语音/视频通话", "#4e9a4e", "wechat"),
        ("短信", "文字消息", COLD, "sms"),
    ]
    for i, (name, desc, col, kind) in enumerate(entries):
        y0 = pb + i*186
        # 图标
        ix, iy, ir = 178, y0+93, 52
        d.ellipse([ix-ir, iy-ir, ix+ir, iy+ir], fill=hx(col)+(46,))
        d.ellipse([ix-ir, iy-ir, ix+ir, iy+ir], outline=hx(col)+(200,), width=3)
        _entry_icon(d, ix, iy, ir, col, kind)
        d.text((268, y0+52), name, font=F(48, True), fill=hx(INK))
        d.text((270, y0+120), desc, font=F(28), fill=hx(MUTED))
        # 右侧箭头
        ax = 950
        d.line([(ax-18, y0+78), (ax, y0+93)], fill=hx(SUB)+(180,), width=5)
        d.line([(ax, y0+93), (ax-18, y0+108)], fill=hx(SUB)+(180,), width=5)

    # 底部取消
    d.rounded_rectangle([70, 1600, 1010, 1712], radius=24,
                        fill=hx("#141e30")+(255,), outline=hx("#22304a")+(255,), width=2)
    ctext(d, 1628, "取消", F(44, True), hx(SUB))
    return im

def _entry_icon(d, cx, cy, r, col, kind):
    c = hx(col)+(255,)
    if kind == "tel":
        d.rounded_rectangle([cx-13, cy-26, cx+13, cy+26], radius=13, fill=c)
    elif kind == "wechat":
        d.ellipse([cx-30, cy-24, cx+6, cy+4], fill=c)
        d.ellipse([cx-6, cy-6, cx+30, cy+20], fill=c)
        d.ellipse([cx-6, cy-30, cx+30, cy+4], outline=c, width=3)
    else:  # sms
        d.rounded_rectangle([cx-28, cy-22, cx+28, cy+10], radius=10, fill=c)
        d.polygon([(cx-10, cy+10), (cx+2, cy+10), (cx-14, cy+26)], fill=c)

# =========================================================
# 10 / 11 对照底版（左冷 / 右暖），各半屏构图
# =========================================================
def _hand_placeholder(d, cx, cy, scale, col_skin, col_sleeve):
    """手部示意占位（供剪映替换为实拍/AI 手部画面）"""
    d.rounded_rectangle([cx-60*scale, cy+40*scale, cx+60*scale, cy+200*scale],
                        radius=40*scale, fill=col_sleeve)
    # 手掌
    d.rounded_rectangle([cx-78*scale, cy-40*scale, cx+78*scale, cy+80*scale],
                        radius=46*scale, fill=col_skin)
    # 拇指
    d.rounded_rectangle([cx-118*scale, cy-20*scale, cx-52*scale, cy+34*scale],
                        radius=26*scale, fill=col_skin)
    # 指尖
    for i in range(4):
        fx = cx - 52*scale + i*36*scale
        d.rounded_rectangle([fx, cy-96*scale, fx+28*scale, cy-16*scale],
                            radius=14*scale, fill=col_skin)

def render_compare_half(side="left"):
    """返回半屏构图底版（1080 宽 × 1920 高，主体偏心一侧）——实际剪映会裁半屏
       这里直接出 540x1920 的半屏图更实用。"""
    w = W // 2
    im = Image.new("RGB", (w, H))
    if side == "left":
        base = [(0, "#101d33"), (0.5, "#0a1526"), (1, "#060b14")]
        accent, label, sub = COLD, "差点转出去", "手指悬在确认键上"
        skin, sleeve = "#c9b09a", "#3d4a63"
    else:
        base = [(0, "#2a2016"), (0.5, "#1c150e"), (1, "#0d0906")]
        accent, label, sub = WARM, "多打一个电话", "手指落在拨号键上"
        skin, sleeve = "#d9bd9f", "#5a4632"
    tmp = Image.new("RGB", (w, H)); vgrad_map = None
    d = ImageDraw.Draw(tmp)
    for y in range(H):
        t = y/(H-1)
        for i in range(len(base)-1):
            p0, c0 = base[i]; p1, c1 = base[i+1]
            if p0 <= t <= p1:
                d.line([(0, y), (w, y)], fill=lerp(hx(c0), hx(c1), (t-p0)/(p1-p0)))
                break
    im = tmp
    d = ImageDraw.Draw(im, "RGBA")

    # 手部窗口（微距留白区）
    win_top, win_bot = 560, 1320
    d.rounded_rectangle([36, win_top, w-36, win_bot], radius=40,
                        outline=hx(accent)+(120,), width=3)
    _hand_placeholder(d, w//2, os.path.join and 940, 1.0, hx(skin), hx(sleeve))
    ctext(d, win_top+28, "手部画面区", F(26), hx("#ffffff")+(90,))

    # 顶部小标
    d.rounded_rectangle([36, 120, w-36, 196], radius=26, fill=hx(accent)+(38,))
    ctext(d, 138, label, F(44, True), hx(accent))
    ctext(d, 244, sub, F(28), hx(SUB))
    return im

# =========================================================
# 12 片尾警示语底板（纯黑 + 文字栈）
# =========================================================
def render_endcard():
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    # 中心极弱径向微光（让黑不死）
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    for rr in range(700, 0, -14):
        a = int(26 * (1 - rr/700) ** 1.6)
        gd.ellipse([540-rr, 860-rr, 540+rr, 860+rr], fill=a)
    im.paste(Image.new("RGB", (W, H), (18, 26, 44)), (0, 0), glow)

    # 主警示语（最大）—— 拆为两行，避免窄屏断字
    lines_main = ["眼见未必真，", "转账先核实"]
    f_main = F(96, True)
    y = 700
    for ln in lines_main:
        ctext(d, y, ln, f_main, hx(INK)); y += 128

    # 分隔细线
    y += 20
    d.line([(400, y), (680, y)], fill=hx("#ffffff")+(80,), width=2)
    y += 52

    # 主题字（次大）
    theme = "涵育网络素养  共建清朗空间"
    f_theme = F(48, True)
    ctext(d, y, theme, f_theme, hx("#9fc4ff"))

    # AI 声明 + 徽标（并排居中，置底）
    f_dec = F(32)
    bsz = 62
    badge = render_ai_badge(bsz)
    decl = "本作品为AI辅助制作"
    tw = d.textlength(decl, font=f_dec)
    gap = 18
    total = bsz + gap + tw
    x0 = (W - total)//2
    by = 1650
    im.paste(badge, (int(x0), int(by-8)), badge)
    d.text((int(x0 + bsz + gap), by+2), decl, font=f_dec, fill=hx(MUTED))
    return im

# =========================================================
# 14 合成示意（左右并置预览）
# =========================================================
def render_compare_preview():
    l = render_compare_half("left").resize((W//2, H), Image.LANCZOS)
    r = render_compare_half("right").resize((W//2, H), Image.LANCZOS)
    im = Image.new("RGB", (W, H))
    im.paste(l, (0, 0)); im.paste(r, (W//2, 0))
    d = ImageDraw.Draw(im, "RGBA")
    # 中缝细竖线
    d.line([(W//2-1, 0), (W//2-1, H)], fill=hx("#ffffff")+(120,), width=3)
    ctext(d, 1760, "差一点，就是两个结局", F(46, True), hx(INK))
    return im

# ---------- 输出 ----------
jobs = [
    (render_ai_badge(256), "13_AI标识_透明.png"),
    (render_callback_panel(), "09_回拨三入口面板.png"),
    (render_compare_half("left"), "10_片尾对照底版_左冷.png"),
    (render_compare_half("right"), "11_片尾对照底版_右暖.png"),
    (render_endcard(), "12_片尾警示语底板.png"),
    (render_compare_preview(), "14_片尾对照_合成示意.png"),
]
for im, fn in jobs:
    im.save(os.path.join(OUT, fn), "PNG")

print("OK ->", OUT)
print("font(reg) =", REG_PATH)
print("font(bld) =", BLD_PATH)
for fn in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, fn)
    print("  ", fn, os.path.getsize(p)//1024, "KB")
