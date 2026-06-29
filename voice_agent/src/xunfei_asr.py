#!/usr/bin/env python3
"""
讯飞中英识别大模型 — 流式语音识别 (WebSocket API)

基于讯飞 spark_zh_iat 接口:
  - 接口地址: wss://iat.xf-yun.com/v1
  - 支持 PCM 原始音频流式传输 (16kHz/16bit/单声道)
  - 实时返回中间结果 + 最终结果
  - 支持动态修正 (dwa=wpgs)

参考文档: https://www.xfyun.cn/doc/spark/spark_zh_iat.html
"""

import json
import base64
import hashlib
import hmac
import time
import threading
import queue
import os
import sys
from datetime import datetime
from urllib.parse import urlencode
from typing import Callable, Optional, Generator
from dataclasses import dataclass, field

# 将上级目录加入 sys.path，使 src/ 中的文件能引用根目录的 config.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import websocket

from config import (
    XUNFEI_ASR_APP_ID,
    XUNFEI_ASR_API_KEY,
    XUNFEI_ASR_API_SECRET,
    XUNFEI_ASR_HOST,
    XUNFEI_ASR_PATH,
)


# ============================================================
# 讯飞 WebSocket 鉴权 (RFC1123 + HMAC-SHA256)
# ============================================================

def _build_auth_url() -> str:
    """构建带鉴权的 WebSocket URL"""
    host = XUNFEI_ASR_HOST
    path = XUNFEI_ASR_PATH
    api_key = XUNFEI_ASR_API_KEY
    api_secret = XUNFEI_ASR_API_SECRET

    # RFC1123 时间 (UTC+0)
    now = datetime.utcnow()
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # 签名原始字符串
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"

    # HMAC-SHA256
    signature_sha = hmac.new(
        api_secret.encode(),
        signature_origin.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode()

    # authorization 原始串
    authorization_origin = (
        f'api_key="{api_key}", '
        f'algorithm="hmac-sha256", '
        f'headers="host date request-line", '
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode()).decode()

    params = {
        "authorization": authorization,
        "date": date,
        "host": host,
    }
    return f"wss://{host}{path}?{urlencode(params)}"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class AsrResult:
    """ASR 识别结果"""
    text: str = ""
    is_final: bool = False


@dataclass
class StreamAsrSession:
    """流式 ASR 会话状态"""
    result_queue: queue.Queue = field(default_factory=queue.Queue)
    final_text: str = ""
    error: Optional[str] = None
    started: bool = False
    finished: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # 动态修正内容映射 (key: 序号, value: 文本片段)
    _content_map: dict = field(default_factory=dict)

    def add_text(self, text: str, is_final: bool = False) -> None:
        with self._lock:
            if is_final:
                self.final_text += text
            self.result_queue.put(AsrResult(text=text, is_final=is_final))

    def set_error(self, error: str) -> None:
        with self._lock:
            self.error = error
            self.finished = True

    def set_finished(self) -> None:
        with self._lock:
            self.finished = True


# ============================================================
# 讯飞中英识别大模型 流式 ASR 客户端
# ============================================================

class XunfeiStreamAsr:
    """讯飞中英识别大模型 — 实时语音转写 (spark_zh_iat)"""

    # 每次发送音频大小 (1280 字节，对应 40ms @ 16kHz/16bit)
    FRAME_SIZE = 1280

    def __init__(self):
        self.app_id = XUNFEI_ASR_APP_ID
        self._check_config()

    @staticmethod
    def _check_config() -> None:
        missing = []
        if not XUNFEI_ASR_APP_ID:
            missing.append("XUNFEI_ASR_APP_ID")
        if not XUNFEI_ASR_API_KEY:
            missing.append("XUNFEI_ASR_API_KEY")
        if not XUNFEI_ASR_API_SECRET:
            missing.append("XUNFEI_ASR_API_SECRET")
        if missing:
            raise ValueError(
                f"讯飞 ASR 配置缺失: {', '.join(missing)}。请在 .env 文件中配置。"
            )

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def recognize_stream(
        self,
        audio_source: Generator[bytes, None, None],
        sample_rate: int = 16000,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        流式识别。

        参数:
            audio_source: 音频数据生成器，每次 yield bytes (int16 PCM)
            sample_rate: 采样率 (8000 或 16000)
            on_partial: 中间结果回调
            on_final: 最终结果回调
            on_error: 错误回调

        返回:
            最终识别文本
        """
        ws_url = _build_auth_url()
        session = StreamAsrSession()
        seq = [0]  # 用列表包装，让闭包可修改

        def _on_open(ws):
            session.started = True

        def _on_message(ws, message):
            try:
                data = json.loads(message)
                header = data.get("header", {})
                code = header.get("code", -1)
                if code != 0:
                    session.set_error(f"ASR error {code}: {header.get('message', '')}")
                    return

                payload = data.get("payload", {})
                result = payload.get("result", {})
                if not result:
                    return

                text_b64 = result.get("text", "")
                if not text_b64:
                    return

                # text 是 base64 编码的 JSON
                text_json = json.loads(base64.b64decode(text_b64).decode("utf-8"))

                # 解析识别词
                req_result = self._parse_ws(text_json)

                # 动态修正处理 (dwa=wpgs)
                pgs = text_json.get("pgs", "")
                if pgs == "apd":
                    # 追加
                    session._content_map[len(session._content_map)] = req_result
                elif pgs == "rpl":
                    # 替换指定范围
                    rg = text_json.get("rg", [])
                    if len(rg) == 2:
                        for i in range(rg[0], rg[1] + 1):
                            session._content_map.pop(i, None)
                    session._content_map[len(session._content_map)] = req_result
                elif not pgs:
                    # 无动态修正，直接追加
                    if req_result:
                        session._content_map[len(session._content_map)] = req_result

                # 拼接当前完整结果
                current_text = "".join(
                    session._content_map[k]
                    for k in sorted(session._content_map)
                )

                is_final = text_json.get("ls", False)
                result_status = result.get("status", 1)

                if result_status == 2 or is_final:
                    # 最终帧
                    session.add_text(current_text, is_final=True)
                    if on_final:
                        on_final(current_text)
                elif on_partial:
                    on_partial(current_text)

            except Exception as e:
                session.set_error(str(e))

        def _on_error(ws, error):
            session.set_error(str(error))

        def _on_close(ws, code, msg):
            session.set_finished()

        def _send_audio():
            """按讯飞官方规范: 1280字节/帧, 间隔40ms"""
            # 等待 WebSocket 连接
            for _ in range(100):
                if session.started:
                    break
                time.sleep(0.05)
            if not session.started:
                session.set_error("WebSocket 连接超时")
                return

            ws = session.ws_app  # type: ignore

            # ---- 收集所有音频数据，按 1280 字节分帧 ----
            audio_buffer = bytearray()
            for chunk in audio_source:
                if session.error:
                    return
                if chunk:
                    audio_buffer.extend(chunk)

            if len(audio_buffer) == 0:
                session.set_error("无音频数据")
                return

            # 按 1280 字节切帧 (40ms @ 16kHz/16bit)
            FRAME_BYTES = 1280
            frames: list[bytes] = []
            for offset in range(0, len(audio_buffer), FRAME_BYTES):
                frames.append(bytes(audio_buffer[offset:offset + FRAME_BYTES]))

            # ---- 逐帧发送 ----
            for i, frame_data in enumerate(frames):
                if session.error:
                    return

                seq[0] += 1
                is_first = (i == 0)
                is_last = (i == len(frames) - 1)

                if is_first:
                    # 第一帧: 带完整参数
                    frame = {
                        "header": {
                            "app_id": self.app_id,
                            "status": 0,
                        },
                        "parameter": {
                            "iat": {
                                "domain": "slm",
                                "language": "zh_cn",
                                "accent": "mandarin",
                                "eos": 6000,
                                "dwa": "wpgs",
                                "result": {
                                    "encoding": "utf8",
                                    "compress": "raw",
                                    "format": "json",
                                },
                            }
                        },
                        "payload": {
                            "audio": {
                                "encoding": "raw",
                                "sample_rate": sample_rate,
                                "channels": 1,
                                "bit_depth": 16,
                                "seq": seq[0],
                                "status": 0,
                                "audio": base64.b64encode(frame_data).decode(),
                            }
                        },
                    }
                elif is_last:
                    # 最后一帧
                    frame = {
                        "header": {
                            "app_id": self.app_id,
                            "status": 2,
                        },
                        "payload": {
                            "audio": {
                                "encoding": "raw",
                                "sample_rate": sample_rate,
                                "channels": 1,
                                "bit_depth": 16,
                                "seq": seq[0],
                                "status": 2,
                                "audio": base64.b64encode(frame_data).decode(),
                            }
                        },
                    }
                else:
                    # 中间帧
                    frame = {
                        "header": {
                            "app_id": self.app_id,
                            "status": 1,
                        },
                        "payload": {
                            "audio": {
                                "encoding": "raw",
                                "sample_rate": sample_rate,
                                "channels": 1,
                                "bit_depth": 16,
                                "seq": seq[0],
                                "status": 1,
                                "audio": base64.b64encode(frame_data).decode(),
                            }
                        },
                    }

                ws.send(json.dumps(frame))
                time.sleep(0.04)  # 官方建议 40ms 间隔

        # ---- 启动 WebSocket ----
        ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )
        session.ws_app = ws_app  # type: ignore

        ws_thread = threading.Thread(
            target=lambda: ws_app.run_forever(sslopt={"cert_reqs": 0}),
            daemon=True,
        )
        ws_thread.start()

        send_thread = threading.Thread(target=_send_audio, daemon=True)
        send_thread.start()

        # 等待完成
        ws_thread.join(timeout=120)
        send_thread.join(timeout=10)

        if session.error:
            if on_error:
                on_error(session.error)
            raise RuntimeError(session.error)

        # 返回拼接后的最终文本
        return "".join(
            session._content_map[k]
            for k in sorted(session._content_map)
        )

    # ----------------------------------------------------------
    # 文本解析
    # ----------------------------------------------------------

    @staticmethod
    def _parse_ws(result: dict) -> str:
        """从识别结果 JSON 中提取词条文本"""
        texts = []
        for ws_item in result.get("ws", []):
            for cw in ws_item.get("cw", []):
                w = cw.get("w", "")
                if w:
                    texts.append(w)
        return "".join(texts)


# ============================================================
# LiveAsrStream — 实时边录边识别 (用于 KWS 唤醒)
# ============================================================

class LiveAsrStream:
    """
    实时流式 ASR 会话。

    用法:
        stream = LiveAsrStream(on_partial=callback, res_id="xxx")
        stream.start()
        stream.feed(audio_bytes)   # 每次喂入 int16 PCM
        stream.feed(audio_bytes)
        stream.end()               # 音频结束
        stream.wait(timeout=10)    # 等待识别完成
    """

    FRAME_BYTES = 1280  # 40ms @ 16kHz/16bit
    SEND_INTERVAL = 0.04

    def __init__(
        self,
        sample_rate: int = 16000,
        res_id: str = "",
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.res_id = res_id
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error

        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._error: Optional[str] = None
        self._finished = threading.Event()

        # 音频缓冲 & 发送控制
        self._buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._seq = 0
        self._first_frame_sent = False
        self._send_cv = threading.Condition()
        self._stream_ended = False

        # 动态修正
        self._content_map: dict[int, str] = {}
        self._latest_text = ""

    # ---- 公开接口 ----

    def start(self) -> None:
        """打开 WebSocket 连接并发送首帧（无音频数据）"""
        if self._ws is not None:
            return

        ws_url = _build_auth_url()
        self._ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        self._ws_thread = threading.Thread(
            target=lambda: self._ws.run_forever(sslopt={"cert_reqs": 0}),
            daemon=True,
        )
        self._ws_thread.start()

        # 等待连接
        if not self._started.wait(timeout=10):
            raise RuntimeError("WebSocket 连接超时")

        # 启动发送线程
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

    def feed(self, audio_bytes: bytes) -> None:
        """喂入 int16 PCM 音频数据"""
        with self._buffer_lock:
            self._buffer.extend(audio_bytes)
        with self._send_cv:
            self._send_cv.notify()

    def end(self) -> None:
        """标记音频流结束"""
        with self._send_cv:
            self._stream_ended = True
            self._send_cv.notify()

    def wait(self, timeout: float = 30) -> str:
        """等待识别完成，返回最终文本"""
        self._finished.wait(timeout=timeout)
        if self._error:
            raise RuntimeError(self._error)
        return self._latest_text

    def close(self) -> None:
        """立即关闭连接"""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._finished.set()

    @property
    def latest_text(self) -> str:
        return self._latest_text

    @property
    def error(self) -> Optional[str]:
        return self._error

    # ---- WebSocket 回调 ----

    def _on_ws_open(self, ws):
        print("  [ASR] WebSocket 已连接", flush=True)
        self._started.set()

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            header = data.get("header", {})
            code = header.get("code", -1)
            if code != 0:
                self._set_error(f"ASR error {code}: {header.get('message', '')}")
                print(f"  [ASR] 服务端错误: code={code} msg={header.get('message', '')}", flush=True)
                return

            payload = data.get("payload", {})
            result = payload.get("result", {})
            if not result:
                # 首帧确认 (status=0, 无 payload.result)
                hdr_status = header.get("status", "?")
                print(f"  [ASR] ← 服务端确认 (header.status={hdr_status})", flush=True)
                return

            text_b64 = result.get("text", "")
            if not text_b64:
                print(f"  [ASR] ← 空结果 seq={result.get('seq','?')} status={result.get('status','?')}", flush=True)
                return

            text_json = json.loads(base64.b64decode(text_b64).decode("utf-8"))
            req_result = XunfeiStreamAsr._parse_ws(text_json)

            # 动态修正 (dwa=wpgs)
            pgs = text_json.get("pgs", "")
            if pgs == "apd":
                self._content_map[len(self._content_map)] = req_result
            elif pgs == "rpl":
                rg = text_json.get("rg", [])
                if len(rg) == 2:
                    for i in range(rg[0], rg[1] + 1):
                        self._content_map.pop(i, None)
                self._content_map[len(self._content_map)] = req_result
            elif req_result:
                self._content_map[len(self._content_map)] = req_result

            self._latest_text = "".join(
                self._content_map[k] for k in sorted(self._content_map)
            )

            is_final = text_json.get("ls", False) or result.get("status") == 2

            # 诊断: 打印每帧识别结果
            marker = "🏁" if is_final else "📝"
            pgs_tag = f" pgs={pgs}" if pgs else ""
            print(f"  [ASR] ← {marker} seq={result.get('seq','?')} "
                  f"text=\"{self._latest_text}\"{pgs_tag}", flush=True)

            if is_final and self._on_final:
                self._on_final(self._latest_text)
            elif self._on_partial:
                self._on_partial(self._latest_text)

            if is_final:
                self._finished.set()

        except Exception as e:
            self._set_error(str(e))

    def _on_ws_error(self, ws, error):
        # 已经拿到最终结果，后续的连接关闭不算错误
        if self._finished.is_set():
            print(f"  [ASR] WebSocket 关闭 (已有结果): {error}", flush=True)
            return
        print(f"  [ASR] WebSocket 错误: {error}", flush=True)
        self._set_error(str(error))

    def _on_ws_close(self, ws, code, msg):
        print(f"  [ASR] WebSocket 关闭: code={code} msg={msg}", flush=True)
        if not self._finished.is_set():
            self._finished.set()

    # ---- 内部 ----

    def _set_error(self, error: str) -> None:
        self._error = error
        if self._on_error:
            self._on_error(error)
        self._finished.set()

    def _sender_loop(self) -> None:
        """后台线程: 从缓冲区取数据，按 1280 字节分帧发送"""
        print("  [ASR] 发送线程启动", flush=True)
        _frame_count = 0
        _fed_total = 0
        while not self._error and not self._finished.is_set():
            with self._send_cv:
                # 等待数据或结束信号
                while (
                    len(self._buffer) < self.FRAME_BYTES
                    and not self._stream_ended
                    and not self._error
                ):
                    self._send_cv.wait(0.1)
                    if self._finished.is_set():
                        print(f"  [ASR] 发送线程被 finished 中断 (已发{_frame_count}帧)", flush=True)
                        return

                if len(self._buffer) == 0 and self._stream_ended:
                    # 发送最后一帧 (空音频)
                    self._send_frame(b"", is_last=True)
                    _frame_count += 1
                    break

                if len(self._buffer) < self.FRAME_BYTES and self._stream_ended:
                    with self._buffer_lock:
                        chunk = bytes(self._buffer)
                        self._buffer.clear()
                else:
                    with self._buffer_lock:
                        chunk = bytes(self._buffer[:self.FRAME_BYTES])
                        self._buffer = self._buffer[self.FRAME_BYTES:]

            if chunk:
                self._send_frame(chunk)
                _frame_count += 1
                _fed_total += len(chunk)
        _last = "(last)" if self._stream_ended else ""
        print(f"  [ASR] 发送线程结束, 共 {_frame_count} 帧 {_fed_total}字节 {_last}", flush=True)

    def _send_frame(self, audio_chunk: bytes, is_last: bool = False) -> None:
        """发送一帧"""
        self._seq += 1

        if not self._first_frame_sent:
            # 首帧带参数
            status = 2 if is_last else 0
            hdr: dict = {"app_id": XUNFEI_ASR_APP_ID, "status": status}
            if self.res_id:
                hdr["res_id"] = self.res_id
            frame: dict = {
                "header": hdr,
                "parameter": {
                    "iat": {
                        "domain": "slm",
                        "language": "zh_cn",
                        "accent": "mandarin",
                        "eos": 6000,
                        "dwa": "wpgs",
                        "result": {"encoding": "utf8", "compress": "raw", "format": "json"},
                    }
                },
                "payload": {
                    "audio": {
                        "encoding": "raw",
                        "sample_rate": self.sample_rate,
                        "channels": 1,
                        "bit_depth": 16,
                        "seq": self._seq,
                        "status": status,
                        "audio": base64.b64encode(audio_chunk).decode(),
                    }
                },
            }
            self._first_frame_sent = True
        elif is_last:
            frame = {
                "header": {"app_id": XUNFEI_ASR_APP_ID, "status": 2},
                "payload": {
                    "audio": {
                        "encoding": "raw",
                        "sample_rate": self.sample_rate,
                        "channels": 1,
                        "bit_depth": 16,
                        "seq": self._seq,
                        "status": 2,
                        "audio": base64.b64encode(audio_chunk).decode(),
                    }
                },
            }
        else:
            frame = {
                "header": {"app_id": XUNFEI_ASR_APP_ID, "status": 1},
                "payload": {
                    "audio": {
                        "encoding": "raw",
                        "sample_rate": self.sample_rate,
                        "channels": 1,
                        "bit_depth": 16,
                        "seq": self._seq,
                        "status": 1,
                        "audio": base64.b64encode(audio_chunk).decode(),
                    }
                },
            }

        try:
            if self._ws:
                self._ws.send(json.dumps(frame))
        except Exception as e:
            self._set_error(str(e))
            return

        time.sleep(self.SEND_INTERVAL)

if __name__ == "__main__":
    import sys
    import sounddevice as sd
    import numpy as np

    print("🧪 讯飞中英识别大模型 ASR 测试")
    print(f"   APP_ID: {XUNFEI_ASR_APP_ID[:8] if XUNFEI_ASR_APP_ID else '(未配置)'}...")
    print(f"   Host: {XUNFEI_ASR_HOST}{XUNFEI_ASR_PATH}")
    print("-" * 45)

    duration = 5
    sample_rate = 16000
    print(f"🎙️ 录音 {duration} 秒...")
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    print("✅ 录音完成")

    def audio_generator():
        """按 1280 字节分块 (官方建议)"""
        data = audio.tobytes()
        frame_size = 1280
        for i in range(0, len(data), frame_size):
            yield data[i:i + frame_size]

    asr = XunfeiStreamAsr()

    def on_partial(text):
        print(f"  📝 中间: {text}")

    try:
        result = asr.recognize_stream(
            audio_generator(),
            on_partial=on_partial,
        )
        print(f"\n📄 最终结果: {result}")
    except Exception as e:
        print(f"❌ 识别失败: {e}")
        sys.exit(1)

