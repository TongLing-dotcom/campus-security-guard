# -*- coding: utf-8 -*-
"""
自制约 iPhone 风格铃声（原创合成 · 无版权争议）
—— 马林巴/钟琴音色 + 明亮琶音动机，听感即"手机来电"，但旋律与音色均为原创，
   不使用 Apple「倒影/Reflection」「Marimba」等受版权保护的铃声录音。

输出：16bit / 48kHz / 立体声 WAV，默认 2.166s（＝用户指定的 35.542–37.708 区间）
"""
import wave, math, struct, os, sys

SR = 48000
OUT = sys.argv[1] if len(sys.argv) > 1 else "铃声_iPhone风格_原创_2.17s.wav"
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 2.166

# 音名 → 频率
def n(name):
    base = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
            "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    k = name[:-1]; octv = int(name[-1])
    semi = base[k] + (octv + 1) * 12      # A4=440 → midi 69
    return 440.0 * (2.0 ** ((semi - 69) / 12.0))

# ★ 原创动机：E 大调琶音上行后回落（7 音），非任何具体版权旋律
MOTIF = ["B6", "E7", "C#7", "G#6", "E6", "G#6", "B6"]
STEP = 0.15           # 音间距（秒）
REST = 0.033          # 一个循环后的停顿
CYCLE = len(MOTIF) * STEP + REST          # = 1.083s
# 打击感/音色参数（马林巴 ≈ 正弦 + 少量奇次泛音 + 快速衰减）
PARTIALS = [(1.00, 1.000, 0.42),   # (频率比, 振幅, 衰减时间s)
            (2.00, 0.45, 0.30),
            (3.01, 0.22, 0.20),
            (4.20, 0.10, 0.13),
            (5.43, 0.05, 0.09)]

N = int(SR * DUR)
bufL = [0.0] * (N + SR)
bufR = [0.0] * (N + SR)

t = 0.0
while t < DUR:
    for i, name in enumerate(MOTIF):
        start = t + i * STEP
        if start >= DUR:
            continue
        f = n(name)
        # 每条音都有极微小的音高/音量随机化，避免"电子味"
        det = 1.0 + 0.0008 * math.sin(2.602 * (i + 3.1 * t))
        amp = 0.92 + 0.08 * math.sin(1.7 * i + 2.1 * t)
        i0 = int(start * SR)
        L = int(min(1.05, DUR - start) * SR)
        for s in range(L):
            x = s / SR
            v = 0.0
            for ratio, pa, tau in PARTIALS:
                v += pa * math.exp(-x / tau) * math.sin(2 * math.pi * f * det * ratio * x)
            # 起音瞬态（木槌击打感）
            if x < 0.006:
                v += 0.35 * math.sin(2 * math.pi * f * 2.6 * x) * (1 - x / 0.006)
            v *= amp * 0.30
            # 循环末尾整体收尾
            g = 1.0
            if start + x > DUR - 0.14:
                g = max(0.0, (DUR - start - x) / 0.14)
            k = i0 + s
            bufL[k] += v * g
            bufR[k + int(0.008 * SR) if k + int(0.008 * SR) < len(bufR) else k] += v * g * 0.96
    t += CYCLE

# 归一 + 软限幅（tanh），并做 6ms 淡入/120ms 淡出
mx = max(1e-9, max(max(abs(v) for v in bufL[:N]), max(abs(v) for v in bufR[:N])))
g = 0.86 / mx
data = bytearray()
for s in range(N):
    for ch in (bufL, bufR):
        v = math.tanh(ch[s] * g * 1.15) * 0.92
        e = 1.0
        if s < int(0.006 * SR):
            e = s / (0.006 * SR)
        elif s > N - int(0.120 * SR):
            e = max(0.0, (N - s) / (0.120 * SR))
        data += struct.pack("<h", int(max(-1.0, min(1.0, v * e)) * 32767))

w = wave.open(OUT, "wb")
w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes(bytes(data)); w.close()
print("✅ 已生成:", OUT, "| %.3fs / %d Hz / 立体声 / %d 字节" % (DUR, SR, len(data)))
