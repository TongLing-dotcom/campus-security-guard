#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把讯飞合成的配音（+原声/音效）合进视频 —— 《真假妈妈》配音入片

三种用法
  1) 单轨简单合成（最快验证）
       python mux_to_video.py simple --video 成片.mp4 --audio 旁白.mp3 --out out.mp4 \\
              --mode mix --delay 5.3 --bg-volume 0.15
  2) 按时间轴精确铺多轨配音（正式合成用）
       python mux_to_video.py timeline --video 成片.mp4 --timeline 时间轴_v12.json --out out.mp4 \\
              --keep-original --bg-volume 0.15
  3) 由配音台词表一键生成时间轴模板（再手工微调时间码）
       python mux_to_video.py template --cast 配音台词表_v12.json \\
              --audiodir audio --out 时间轴_v12.json

要点
  · 视频流一律 `-c:v copy` 不重编码；音频统一重采样到 48k 立体声后 adelay 对位、amix 叠加。
  · 末尾 `apad` + `-shortest`：配音比画面短时自动补静音，成片时长严格等于视频时长。
  · amix 用 normalize=0，各路音量按输入值原样相加，不被自动衰减。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from xfyun_tts import load_config, resolve_tool, duration_of
except ImportError:                                     # pragma: no cover
    raise SystemExit(f"找不到 xfyun_tts.py，请与本脚本放在同一目录（当前 {HERE}）")


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #

