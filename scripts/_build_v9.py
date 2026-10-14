# -*- coding: utf-8 -*-
"""
《真假妈妈》成片合成脚本 v9（横屏 1920x1080 / 24fps）
========================================================
在已有 AI 素材基础上做「电影级收尾」：
  1) 片头信息层（0:00-0:02 淡入淡出，1080p 重绘，替代模糊竖屏素材）
  2) 逐镜微调（镜3 反色勾边、镜5/6 冷调压色、镜1 去水印羽化）
  3) 镜7 尾部 1s 渐黑 → 镜8 片尾卡三段式（对照组 / 黑场 / 警示语＋AI标识）
  4) 音效层合成（正弦音效 + 环境底噪，全部自适应生成，无版权风险）
  5) 硬字幕：仅角色对话（V10 中文字体）

用法: python _build_v9.py [步骤名]   不带参数则跑全部
"""
import os, sys, math, subprocess, struct, wave, shutil

# ---------------- 路径与常量 ----------------
ROOT = r"D:/WorkBuddy/反诈短视频项目"
FF = r"ffmpeg"
FONT = "C\\:/Windows/Fonts/msyh.ttc"      # 预览用；正式参赛版须替换为思源黑体
UI = ROOT + "/03_UI素材/png"
SRC = ROOT + "/02_生成视频"
OUT = ROOT + "/06_导出成片"
WORK = ROOT + "/07_脚本/_work"

W, H, FPS = 1920, 1080, 24
FONT_KAI = "C\\:/Windows/Fonts/simkai.ttf"

os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def run(args, tag=""):
    r = subprocess.run([FF, "-y"] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("[FAIL]", tag or args[-1])
        print(r.stderr[-1500:])
        raise SystemExit(1)
    print("[ OK ]", tag or args[-1])
    return r


# =====================================================================
# 步骤 1：片头信息层（0:00-0:02）
# =====================================================================
def step_title():
    """生成 2s 片头信息层（透明底 PNG 序列 -> 带 alpha 的 mp4）"""
    frames = int(2.0 * FPS)
    seq = WORK + "/title"
    if os.path.isdir(seq):
        shutil.rmtree(seq)
    os.makedirs(seq)

    t1 = "真 假 妈 妈"
    t2 = "本作品为AI辅助制作"
    t3 = "曹家洋 · 河南财经政法大学"

    # 主标题用较大字号；淡入 0.2s / 保持 1.6s / 淡出 0.2s
    for i in range(frames):
        t = i / FPS
        if t < 0.2:
            a = t / 0.2
        elif t > 1.8:
            a = max(0.0, (2.0 - t) / 0.2)
        else:
            a = 1.0
        alpha = int(255 * a)

        vf = (
            # 半透明暗角底 + 三行文字
            f"drawbox=x=0:y=0:w={W}:h={H}:color=black@0.38:t=fill,"
            f"drawtext=fontfile='{FONT}':text='{t1}':fontsize=112:fontcolor=white@{a:.3f}:"
            f"x=(w-text_w)/2:y=h/2-190:borderw=3:bordercolor=black@0.65,"
            f"drawbox=x=(w-360)/2:y=h/2-40:w=360:h=4:color=white@{a*0.85:.3f}:t=fill,"
            f"drawtext=fontfile='{FONT}':text='{t2}':fontsize=42:fontcolor=white@{a*0.9:.3f}:"
            f"x=(w-text_w)/2:y=h/2+20,"
            f"drawtext=fontfile='{FONT}':text='{t3}':fontsize=40:fontcolor=white@{a*0.82:.3f}:"
            f"x=(w-text_w)/2:y=h/2+100"
        )
        run(["-f", "lavfi", "-i", f"color=c=black@0.0:s={W}x{H}:d=0.05:r=24",
             "-vf", vf, "-frames:v", "1",
             f"{seq}/t_{i:04d}.png"], tag=f"title frame {i}")

    # PNG 序列 -> 带 alpha 的 mov (qtrle)
    run(["-framerate", "24", "-i", f"{seq}/t_%04d.png",
         "-c:v", "qtrle", "-pix_fmt", "argb",
         f"{WORK}/title_layer.mov"], tag="title layer")


# =====================================================================
# 步骤 2：音效生成（正弦/噪声合成，无版权）
# =====================================================================
SR = 48000


def write_wav(path, samples):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))


def env(i, n, attack=0.01, release=0.3):
    """简单 AD 包络"""
    a = int(n * attack) or 1
    r = int(n * release) or 1
    if i < a:
        return i / a
    if i > n - r:
        return max(0.0, (n - i) / r)
    return 1.0


