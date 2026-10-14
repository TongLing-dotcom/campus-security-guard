# -*- coding: utf-8 -*-
"""用 Shotcut 的 melt 引擎把「人物语音 ＋ 背景音乐 ＋ 电话铃声 ＋ 角色字幕」合成进成片《改3》，
   输出新文件，全程不改动源文件 改3.mp4。

   音频层（★v12.7 新增 BGM 与铃声）：
     A1 人声轨   —— 15 条讯飞配音，按绝对秒数错位混音
     A2 背景音乐 —— 2 首 CC0 曲目（悬念压迫 → 温暖释然），带交叉过渡与自动音量曲线
     A3 音效     —— 原创 iPhone 风格电话铃声（35.542–37.708）
     并用 sidechaincompress 以「人声＋铃声」为触发信号对 BGM 做闪避（ducking）

   用法:
     python _melt_字幕配音合成.py audio     # 只混音轨
     python _melt_字幕配音合成.py mlt       # 只生成 .mlt 工程
     python _melt_字幕配音合成.py render    # 渲染最终 mp4
"""
import io, os, sys, json, subprocess

# ---------- 路径 ----------
PROJ   = r"<PROJECT_ROOT>"
SRCVID = r"<PROJECT_ROOT>/09_源素材与历史成片/改3.mp4"                       # 源文件（只读）
TIMEL  = os.path.join(PROJ, "08_配音", "时间轴_v12.json")
AUDDIR = os.path.join(PROJ, "08_配音")
EXTDIR = os.path.join(PROJ, "08_配音", "外部素材")
SUBDIR = os.path.join(PROJ, "06_导出成片", "字幕")
WORK   = os.path.join(PROJ, "06_导出成片", "_render_tmp")   # ★归档后改为项目内

VERSION = "v12.7"
MLT     = os.path.join(PROJ, "06_导出成片", "真假妈妈_%s_字幕配音工程.mlt" % VERSION)
MIXWAV  = os.path.join(AUDDIR, "audio", "配音音乐混合轨_%s.wav" % VERSION)

FFMPEG  = r"D:/Shotcut/ffmpeg.exe"
FFPROBE = r"D:/Shotcut/ffprobe.exe"
MELT    = r"D:/Shotcut/melt.exe"

FPS = 24
W, H = 1920, 1080

# ---------- 字幕样式（对齐 ASS：思源黑体 CN / 52 / 白 / 黑描边3 / MarginV 150）----------
FONT_FAMILY = "思源黑体 CN"
FONT_SIZE   = 58
OUTLINE     = 3
MARGIN_V    = 150
GEOMETRY    = "0 0 1920 %d 1" % (H - MARGIN_V)

# ---------- ★v12.7 音频编排 ----------
BGM_A   = os.path.join(EXTDIR, "BGM_A_悬念压迫.mp3")     # Abstract Anxiety（CC0）
BGM_B   = os.path.join(EXTDIR, "BGM_B_温暖释然.mp3")     # Nostalgic Piano（CC0）
RING    = os.path.join(EXTDIR, "铃声_iPhone风格_原创_2.17s.wav")

BGM_A_OUT   = 36.20     # BGM A 播出到 36.20s
BGM_A_RAMP  = (18.20, 20.20)   # 音量平滑抬升区间（镜3 施压开始）
BGM_A_LOW   = 0.70      # 低档音量系数（≈ −3.1 dB）
BGM_B_IN    = 34.20     # BGM B 进入时刻（与 A 交叉过渡）
BGM_B_FADE_OUT = (54.30, 56.30)
BGM_A_TARGET_DB = -33.0   # A 段（悬念/压迫）铺底目标 RMS
BGM_B_TARGET_DB = -33.0   # B 段（温暖）铺底目标 RMS
DUCK_DB     = -8.0      # 闪避时额外压低量（校验用）
RING_START  = 35.542
RING_PEAK_DB = -7.0
VOICE_PEAK_DB = -2.5

os.makedirs(WORK, exist_ok=True)


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        print("!! 命令失败:", " ".join(cmd[:8]), "...")
        print(p.stderr[-2000:])
        raise SystemExit(1)
    return (p.stdout or "") + (p.stderr or "")


def vol_detect(path, extra=None):
    """返回 (peak_dB, mean_dB)"""
    cmd = [FFMPEG, "-hide_banner", "-i", path]
    if extra:
        cmd = [FFMPEG, "-hide_banner", "-ss", str(extra[0]), "-t", str(extra[1]), "-i", path]
    cmd += ["-af", "volumedetect", "-f", "null", "-"]
    o = run(cmd)
    pk = mn = None
    for l in o.splitlines():
        if "max_volume" in l:
            pk = float(l.split("max_volume:")[1].replace("dB", "").strip())
        if "mean_volume" in l:
            mn = float(l.split("mean_volume:")[1].replace("dB", "").strip())
    return pk, mn


