#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
讯飞开放平台 · 超拟人语音合成（WebSocket 流式）客户端  —— 《真假妈妈》配音专用

★ 已联调确认（2026-10-07）
  本账号 `YOUR_APPID` 实际开通的是 **新版「超拟人语音合成」**：
      wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6
  旧版「超拟人合成」`/v1/private/medd90fec` 返回 11200 licc failed（未授权），勿再用。

官方文档
  接口文档  https://www.xfyun.cn/doc/spark/super%20smart-tts.html
  鉴权说明  https://www.xfyun.cn/doc/spark/general_url_authentication.html

鉴权方式（两种任选，本项目默认 hmac）
  hmac   —— APPID + APIKey + APISecret，握手 URL 带 HMAC-SHA256 签名（鉴权方式二）
  apikey —— 请求头 x-api-key: <APIPassword>（鉴权方式一，即控制台『鉴权信息·系统默认』的 ak- 串）

用法
  python xfyun_tts.py --probe                      # 体检：验签 + 授权 + 可用发音人
  python xfyun_tts.py --list-vcn                   # 列出本账号已授权发音人
  python xfyun_tts.py --text "小宇，是你吗？" --out demo.mp3
  python xfyun_tts.py --text-file 旁白.txt --out 旁白.mp3 --vcn x6_pangbainv1_pro
  python xfyun_tts.py --cast 配音台词表_v12.json --outdir audio   # 按角色批量配音
  python xfyun_tts.py --text "长文…" --out a.mp3 --stream         # 双向流式分片发送
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

try:
    import websocket  # websocket-client
    from websocket import WebSocketApp
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少依赖 websocket-client，请执行：\n"
                     "    python -m pip install websocket-client\n")
    raise SystemExit(2)


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "xfyun_config.json"

# 超拟人语音合成接口（新版）
HOST = "cbm01.cn-huabei-1.xf-yun.com"
PATH = "/v1/private/mcd9m97e6"

# 旧版超拟人合成（本账号未授权，仅作诊断用）
LEGACY_HOST = "cbm01.cn-huabei-1.xf-yun.com"
LEGACY_PATH = "/v1/private/medd90fec"

# 本账号已联调验证 **可用** 的发音人（未列出的 vcn 会返回 11200 licc limit）
AUTHORIZED_VCN = {
    "x6_lingxiaoxuan_pro": "聆小璇 · 成年女 · 交互聊天（默认免费）",
    "x6_lingfeiyi_pro":    "聆飞逸 · 成年男 · 交互聊天（默认免费）",
    "x6_lingyuyan_pro":    "聆玉言 · 成年女 · 交互聊天",
    "x6_pangbainv1_pro":   "旁白女声 · 成年女 · 旁白配音",
    "x6_pangbainan1_pro":  "旁白男声 · 成年男 · 旁白配音",
    "x5_lingxiaoxuan_flow": "聆小璇 · 成年女 · 旧版流式",
    "x5_lingyuzhao_flow":   "聆玉昭 · 成年女 · 旧版流式",
}

# 未经授权、验证会报 11200 的常见角色音（备查，充值/开通后可直接启用）
KNOWN_UNAUTHORIZED_VCN = {
    "x6_huoposhaonian_pro": "活泼少年", "x6_wenrounansheng_mini": "温柔男声",
    "x6_wennuancixingnansheng_mini": "温暖磁性男声", "x6_gaolengnanshen_pro": "高冷男神",
    "x6_huajidama_pro": "滑稽大妈", "x6_lingxiaoxue_pro": "聆小雪",
    "x6_dongmanshaonv_pro": "动漫少女", "x6_lingxiaoyue_pro": "聆小玥",
    "x6_lingyuzhao_pro": "聆玉昭(新)", "x4_lingxiaoxuan_oral": "聆小璇(x4·旧接口)",
}

# 《真假妈妈》角色 → 发音人 / 语速语调 选角表（全部落在已授权名单内）
CAST_DEFAULT = {
    "旁白":     {"vcn": "x6_pangbainv1_pro",  "speed": 46, "pitch": 50, "oral_level": "low"},
    "男主":     {"vcn": "x6_lingfeiyi_pro",   "speed": 52, "pitch": 52, "oral_level": "mid"},
    "真妈妈":   {"vcn": "x6_lingyuyan_pro",   "speed": 48, "pitch": 56, "oral_level": "mid"},
    "假妈妈":   {"vcn": "x6_lingxiaoxuan_pro", "speed": 50, "pitch": 54, "oral_level": "mid"},
    "骗子":     {"vcn": "x6_pangbainan1_pro", "speed": 50, "pitch": 44, "oral_level": "low"},
}

# ★ 语气预设：说话方式的「档位」。用法见 xfyun_config.json 的 tone_presets 注释。
#   三个可调旋钮（均已实测生效）：
#     speed 语速 0-100 —— 50=默认；100≈2 倍速；30≈默认的 1.3 倍时长。改变时长，最强杠杆。
#     pitch 语调 0-100 —— 实测谱质心随 pitch 单调上升（799→1407Hz），数值越大越"高/亮/年轻"。
#     volume 音量 0-100 —— 实测响度单调上升（-29.2→-18.1 dBFS）。
TONE_PRESETS = {
    "平静":     {"speed": 50, "pitch": 50, "volume": 50},
    "温柔":     {"speed": 44, "pitch": 56, "volume": 46},
    "亲切":     {"speed": 48, "pitch": 54, "volume": 50},
    "疑惑":     {"speed": 46, "pitch": 60, "volume": 48},
    "焦急":     {"speed": 78, "pitch": 62, "volume": 60},
    "慌张":     {"speed": 86, "pitch": 68, "volume": 62},
    "施压":     {"speed": 60, "pitch": 36, "volume": 56},
    "冷酷":     {"speed": 52, "pitch": 32, "volume": 52},
    "威胁":     {"speed": 56, "pitch": 30, "volume": 60},
    "委屈":     {"speed": 44, "pitch": 64, "volume": 42},
    "释然":     {"speed": 42, "pitch": 46, "volume": 44},
    "激动":     {"speed": 72, "pitch": 66, "volume": 58},
    "低沉":     {"speed": 44, "pitch": 32, "volume": 48},
    "念白":     {"speed": 42, "pitch": 50, "volume": 48},
}