def tone(freq, dur, amp=0.3, attack=0.01, release=0.3, harm=False):
    n = int(dur * SR)
    out = []
    for i in range(n):
        t = i / SR
        s = math.sin(2 * math.pi * freq * t)
        if harm:
            s += 0.35 * math.sin(2 * math.pi * freq * 2 * t)
        s *= amp * env(i, n, attack, release)
        out.append(s)
    return out


def silence(dur):
    return [0.0] * int(dur * SR)


def mix(*tracks):
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return out


def step_sfx():
    import random
    random.seed(7)
    d = WORK + "/sfx"
    os.makedirs(d, exist_ok=True)

    # 1) 手机震动 (0.6s)
    n = int(0.6 * SR)
    v = []
    for i in range(n):
        t = i / SR
        buzz = 0.35 * math.sin(2 * math.pi * 62 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 24 * t))
        v.append(buzz * env(i, n, 0.02, 0.4))
    write_wav(f"{d}/vibrate.wav", v)

    # 2) 来电铃声 (2.4s)：两短一长
    ring = tone(880, 0.4, 0.16, 0.01, 0.5, harm=True) + silence(0.25)
    ring += tone(880, 0.4, 0.16, 0.01, 0.5, harm=True) + silence(0.25)
    ring += tone(660, 1.0, 0.15, 0.02, 0.6, harm=True) + silence(0.4)
    write_wav(f"{d}/ring.wav", ring)

    # 3) 接通音 (0.25s)
    write_wav(f"{d}/connect.wav", tone(1320, 0.25, 0.18, 0.01, 0.7, harm=True))

    # 4) 预警提示音 (1.2s)：三声急促高音
    p = []
    for _ in range(3):
        p += tone(1560, 0.12, 0.24, 0.005, 0.5, harm=True) + silence(0.12)
    p += silence(0.24)
    write_wav(f"{d}/alert.wav", p)

    # 5) 挂断音 (0.3s)：下行短音
    h = tone(900, 0.3, 0.2, 0.01, 0.6)
    h = [s * (1 - 0.4 * i / len(h)) for i, s in enumerate(h)]
    write_wav(f"{d}/hangup.wav", h)

    # 6) 回铃音 (3.0s)：嘟—嘟—
    rb = silence(0.1) + tone(450, 0.8, 0.14, 0.02, 0.35) + silence(1.2) \
         + tone(450, 0.8, 0.14, 0.02, 0.35) + silence(0.1)
    write_wav(f"{d}/ringback.wav", rb)

    # 7) 心跳 (2.0s)：低频双击
    n = int(2.0 * SR)
    hb = [0.0] * n
    for start in (0.0, 1.0):
        for k, (f, a, dur) in enumerate([(58, 0.55, 0.16), (46, 0.35, 0.22)]):
            s0 = int((start + k * 0.18) * SR)
            m = int(dur * SR)
            for i in range(m):
                if s0 + i < n:
                    t = i / SR
                    hb[s0 + i] += a * math.sin(2 * math.pi * f * t) * env(i, m, 0.02, 0.75)
    write_wav(f"{d}/heartbeat.wav", hb)

    # 8) 低频紧张弦乐底噪 (10s，循环用)
    n = int(10.0 * SR)
    drone = []
    for i in range(n):
        t = i / SR
        s = 0.0
        for f, a in ((55, 0.5), (82.5, 0.3), (110, 0.2), (164.8, 0.1)):
            s += a * math.sin(2 * math.pi * f * t + 0.6 * math.sin(2 * math.pi * 0.13 * t))
        s *= 0.10 * (0.75 + 0.25 * math.sin(2 * math.pi * 0.07 * t))
        drone.append(s)
    write_wav(f"{d}/drone.wav", drone)

    # 9) 黑屏"啪" (0.18s)：白噪脉冲
    n = int(0.18 * SR)
    pd = []
    for i in range(n):
        pd.append(random.uniform(-1, 1) * 0.5 * env(i, n, 0.005, 0.9))
    write_wav(f"{d}/blackout.wav", pd)

    # 10) 键盘轻敲 (1.6s)
    kb = [0.0] * int(1.6 * SR)
    for k in range(9):
        s0 = int((0.08 * k + random.uniform(0, 0.05)) * SR)
        m = int(0.045 * SR)
        for i in range(m):
            if s0 + i < len(kb):
                kb[s0 + i] += random.uniform(-1, 1) * 0.22 * env(i, m, 0.02, 0.85)
    write_wav(f"{d}/keyboard.wav", kb)

    # 11) 房间底噪 (6s)
    n = int(6.0 * SR)
    amb = []
    lp = 0.0
    for i in range(n):
        lp = lp * 0.985 + random.uniform(-1, 1) * 0.015
        amb.append(lp * 0.5)
    write_wav(f"{d}/room.wav", amb)

    # 12) 钢琴单音收束 (3s)：C 大三和弦泛音衰减
    n = int(3.0 * SR)
    pn = []
    for i in range(n):
        t = i / SR
        s = 0.0
        for f, a, dec in ((523.25, 1.0, 1.6), (1046.5, 0.42, 2.2), (1568.0, 0.2, 2.8), (2093, 0.09, 3.2)):
            s += a * math.sin(2 * math.pi * f * t) * math.exp(-dec * t)
        pn.append(s * 0.16)
    write_wav(f"{d}/piano.wav", pn)

    print("[ OK ] sfx 全部生成")


