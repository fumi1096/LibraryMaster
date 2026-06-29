#!/usr/bin/env python3
"""
voice_relay.py — 宿主机语音中继服务

浏览器无法直接访问麦克风（WebKit2GTK 不支持 getUserMedia），
此服务运行在 RDK X5 宿主机上，提供 HTTP 接口供浏览器调用录音。

用法:
  python3 src/voice_relay.py                          # 默认端口 9016
  python3 src/voice_relay.py --port 9017 --duration 5 # 自定义参数

API:
  POST /record           → 录音并返回转写文本
  GET  /health           → 健康检查
"""

import sys
import os
import json
import time
import wave
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import numpy as np
import sounddevice as sd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from xunfei_asr import LiveAsrStream

SAMPLE_RATE = 16000
DEFAULT_DURATION = 5
DEFAULT_PORT = 9016


def record_audio(duration: float) -> np.ndarray:
    """录制音频，返回 int16 numpy 数组"""
    print(f"🎙️ 录音 {duration}s...", flush=True)
    audio_f32 = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE, channels=1, dtype="float32"
    )
    sd.wait()
    audio = (audio_f32[:, 0] * 32767).astype(np.int16)
    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
    print(f"📊 录音完成 rms={rms:.0f} max={audio.max()}", flush=True)
    return audio


def transcribe_audio(audio: np.ndarray, timeout: float = 15) -> str:
    """通过讯飞 ASR 转写音频"""
    stream = LiveAsrStream(
        sample_rate=SAMPLE_RATE,
        on_partial=lambda t: None,
        on_final=lambda t: None,
        on_error=lambda e: print(f"  ASR 错误: {e}", flush=True),
    )
    stream.start()
    raw_bytes = audio.tobytes()
    stream.feed(raw_bytes)
    stream.end()
    result = stream.wait(timeout=timeout)
    return result or ""


class VoiceHandler(BaseHTTPRequestHandler):
    duration = DEFAULT_DURATION

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}", flush=True)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "service": "voice_relay"})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/record":
            try:
                duration = self.duration
                # 读取请求中的 duration 参数
                content_len = int(self.headers.get("Content-Length", 0))
                if content_len > 0:
                    body = json.loads(self.rfile.read(content_len))
                    duration = float(body.get("duration", self.duration))

                audio = record_audio(duration)
                text = transcribe_audio(audio)

                if text:
                    self._send_json({"text": text, "duration": duration})
                else:
                    self._send_json({"error": "语音识别无结果"}, 422)
            except Exception as e:
                print(f"❌ 录音失败: {e}", flush=True)
                self._send_json({"error": str(e)}, 500)
        else:
            self._send_json({"error": "not found"}, 404)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Voice Relay Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    args = parser.parse_args()

    VoiceHandler.duration = args.duration

    # 列出音频设备
    print("🎧 可用音频设备:", flush=True)
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                print(f"  [{i}] {d['name']} (in={d['max_input_channels']})", flush=True)
    except Exception:
        pass

    server = HTTPServer(("0.0.0.0", args.port), VoiceHandler)
    print(f"\n🚀 Voice Relay 已启动: http://0.0.0.0:{args.port}", flush=True)
    print(f"   POST /record  → 录音 + 转写 (默认 {args.duration}s)", flush=True)
    print(f"   GET  /health  → 健康检查", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 已停止", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()