def rms_db(path):
    o = run([FFMPEG, "-hide_banner", "-i", path, "-af", "astats=metadata=1:reset=0", "-f", "null", "-"])
    for l in o.splitlines():
        if "RMS level dB" in l:
            try:
                return float(l.split(":")[-1].strip())
            except ValueError:
                pass
    # 兜底用 volumedetect 的 mean
    return vol_detect(path)[1]


def load_lines():
    d = json.load(io.open(TIMEL, encoding="utf-8"))
    out = []
    for ln in d["lines"]:
        if str(ln.get("id", "")).startswith("自定义"):
            continue
        if ln.get("start") is None or ln.get("end") is None:
            continue
        f = ln.get("file") or ""
        path = os.path.normpath(os.path.join(AUDDIR, f))
        if not os.path.exists(path):
            print("  跳过（缺音频）:", ln["id"], path)
            continue
        out.append(dict(id=ln["id"], text=ln["text"], start=float(ln["start"]),
                        end=float(ln["end"]), path=path, role=ln.get("role", "")))
    out.sort(key=lambda x: x["start"])
    return out


def load_subs():
    s = io.open(os.path.join(SUBDIR, "真假妈妈_字幕_v12.ass"), encoding="utf-8-sig").read()
    subs = []
    for line in s.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line[len("Dialogue:"):].split(",", 9)
        if len(parts) < 10:
            continue

        def sec(t):
            h, m, rest = t.strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(rest)
        subs.append(dict(start=sec(parts[1]), end=sec(parts[2]),
                         text=parts[9].replace(r"\N", "\n").strip()))
    return subs


# ============================ 音频 ============================

def build_voice(lines, total):
    """A1 人声轨：各句按绝对秒数错位混音，峰值归一到 VOICE_PEAK_DB。"""
    raw = os.path.join(WORK, "voice_raw.wav")
    o1 = os.path.join(WORK, "a1_voice.wav")
    ins, filt = [], []
    for i, ln in enumerate(lines):
        ins += ["-i", ln["path"]]
        ms = int(round(ln["start"] * 1000))
        filt.append("[%d:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    "pan=stereo|c0=c0|c1=c0,adelay=%d|%d[v%d]" % (i, ms, ms, i))
    joined = "".join("[v%d]" % i for i in range(len(lines)))
    filt.append("%samix=inputs=%d:normalize=0:duration=longest,"
                "apad=whole_dur=%.3f,atrim=0:%.3f[m]" % (joined, len(lines), total, total))
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + ins +
        ["-filter_complex", ";".join(filt), "-map", "[m]",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", raw])
    pk, _ = vol_detect(raw)
    gain = round(VOICE_PEAK_DB - pk, 2)
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", raw,
         "-af", "volume=%.2fdB" % gain, "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", o1])
    print("  A1 人声轨: 峰值 %.1f dB → 增益 %+.2f dB → %.1f dB" % (pk, gain, VOICE_PEAK_DB))
    return o1


def _norm_rms(src, dur, target_db, out):
    """把 src 的前 dur 秒按整体 RMS 归一到 target_db，返回 (原RMS, 增益)。"""
    pre = os.path.join(WORK, os.path.splitext(os.path.basename(out))[0] + ".pre.wav")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
         "-af", "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                "pan=stereo|c0=c0|c1=c0,atrim=0:%.3f,asetpts=N/SR/TB" % dur,
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", pre])
    cur = rms_db(pre)
    g = round(target_db - cur, 2)
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", pre,
         "-af", "volume=%.2fdB" % g, "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", out])
    return cur, g