# =====================================================================
# 步骤 3：逐镜视觉微调 + 镜7 渐黑
# =====================================================================
def step_shots():
    d = WORK + "/shots"
    os.makedirs(d, exist_ok=True)

    # 镜1：0-2s 叠片头信息层；并羽化左侧噪声水印
    run(["-i", f"{SRC}/shot01_v8_landscape/镜1_横屏_v3_侧拍上滑接听.mp4",
         "-i", f"{WORK}/title_layer.mov",
         "-filter_complex",
         "[0:v]trim=0:5.04,setpts=PTS-STARTPTS,scale=1920:1080,setsar=1,"
         "crop=1800:1080:60:0,pad=1920:1080:60:0:black,format=rgba[b];"
         "[1:v]format=rgba[o];[b][o]overlay=0:0:format=auto,format=yuv420p[v]",
         "-map", "[v]", "-r", "24", "-c:v", "libx264", "-crf", "17",
         "-pix_fmt", "yuv420p", f"{d}/s01.mp4"], tag="shots s01")

    # 镜2 分屏（已合成，直接转码）
    run(["-i", f"{SRC}/shot02/镜2_分屏.mp4", "-vf", "scale=1920:1080,setsar=1",
         "-r", "24", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{d}/s02.mp4"], tag="shots s02")

    # 镜3：反色勾边（抑制"类 Windows 界面"的可辨识度与外国面孔辨识度）
    run(["-i", f"{SRC}/shot03/镜3_采集合成_图生.mp4",
         "-vf", "scale=1920:1080,setsar=1,negate,hue=h=178:s=1.35,eq=contrast=1.06:brightness=-0.015",
         "-r", "24", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{d}/s03.mp4"], tag="shots s03")

    # 镜4 分屏：冷调压色
    run(["-i", f"{SRC}/shot04_分屏.mp4",
         "-vf", "scale=1920:1080,setsar=1,eq=contrast=1.08:saturation=0.88:brightness=-0.012",
         "-r", "24", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{d}/s04.mp4"], tag="shots s04")

    # 镜5：冷调压色 + 右侧压暗（为 UI 留出对比）
    run(["-i", f"{SRC}/shot05/镜5_预警打断_图生.mp4",
         "-vf", "scale=1920:1080,setsar=1,eq=contrast=1.10:saturation=0.80:brightness=-0.02",
         "-r", "24", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{d}/s05.mp4"], tag="shots s05")

    # 镜6：冷调偏暖过渡
    run(["-i", f"{SRC}/shot06/镜6_回拨核实_图生.mp4",
         "-vf", "scale=1920:1080,setsar=1,eq=contrast=1.05:saturation=0.95",
         "-r", "24", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{d}/s06.mp4"], tag="shots s06")

    # 镜7：尾 1s 渐黑（fade out）
    run(["-i", f"{SRC}/shot07/镜7_接通真妈妈_图生.mp4",
         "-vf", f"scale=1920:1080,setsar=1,fade=t=out:st=4.04:d=1.0:color=black",
         "-r", "24", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{d}/s07.mp4"], tag="shots s07")


# =====================================================================
# 步骤 4：镜8 片尾卡三段式
# =====================================================================
def step_ending():
    d = WORK + "/shots"
    seg = WORK + "/ending"
    os.makedirs(seg, exist_ok=True)

    L = f"{UI}/10_片尾对照底版_左冷.png"
    R = f"{UI}/11_片尾对照底版_右暖.png"
    BASE = f"{UI}/12_片尾警示语底板.png"
    AI = f"{UI}/13_AI标识_透明.png"

    # ---- 8a 对照组（2.5s）：左冷 / 右暖 并置 + 标注文字 ----
    # 底版为 540x1920 竖屏半幅素材，取手部区域（y 620~1700）裁为 540x1080 -> scale 到 960x1080
    lab = ("drawtext=fontfile='%s':text='差点转出去':fontsize=40:fontcolor=white@0.95:"
           "x=(w/4-text_w/2):y=h-108,"
           "drawtext=fontfile='%s':text='多打一个电话':fontsize=40:fontcolor=white@0.95:"
           "x=(3*w/4-text_w/2):y=h-108"
           % (FONT, FONT))
    run(["-loop", "1", "-t", "2.5", "-i", L, "-loop", "1", "-t", "2.5", "-i", R,
         "-filter_complex",
         "[0:v]crop=540:1080:0:620,scale=880:1080,setsar=1,"
         "pad=960:1080:40:0:color=0x08111f[a];"
         "[1:v]crop=540:1080:0:620,scale=880:1080,setsar=1,"
         "pad=960:1080:40:0:color=0x1a1008[b];"
         "[a][b]hstack=inputs=2,drawbox=x=958:y=0:w=4:h=1080:color=white@0.55:t=fill,"
         + lab + ",format=yuv420p[v]",
         "-map", "[v]", "-r", "24", "-c:v", "libx264", "-crf", "17",
         "-pix_fmt", "yuv420p", f"{seg}/8a.mp4"], tag="ending 8a")

    # ---- 8b 黑场留白（1.0s）----
    run(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:d=1.0:r=24",
         "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{seg}/8b.mp4"], tag="ending 8b")

    # ---- 8c 警示语浮现（2.5s）：纯黑底 + 重绘三级文字 + AI 标识 ----
    zhuti = "涵育网络素养 共建清朗空间"
    jingshi = "眼见未必真，转账先核实"

    vf = (
        f"[1:v]scale=140:-1,setsar=1,format=rgba,fade=t=in:st=1.2:d=0.5:alpha=1[ai];"
        f"[0:v][ai]overlay=x={W}-210:y={H}-190:format=auto[bg];"
        f"[bg]drawtext=fontfile='{FONT}':text='{jingshi}':fontsize=112:fontcolor=white:"
        f"x=(w-text_w)/2:y=h/2-160:"
        f"alpha='if(lt(t,0.1),0,min(1,(t-0.1)/1.0))':borderw=3:bordercolor=black@0.4,"
        f"drawbox=x=(w-320)/2:y=h/2-10:w=320:h=3:color=white@0.45:t=fill:"
        f"enable='gte(t,0.9)',"
        f"drawtext=fontfile='{FONT}':text='{zhuti}':fontsize=50:fontcolor=white:"
        f"x=(w-text_w)/2:y=h/2+40:"
        f"alpha='if(lt(t,0.9),0,min(1,(t-0.9)/0.9))',"
        f"drawtext=fontfile='{FONT}':text='本作品为AI辅助制作':fontsize=36:fontcolor=white@0.86:"
        f"x=(w-text_w)/2:y=h/2+170:alpha='if(lt(t,1.4),0,min(1,(t-1.4)/0.6))',"
        f"format=yuv420p[v]"
    )
    run(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:d=2.5:r=24",
         "-loop", "1", "-t", "2.5", "-i", AI,
         "-filter_complex", vf, "-map", "[v]", "-r", "24",
         "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
         f"{seg}/8c.mp4"], tag="ending 8c")

    # ---- 合成镜8（6s）----
    with open(f"{seg}/list.txt", "w", encoding="utf-8") as f:
        f.write(f"file '{seg}/8a.mp4'\n")
        f.write(f"file '{seg}/8b.mp4'\n")
        f.write(f"file '{seg}/8c.mp4'\n")
    run(["-f", "concat", "-safe", "0", "-i", f"{seg}/list.txt",
         "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "24",
         f"{d}/s08.mp4"], tag="ending s08")


# =====================================================================
# 步骤 5：音轨合成
# =====================================================================
def step_audio():
    d = WORK + "/sfx"
    a = WORK + "/audio"
    os.makedirs(a, exist_ok=True)

    # 时间轴（秒）：每镜 5s 起
    # s01 0-5 / s02 5-10 / s03 10-15 / s04 15-20 / s05 20-25 / s06 25-30 / s07 30-35 / s08 35-41
    filters = []
    inputs = []          # 输入参数（非局部）
    idx = 0

    def add(path, delay, vol=1.0, loop=False):
        """返回输入序号"""
        nonlocal idx
        if loop:
            inputs.extend(["-stream_loop", "-1", "-i", path])
        else:
            inputs.extend(["-i", path])
        i = idx
        idx += 1
        filters.append(
            f"[{i}:a]volume={vol},adelay={int(delay*1000)}|{int(delay*1000)},"
            f"apad[a{i}]")
        return i

    # 环境底噪铺满全程（41s）
    add(f"{d}/room.wav", 0, 0.9, loop=True)
    # 紧张弦乐 0-35s
    add(f"{d}/drone.wav", 0, 0.85, loop=True)
    # 镜1：震动 2.0s / 铃声 2.2s / 接通 3.4s
    add(f"{d}/vibrate.wav", 2.0, 1.0)
    add(f"{d}/ring.wav", 2.2, 0.85)
    add(f"{d}/connect.wav", 3.6, 0.8)
    # 镜3：键盘 11.0s
    add(f"{d}/keyboard.wav", 11.0, 0.75)
    # 镜4：心跳 15.6s 起
    add(f"{d}/heartbeat.wav", 15.6, 0.9)
    # 镜5：预警 20.2s / 挂断+黑屏 21.6s
    add(f"{d}/alert.wav", 20.2, 1.0)
    add(f"{d}/hangup.wav", 21.6, 0.9)
    add(f"{d}/blackout.wav", 21.9, 1.0)
    # 镜6：回铃音 26.4s
    add(f"{d}/ringback.wav", 26.4, 0.9)
    # 镜7：接通音 30.6s
    add(f"{d}/connect.wav", 30.6, 0.7)
    # 镜8c：钢琴 38.4s
    add(f"{d}/piano.wav", 38.4, 1.0)

    fc = ";".join(filters)
    fc += ";" + "".join(f"[a{i}]" for i in range(idx)) + \
          f"amix=inputs={idx}:duration=longest:normalize=0[mix];" \
          f"[mix]atrim=0:41,afade=t=out:st=39.6:d=1.4,volume=1.6[aout]"

    run(inputs + ["-filter_complex", fc, "-map", "[aout]",
                  "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                  f"{a}/mix.m4a"], tag="audio mix")


# =====================================================================
# 步骤 6：拼片 + 字幕后烧
# =====================================================================
SUBS = [
    # (开始, 结束, 文本)  仅角色对话（镜2/4/7）；镜6 无台词，仅系统 UI
    (5.30, 7.70, "小宇……妈出事了，你先帮帮妈。"),
    (7.90, 9.70, "妈？你怎么了？你在哪儿？"),
    (9.90, 12.30, "妈在外地，不方便细说。你先给妈转点钱，回头再说。"),
    (12.50, 14.70, "出什么事了？你说明白我才能帮你啊。"),
    (15.30, 17.70, "来不及了……别问那么多，也别告诉别人。"),
    (17.90, 19.00, "小宇，真的来不及了！妈这条命，就靠你了……"),
    (19.15, 20.30, "妈，你别急，我这就……"),
    (31.60, 33.60, "小宇？怎么啦？"),
    (33.70, 35.20, "妈……你没事就好。"),
]


def step_final():
    d = WORK + "/shots"
    a = WORK + "/audio"

    # 拼接视频
    lst = WORK + "/final_list.txt"
    with open(lst, "w", encoding="utf-8") as f:
        for n in ("s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08"):
            f.write(f"file '{d}/{n}.mp4'\n")
    run(["-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "24",
         f"{WORK}/video_nosub.mp4"], tag="concat video")

    # 字幕链（下轨）：仅角色对话
    parts = []
    for k, (s, e, txt) in enumerate(SUBS):
        esc = txt.replace("'", "\u2019").replace(":", "\\:")
        parts.append(
            f"drawtext=fontfile='{FONT}':text='{esc}':fontsize=52:fontcolor=white:"
            f"x=(w-text_w)/2:y=h-150:borderw=3:bordercolor=black@0.75:"
            f"box=1:boxcolor=black@0.30:boxborderw=16:"
            f"enable='between(t,{s},{e})'")
    vf = ",".join(parts)

    run(["-i", f"{WORK}/video_nosub.mp4", "-i", f"{a}/mix.m4a",
         "-vf", vf,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow",
         "-pix_fmt", "yuv420p", "-r", "24",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
         f"{OUT}/真假妈妈_成片_v9_横屏1080p.mp4"], tag="final mux")


if __name__ == "__main__":
    steps = sys.argv[1:] or ["title", "sfx", "shots", "ending", "audio", "final"]
    for s in steps:
        print(f"\n{'='*50}\n步骤: {s}\n{'='*50}")
        {"title": step_title, "sfx": step_sfx, "shots": step_shots,
         "ending": step_ending, "audio": step_audio, "final": step_final}[s]()
    print("\n全部完成")