ERROR_HINTS = {
    10009: "输入数据非法，检查文本是否为空或含非法字符。",
    10010: "没有授权许可或授权数已满，需到控制台提交工单。",
    10139: "参数错误，检查 vcn / audio 参数是否合法。",
    10160: "请求 JSON 非法。",
    10161: "base64 解码失败，检查 text 字段编码。",
    10163: "参数校验失败（详见 message；常见于 vcn 未在平台发音人白名单内）。",
    10200: "读取数据超时：累计 10s 未发送数据且未关闭连接。",
    10222: "数据超限（文本 >64K 字节）或 SSL 证书无效。",
    10313: "appid 与 apikey 不匹配，检查控制台凭据。",
    10700: "引擎异常，附 sid 提交工单。",
    11200: "★未授权：①该 APPID 未开通『超拟人语音合成』服务量；②或该发音人未单独开通权限"
           "（服务量与发音人是两项独立授权）。控制台：https://console.xfyun.cn/services/uts",
    11201: "该 APPID 当日调用次数超限。",
    26005: "上行数据超时：超过 14s 没收到客户端数据。",
    26006: "下行数据超时：服务内部下发超时，提交工单。",
}

# 新版接口单次会话文本总字节上限 64K
MAX_SESSION_BYTES = 64 * 1024


class XfyunTTSError(RuntimeError):
    """带错误码与 sid 的讯飞接口异常。"""

    def __init__(self, code: int, message: str = "", sid: str = ""):
        self.code, self.message, self.sid = code, message, sid
        text = f"讯飞接口返回错误 code={code} message={message!r}"
        if sid:
            text += f" sid={sid}"
        hint = ERROR_HINTS.get(code)
        if hint:
            text += f"\n  → 处理建议：{hint}"
        super().__init__(text)


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #

def load_config(path: str | os.PathLike | None = None) -> dict:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}

    ep = cfg.setdefault("endpoint", {})
    ep.setdefault("host", HOST)
    ep.setdefault("path", PATH)
    cfg.setdefault("tts_defaults", {})
    cfg.setdefault("tools", {})
    cfg.setdefault("auth_mode", "hmac")          # hmac | apikey
    cfg.setdefault("api_password", cfg.get("extra_auth_key", ""))
    cfg.setdefault("timeout", 120)

    for env_key, cfg_key in (("XFYUN_APPID", "appid"),
                             ("XFYUN_API_KEY", "api_key"),
                             ("XFYUN_API_SECRET", "api_secret"),
                             ("XFYUN_API_PASSWORD", "api_password")):
        if os.environ.get(env_key):
            cfg[cfg_key] = os.environ[env_key]

    mode = str(cfg.get("auth_mode", "hmac")).lower()
    need = ("appid",) if mode == "apikey" else ("appid", "api_key", "api_secret")
    missing = [k for k in need if not cfg.get(k)]
    if missing:
        raise SystemExit(f"配置缺少字段 {missing}（auth_mode={mode}）。"
                         f"请在 {cfg_path} 填写，或设置 XFYUN_* 环境变量。")
    return cfg


# --------------------------------------------------------------------------- #
# 鉴权
# --------------------------------------------------------------------------- #

def rfc1123_gmt_now() -> str:
    """RFC1123 格式的 GMT 时间戳，例：Fri, 05 May 2023 10:43:39 GMT。"""
    return format_date_time(mktime(datetime.now().timetuple()))


def build_auth_url(appid: str, api_key: str, api_secret: str,
                   host: str, path: str, date: str | None = None) -> str:
    """按官方签名规则生成可握手的 wss:// URL（鉴权方式二）。"""
    date = date or rfc1123_gmt_now()
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    digest = hmac.new(api_secret.encode("utf-8"),
                      signature_origin.encode("utf-8"),
                      digestmod=hashlib.sha256).digest()
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="'
        f'{base64.b64encode(digest).decode("utf-8")}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    return f"wss://{host}{path}?" + urlencode(
        {"authorization": authorization, "date": date, "host": host})


_ONLINE_ALIASES = {"online", "v2", "tts", "online_tts", "onlinetts"}


def resolve_line(cfg: dict, line: str | None = None) -> str:
    """把用户传入的 line 归一化为 'ultra' 或 'online'。"""
    name = str(line or cfg.get("active_line") or "ultra").strip().lower()
    return "online" if name in _ONLINE_ALIASES else "ultra"


def resolve_endpoint(cfg: dict, line: str | None = None) -> dict:
    """按产品线取端点：online → 在线语音合成 v2/tts；其余 → 超拟人端点。"""
    if resolve_line(cfg, line) == "online":
        return cfg.get("endpoint_online_tts") or {
            "host": "tts-api.xfyun.cn", "path": "/v2/tts"}
    return cfg["endpoint"]