def build_bgm(total):
    """A2 背景音乐轨：A/B 两段**各自按 RMS 归一**后再拼接（保证两段响度一致），
       带交叉过渡与 A 段音量曲线。"""
    a_n = os.path.join(WORK, "bgmA_norm.wav")
    b_n = os.path.join(WORK, "bgmB_norm.wav")
    b_len = total - BGM_B_IN
    ca, ga = _norm_rms(BGM_A, BGM_A_OUT, BGM_A_TARGET_DB, a_n)
    cb, gb = _norm_rms(BGM_B, b_len,     BGM_B_TARGET_DB, b_n)
    print("  A 段归一: RMS %.1f → %.1f dB (增益 %+.2f)" % (ca, BGM_A_TARGET_DB, ga))
    print("  B 段归一: RMS %.1f → %.1f dB (增益 %+.2f)" % (cb, BGM_B_TARGET_DB, gb))

    o2 = os.path.join(WORK, "a2_bgm.wav")
    t0, t1 = BGM_A_RAMP
    f1 = ("[0:a]volume='%.2f+%.2f*clip((t-%.2f)/%.2f,0,1)':eval=frame,"
          "afade=t=in:st=0:d=1.60,"
          "afade=t=out:st=%.2f:d=%.3f,"
          "adelay=0|0[b1]" % (BGM_A_LOW, 1.0 - BGM_A_LOW, t0, t1 - t0,
                              BGM_B_IN, BGM_A_OUT - BGM_B_IN + 0.02))
    f2 = ("[1:a]afade=t=in:st=0:d=2.60,"
          "afade=t=out:st=%.3f:d=%.2f,"
          "adelay=%d|%d[b2]" % (BGM_B_FADE_OUT[0] - BGM_B_IN,
                                BGM_B_FADE_OUT[1] - BGM_B_FADE_OUT[0],
                                int(BGM_B_IN * 1000), int(BGM_B_IN * 1000)))
    f3 = ("[b1][b2]amix=inputs=2:normalize=0:duration=longest,"
          "apad=whole_dur=%.3f,atrim=0:%.3f,"
          "aformat=sample_fmts=fltp:channel_layouts=stereo[mix]" % (total, total))
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", a_n, "-i", b_n,
         "-filter_complex", ";".join([f1, f2, f3]), "-map", "[mix]",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", o2])
    pkb, mnb = vol_detect(o2)
    print("  A2 背景音乐轨: 峰值 %.1f dB / 均值 %.1f dB" % (pkb, mnb))
    return o2


def build_ring(total):
    """A3 音效轨：原创铃声放在 RING_START，峰值归一。"""
    o3 = os.path.join(WORK, "a3_ring.wav")
    pk, _ = vol_detect(RING)
    gain = round(RING_PEAK_DB - pk, 2)
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", RING,
         "-af", "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                "volume=%.2fdB,adelay=%d|%d,apad=whole_dur=%.3f,atrim=0:%.3f"
                % (gain, int(RING_START * 1000), int(RING_START * 1000), total, total),
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", o3])
    print("  A3 电话铃声: 峰值 %.1f dB → 增益 %+.2f dB，落在 %.3f–%.3fs"
          % (pk, gain, RING_START, RING_START + 2.166))
    return o3


def mix_final(a_voice, a_bgm, a_ring, total):
    """闪避 + 三轨合并 + 限幅。
       侧链键 = 人声 ＋ 铃声（谁在响就压 BGM），被压的是 **BGM**，
       人声与铃声本身不做压缩，保证台词与铃声始终清晰。"""
    flt = ("[0:a][2:a]amix=inputs=2:normalize=0:duration=longest,"
           "apad=whole_dur=%.3f,atrim=0:%.3f[key];"
           "[1:a][key]sidechaincompress=threshold=0.030:ratio=8:attack=15:release=600:"
           "makeup=1:level_sc=1.0:mix=0.55[bd];"
           "[0:a][bd][2:a]amix=inputs=3:normalize=0:duration=longest,"
           "alimiter=limit=0.891:attack=5:release=50,"
           "apad=whole_dur=%.3f,atrim=0:%.3f,"
           "aformat=sample_fmts=fltp:channel_layouts=stereo[out]"
           % (total, total, total, total))
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", a_voice, "-i", a_bgm, "-i", a_ring,
         "-filter_complex", flt, "-map", "[out]",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", MIXWAV])
    # 另存一条「闪避后的 BGM」便于校验
    dbg = os.path.join(WORK, "a2_bgm_ducked.wav")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", a_voice, "-i", a_bgm, "-i", a_ring,
         "-filter_complex",
         "[0:a][2:a]amix=inputs=2:normalize=0:duration=longest,"
         "apad=whole_dur=%.3f,atrim=0:%.3f[key];"
         "[1:a][key]sidechaincompress=threshold=0.030:ratio=8:attack=15:release=600:"
         "makeup=1:level_sc=1.0:mix=0.55,apad=whole_dur=%.3f,atrim=0:%.3f[bd]"
         % (total, total, total, total),
         "-map", "[bd]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", dbg])
    pk, mn = vol_detect(MIXWAV)
    print("  最终音轨: %s  (峰值 %.1f dB / 均值 %.1f dB)" % (os.path.basename(MIXWAV), pk, mn))
    return MIXWAV


def mix_audio(lines, total):
    v = build_voice(lines, total)
    b = build_bgm(total)
    r = build_ring(total)
    return mix_final(v, b, r, total)


# ============================ MLT / 渲染 ============================

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _tc(frames):
    s = frames / float(FPS)
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return "%02d:%02d:%06.3f" % (h, m, sec)