def has_audio(path: Path, cfg: dict) -> bool:
    try:
        out = subprocess.run(
            [resolve_tool("ffprobe", cfg), "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return bool(out)
    except Exception:                                   # noqa: BLE001
        return False


def run(cmd: list[str]) -> None:
    print("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-25:])
        raise RuntimeError(f"ffmpeg 失败（exit {proc.returncode}）：\n{tail}")


def channels_of(path: Path, cfg: dict) -> int:
    """读取音频声道数；失败返回 2。"""
    try:
        out = subprocess.run(
            [resolve_tool("ffprobe", cfg), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=channels", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return int(out) if out.isdigit() else 2
    except Exception:                                   # noqa: BLE001
        return 2


def norm_chain(idx: int, path: Path, cfg: dict) -> str:
    """
    把第 idx 路输入统一成 48k 立体声 fltp。

    单声道用 pan 原地复制到左右两轨（0 dB 增益）。若交给 aformat 自动上混，
    swresample 的默认重矩阵会给每声道乘 0.7071（−3 dB），配音会白白变小。
    """
    base = f"[{idx}:a]aresample=48000"
    if channels_of(path, cfg) == 1:
        return base + ",pan=stereo|c0=c0|c1=c0"
    return base + ",aformat=sample_fmts=fltp:channel_layouts=stereo"


# --------------------------------------------------------------------------- #
# simple：单条音轨
# --------------------------------------------------------------------------- #

def cmd_simple(args, cfg) -> int:
    video, audio, out = Path(args.video), Path(args.audio), Path(args.out)
    for p in (video, audio):
        if not p.exists():
            raise SystemExit(f"文件不存在：{p}")

    delay = int(round(args.delay * 1000))
    parts = [f"{norm_chain(1, audio, cfg)},adelay={delay}:all=1,"
             f"volume={args.vo_volume}[vo]"]
    tail = "[vo]"
    keep = args.mode == "mix" and has_audio(video, cfg)
    if args.mode == "mix" and not keep:
        print("提示：视频无音轨，自动按 replace 处理。")
    if keep:
        parts.append(f"{norm_chain(0, video, cfg)},volume={args.bg_volume}[bg]")
        parts.append("[bg][vo]amix=inputs=2:normalize=0:dropout_transition=0[m]")
        tail = "[m]"
    parts.append(f"{tail}apad[out]")

    cmd = [resolve_tool("ffmpeg", cfg), "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video), "-i", str(audio),
           "-filter_complex", ";".join(parts),
           "-map", "0:v", "-map", "[out]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", str(out)]
    run(cmd)
    print(f"\n✅ 输出：{out}  {duration_of(out, cfg):.2f}s")
    return 0


# --------------------------------------------------------------------------- #
# timeline：多轨精确对位
# --------------------------------------------------------------------------- #

def cmd_timeline(args, cfg) -> int:
    video, out = Path(args.video), Path(args.out)
    if not video.exists():
        raise SystemExit(f"视频不存在：{video}")

    data = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
    lines = data.get("lines") if isinstance(data, dict) else data
    if not lines:
        raise SystemExit("时间轴文件需含 lines 数组。")

    base = Path(args.timeline).resolve().parent
    tracks = []
    for i, ln in enumerate(lines, 1):
        fp = Path(ln["file"])
        if not fp.is_absolute():
            for cand in (base / fp, base / args.audiodir / fp.name, Path(args.audiodir) / fp.name):
                if cand.exists():
                    fp = cand
                    break
        if not fp.exists():
            print(f"⚠️  跳过（找不到音频）：{ln.get('id', i)} → {ln['file']}")
            continue
        start = float(ln.get("start", 0))
        end = ln.get("end")
        if end is not None:                      # 给了结束时间 → 超长自动截断
            dur = duration_of(fp, cfg)
            if dur and dur > float(end) - start + 0.001:
                print(f"⚠️  {ln.get('id', i)} 音频 {dur:.2f}s 超过槽位 "
                      f"{float(end) - start:.2f}s，将截断（建议调 speed 重新合成）")
        tracks.append({"id": ln.get("id", f"t{i}"), "file": fp, "start": start,
                       "volume": float(ln.get("volume", 1.0)),
                       "end": float(end) if end is not None else None,
                       "text": ln.get("text", "")})

    if not tracks:
        raise SystemExit("没有可用音轨。")

    inputs = ["-i", str(video)]
    for t in tracks:
        inputs += ["-i", str(t["file"])]

    parts, labels = [], []
    for i, t in enumerate(tracks, start=1):
        # ★ 顺序要紧：先 atrim 截断，再 adelay 定位。
        #   反过来的话 atrim=0:DUR 切掉的是 adelay 补的前导静音，整条配音会变成无声。
        chain = norm_chain(i, t["file"], cfg)
        if t["end"] is not None:
            chain += f",atrim=0:{max(0.01, t['end'] - t['start']):.3f}"
        chain += f",adelay={int(round(t['start'] * 1000))}:all=1"
        chain += f",volume={t['volume']}[a{i}]"
        parts.append(chain)
        labels.append(f"[a{i}]")

    if len(labels) == 1:
        parts.append(f"{labels[0]}anull[mix]")
    else:
        parts.append("".join(labels) +
                     f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0[mix]")

    keep = args.keep_original and has_audio(video, cfg)
    if args.keep_original and not keep:
        print("提示：视频无音轨，忽略 --keep-original。")
    tail = "[mix]"
    if keep:
        parts.append(f"{norm_chain(0, video, cfg)},volume={args.bg_volume}[bg]")
        parts.append("[bg][mix]amix=inputs=2:normalize=0:dropout_transition=0[pre]")
        tail = "[pre]"
    parts.append(f"{tail}apad[out]")

    cmd = [resolve_tool("ffmpeg", cfg), "-y", "-hide_banner", "-loglevel", "error",
           *inputs, "-filter_complex", ";".join(parts),
           "-map", "0:v", "-map", "[out]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
           "-movflags", "+faststart", str(out)]
    run(cmd)

    print(f"\n铺入 {len(tracks)} 条配音：")
    for t in sorted(tracks, key=lambda x: x["start"]):
        print(f"  {t['start']:>7.2f}s  {t['id']:<16} {Path(t['file']).name}")
    print(f"\n✅ 输出：{out}  {duration_of(out, cfg):.2f}s")
    return 0


# --------------------------------------------------------------------------- #
# template：由台词表生成时间轴模板
# --------------------------------------------------------------------------- #

_TC = re.compile(r"(\d+):(\d+(?:\.\d+)?)")


def _parse_tc(s: str) -> float | None:
    m = _TC.search(s or "")
    if not m:
        return None
    return int(m.group(1)) * 60 + float(m.group(2))


def cmd_template(args, cfg) -> int:
    lines, missing, seen = [], [], set()
    for cast_path in args.cast:
        cast = json.loads(Path(cast_path).read_text(encoding="utf-8"))
        if isinstance(cast, list):
            cast = {"lines": cast}
        for ln in cast.get("lines", []):
            if isinstance(ln, str):
                ln = {"text": ln}
            ident = str(ln.get("id") or f"line{len(lines) + 1:03d}")
            if ident in seen:                      # 允许后一份文件覆盖同名条目
                lines = [x for x in lines if x["id"] != ident]
            seen.add(ident)
            mp3 = Path(args.audiodir) / f"{ident}.mp3"
            if ln.get("start") is not None:
                start = float(ln["start"])
            else:
                start = _parse_tc(ln.get("timecode", ""))
            if start is None:
                start = 0.0
                missing.append(ident)
            lines.append({"id": ident, "role": ln.get("role", ""),
                          "shot": ln.get("shot", ""), "text": ln.get("text", ""),
                          "start": round(start, 3),
                          "end": float(ln["end"]) if ln.get("end") is not None else None,
                          "volume": 1.0, "file": str(mp3)})

    lines.sort(key=lambda x: x["start"])
    data = {
        "_说明": "配音时间轴：start/end 为成片绝对秒数。改完直接跑 timeline 子命令。",
        "_来源台词表": [str(Path(c)) for c in args.cast],
        "_音频目录": str(args.audiodir),
        "_待补时间码": missing,
        "lines": lines,
    }
    out = Path(args.out)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 时间轴已生成：{out}")
    print(f"   共 {len(lines)} 条（按 start 排序）；{len(missing)} 条无时间码，start=0 需手工填写：{missing}")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="《真假妈妈》配音入视频")
    p.add_argument("--config", help="xfyun_config.json 路径")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simple", help="单条音轨入视频")
    s.add_argument("--video", required=True)
    s.add_argument("--audio", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--mode", choices=["replace", "mix"], default="mix",
                   help="replace=替换原声；mix=与原声混合")
    s.add_argument("--delay", type=float, default=0.0, help="配音起始延迟（秒）")
    s.add_argument("--vo-volume", type=float, default=1.0, help="配音音量倍数")
    s.add_argument("--bg-volume", type=float, default=0.15, help="原声压低倍数（mix 时）")

    t = sub.add_parser("timeline", help="按时间轴铺多轨配音")
    t.add_argument("--video", required=True)
    t.add_argument("--timeline", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--audiodir", default="audio", help="音频目录（timeline 中 file 仅给文件名时用）")
    t.add_argument("--keep-original", action="store_true", help="保留并压低原声")
    t.add_argument("--bg-volume", type=float, default=0.15, help="原声压低倍数")

    g = sub.add_parser("template", help="由台词表生成时间轴模板（可合并多份）")
    g.add_argument("--cast", action="append", required=True, metavar="JSON",
                   help="台词表 JSON，可重复多次以合并（如 v12 表 + 自定义台词）")
    g.add_argument("--audiodir", default="audio")
    g.add_argument("--out", required=True)

    args = p.parse_args(argv)
    cfg = load_config(args.config)
    return {"simple": cmd_simple, "timeline": cmd_timeline,
            "template": cmd_template}[args.cmd](args, cfg)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        raise SystemExit(1)
