#!/usr/bin/env python3
"""
语音助手主流程 — 宿主机直接运行

流程：
  ┌─────────────────────────────────────────────────────────┐
  │  USB 麦克风 ─→ [KWS 持续监听]                           │
  │     │ 检测到"你好小图"                                   │
  │     ▼                                                    │
  │  TTS "我在" ─→ 开始录音                                  │
  │     │                                                    │
  │     ▼                                                    │
  │  讯飞流式 ASR (带 VAD: 静音 2s 停止)                    │
  │     │                                                    │
  │     ▼                                                    │
  │  Agent HTTP API (Docker 内) ─→ 获取回复文本             │
  │     │                                                    │
  │     ▼                                                    │
  │  讯飞超拟人 TTS ─→ 播放语音回复                         │
  │     │                                                    │
  │     └──→ 回到 KWS 监听                                   │
  └─────────────────────────────────────────────────────────┘

依赖:
  pip install funasr sounddevice numpy requests websocket-client
"""

import os
import sys
import time
import json
import queue
import threading
from typing import Optional

import numpy as np
import requests
import sounddevice as sd

from config import (
    KWS_WAKEUP_KEYWORD,
    KWS_SILENCE_TIMEOUT_S,
    KWS_MAX_RECORD_S,
    AGENT_SERVER_HOST,
    AGENT_SERVER_PORT,
)

# 绕过系统代理
SESSION = requests.Session()
SESSION.trust_env = False


# ============================================================
# State Machine
# ============================================================

class State:
    IDLE = "idle"
    WOKEN_UP = "woken_up"
    LISTENING = "listening"
    PROCESSING = "processing"


# ============================================================
# KWS 关键词唤醒
# ============================================================

class KeywordSpotter:
    """基于 SenseVoiceSmall 的关键词检测器
    
    持续录音 2 秒 → ASR 转写 → 匹配唤醒词 → 触发唤醒
    """

    def __init__(self, keyword: str = "你好小图", sample_rate: int = 16000):
        self.keyword = keyword
        self.sample_rate = sample_rate
        self.chunk_seconds = 2.0  # 每次检测录 2 秒
        self.cooldown_seconds = 2.0  # 唤醒后冷却 2 秒
        self.model = None
        self._buffer = []  # 音频环形缓冲区
        self._last_check = 0.0
        self._cooldown_until = 0.0
        self._load_model()

    def _load_model(self):
        """加载 SenseVoiceSmall 模型"""
        from funasr import AutoModel
        import wave, tempfile

        print(f"📦 加载 ASR 模型 (用于唤醒词检测)...")
        t0 = time.perf_counter()
        self.model = AutoModel(
            model="iic/SenseVoiceSmall",
            device="cpu",
            disable_update=True,
        )
        elapsed = time.perf_counter() - t0
        print(f"✅ 模型加载完成 ({elapsed:.1f}s)")

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """处理音频块，检测唤醒词"""
        # 冷却期，跳过检测
        if time.perf_counter() < self._cooldown_until:
            return False

        self._buffer.append(audio_chunk.copy())

        # 保持最近 chunk_seconds 秒的音频
        max_chunks = int(self.chunk_seconds * self.sample_rate / len(audio_chunk))
        if len(self._buffer) > max_chunks:
            self._buffer = self._buffer[-max_chunks:]

        # 每 500ms 检测一次
        now = time.perf_counter()
        if now - self._last_check < 0.5:
            return False
        self._last_check = now

        # 检查是否有足够音频
        if len(self._buffer) < max_chunks:
            return False

        # 简易能量检测：无声则跳过
        chunk_data = np.concatenate(self._buffer)
        rms = np.sqrt(np.mean(chunk_data.astype(np.float64) ** 2))
        if rms < 200:  # 静音阈值
            return False

        # ASR 转写
        try:
            import wave, tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(chunk_data.tobytes())

            result = self.model.generate(input=tmp_path, return_raw_text=True)
            os.unlink(tmp_path)

            if result and len(result) > 0:
                text = result[0].get("text", "").lower()
                keyword_lower = self.keyword.lower()
                # SenseVoiceSmall 输出格式: "<|zh|><|EMO_...|><|Speech|><|woitn|>文本"
                # 去掉特殊标记后匹配
                clean = text.split(">")[-1] if ">" in text else text
                if keyword_lower in clean or keyword_lower in text:
                    self._cooldown_until = time.perf_counter() + self.cooldown_seconds
                    self._buffer.clear()
                    return True
        except Exception:
            pass

        return False