def build_mlt(audio_path, subs):
    dur = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", SRCVID]).strip().splitlines()[0]
    total_frames = int(round(float(dur) * FPS))
    last = total_frames - 1

    p = []
    p.append('<?xml version="1.0" encoding="utf-8"?>')
    p.append('<mlt LC_NUMERIC="C" version="7.41.0" title="真假妈妈 %s 字幕配音工程" '
             'root="%s" producer="main_bin">' % (VERSION, esc(os.path.dirname(MLT).replace("\\", "/"))))
    p.append('  <profile description="HD 1080p 24fps" width="1920" height="1080" progressive="1" '
             'sample_aspect_num="1" sample_aspect_den="1" display_aspect_num="16" display_aspect_den="9" '
             'frame_rate_num="24" frame_rate_den="1" colorspace="709"/>')
    p.append('  <producer id="vid" in="0" out="%d">' % last)
    p.append('    <property name="resource">%s</property>' % esc(SRCVID))
    p.append('    <property name="mlt_service">avformat</property>')
    p.append('    <property name="seekable">1</property>')
    p.append('    <property name="audio_index">-1</property>')
    p.append('    <property name="video_index">0</property>')
    p.append('  </producer>')
    p.append('  <producer id="mix" in="0" out="%d">' % last)
    p.append('    <property name="resource">%s</property>' % esc(audio_path.replace("\\", "/")))
    p.append('    <property name="mlt_service">avformat</property>')
    p.append('    <property name="seekable">1</property>')
    p.append('    <property name="audio_index">0</property>')
    p.append('    <property name="video_index">-1</property>')
    p.append('  </producer>')
    p.append('  <tractor id="main" in="0" out="%d">' % last)
    p.append('    <property name="mlt_service">tractor</property>')
    p.append('    <track producer="vid"/>')
    p.append('    <track producer="mix"/>')
    p.append('    <transition id="mixA">')
    p.append('      <property name="mlt_service">mix</property>')
    p.append('      <property name="a_track">0</property>')
    p.append('      <property name="b_track">1</property>')
    p.append('      <property name="always_active">1</property>')
    p.append('    </transition>')
    for i, sb in enumerate(subs):
        fin = int(round(sb["start"] * FPS))
        fout = max(fin + 1, int(round(sb["end"] * FPS)))
        p.append('    <filter id="sub%d" in="%d" out="%d">' % (i + 1, fin, fout))
        p.append('      <property name="mlt_service">dynamictext</property>')
        p.append('      <property name="argument">%s</property>' % esc(sb["text"]))
        p.append('      <property name="family">%s</property>' % esc(FONT_FAMILY))
        p.append('      <property name="size">%d</property>' % FONT_SIZE)
        p.append('      <property name="weight">700</property>')
        p.append('      <property name="fgcolour">#ffffffff</property>')
        p.append('      <property name="olcolour">#000000ff</property>')
        p.append('      <property name="outline">%d</property>' % OUTLINE)
        p.append('      <property name="halign">center</property>')
        p.append('      <property name="valign">bottom</property>')
        p.append('      <property name="geometry">%s</property>' % GEOMETRY)
        p.append('      <property name="pad">0</property>')
        p.append('    </filter>')
    p.append('  </tractor>')
    p.append('  <playlist id="main_bin">')
    p.append('    <property name="xml_retain">1</property>')
    p.append('    <entry producer="main" in="00:00:00.000" out="%s"/>' % _tc(last))
    p.append('  </playlist>')
    p.append('</mlt>')
    io.open(MLT, "w", encoding="utf-8").write("\n".join(p) + "\n")
    print("  .mlt 已生成: %s  (%d 帧, %d 条字幕)" % (MLT, total_frames, len(subs)))
    return total_frames


def render(out_path):
    tmp = os.path.join(WORK, "render_tmp.mlt")
    io.open(tmp, "w", encoding="utf-8").write(io.open(MLT, encoding="utf-8").read())
    run([MELT, tmp,
         "-consumer", "avformat:%s" % out_path,
         "vcodec=libx264", "acodec=aac",
         "crf=17", "preset=medium", "pix_fmt=yuv420p",
         "ar=48000", "ab=192k", "channels=2"])
    print("  渲染完成:", out_path)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    lines = load_lines()
    subs = load_subs()
    total = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                       "-of", "csv=p=0", SRCVID]).strip().splitlines()[0])
    print("台词 %d 条 / 字幕 %d 条 / 全片 %.3fs" % (len(lines), len(subs), total))
    if mode in ("audio", "all"):
        mix_audio(lines, total)
    if mode in ("mlt", "all"):
        build_mlt(MIXWAV, subs)
    if mode in ("render", "all"):
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
            PROJ, "06_导出成片", "真假妈妈_成片_%s_配音音乐字幕_56.3s_1080p.mp4" % VERSION)
        render(out)