def make_connection_args(cfg: dict, line: str | None = None) -> tuple[str, dict, dict]:
    """返回 (url, header, sslopt)。line: ultra=超拟人端点（默认）｜online=v2/tts。"""
    ep = resolve_endpoint(cfg, line)
    mode = str(cfg.get("auth_mode", "hmac")).lower()
    sslopt = {"cert_reqs": ssl.CERT_NONE} if os.environ.get("XFYUN_INSECURE") else {}
    if mode == "apikey":
        pw = cfg.get("api_password") or cfg.get("extra_auth_key", "")
        if not pw:
            raise SystemExit("auth_mode=apikey 但未配置 api_password。")
        url = f"wss://{ep['host']}{ep['path']}"
        return url, {"x-api-key": pw}, sslopt
    url = build_auth_url(cfg["appid"], cfg["api_key"], cfg["api_secret"],
                         ep["host"], ep["path"])
    return url, {}, sslopt


# --------------------------------------------------------------------------- #
# 文本切分
# --------------------------------------------------------------------------- #

_PUNCT = "。！？；…，、.!?;,\n"

# 用户可能打出全角括号，统一成接口认的半角 [p500]
_BRACKET_FIX = {"［": "[", "］": "]", "【": "[", "】": "]", "〔": "[", "〕": "]"}
_PAUSE_RE = re.compile(r"\[p(\d+)\]")
_PINYIN_RE = re.compile(r"\[=([A-Za-z]+[1-5])\]")


def normalize_text(text: str) -> tuple[str, list[str]]:
    """
    规范化待合成文本，返回 (规范后文本, 警告列表)。

    识别两种接口自带的控制语法（均已实测生效）：
        [p500]      在当前位置插入 500 毫秒静音 —— ★ 台词卡口型/凑时长的核心手段
        着[=zhuo2]  指定前一个字的读音（声调 1-5）
    """
    warns: list[str] = []
    out = "".join(_BRACKET_FIX.get(c, c) for c in text)
    for m in _PAUSE_RE.finditer(out):
        ms = int(m.group(1))
        if ms > 10000:
            warns.append(f"[p{ms}] 停顿 {ms}ms 过长（建议 ≤10000）")
    for m in _PINYIN_RE.finditer(out):
        if not re.fullmatch(r"[A-Za-z]+[1-5]", m.group(1)):
            warns.append(f"[={m.group(1)}] 拼音格式可疑，应为 字母+声调(1-5)，如 [=zhuo2]")
    if "[" in out:
        leftover = re.sub(r"\[p\d+\]|\[=[A-Za-z]+[1-5]\]", "", out)
        if "[" in leftover or "]" in leftover:
            warns.append("文本里有无法识别的方括号语法，将被原样送给引擎（可能读出来）")
    return out, warns


def resolve_tone(cfg: dict, name: str | None) -> dict:
    """按名称取语气预设；不认识的名字给出可用清单。"""
    if not name:
        return {}
    table = {**TONE_PRESETS, **(cfg.get("tone_presets") or {})}
    if name not in table:
        raise SystemExit(f"未知语气「{name}」。可用：" + "、".join(table))
    return dict(table[name])


def write_manifest(outdir: Path, manifest: list[dict], failed: list[dict],
                   ovf: list[dict]) -> Path:
    """
    写入 audio/_manifest.json。

    ★ 与已有清单**合并**（按 id 覆盖同名条目）——这样先合成 v12 台词表、
    再合成自定义台词表，两次的结果会累积在一份清单里，不会互相冲掉。
    """
    path = outdir / "_manifest.json"
    old = {"lines": [], "failed": [], "oversize": []}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    def merge(key: str, new_items: list[dict]) -> list[dict]:
        by_id: dict[str, dict] = {}
        for x in old.get(key, []):
            if isinstance(x, dict) and "id" in x:
                by_id[x["id"]] = x
        for x in new_items:
            if isinstance(x, dict) and "id" in x:
                by_id[x["id"]] = x          # 同名覆盖，位置保持
        return list(by_id.values())

    data = {"lines": merge("lines", manifest),
            "failed": merge("failed", failed),
            "oversize": merge("oversize", ovf)}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path




