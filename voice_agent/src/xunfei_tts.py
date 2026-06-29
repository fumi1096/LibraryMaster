#!/usr/bin/env python3
"""
讯飞超拟人语音合成 (TTS) — WebSocket 流式

基于讯飞超拟人合成 WebSocket API:
  - 接口地址: wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6
  - 支持多种超拟人音色
  - 流式返回 PCM/MP3 音频
  - 本地扬声器播放

参考文档: https://www.xfyun.cn/doc/spark/super%20smart-tts.html
"""

import json
import base64
import hashlib
import hmac
import time
import threading
import os
import sys
import queue
from datetime import datetime
from urllib.parse import urlencode
from typing import Optional, Generator

# 将上级目录加入 sys.path，使 src/ 中的文件能引用根目录的 config.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import websocket
import sounddevice as sd

from config import (
    XUNFEI_TTS_APP_ID,
    XUNFEI_TTS_API_KEY,
    XUNFEI_TTS_API_SECRET,
    XUNFEI_TTS_HOST,
    XUNFEI_TTS_PATH,
    XUNFEI_TTS_VOICE,
)


# ============================================================
# WebSocket 鉴权
# ============================================================

def _build_auth_url() -> str:
    host = XUNFEI_TTS_HOST
    path = XUNFEI_TTS_PATH
    api_key = XUNFEI_TTS_API_KEY
    api_secret = XUNFEI_TTS_API_SECRET

    now = datetime.utcnow()
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode(), signature_origin.encode(), digestmod=hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode()

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode()).decode()

    params = {"authorization": authorization, "date": date, "host": host}
    return f"wss://{host}{path}?{urlencode(params)}"


# ============================================================
# 讯飞超拟人 TTS 客户端 (WebSocket)
# ============================================================

