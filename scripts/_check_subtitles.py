# -*- coding: utf-8 -*-
"""校验 .ass / .srt 语法与时间轴（不依赖 ffmpeg 的 libass）。"""
import io, os, sys

D = os.path.dirname(os.path.abspath(__file__))
NL = chr(92) + "N"   # ASS 硬换行标记 \N


def check_ass(p):
    raw = io.open(p, encoding="utf-8").read()
    sec, styles, events = None, [], []
    fmt = efmt = None
    for ln in raw.split("\n"):
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s
            continue
        if not s or s.startswith(";"):
            continue
        if sec == "[V4+ Styles]":
            if s.startswith("Format:"):
                fmt = [x.strip() for x in s[7:].split(",")]
            elif s.startswith("Style:") and fmt:
                styles.append(dict(zip(fmt, [x.strip() for x in s[6:].split(",")])))
        elif sec == "[Events]":
            if s.startswith("Format:"):
                efmt = [x.strip() for x in s[7:].split(",")]
            elif s.startswith("Dialogue:") and efmt:
                events.append(dict(zip(efmt, [x.strip() for x in s[9:].split(",", 9)])))

    print("文件:", os.path.basename(p))
    print("  样式数:", len(styles))
    for st in styles:
        print("    %s | font=%s size=%s Outline=%s MarginV=%s Align=%s"
              % (st["Name"], st["Fontname"], st["Fontsize"],
                 st["Outline"], st["MarginV"], st["Alignment"]))
    print("  事件数:", len(events))
    bad = 0
    for e in events:
        txt = e["Text"]
        parts = txt.split(NL) if NL in txt else [txt]
        for seg in parts:
            if len(seg) > 15:
                print("    !! 超 15 字:", txt)
                bad += 1
    print("  每行<=15字:", "通过" if bad == 0 else "%d 处超标" % bad)
    print("  字段完整:", all(len(e) == 10 for e in events))
    return len(events), bad


def check_srt(p):
    raw = io.open(p, encoding="utf-8-sig").read()
    blocks = [b for b in raw.strip().split("\n\n") if b.strip()]
    print("文件:", os.path.basename(p))
    print("  条数:", len(blocks))

    def tos(t):
        h, m, rest = t.split(":")
        s, ms = rest.split(",") if "," in rest else (rest, "0")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    prev, ok = 0.0, True
    for b in blocks:
        L = b.split("\n")
        a, bb = L[1].split(" --> ")
        a, bb = tos(a), tos(bb)
        if not (a >= prev - 1e-6 and bb > a):
            ok = False
            print("    !! 时间轴异常:", L[0])
        prev = bb
    print("  时间轴递增:", "通过" if ok else "异常")
    return len(blocks), 0 if ok else 1


if __name__ == "__main__":
    VER = sys.argv[1] if len(sys.argv) > 1 else "v12"
    total_bad = 0
    for f in ("真假妈妈_字幕_%s.ass" % VER, "真假妈妈_字幕_%s_NotoSansSC.ass" % VER):
        n, bad = check_ass(os.path.join(D, f))
        total_bad += bad
        print()
    n, bad = check_srt(os.path.join(D, "真假妈妈_字幕_%s.srt" % VER))
    total_bad += bad
    print()
    print("=== 总结:", "全部通过" if total_bad == 0 else "%d 处问题" % total_bad)
    sys.exit(1 if total_bad else 0)
