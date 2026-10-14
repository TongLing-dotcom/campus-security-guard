#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配音环境自检 —— 一条命令确认「前置要求」是否全部就绪

    python verify_env.py            # 只做本地检查（不消耗额度）
    python verify_env.py --online   # 额外做一次真实合成，验证鉴权与服务授权（消耗 ~7 字）

退出码：0 全通过 / 1 有失败项
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OK, WARN, BAD = "✅", "⚠️ ", "❌"
results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"{status} {name}" + (f"\n     {detail}" if detail else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="配音环境自检")
    ap.add_argument("--config", help="xfyun_config.json 路径")
    ap.add_argument("--online", action="store_true",
                    help="额外做真实合成调用，验证鉴权/授权（消耗少量字符额度）")
    args = ap.parse_args(argv)

    print("=" * 70)
    print("《真假妈妈》配音环境自检")
    print("=" * 70)

    # ---- 1. Python ----
    v = sys.version_info
    check("Python 版本", OK if v >= (3, 9) else BAD,
          f"{v.major}.{v.minor}.{v.micro}  @ {sys.executable}")

    # ---- 2. 依赖 ----
    for mod, why in (("websocket", "WebSocket 通信（讯飞接口必需）"),):
        try:
            m = importlib.import_module(mod)
            check(f"依赖 {mod}", OK, f"v{getattr(m, '__version__', '?')} —— {why}")
        except ImportError:
            check(f"依赖 {mod}", BAD,
                  f"缺失（{why}）。修复：python -m pip install websocket-client")
    try:
        import numpy  # noqa: F401
        check("依赖 numpy", OK, "已安装")
    except ImportError:
        check("依赖 numpy", WARN, "未安装（本工具链不依赖，可忽略）")

    # ---- 3. 配置 ----
    cfg = None
    try:
        import xfyun_tts
        cfg = xfyun_tts.load_config(args.config)
        ep = cfg["endpoint"]
        check("配置文件", OK, f"{Path(args.config).resolve() if args.config else xfyun_tts.DEFAULT_CONFIG}")
        check("服务端点", OK, f"wss://{ep['host']}{ep['path']}")
        def masked(s: str | None) -> str:
            if not s:
                return "(未设置)"
            return s if len(s) <= 8 else s[:4] + "…" + s[-4:]
        mode = cfg.get("auth_mode", "hmac")
        need = "appid" if mode == "apikey" else "appid/api_key/api_secret"
        have = {"appid": cfg.get("appid"), "api_key": cfg.get("api_key"),
                "api_secret": cfg.get("api_secret")}
        check(f"凭据（auth_mode={mode}，需要 {need}）", OK,
              "  ".join(f"{k}={masked(v)}" for k, v in have.items()))
        if mode == "apikey":
            check("APIPassword", OK if cfg.get("api_password") else BAD,
                  masked(cfg.get("api_password")))
    except SystemExit as e:
        check("配置文件", BAD, str(e))
    except Exception as e:                              # noqa: BLE001
        check("配置文件", BAD, f"{type(e).__name__}: {e}")

    # ---- 4. ffmpeg / ffprobe ----
    if cfg:
        import xfyun_tts
        for tool in ("ffmpeg", "ffprobe"):
            try:
                path = xfyun_tts.resolve_tool(tool, cfg)
                import subprocess
                out = subprocess.run([path, "-version"], capture_output=True,
                                     text=True).stdout.splitlines()
                ver = out[0] if out else "(无法读取版本)"
                check(f"{tool}", OK, f"{path}\n     {ver[:100]}")
            except Exception as e:                      # noqa: BLE001
                check(f"{tool}", BAD,
                      f"找不到（{e}）。修复：把路径写进配置 tools.{tool}，"
                      f"或设置 {tool.upper()} 环境变量")

    # ---- 5. 关键素材 ----
    proj = HERE.parent
    assets = {
        "分镜工程表 v12": proj / "01_方案与分镜" / "反诈短视频_分镜工程表_v12.md",
        "成片 v9（当前唯一可合成的主片）":
            proj / "06_导出成片" / "真假妈妈_成片_v9_横屏1080p.mp4",
        "配音台词表 v12": HERE / "配音台词表_v12.json",
    }
    for label, p in assets.items():
        check(label, OK if p.exists() else WARN,
              str(p) if p.exists() else f"未找到：{p}")

    # ---- 6. 在线验证 ----
    if args.online and cfg:
        import xfyun_tts
        print("\n" + "-" * 70)
        print("在线验证（真实调用一次，消耗少量字符额度）")
        print("-" * 70)
        try:
            audio, sid, meta = xfyun_tts.synthesize("测试", cfg,
                                                    overrides={"vcn": "x6_lingxiaoxuan_pro"})
            check("鉴权 + 服务授权", OK,
                  f"收到 {len(audio)} 字节 mp3，sid={sid}")
        except xfyun_tts.XfyunTTSError as e:
            if e.code == 11200:
                check("鉴权", OK, "HMAC/APIKey 签名有效，握手通过")
                check("服务授权", BAD,
                      f"180 code=11200 —— 该 APPID 未开通『超拟人语音合成』或发音人未授权。"
                      f"控制台：https://console.xfyun.cn/services/uts\n     sid={e.sid}")
            else:
                check("鉴权 + 服务授权", BAD, str(e))
        except Exception as e:                          # noqa: BLE001
            check("网络连接", BAD,
                  f"{type(e).__name__}: {e}\n"
                  f"     检查代理/防火墙是否放行 wss://{cfg['endpoint']['host']}")
    elif cfg:
        print("\n（未加 --online，跳过真实调用；建议执行一次以确认额度与授权）")

    # ---- 汇总 ----
    bad = [r for r in results if r[0] == BAD]
    warn = [r for r in results if r[0] == WARN]
    print("\n" + "=" * 70)
    print(f"结论：{len(results) - len(bad) - len(warn)} 项通过 / "
          f"{len(warn)} 项警告 / {len(bad)} 项失败")
    if bad:
        print("\n必须修复：")
        for _, n, d in bad:
            print(f"  {BAD} {n}")
    print("=" * 70)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