class XunfeiTTS:
    """讯飞超拟人语音合成"""

    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or XUNFEI_TTS_VOICE
        self._check_config()

    @staticmethod
    def _check_config() -> None:
        missing = []
        if not XUNFEI_TTS_APP_ID:
            missing.append("XUNFEI_TTS_APP_ID")
        if not XUNFEI_TTS_API_KEY:
            missing.append("XUNFEI_TTS_API_KEY")
        if not XUNFEI_TTS_API_SECRET:
            missing.append("XUNFEI_TTS_API_SECRET")
        if missing:
            raise ValueError(
                f"讯飞 TTS 配置缺失: {', '.join(missing)}。请在 .env 文件中配置。"
            )

    def synthesize(self, text: str, speed: int = 50, volume: int = 50,
                   sample_rate: int = 16000, encoding: str = "raw") -> bytes:
        """
        合成语音。

        Args:
            text: 待合成文本
            speed: 语速 0-100
            volume: 音量 0-100
            sample_rate: 采样率 16000 或 24000
            encoding: raw=PCM, lame=MP3

        Returns:
            音频 bytes
        """
        ws_url = _build_auth_url()
        audio_chunks: list[bytes] = []
        error: list[str] = []
        finished = threading.Event()
        lock = threading.Lock()

        def _on_open(ws):
            payload = {
                "header": {"app_id": XUNFEI_TTS_APP_ID, "status": 2},
                "parameter": {
                    "oral": {"oral_level": "mid"},
                    "tts": {
                        "vcn": self.voice,
                        "speed": speed,
                        "volume": volume,
                        "pitch": 50,
                        "audio": {
                            "encoding": encoding,
                            "sample_rate": sample_rate,
                            "channels": 1,
                            "bit_depth": 16,
                            "frame_size": 0,
                        },
                    },
                },
                "payload": {
                    "text": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                        "status": 2,
                        "seq": 0,
                        "text": base64.b64encode(text.encode("utf-8")).decode(),
                    }
                },
            }
            ws.send(json.dumps(payload))

        def _on_message(ws, message):
            try:
                data = json.loads(message)
                header = data.get("header", {})
                code = header.get("code", -1)
                if code != 0:
                    error.append(f"TTS error {code}: {header.get('message', '')}")
                    finished.set()
                    return

                audio_payload = data.get("payload", {}).get("audio", {})
                audio_b64 = audio_payload.get("audio", "")
                if audio_b64:
                    with lock:
                        audio_chunks.append(base64.b64decode(audio_b64))

                if audio_payload.get("status") == 2:
                    finished.set()
            except Exception as e:
                error.append(str(e))
                finished.set()

        def _on_error(ws, err):
            error.append(str(err))
            finished.set()

        def _on_close(ws, code, msg):
            finished.set()

        ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )
        threading.Thread(
            target=lambda: ws_app.run_forever(sslopt={"cert_reqs": 0}),
            daemon=True,
        ).start()

        finished.wait(timeout=30)
        if error:
            raise RuntimeError(error[0])
        return b"".join(audio_chunks)

    def speak(self, text: str, block: bool = True, sample_rate: int = 16000) -> None:
        """合成并播放"""
        import sounddevice as sd

        print(f"🔊 合成: \"{text}\"", flush=True)
        pcm_data = self.synthesize(text, sample_rate=sample_rate, encoding="raw")

        if not pcm_data:
            print("⚠️ 无音频数据", flush=True)
            return

        audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        print(f"� 播放 {len(audio)/sample_rate:.1f}s @ {sample_rate}Hz", flush=True)
        sd.play(audio, samplerate=sample_rate)
        if block:
            sd.wait()
    def synthesize_stream(
        self, text: str, speed: int = 50, volume: int = 50,
        sample_rate: int = 16000, encoding: str = "raw",
    ) -> Generator[bytes, None, None]:
        """
        流式合成语音，逐块返回 PCM 音频数据。

        Yields:
            bytes: PCM 音频数据块
        """
        ws_url = _build_auth_url()
        audio_queue: queue.Queue = queue.Queue()
        error: list[str] = []
        finished = threading.Event()

        def _on_open(ws):
            payload = {
                "header": {"app_id": XUNFEI_TTS_APP_ID, "status": 2},
                "parameter": {
                    "oral": {"oral_level": "mid"},
                    "tts": {
                        "vcn": self.voice,
                        "speed": speed,
                        "volume": volume,
                        "pitch": 50,
                        "audio": {
                            "encoding": encoding,
                            "sample_rate": sample_rate,
                            "channels": 1,
                            "bit_depth": 16,
                            "frame_size": 0,
                        },
                    },
                },
                "payload": {
                    "text": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                        "status": 2,
                        "seq": 0,
                        "text": base64.b64encode(text.encode("utf-8")).decode(),
                    }
                },
            }
            ws.send(json.dumps(payload))

        def _on_message(ws, message):
            try:
                data = json.loads(message)
                header = data.get("header", {})
                code = header.get("code", -1)
                if code != 0:
                    audio_queue.put(("error", f"TTS error {code}: {header.get('message', '')}"))
                    finished.set()
                    return

                audio_payload = data.get("payload", {}).get("audio", {})
                audio_b64 = audio_payload.get("audio", "")
                if audio_b64:
                    audio_queue.put(("chunk", base64.b64decode(audio_b64)))

                if audio_payload.get("status") == 2:
                    audio_queue.put(("done", None))
                    finished.set()
            except Exception as e:
                audio_queue.put(("error", str(e)))
                finished.set()

        def _on_error(ws, err):
            audio_queue.put(("error", str(err)))
            finished.set()

        def _on_close(ws, code, msg):
            audio_queue.put(("done", None))
            finished.set()

        ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )
        threading.Thread(
            target=lambda: ws_app.run_forever(sslopt={"cert_reqs": 0}),
            daemon=True,
        ).start()

        while True:
            try:
                item_type, data = audio_queue.get(timeout=30)
                if item_type == "chunk":
                    yield data
                elif item_type == "done":
                    break
                elif item_type == "error":
                    raise RuntimeError(data)
            except queue.Empty:
                if finished.is_set():
                    break
                raise TimeoutError("TTS 流式合成超时")


# ============================================================
# 可打断的音频播放器
# ============================================================

