# -*- coding: utf-8 -*-
"""
字幕生成脚本 · v12.1
单一数据源 = 08_配音/时间轴_v12.json（权威时间码，已对齐成片《改2》实测分段）
规则：只输出「角色对话字幕」，旁白不叠字幕（分镜表 §四 字幕约定）
      跳过「自定义_*」草稿行（无时间码，属 08_配音 的自定义试音，不进成片字幕）
输出：真假妈妈_字幕_v12.srt / .ass / _NotoSansSC.ass
"""
import json, os

BASE = r"<PROJECT_ROOT>"
SRC = os.path.join(BASE, "08_配音", "时间轴_v12.json")
OUT = os.path.join(BASE, "06_导出成片", "字幕")

# ── 读取权威时间轴 ─────────────────────────────────────────────
with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

# 旁白不叠字幕
SKIP_ROLES = {"旁白"}
# 自定义草稿行不进字幕（id 前缀）
SKIP_ID_PREFIX = ("自定义",)

# ── 字幕层文本覆盖（不改动权威 JSON，保持单一数据源可追溯） ──────
TEXT_OVERRIDE = {}

subs = []
for ln in data["lines"]:
    if ln["role"] in SKIP_ROLES:
        continue
    if str(ln["id"]).startswith(SKIP_ID_PREFIX):
        continue
    if ln.get("start") is None or ln.get("end") is None:
        continue          # 待补时间码，不进字幕
    subs.append({
        "role": ln["role"],
        "text": TEXT_OVERRIDE.get(ln["id"], ln["text"]).strip(),
        "start": float(ln["start"]),
        "end": float(ln["end"]),
        "id": ln["id"],
    })

subs.sort(key=lambda x: x["start"])

# ── 样式 ─────────────────────────────────────────────────────
FONT_NAME = "思源黑体 CN"
FONT_FALLBACK = "Noto Sans SC"
FONT_SIZE = 52
PRIMARY = "&H00FFFFFF"      # 白字
OUTLINE = "&H30000000"      # 半透明黑描边
BACK = "&H4D000000"
BORDER = 3
MARGIN_V = 150
ALIGN = 2
LINE_LIMIT = 15          # ★v12.4：12 → 15（校验脚本上限即 15），避免在词中间硬断行

# ── 工具 ─────────────────────────────────────────────────────
def _hard_wrap(text, limit):
    return [text[i:i + limit] for i in range(0, len(text), limit)]

def wrap(text, limit=LINE_LIMIT):
    """按标点优先断行，每行 <= limit 字"""
    if len(text) <= limit:
        return [text]
    best = -1
    for i in range(limit - 1, 0, -1):
        if text[i] in "，。？！、；：,.?!;:":
            best = i + 1
            break
    if best <= 0:
        best = limit
    head, tail = text[:best], text[best:]
    if len(tail) > limit:
        return [head] + _hard_wrap(tail, limit)
    return [head, tail]

def srt_ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def ass_ts(sec):
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

NL = chr(92) + "N"   # ASS 硬换行

# ── 生成 SRT ─────────────────────────────────────────────────
srt_parts = []
for i, s in enumerate(subs, 1):
    body = "\n".join(wrap(s["text"]))
    srt_parts.append(f"{i}\n{srt_ts(s['start'])} --> {srt_ts(s['end'])}\n{body}\n")
srt_txt = "\n".join(srt_parts)

srt_path = os.path.join(OUT, "真假妈妈_字幕_v12.srt")
with open(srt_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
    f.write(srt_txt)

# ── 生成 ASS ─────────────────────────────────────────────────
ASS_HEAD = """[Script Info]
Title: 真假妈妈 · 角色对话字幕 v12
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: 对话,{FONT},{SIZE},{PRIMARY},&H000000FF,{OUTLINE},{BACK},0,0,0,0,100,100,0,0,1,{BORDER},1,{ALIGN},60,60,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def build_ass(font):
    ev = []
    for s in subs:
        body = NL.join(wrap(s["text"]))
        ev.append(f"Dialogue: 0,{ass_ts(s['start'])},{ass_ts(s['end'])},对话,,0,0,0,,{body}")
    head = ASS_HEAD.format(FONT=font, SIZE=FONT_SIZE, PRIMARY=PRIMARY,
                           OUTLINE=OUTLINE, BACK=BACK, BORDER=BORDER,
                           ALIGN=ALIGN, MARGIN_V=MARGIN_V)
    return head + "\n".join(ev) + "\n"

ass_path = os.path.join(OUT, "真假妈妈_字幕_v12.ass")
with open(ass_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(build_ass(FONT_NAME))

ass_fb_path = os.path.join(OUT, "真假妈妈_字幕_v12_NotoSansSC.ass")
with open(ass_fb_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(build_ass(FONT_FALLBACK))

# ── 报告 ─────────────────────────────────────────────────────
print(f"角色对话字幕条数: {len(subs)}")
print(f"{'序号':<4}{'角色':<10}{'时间码':<28}{'时长':<8}{'字数':<5} 文本")
for i, s in enumerate(subs, 1):
    dur = s["end"] - s["start"]
    spd = len(s["text"]) / dur if dur > 0 else 0
    flag = "  <-- 偏快" if spd > 6.5 else ""
    print(f"{i:<4}{s['role']:<10}{srt_ts(s['start'])[:12]:<28}{dur:<8.2f}{len(s['text']):<5} {s['text']}{flag}")

print(f"\n已写出:\n  {srt_path}\n  {ass_path}\n  {ass_fb_path}")
