#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
《真假妈妈》配音工具 · 交互菜单

双击同目录的「配音工具.bat」即可运行（.bat 会先设好中文编码）。
也可以直接命令行运行：python menu.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
PROJ = HERE.parent

CAST = "配音台词表_v12.json"
CUSTOM = "自定义台词.json"
TIMELINE = "时间轴_v12.json"
AUDIODIR = "audio"

# 已联调验证可用的发音人
VOICES = [
    ("x6_pangbainv1_pro", "旁白女声 · 女（推荐旁白）"),
    ("x6_pangbainan1_pro", "旁白男声 · 男（推荐骗子）"),
    ("x6_lingfeiyi_pro", "聆飞逸 · 男（推荐男主）"),
    ("x6_lingxiaoxuan_pro", "聆小璇 · 女（推荐假妈妈）"),
    ("x6_lingyuyan_pro", "聆玉言 · 女（推荐真妈妈）"),
    ("x5_lingxiaoxuan_flow", "聆小璇 · x5 旧版流式"),
    ("x5_lingyuzhao_flow", "聆玉昭 · x5 旧版流式"),
]

# 自动寻找可用于合成的成片
CANDIDATE_VIDEOS = [
    PROJ / "06_导出成片" / "真假妈妈_成片_v12_横屏1080p.mp4",
    PROJ / "06_导出成片" / "真假妈妈_成片_v9_横屏1080p.mp4",
]


def hr(ch: str = "─", n: int = 66) -> None:
    print(ch * n)


def run(args: list[str], title: str) -> int:
    hr("=")
    print(f"▶ {title}")
    print(f"  {' '.join(args)}")
    hr("=")
    proc = subprocess.run([PY, *args], cwd=str(HERE))
    print()
    if proc.returncode == 0:
        print("✅ 完成")
    else:
        print(f"❌ 失败（退出码 {proc.returncode}），请把上面的报错信息发我")
    return proc.returncode


def ask(prompt: str, default: str = "") -> str:
    tip = f"（直接回车 = {default}）" if default else ""
    s = input(f"{prompt}{tip}：").strip().lstrip("\ufeff")
    return s or default


def pause() -> None:
    input("\n按回车返回菜单…")


# --------------------------------------------------------------------------- #

def m_selfcheck(online: bool) -> None:
    args = ["verify_env.py"] + (["--online"] if online else [])
    run(args, "环境自检" + ("（含真实试听）" if online else "（不消耗额度）"))
    pause()


def m_synth_all() -> None:
    print("\n这会把《真假妈妈》v12 的 18 句台词全部合成到 audio\\ 目录。")
    print("自动按剧本槽位提速，塞不进的会标 ❌ 提醒你。")
    if ask("开始？（y/n）", "y").lower() not in ("y", "yes", "是"):
        return
    run(["xfyun_tts.py", "--cast", CAST, "--outdir", AUDIODIR, "--autofit"],
        "合成全部配音")
    pause()


def m_synth_custom() -> None:
    hr()
    print("★ 自己加台词")
    print()
    print("  不在 v12 工程表里的对话，写进这个文件：")
    print(f"    {HERE / CUSTOM}")
    print()
    print("  格式（就照着里面的示例改）：")
    print('    { "id": "自定义_01", "role": "男主", "tone": "疑惑",')
    print('      "text": "等等，[p500]你刚才说什么？", "start": 7.0, "end": 9.0 }')
    print()
    print("  · id    = 生成的文件名（audio/自定义_01.mp3）")
    print("  · role  = 旁白 / 男主 / 真妈妈 / 假妈妈 / 骗子")
    print("  · tone  = 语气，可选：见下面选项 12")
    print("  · text  = 台词；[p500] 表示此处停顿 500 毫秒")
    print("  · start/end = 在成片里的秒数（不写就不做槽位检查）")
    print()
    if not (HERE / CUSTOM).exists():
        print(f"❌ 找不到 {CUSTOM}")
        pause()
        return
    if ask("直接开始合成？（y=合成 / n=先去改文件）", "y").lower() not in ("y", "yes", "是"):
        print(f"\n文件位置：{HERE / CUSTOM}")
        subprocess.run(["notepad", str(HERE / CUSTOM)], check=False)
        return
    run(["xfyun_tts.py", "--cast", CUSTOM, "--outdir", AUDIODIR, "--autofit"],
        "合成自定义台词")
    pause()


def m_synth_merged() -> None:
    print("\n把 v12 工程表的台词 + 你自己加的台词 一起合成。")
    run(["xfyun_tts.py", "--cast", CAST, "--cast", CUSTOM,
         "--outdir", AUDIODIR, "--autofit"], "合成全部（v12 + 自定义）")
    print(f"\n清单已合并到：{HERE / AUDIODIR / '_manifest.json'}")
    pause()


def m_edit_custom() -> None:
    f = HERE / CUSTOM
    if not f.exists():
        print(f"❌ 找不到 {CUSTOM}")
        pause()
        return
    print(f"正在用记事本打开：{f}")
    print("改完保存、关掉记事本，再回菜单选 9 或 10 合成。")
    subprocess.run(["notepad", str(f)], check=False)
    pause()


def m_tone_help() -> None:
    run(["xfyun_tts.py", "--list-tone"], "语气预设与停顿语法速查")
    pause()