class InterruptiblePlayer:
    """可被打断的音频播放器，支持流式播放（带预缓冲）和即时停止"""

    def __init__(self):
        self._stop_event = threading.Event()
        self._active_lock = threading.Lock()
        self._active = False
        self._play_thread: Optional[threading.Thread] = None

    def play_stream(
        self,
        audio_source: Generator[bytes, None, None],
        sample_rate: int = 16000,
        pre_buffer_sec: float = 0.5,
    ) -> threading.Thread:
        """
        流式播放音频块，可随时调用 stop() 打断。

        使用 sd.OutputStream + 预缓冲，消除块间间隙。

        Args:
            audio_source: PCM 音频数据生成器
            sample_rate: 采样率
            pre_buffer_sec: 预缓冲秒数（默认 0.5s）
        """
        self._stop_event.clear()
        with self._active_lock:
            self._active = True

        # 共享缓冲区: producer (TTS 线程) 写, callback (PortAudio 线程) 读
        buffer = bytearray()
        buffer_lock = threading.Lock()
        producer_done = threading.Event()

        def _producer():
            try:
                for chunk in audio_source:
                    if self._stop_event.is_set():
                        break
                    with buffer_lock:
                        buffer.extend(chunk)
            finally:
                producer_done.set()

        def _callback(outdata, frames, time_info, status):
            if status:
                return
            # 🔑 每次回调都检查打断标记
            if self._stop_event.is_set():
                raise sd.CallbackStop()

            needed = frames * 2  # int16 = 2 bytes/sample

            with buffer_lock:
                available = len(buffer)
                if available >= needed:
                    raw = bytes(buffer[:needed])
                    del buffer[:needed]
                    outdata[:, 0] = np.frombuffer(
                        raw, dtype=np.int16
                    ).astype(np.float32) / 32768.0
                elif available > 0:
                    # 数据不足，补零
                    raw = bytes(buffer) + b'\x00' * (needed - available)
                    buffer.clear()
                    outdata[:, 0] = np.frombuffer(
                        raw, dtype=np.int16
                    ).astype(np.float32) / 32768.0
                else:
                    outdata.fill(0)
                    if producer_done.is_set() or self._stop_event.is_set():
                        raise sd.CallbackStop()

        def _run():
            producer_t = threading.Thread(target=_producer, daemon=True)
            producer_t.start()

            # 预缓冲: 等待至少 pre_buffer_sec 秒的音频数据
            pre_target = int(sample_rate * 2 * pre_buffer_sec)
            wait_start = time.perf_counter()
            while (len(buffer) < pre_target
                   and not producer_done.is_set()
                   and time.perf_counter() - wait_start < 3.0):
                time.sleep(0.05)

            if not buffer and producer_done.is_set():
                with self._active_lock:
                    self._active = False
                return

            try:
                with sd.OutputStream(
                    samplerate=sample_rate, channels=1, dtype='float32',
                    blocksize=0, callback=_callback,
                ) as stream:
                    while stream.active and not self._stop_event.is_set():
                        time.sleep(0.05)
            except sd.CallbackStop:
                pass
            except Exception:
                pass
            finally:
                with self._active_lock:
                    self._active = False

        self._play_thread = threading.Thread(target=_run, daemon=True)
        self._play_thread.start()
        return self._play_thread

    def play_bytes(
        self, audio_bytes: bytes, sample_rate: int = 16000,
    ) -> threading.Thread:
        """播放单段音频 bytes"""
        self._stop_event.clear()
        with self._active_lock:
            self._active = True

        def _run():
            try:
                if self._stop_event.is_set():
                    return
                audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                sd.play(audio, samplerate=sample_rate)
                sd.wait()
            except Exception:
                pass
            finally:
                with self._active_lock:
                    self._active = False

        self._play_thread = threading.Thread(target=_run, daemon=True)
        self._play_thread.start()
        return self._play_thread

    def stop(self):
        """立即停止播放（仅停止输出流，不影响麦克风输入）"""
        self._stop_event.set()
        # 不调用 sd.stop() — 会同时杀掉麦克风 InputStream
        with self._active_lock:
            self._active = False

    @property
    def is_active(self) -> bool:
        with self._active_lock:
            return self._active

    def wait(self, timeout: Optional[float] = None):
        """等待播放完成"""
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=timeout)

# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import sys

    print("🧪 讯飞超拟人 TTS 测试 (WebSocket)")
    print(f"   音色: {XUNFEI_TTS_VOICE}")
    print(f"   接口: wss://{XUNFEI_TTS_HOST}{XUNFEI_TTS_PATH}")
    print("-" * 45)

    tts = XunfeiTTS()
    try:
        tts.speak("你好，我是图书馆助手小图，有什么可以帮你的吗？")
        print("✅ 完成")
    except Exception as e:
        print(f"❌ 失败: {e}")
        sys.exit(1)