# ============================================================
# VAD 静音检测
# ============================================================

class SimpleVAD:
    """基于能量的简单 VAD"""

    def __init__(self, threshold_db: float = -40, sample_rate: int = 16000):
        self.threshold_db = threshold_db
        self.sample_rate = sample_rate

    def is_speech(self, audio: np.ndarray) -> bool:
        """检测音频帧是否有人声"""
        if len(audio) == 0:
            return False
        rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
        if rms < 1e-10:
            return False
        db = 20 * np.log10(rms / 32768.0)
        return db > self.threshold_db


# ============================================================
# Agent HTTP 客户端
# ============================================================

class AgentClient:
    """与 Docker 内 Agent Server 通信"""

    def __init__(self):
        self.base_url = f"http://{AGENT_SERVER_HOST}:{AGENT_SERVER_PORT}"

    def chat(self, text: str) -> str:
        """发送文本给 Agent，返回回复"""
        try:
            resp = SESSION.post(
                f"{self.base_url}/chat",
                json={"text": text},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data.get("reply", "")
        except requests.ConnectionError:
            raise RuntimeError(
                f"无法连接 Agent Server ({self.base_url})。请确保 Docker 容器已启动。"
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Agent 请求失败: {e}")

    def reset(self):
        """重置 Agent 对话历史"""
        try:
            SESSION.post(f"{self.base_url}/reset", timeout=10)
        except Exception:
            pass

    def health(self) -> bool:
        """检查 Agent 是否在线"""
        try:
            resp = SESSION.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


# ============================================================
# 主流程控制器
# ============================================================

class VoiceAssistant:
    """语音助手主控制器"""

    def __init__(self):
        # 检查依赖
        self._check_env()

        # 状态
        self.state = State.IDLE
        self.state_lock = threading.Lock()

        # 组件（延迟加载）
        self._kws: Optional[KeywordSpotter] = None
        self._vad: Optional[SimpleVAD] = None
        self._tts = None
        self._asr = None
        self._agent = None

        print("=" * 55)
        print("  🎤 图书馆语音助手")
        print(f"  唤醒词: \"{KWS_WAKEUP_KEYWORD}\"")
        print(f"  Agent:  http://{AGENT_SERVER_HOST}:{AGENT_SERVER_PORT}")
        print("=" * 55)

    def _check_env(self):
        """检查 Agent Server 是否可达"""
        agent = AgentClient()
        if not agent.health():
            print("⚠️ Agent Server 未响应！请先启动 Docker:")
            print("   cd voice_agent && docker-compose up -d")
            print()
            # 不退出，稍后重试

    @property
    def kws(self) -> KeywordSpotter:
        if self._kws is None:
            self._kws = KeywordSpotter(keyword=KWS_WAKEUP_KEYWORD)
        return self._kws

    @property
    def vad(self) -> SimpleVAD:
        if self._vad is None:
            self._vad = SimpleVAD()
        return self._vad

    @property
    def tts(self):
        if self._tts is None:
            from xunfei_tts import XunfeiTTS
            self._tts = XunfeiTTS()
        return self._tts

    @property
    def asr(self):
        if self._asr is None:
            from xunfei_asr import XunfeiStreamAsr
            self._asr = XunfeiStreamAsr()
        return self._asr

    @property
    def agent(self) -> AgentClient:
        if self._agent is None:
            self._agent = AgentClient()
        return self._agent

    def run(self):
        """主循环"""
        self._print_help()

        sample_rate = 16000
        block_size = int(sample_rate * 0.1)  # 100ms per block

        # 音频缓冲区（ring buffer 用于 KWS + 录音）
        audio_buffer = []  # 累积正在说的话
        recording = False
        silence_start = None
        last_state_print = ""

        def audio_callback(indata, frames, time_info, status):
            nonlocal recording, silence_start, last_state_print

            if status:
                print(f"⚠️ 音频状态: {status}", flush=True)

            audio_chunk = indata[:, 0].copy()

            with self.state_lock:
                state = self.state

            if state == State.IDLE:
                # KWS 关键词检测
                detected = self.kws.process_chunk(audio_chunk)
                if detected:
                    self._on_wakeup()
                    recording = True
                    audio_buffer.clear()
                    silence_start = None

            elif state == State.LISTENING:
                audio_buffer.append(audio_chunk.copy())

                # VAD 静音检测
                if self.vad.is_speech(audio_chunk):
                    silence_start = None
                    # 打印提示
                    if last_state_print != "listening":
                        print("🎙️ 正在听...", flush=True)
                        last_state_print = "listening"
                else:
                    if silence_start is None:
                        silence_start = time.perf_counter()
                    silence_elapsed = time.perf_counter() - silence_start

                    if silence_elapsed >= KWS_SILENCE_TIMEOUT_S:
                        self.state = State.PROCESSING
                        self._on_speech_end(audio_buffer)
                        audio_buffer.clear()
                        recording = False
                        silence_start = None
                        last_state_print = ""

                # 超时保护
                total_duration = len(audio_buffer) * block_size / sample_rate
                if total_duration >= KWS_MAX_RECORD_S:
                    self.state = State.PROCESSING
                    self._on_speech_end(audio_buffer)
                    audio_buffer.clear()
                    recording = False
                    silence_start = None

        # 启动音频流
        print("🟢 开始监听... (说 \"你好小图\" 唤醒我)", flush=True)
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            callback=audio_callback,
            blocksize=block_size,
        )

        with stream:
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n👋 再见！")

    def _on_wakeup(self):
        """检测到唤醒词"""
        with self.state_lock:
            self.state = State.WOKEN_UP

        print(f"\n🔔 检测到唤醒词 \"{KWS_WAKEUP_KEYWORD}\"", flush=True)

        # 在后台线程中说"我在"（不阻塞音频流）
        def _say_hello():
            try:
                self.tts.speak("我在", block=True)
            except Exception as e:
                print(f"⚠️ TTS 唤醒回复失败: {e}")

        t = threading.Thread(target=_say_hello, daemon=True)
        t.start()

        # 短暂等待后进入听写状态
        time.sleep(0.3)
        with self.state_lock:
            self.state = State.LISTENING
        print("👂 请说话... (静音 2 秒自动结束)", flush=True)

    def _on_speech_end(self, audio_chunks: list):
        """录音结束，开始 ASR → Agent → TTS"""
        print("⏸️ 检测到静音，识别中...", flush=True)

        # 合并音频
        audio = np.concatenate(audio_chunks)
        duration = len(audio) / 16000
        print(f"   录音时长: {duration:.1f}s", flush=True)

        # 在后台线程中处理（不阻塞音频流）
        def _process():
            try:
                # 1. ASR
                def audio_gen():
                    yield audio.tobytes()

                partial_text = [""]

                def on_partial(text):
                    if text != partial_text[0]:
                        print(f"  📝 {text}", flush=True)
                        partial_text[0] = text

                text = self.asr.recognize_stream(
                    audio_gen(),
                    on_partial=on_partial,
                )

                if not text or not text.strip():
                    print("⚠️ 未识别到语音内容", flush=True)
                    self._back_to_idle()
                    return

                print(f"✅ 识别结果: {text}", flush=True)

                # 2. Agent
                print("🤔 Agent 思考中...", flush=True)
                reply = self.agent.chat(text)
                print(f"🤖 Agent: {reply}", flush=True)

                # 3. TTS
                print("🔊 播放回复...", flush=True)
                self.tts.speak(reply, block=True)

            except Exception as e:
                print(f"❌ 处理失败: {e}", flush=True)
                # 出错时至少用 TTS 告知用户
                try:
                    self.tts.speak("抱歉，我遇到了一些问题，请稍后重试。", block=True)
                except Exception:
                    pass
            finally:
                self._back_to_idle()

        t = threading.Thread(target=_process, daemon=True)
        t.start()

    def _back_to_idle(self):
        """回到监听状态"""
        with self.state_lock:
            self.state = State.IDLE
        print("\n🟢 继续监听... (说 \"你好小图\" 唤醒我)\n", flush=True)

    @staticmethod
    def _print_help():
        print()
        print("  按 Ctrl+C 退出")
        print()


# ============================================================
# 入口
# ============================================================

def main():
    assistant = VoiceAssistant()
    assistant.run()


if __name__ == "__main__":
    main()