def m_synth_one() -> None:
    hr()
    print("试听单句。可用发音人：")
    for i, (vcn, desc) in enumerate(VOICES, 1):
        print(f"  {i}. {desc:<28} {vcn}")
    hr()
    print("可用语气（也可留空）：平静 温柔 亲切 疑惑 焦急 慌张 施压 冷酷 威胁 委屈 释然 激动 低沉 念白")
    text = ask("要合成的文字", "小宇，是你吗？[p300]")
    v = ask("选发音人编号", "4")
    try:
        vcn = VOICES[int(v) - 1][0]
    except (ValueError, IndexError):
        print("编号无效。")
        pause()
        return
    tone = ask("语气（留空=不用预设）", "")
    out = ask("输出文件名", "试听.mp3")
    args = ["xfyun_tts.py", "--text", text, "--out", out, "--vcn", vcn]
    if tone:
        args += ["--tone", tone]
    run(args, "单句试听")
    print(f"\n音频已存到：{HERE / out}  —— 双击就能听")
    pause()


def m_template() -> None:
    print("\n从两张台词表（v12 工程表 + 你的自定义台词）合并生成时间轴。")
    run(["mux_to_video.py", "template", "--cast", CAST, "--cast", CUSTOM,
         "--audiodir", AUDIODIR, "--out", TIMELINE],
        "生成时间轴（合并 v12 + 自定义）")
    pause()


def m_mux() -> None:
    # 找视频
    default_video = ""
    for p in CANDIDATE_VIDEOS:
        if p.exists():
            default_video = str(p)
            break
    if not default_video:
        print("⚠️  没在 06_导出成片\\ 里找到成片。")
    print("\n这一步会把 audio\\ 里的配音按时间轴铺进视频。")
    video = ask("视频文件路径", default_video)
    if not video or not Path(video).exists():
        print(f"❌ 找不到视频：{video}")
        pause()
        return
    out = ask("输出文件路径", str(Path(video).with_name(Path(video).stem + "_配音版.mp4")))
    bg = ask("原声压低到百分之几（0=完全静音原声）", "12")
    args = ["mux_to_video.py", "timeline", "--video", video,
            "--timeline", TIMELINE, "--out", out, "--bg-volume", str(int(bg) / 100)]
    if int(bg) > 0:
        args.append("--keep-original")
    run(args, "配音入视频")
    print(f"\n成片已存到：{out}")
    pause()


def m_show_manifest() -> None:
    hr()
    f = HERE / AUDIODIR / "_manifest.json"
    if not f.exists():
        print("还没有合成过配音。请先选 3。")
        pause()
        return
    m = json.loads(f.read_text(encoding="utf-8"))
    lines = m.get("lines", [])
    print(f"{'编号':<18}{'角色':<7}{'时长':>7}  {'槽位':>6}  台词")
    hr()
    for x in lines:
        slot = x.get("slot")
        slot_s = f"{slot:>6.2f}" if slot else "   —  "
        over = " ⚠️" if slot and x["duration"] > slot * 1.02 else ""
        print(f"{x['id']:<18}{x['role']:<7}{x['duration']:>6.2f}s {slot_s}  "
              f"{x['text'][:22]}{over}")
    hr()
    total = sum(x["duration"] for x in lines)
    bad = [o for o in m.get("oversize", []) if o.get("infeasible")]
    print(f"共 {len(lines)} 条，总时长 {total:.2f}s")
    if bad:
        print(f"\n❌ {len(bad)} 条即使最快语速也塞不进剧本槽位：")
        for o in bad:
            print(f"   {o['id']:<18} {o['duration']:.2f}s / 槽位 {o['slot']:.2f}s")
        print("   → 见 README_配音工作流.md 第四节的修改建议")
    pause()


def m_open_folder() -> None:
    subprocess.run(["explorer", str(HERE)], check=False)


# --------------------------------------------------------------------------- #

MENU = [
    ("1", "环境自检（不消耗额度）", lambda: m_selfcheck(False)),
    ("2", "环境自检 + 真实试听（消耗少量字符额度）", lambda: m_selfcheck(True)),
    ("3", "★ 合成全部配音（18 句 → audio\\）", m_synth_all),
    ("4", "单句试听（挑音色 / 试语气用）", m_synth_one),
    ("5", "生成时间轴（合并 v12 + 自定义）", m_template),
    ("6", "★ 配音入视频（合成带配音的成片）", m_mux),
    ("7", "查看已合成配音清单 + 槽位体检", m_show_manifest),
    ("8", "打开本文件夹", m_open_folder),
    ("─", "", None),
    ("9", "★ 合成自定义台词（自己加的对话）", m_synth_custom),
    ("10", "合成全部（v12 台词表 + 自定义台词）", m_synth_merged),
    ("11", "编辑自定义台词文件（记事本）", m_edit_custom),
    ("12", "语气预设 + 停顿语法 速查表", m_tone_help),
    ("0", "退出", None),
]


def main() -> int:
    while True:
        print()
        hr("═")
        print("   《真假妈妈》配音工具 · 讯飞超拟人语音合成")
        hr("═")
        for k, label, _ in MENU:
            if k == "─":
                print("   " + "┈" * 58)
            else:
                print(f"   {k:>2}.  {label}")
        hr("═")
        choice = input("请输入编号后按回车：").strip().lstrip("\ufeff")

        if choice == "0":
            print("\n再见。")
            return 0
        hit = next((f for k, _, f in MENU if k == choice and f), None)
        if hit is None:
            print(f"没有编号 {choice}，请重新输入。")
            continue
        try:
            hit()
        except KeyboardInterrupt:
            print("\n（已取消）")
        except Exception as e:                          # noqa: BLE001
            print(f"\n❌ 出错了：{type(e).__name__}: {e}")
            pause()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