def split_text(text: str, limit: int) -> list[str]:
    """按标点优先、长度兜底切分文本。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    chunks, buf = [], ""
    for ch in text:
        buf += ch
        if ch in _PUNCT and len(buf) >= limit * 0.6:
            chunks.append(buf); buf = ""
        elif len(buf) >= limit:
            chunks.append(buf); buf = ""
    if buf.strip():
        chunks.append(buf)
    out = []
    for c in chunks:
        while len(c) > limit:
            out.append(c[:limit]); c = c[limit:]
        if c.strip():
            out.append(c)
    return out


def _reorder(frames: list[tuple[int, bytes]]) -> bytes:
    """按 seq 重排后拼接；自动识别 seq 归零（按句重置）并分段处理。"""
    if not frames:
        return b""
    groups: list[list[tuple[int, bytes]]] = [[]]
    prev = -1
    for seq, data in frames:
        if seq <= prev - 1 and groups[-1]:   # seq 明显回退 → 新的一轮
            groups.append([])
        groups[-1].append((seq, data))
        prev = seq
    out = bytearray()
    for g in groups:
        for _, d in sorted(g, key=lambda x: x[0]):
            out += d
    return bytes(out)


# --------------------------------------------------------------------------- #
# 请求体
# --------------------------------------------------------------------------- #

def build_request(appid: str, text: str, *, vcn: str, speed: int = 50, volume: int = 50,
                  pitch: int = 50, oral_level: str = "mid", bgs: int = 0, reg: int = 0,
                  rdn: int = 0, rhy: int = 0, sample_rate: int = 24000, channels: int = 1,
                  bit_depth: int = 16, frame_size: int = 0, encoding: str = "lame",
                  seq: int = 0, status: int = 2, oral_extra: dict | None = None) -> dict:
    """构造请求体。status: 0 开始 / 1 中间 / 2 结束（一次性传完直接传 2）。"""
    oral = {"oral_level": oral_level}
    if oral_extra:
        oral.update(oral_extra)
    return {
        "header": {"app_id": appid, "status": status},
        "parameter": {
            "oral": oral,
            "tts": {
                "vcn": vcn, "speed": speed, "volume": volume, "pitch": pitch,
                "bgs": bgs, "reg": reg, "rdn": rdn, "rhy": rhy,
                "audio": {"encoding": encoding, "sample_rate": sample_rate,
                          "channels": channels, "bit_depth": bit_depth,
                          "frame_size": frame_size},
            },
        },
        "payload": {
            "text": {"encoding": "utf8", "compress": "raw", "format": "plain",
                     "status": status, "seq": seq,
                     "text": base64.b64encode(text.encode("utf-8")).decode("utf-8")}
        },
    }


def build_request_v2(appid: str, text: str, *, vcn: str, speed: int = 50,
                     volume: int = 50, pitch: int = 50, bgs: int = 0,
                     reg: str = "0", rdn: str = "0", rhy: str = "0",
                     aue: str = "lame", tte: str = "UTF8",
                     emotion: str | None = None, status: int = 2) -> dict:
    """在线语音合成（流式版）v2/tts 请求体：common/business/data 结构。

    与超拟人的 header/parameter/payload 完全不同（实测踩坑记录）：
      · 音频格式用 business.aue（"raw"=pcm 16k / "lame"=mp3），没有 audio 对象；
      · reg / rdn / rhy 必须是字符串，传 int 会报 10163；
      · data 段必须带 encoding（与 tte 一致），status 固定 2（不支持分段）；
      · 情绪音色通过选发音人（vcn 带 _emo）实现。
    """
    business: dict = {"vcn": vcn, "speed": speed, "volume": volume, "pitch": pitch,
                      "bgs": bgs, "reg": str(reg), "rdn": str(rdn), "rhy": str(rhy),
                      "aue": aue, "tte": tte}
    if emotion is not None and emotion != "":
        # emotion 必须是整数编码：0 默认 / 1 高兴 / 2 生气 / 3 害怕 / 4 悲伤 /
        #                     5 厌恶 / 6 惊讶（传字符串数字也自动转 int）
        try:
            business["emotion"] = int(emotion)
        except (TypeError, ValueError):
            business["emotion"] = emotion
    return {
        "common": {"app_id": appid},
        "business": business,
        "data": {"status": status, "encoding": tte,
                 "text": base64.b64encode(text.encode("utf-8")).decode("utf-8")},
    }


# --------------------------------------------------------------------------- #
# 合成核心（WebSocketApp：发送/接收解耦，支持双向流式）
# --------------------------------------------------------------------------- #

def _synth(cfg: dict, text: str, *, params: dict, stream: bool = False,
           stream_chunk: int = 200, timeout: float | None = None,
           trace: bool = False, line: str | None = None) -> tuple[bytes, str, dict]:
    """执行一次合成会话，返回 (mp3 字节, sid, 统计信息)。

    line: ultra = 超拟人端点（header/parameter/payload 请求体，payload.audio 响应）；
          online = 在线语音合成 v2/tts（common/business/data 请求体，data.audio 响应）。
    """
    timeout = float(timeout or cfg.get("timeout", 120))
    is_online = resolve_line(cfg, line) == "online"
    url, header, sslopt = make_connection_args(cfg, line)
    appid = cfg["appid"]

    frames: list[tuple[int, bytes]] = []
    state = {"sid": "", "err": None, "done": False, "chunks": 0, "sent": 0}
    lock = threading.Lock()
    done_evt = threading.Event()

    chunks = split_text(text, stream_chunk) if stream else [text]
    if stream and len(chunks) == 1:
        stream = False

    def _req(part: str, status: int, seq: int) -> dict:
        """按产品线构造请求体。"""
        if is_online:
            v2_params = {k: v for k, v in params.items()
                         if k in {"vcn", "speed", "volume", "pitch", "bgs", "reg",
                                  "rdn", "rhy", "aue", "tte", "emotion"}}
            return build_request_v2(appid, part, status=status, **v2_params)
        return build_request(appid, part, status=status, seq=seq, **params)

    def on_open(ws):
        def sender():
            try:
                total = len(chunks)
                for i, part in enumerate(chunks):
                    status = 0 if total > 1 and i == 0 else (2 if i == total - 1 else 1)
                    if total == 1:
                        status = 2
                    ws.send(json.dumps(_req(part, status, i),
                                       ensure_ascii=False))
                    with lock:
                        state["sent"] += 1
                    if i < total - 1:
                        time.sleep(0.02)   # 避免瞬时灌满缓冲区
            except Exception as e:          # noqa: BLE001
                with lock:
                    state["err"] = state["err"] or e
                done_evt.set()
                try:
                    ws.close()
                except Exception:
                    pass

        if stream:
            threading.Thread(target=sender, daemon=True).start()
        else:
            try:
                ws.send(json.dumps(_req(chunks[0], 2, 0),
                                   ensure_ascii=False))
                with lock:
                    state["sent"] += 1
            except Exception as e:          # noqa: BLE001
                with lock:
                    state["err"] = e
                done_evt.set()

    def on_message(ws, raw):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        if is_online:
            # v2/tts：code/sid 在顶层，音频在 data.audio，结束标志在 data.status
            code = msg.get("code", -1)
            sid = msg.get("sid", "")
            if sid:
                state["sid"] = sid
            if code != 0:
                with lock:
                    state["err"] = XfyunTTSError(code, msg.get("message", ""), sid)
                done_evt.set()
                try:
                    ws.close()
                except Exception:
                    pass
                return
            d = msg.get("data") or {}
            blob = d.get("audio")
            if blob:
                try:
                    frames.append((int(d.get("ced", 0) or 0), base64.b64decode(blob)))
                except Exception:           # noqa: BLE001
                    pass
                with lock:
                    state["chunks"] += 1
            if trace:
                sys.stderr.write(f"[trace] ced={d.get('ced')} data.status={d.get('status')}\n")
            if int(d.get("status", 0) or 0) == 2:
                done_evt.set()
                try:
                    ws.close()
                except Exception:
                    pass
            return

        h = msg.get("header") or {}
        code = h.get("code", -1)
        sid = h.get("sid", "")
        if sid:
            state["sid"] = sid
        if code != 0:
            with lock:
                state["err"] = XfyunTTSError(code, h.get("message", ""), sid)
            done_evt.set()
            try:
                ws.close()
            except Exception:
                pass
            return

        a = (msg.get("payload") or {}).get("audio") or {}
        blob = a.get("audio")
        if blob:
            try:
                frames.append((int(a.get("seq", 0) or 0), base64.b64decode(blob)))
            except Exception:               # noqa: BLE001
                pass
            with lock:
                state["chunks"] += 1
        if trace:
            sys.stderr.write(f"[trace] seq={a.get('seq')} status={a.get('status')} "
                             f"audio.status={a.get('status')} hdr.status={h.get('status')}\n")

        if int(a.get("status", 0) or 0) == 2 or int(h.get("status", 0) or 0) == 2:
            done_evt.set()
            try:
                ws.close()
            except Exception:
                pass

    def on_error(ws, err):
        with lock:
            state["err"] = state["err"] or err
        done_evt.set()

    def on_close(ws, code, msg):
        done_evt.set()

    app = WebSocketApp(url, header=header or None, on_open=on_open,
                       on_message=on_message, on_error=on_error, on_close=on_close)

    t = threading.Thread(target=lambda: app.run_forever(sslopt=sslopt or None,
                                                        ping_interval=0), daemon=True)
    t.start()

    if not done_evt.wait(timeout):
        try:
            app.close()
        except Exception:
            pass
        raise TimeoutError(f"等待合成结果超时（{timeout}s），已收 {len(frames)} 帧")

    if state["err"]:
        raise state["err"] if isinstance(state["err"], Exception) \
            else XfyunTTSError(-1, str(state["err"]), state["sid"])

    audio = _reorder(frames)
    if not audio:
        raise XfyunTTSError(-1, "未收到任何音频数据", state["sid"])
    return audio, state["sid"], {"frames": len(frames), "sent": state["sent"],
                                 "chunks": len(chunks)}


def synthesize(text: str, cfg: dict, *, stream: bool = False, timeout: float | None = None,
               trace: bool = False, overrides: dict | None = None,
               line: str | None = None) -> tuple[bytes, str, dict]:
    """对外主入口：合成文本，返回 (mp3 字节, sid, 统计)。

    line: ultra = 超拟人端点（默认；tts_defaults + AUTHORIZED_VCN 校验）；
          online = 在线语音合成 v2/tts（online_tts_defaults；vcn 为 xiaoyan /
                   x4_*_emo 等另一套命名，不做 AUTHORIZED_VCN 校验）。
    """
    text, warns = normalize_text(text)
    for w in warns:
        sys.stderr.write(f"⚠️  {w}\n")
    is_online = resolve_line(cfg, line) == "online"
    if is_online:
        defaults = dict(cfg.get("online_tts_defaults") or {
            "vcn": "xiaoyan", "speed": 50, "volume": 50, "pitch": 50,
            "aue": "lame", "tte": "UTF8"})
        defaults.update({k: v for k, v in (overrides or {}).items() if v is not None})
        allowed = {"vcn", "speed", "volume", "pitch", "bgs", "reg", "rdn", "rhy",
                   "aue", "tte", "emotion"}
        params = {k: v for k, v in defaults.items() if k in allowed}
        if not params.get("vcn"):
            params["vcn"] = "xiaoyan"
        # 注：在线 TTS 的 vcn 命名与超拟人不同，不做 AUTHORIZED_VCN 校验；
        #     报 11200 即该发音人未授权，去控制台『在线语音合成』开通。
        max_bytes = 8000          # 在线 TTS 单次上限（约 2000 汉字）
    else:
        defaults = dict(cfg.get("tts_defaults") or {})
        defaults.update({k: v for k, v in (overrides or {}).items() if v is not None})
        allowed = {"vcn", "speed", "volume", "pitch", "oral_level", "bgs", "reg", "rdn", "rhy",
                   "sample_rate", "channels", "bit_depth", "frame_size", "encoding"}
        params = {k: v for k, v in defaults.items() if k in allowed}
        if not params.get("vcn"):
            params["vcn"] = "x6_lingxiaoxuan_pro"
        if params["vcn"] not in AUTHORIZED_VCN:
            sys.stderr.write(
                f"⚠️  发音人 {params['vcn']} 不在已验证授权名单内，可能返回 11200。"
                f" 当前可用：{', '.join(AUTHORIZED_VCN)}\n")
    limit = max_bytes if is_online else MAX_SESSION_BYTES
    if len(text.encode("utf-8")) > limit:
        raise ValueError(f"文本超过单会话上限 {limit} 字节")
    return _synth(cfg, text, params=params, stream=stream, timeout=timeout, trace=trace,
                  line=line)


# --------------------------------------------------------------------------- #
# ffmpeg 定位 / 落盘
# --------------------------------------------------------------------------- #

def resolve_tool(name: str, cfg: dict | None = None) -> str:
    env = os.environ.get(name.upper())
    if env:
        return env
    if cfg and (cfg.get("tools") or {}).get(name):
        return cfg["tools"][name]
    from shutil import which
    found = which(name) or which(name + ".exe")
    if found:
        return found
    for cand in (rf"D:\Shotcut\{name}.exe", rf"C:\ffmpeg\bin\{name}.exe"):
        if Path(cand).exists():
            return cand
    raise FileNotFoundError(f"找不到 {name}，请在配置 tools.{name} 或设置 {name.upper()} 环境变量")


def duration_of(path: Path, cfg: dict | None = None) -> float:
    """用 ffprobe 读取音频/视频时长（秒）。"""
    try:
        out = subprocess.run(
            [resolve_tool("ffprobe", cfg), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:                       # noqa: BLE001
        return 0.0


# --------------------------------------------------------------------------- #
# 自检
# --------------------------------------------------------------------------- #

PROBE_TEXT = "接口连通性测试。"


def probe(cfg: dict, voices: list[str] | None = None, verbose: bool = True) -> dict:
    """体检：验签 + 服务授权 + 逐个发音人授权情况。"""
    report: dict = {"auth_mode": cfg.get("auth_mode"), "endpoint": cfg["endpoint"]["path"],
                    "auth_ok": False, "voices": {}}

    def line(s):
        if verbose:
            print(s)

    line("─" * 68)
    line(f"端点     : wss://{cfg['endpoint']['host']}{cfg['endpoint']['path']}")
    line(f"鉴权方式 : {cfg.get('auth_mode')}   APPID: {cfg.get('appid')}")
    line("─" * 68)

    # 1) 基础鉴权 + 服务授权
    try:
        audio, sid, meta = synthesize(PROBE_TEXT, cfg,
                                      overrides={"vcn": "x6_lingxiaoxuan_pro", "speed": 50})
        report["auth_ok"] = True
        report["sid"] = sid
        report["probe_bytes"] = len(audio)
        line(f"✅ 鉴权通过 + 服务已授权   收到 {len(audio)} 字节 mp3  sid={sid}")
    except XfyunTTSError as e:
        report["error"] = str(e)
        if e.code == 11200:
            line(f"✅ 鉴权通过（签名有效），但服务未授权 code=11200  sid={e.sid}")
            line("   → 到控制台为该 APPID 开通『超拟人语音合成』服务量："
                 "https://console.xfyun.cn/services/uts")
        elif e.code == 10163:
            line(f"⚠️  鉴权通过，参数校验失败 code=10163 → {e.message[:120]}")
        else:
            line(f"❌ 失败：{e}")
        return report
    except Exception as e:                  # noqa: BLE001
        report["error"] = f"{type(e).__name__}: {e}"
        line(f"❌ 连接/鉴权失败：{type(e).__name__}: {str(e)[:200]}")
        return report

    # 2) 发音人授权
    targets = voices or list(AUTHORIZED_VCN) + list(KNOWN_UNAUTHORIZED_VCN)
    line("")
    line("发音人授权探测：")
    for vcn in targets:
        try:
            _, _, _ = synthesize(PROBE_TEXT, cfg, overrides={"vcn": vcn, "speed": 50})
            report["voices"][vcn] = "ok"
            line(f"  ✅ {vcn:<34} 可用")
        except XfyunTTSError as e:
            if e.code == 11200:
                report["voices"][vcn] = "unauthorized"
                line(f"  ❌ {vcn:<34} 未授权（11200）")
            else:
                report["voices"][vcn] = f"err:{e.code}"
                line(f"  ⚠️  {vcn:<34} code={e.code}")
        except Exception as e:               # noqa: BLE001
            report["voices"][vcn] = f"err:{type(e).__name__}"
            line(f"  ⚠️  {vcn:<34} {type(e).__name__}")
        time.sleep(0.2)

    ok = [v for v, s in report["voices"].items() if s == "ok"]
    line("")
    line(f"可用发音人 {len(ok)} 个：" + "、".join(ok))
    return report


# --------------------------------------------------------------------------- #
# 命令行
# --------------------------------------------------------------------------- #

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="讯飞超拟人语音合成（WebSocket 流式）· 《真假妈妈》配音",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", help="待合成文本")
    src.add_argument("--text-file", help="UTF-8 文本文件")
    src.add_argument("--cast", action="append", metavar="JSON",
                     help="按角色批量配音（可重复多次以合并多张台词表）："
                          '{"lines":[{"id","role","text","tone"}…]}')
    src.add_argument("--lines-json", help='批量：JSON 数组 [{"id","text","vcn"}] 或 {"id":"文本"}')
    src.add_argument("--probe", action="store_true", help="体检：验签 + 授权 + 发音人")
    src.add_argument("--list-vcn", action="store_true", help="列出已验证可用的发音人")
    src.add_argument("--list-tone", action="store_true", help="列出语气预设与停顿语法")

    p.add_argument("--out", help="输出 mp3 路径")
    p.add_argument("--outdir", default="audio", help="批量输出目录（默认 audio/）")
    p.add_argument("--config", help="配置文件路径")
    p.add_argument("--vcn", help="发音人（默认取配置 tts_defaults.vcn）")
    p.add_argument("--speed", type=int, help="语速 0-100")
    p.add_argument("--volume", type=int, help="音量 0-100")
    p.add_argument("--pitch", type=int, help="语调 0-100")
    p.add_argument("--tone", help="语气预设（见 --list-tone），如 焦急/温柔/冷酷")
    p.add_argument("--line", choices=["ultra", "online"], default=None,
                   help="产品线：ultra=超拟人端点（默认，项目配音在用）；"
                        "online=在线语音合成流式版 v2/tts（情绪音色走这条，"
                        "vcn 用 xiaoyan / x4_*_emo 等命名）")
    p.add_argument("--emotion", help="情绪（仅 online 线且音色支持时生效，如 happy/sad/angry；"
                                     "缺省用所选发音人默认情绪）")
    p.add_argument("--oral-level", choices=["high", "mid", "low"], help="口语化等级")
    p.add_argument("--sample-rate", type=int, choices=[8000, 16000, 24000], help="采样率")
    p.add_argument("--autofit", action="store_true",
                   help="配音超出台词表槽位时自动提高 speed 重合成（上限 100）")
    p.add_argument("--stream", action="store_true", help="双向流式分片发送文本")
    p.add_argument("--stream-chunk", type=int, default=200, help="流式分片字数（默认 200）")
    p.add_argument("--timeout", type=float, default=120.0, help="单次会话超时秒数")
    p.add_argument("--trace", action="store_true", help="打印每个响应帧")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.list_vcn:
        print("本账号已联调验证可用的发音人：\n")
        for k, v in AUTHORIZED_VCN.items():
            print(f"  {k:<24} {v}")
        print("\n《真假妈妈》推荐选角：")
        for role, c in CAST_DEFAULT.items():
            print(f"  {role:<8} → {c['vcn']:<22} speed={c['speed']} pitch={c['pitch']}")
        print("\n（以下发音人当前未授权，开通后可直接使用）：")
        for k, v in KNOWN_UNAUTHORIZED_VCN.items():
            print(f"  {k:<32} {v}")
        return 0

    if args.list_tone:
        cfg0 = {}
        try:
            cfg0 = load_config(args.config)
        except SystemExit:
            pass
        table = {**TONE_PRESETS, **(cfg0.get("tone_presets") or {})}
        print("语气预设（speed 语速 / pitch 语调 / volume 音量，均已实测生效）：\n")
        print(f"  {'名称':<8}{'speed':>7}{'pitch':>7}{'volume':>8}   听感")
        print("  " + "─" * 56)
        feel = {
            "平静": "基准，无修饰", "温柔": "放慢、提调、收音量→亲切",
            "亲切": "略慢略高，日常对话", "疑惑": "略慢、提调、收音量→疑问感",
            "焦急": "大幅提速＋提调＋加音量→急",
            "慌张": "最快最亮最大声→失控", "施压": "压低调门、提音量→冷硬压迫",
            "冷酷": "压低沉、中速→无起伏", "威胁": "更低更响→凶",
            "委屈": "放慢、提调、压音量→哭腔", "释然": "放慢、压调、轻→松下来",
            "激动": "快、亮、响", "低沉": "慢、很低、偏轻", "念白": "慢而稳，旁白用",
        }
        for k, v in table.items():
            print(f"  {k:<8}{v.get('speed', 50):>7}{v.get('pitch', 50):>7}"
                  f"{v.get('volume', 50):>8}   {feel.get(k, '')}")
        print("\n用法：")
        print('  · 命令行：  --tone 焦急')
        print('  · 台词表：  {"id":"x","role":"男主","tone":"焦急","text":"…"}')
        print("\n★ 停顿与多音字（写在 text 里，接口原生支持）：")
        print("  [p500]        在当前位置插入 500 毫秒静音 —— 卡口型/凑时长主力")
        print("  [p300] 累加     可多处使用，例如「小宇，[p300]你爸进医院了。」")
        print("  着[=zhuo2]手   指定前一个字的读音（声调 1-5）")
        print("  全角［p500］   也会被自动转成半角，直接打就行")
        return 0

    cfg = load_config(args.config)

    if args.probe:
        probe(cfg)
        return 0

    overrides = {**resolve_tone(cfg, args.tone),
                 "vcn": args.vcn, "speed": args.speed, "volume": args.volume,
                 "pitch": args.pitch, "oral_level": args.oral_level,
                 "emotion": args.emotion,
                 "sample_rate": args.sample_rate}

    # ---- 按角色批量配音（本项目主用路径） ----
    if args.cast:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        cast_map = dict(CAST_DEFAULT)
        lines: list[dict] = []
        for path in args.cast:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(raw, list):                    # 裸数组也接受
                job = {"lines": raw}
            elif isinstance(raw, dict):
                job = raw
            else:
                raise SystemExit(f"{path} 格式不对：应为 {{lines:[…]}} 或 […]。")
            cast_map.update(job.get("cast") or {})
            for ln in job.get("lines") or []:
                if isinstance(ln, str):                  # ["文本", …] 也可
                    ln = {"text": ln}
                lines.append(ln)
        if not lines:
            raise SystemExit('--cast 文件需含 "lines": [{"id","role","text"}, …]')

        manifest, failed, ovf = [], [], []
        probe_path = outdir / ".probe.mp3"   # 注意：勿命名为 probe，否则会遮蔽模块级 probe() 函数
        for i, item in enumerate(lines, 1):
            ident = str(item.get("id") or f"{i:03d}")
            role = str(item.get("role") or "旁白")
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            voice = {**cast_map.get(role, {}),
                     **resolve_tone(cfg, item.get("tone")),
                     **{k: v for k, v in item.items()
                        if k in ("vcn", "speed", "pitch", "volume", "oral_level")}}
            slot = None
            if item.get("start") is not None and item.get("end") is not None:
                slot = float(item["end"]) - float(item["start"])

            tone_tag = f"  [{item['tone']}]" if item.get("tone") else ""
            print(f"[{i:>2}/{len(lines)}] {ident:<16} {role:<6} vcn={voice.get('vcn')}{tone_tag}")
            print(f"          「{text}」")

            chosen, speed = None, int(voice.get("speed", 50))
            for _ in range(4 if args.autofit else 1):
                try:
                    audio, sid, meta = synthesize(text, cfg, stream=args.stream,
                                                  timeout=args.timeout, trace=args.trace,
                                                  line=args.line,
                                                  overrides={**voice, "speed": speed})
                except XfyunTTSError as e:
                    print(f"          ❌ {e}\n")
                    failed.append({"id": ident, "role": role, "text": text, "error": str(e)})
                    break
                probe_path.write_bytes(audio)
                dur = duration_of(probe_path, cfg)
                chosen = (audio, sid, meta, dur, speed)
                if slot is None or dur <= slot + 0.02:
                    break
                # 时长与 speed 近似成反比：dur(speed) ≈ dur*speed/50 * 50/speed'
                new_speed = min(100, int(round(dur * speed / slot)) + 3)
                if new_speed <= speed:
                    break
                print(f"          ↻ {dur:.2f}s 超出槽位 {slot:.2f}s → "
                      f"提速 speed {speed}→{new_speed} 重合成")
                speed = new_speed

            if chosen is None:
                continue
            audio, sid, meta, dur, speed = chosen
            out = outdir / f"{ident}.mp3"
            out.write_bytes(audio)

            if slot is not None:
                ratio = dur / slot
                mark = "✅" if ratio <= 1.02 else ("⚠️ " if ratio <= 1.30 else "❌")
                rate = len(text) / dur if dur else 0
                print(f"          {mark} {dur:5.2f}s / 槽位 {slot:4.2f}s"
                      f"  speed={speed:<3} {rate:4.1f} 字/秒  sid={sid}")
                if ratio > 1.02:
                    need = dur * speed / slot
                    ovf.append({"id": ident, "role": role, "slot": round(slot, 2),
                                "duration": round(dur, 2), "ratio": round(ratio, 2),
                                "speed_used": speed,
                                "min_speed_needed": None if need > 100 else round(need + 3),
                                "infeasible": need > 100,
                                "chars": len(text)})
            else:
                print(f"          ✅ {dur:5.2f}s  无槽位约束  speed={speed}  sid={sid}")
            print()
            manifest.append({"id": ident, "role": role, "text": text,
                             "vcn": voice.get("vcn"), "speed": speed, "file": str(out),
                             "bytes": len(audio), "duration": round(dur, 3),
                             "slot": round(slot, 3) if slot is not None else None,
                             "sid": sid, **meta})

        probe_path.unlink(missing_ok=True)
        mpath = write_manifest(outdir, manifest, failed, ovf)

        total = sum(m["duration"] for m in manifest)
        print("=" * 70)
        print(f"完成：{len(manifest)} 条成功 / {len(failed)} 条失败，"
              f"音频总时长 {total:.2f}s")
        if ovf:
            print(f"\n⚠️  {len(ovf)} 条超出剧本槽位：")
            for o in ovf:
                if o["infeasible"]:
                    print(f"   ❌ {o['id']:<16} {o['duration']:5.2f}s / {o['slot']:4.2f}s"
                          f"  —— 即使 speed=100（最快）也塞不进；"
                          f"需改台词长度或放宽槽位")
                else:
                    print(f"   ⚠️  {o['id']:<16} {o['duration']:5.2f}s / {o['slot']:4.2f}s"
                          f"  —— speed 提到 {o['min_speed_needed']} 可塞进"
                          f"（加 --autofit 自动重合成）")
        print(f"\n清单：{outdir / '_manifest.json'}")
        return 1 if failed else 0

    # ---- 普通批量 ----
    if args.lines_json:
        raw = json.loads(Path(args.lines_json).read_text(encoding="utf-8"))
        items = ([{"id": k, "text": v} for k, v in raw.items()]
                 if isinstance(raw, dict) else raw)
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        manifest = []
        for i, item in enumerate(items, 1):
            ident = str(item.get("id") or f"{i:03d}")
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            print(f"[{i}/{len(items)}] {ident}")
            ov = {**overrides, **{k: item[k] for k in
                                  ("vcn", "speed", "pitch", "volume", "oral_level")
                                  if k in item}}
            audio, sid, meta = synthesize(text, cfg, stream=args.stream,
                                          timeout=args.timeout, trace=args.trace,
                                          line=args.line,
                                          overrides=ov)
            out = outdir / f"{ident}.mp3"
            out.write_bytes(audio)
            manifest.append({"id": ident, "text": text, "file": str(out), "sid": sid, **meta})
            print(f"    → {out}  {len(audio)} 字节  sid={sid}")
        write_manifest(outdir, manifest, [], [])
        print(f"\n批次完成 {len(manifest)} 条；清单：{outdir / '_manifest.json'}")
        return 0

    # ---- 单条 ----
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text
    else:
        _parser().print_help()
        print("\n错误：需要 --text / --text-file / --cast / --lines-json / --probe 之一。")
        return 2

    audio, sid, meta = synthesize(text, cfg, stream=args.stream,
                                  timeout=args.timeout, trace=args.trace,
                                  line=args.line,
                                  overrides=overrides)
    out = Path(args.out or "tts_output.mp3")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio)
    print(f"✅ {out}  {len(audio)} 字节 / {duration_of(out, cfg):.2f}s  "
          f"帧{meta['frames']}  sid={sid}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except XfyunTTSError as e:
        print(f"❌ {e}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
