#!/usr/bin/env python3
"""
KWS 全双工语音助手

状态机:
  IDLE ──[唤醒词]──→ WAKING ──[播"我在"]──→ LISTENING ──[VAD+ASR→Agent]──→ SPEAKING
    ↑                                                                        │
    ├──────────────[10s 无语音]────── WAITING ←──[播放完]─────────────────────┤
    │                                    │                                   │
    └────────────────────────────────────┘     [VAD 打断] ──→ LISTENING ──────┘
"""

import sys, os, time, argparse, threading
from enum import Enum, auto
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import sounddevice as sd
import requests

from kws_asr_detector import ASRWakeupDetector, SAMPLE_RATE
from xunfei_asr import LiveAsrStream

SAMPLE_RATE = 16000
VAD_CHUNK_MS = 200
VAD_CHUNK_SAMPLES = int(VAD_CHUNK_MS * SAMPLE_RATE / 1000)
AGENT_CHAT_URL = "http://localhost:9015/api/chat"
AGENT_WAKEUP_URL = "http://localhost:9015/api/voice/wakeup"
AGENT_STATE_URL = "http://localhost:9015/api/voice/state"
AGENT_INTERRUPT_URL = "http://localhost:9015/api/voice/interrupt"
AGENT_REPLY_URL = "http://localhost:9015/api/voice/last-reply"

SESSION = requests.Session()
SESSION.trust_env = False


class State(Enum):
    IDLE = auto()
    WAKING = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    WAITING = auto()


class VadDetector:
    """基于 fsmn-vad 的语音活动检测"""

    def __init__(self):
        self._model = None
        self._cache = {}
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None:
            return
        print("📦 加载 VAD (fsmn-vad)...", flush=True)
        from funasr import AutoModel
        self._model = AutoModel(
            model="fsmn-vad", model_revision="v2.0.4",
            disable_pbar=True, disable_update=True,
        )
        print("✅ VAD 就绪", flush=True)

    def check(self, audio_float: np.ndarray) -> bool:
        self._load()
        with self._lock:
            result = self._model.generate(
                input=audio_float, cache=self._cache,
                is_final=False, chunk_size=VAD_CHUNK_MS,
            )
        boundaries = result[0].get("value", []) if result else []
        for _ts, vad_status in boundaries:
            if vad_status == -1:
                return True
        return False

    def is_speech_end(self, audio_float: np.ndarray) -> bool:
        self._load()
        with self._lock:
            result = self._model.generate(
                input=audio_float, cache=self._cache,
                is_final=False, chunk_size=VAD_CHUNK_MS,
            )
        boundaries = result[0].get("value", []) if result else []
        for _ts, vad_status in boundaries:
            if vad_status >= 0:
                return True
        return False


class VoiceAssistant:
    LISTEN_TIMEOUT = 30.0
    WAITING_TIMEOUT = 10.0
    SILENCE_TIMEOUT = 2.0

    def __init__(self, keyword="你好小图,小图小图", cooldown=3.0,
                 agent_chat_url=AGENT_CHAT_URL, agent_wakeup_url=AGENT_WAKEUP_URL,
                 enable_tts=True):
        self.enable_tts = enable_tts
        self.agent_chat_url = agent_chat_url
        self.agent_wakeup_url = agent_wakeup_url

        self.state = State.IDLE
        self._state_lock = threading.Lock()

        self._detector = ASRWakeupDetector(keywords=keyword, cooldown=cooldown)
        self._vad = VadDetector()
        self._vad._load()  # 预热加载

        self._tts = None
        self._player = None
        self._wozai_pcm: Optional[bytes] = None

        self._asr_stream: Optional[LiveAsrStream] = None
        self._asr_lock = threading.Lock()

        self._speech_active = False
        self._asr_finishing = False
        self._silence_start: Optional[float] = None
        self._listen_start: Optional[float] = None
        self._waiting_start: Optional[float] = None
        self._speaking_start: Optional[float] = None
        self._interrupted = False
        self._thinking_start: Optional[float] = None

        # 回复轮询（避免重复调用 Agent）
        self._last_reply_id_seen: int = 0

        self.wakeup_count = 0
        self.dialog_count = 0

        if self.enable_tts:
            self._pre_generate_wozai()

    @property
    def tts(self):
        if self._tts is None:
            from xunfei_tts import XunfeiTTS
            self._tts = XunfeiTTS()
        return self._tts

    @property
    def player(self):
        if self._player is None:
            from xunfei_tts import InterruptiblePlayer
            self._player = InterruptiblePlayer()
        return self._player

    def _pre_generate_wozai(self):
        print("🔊 预生成「我在」...", flush=True)
        try:
            pcm = self.tts.synthesize("我在", sample_rate=SAMPLE_RATE, encoding="raw")
            if pcm:
                self._wozai_pcm = pcm
                print(f"✅ 预生成完成 ({len(pcm)/2/SAMPLE_RATE:.1f}s)", flush=True)
        except Exception as e:
            print(f"⚠️ 预生成失败: {e}", flush=True)

    def _play_wozai(self):
        if not self._wozai_pcm:
            return
        print("🔊 「我在」", flush=True)
        self.player.play_bytes(self._wozai_pcm, sample_rate=SAMPLE_RATE)

    def _set_state(self, new_state: State):
        with self._state_lock:
            old = self.state
            self.state = new_state
        if old != new_state:
            print(f"  🔄 {old.name} → {new_state.name}", flush=True)

    def _clear_vad_cache(self):
        with self._vad._lock:
            self._vad._cache.clear()

    # ── 音频回调 ─────────────────────────────────

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            return
        audio_float = indata[:, 0].copy()

        with self._state_lock:
            state = self.state

        if state == State.IDLE:
            self._detector._audio_callback(indata, frames, time_info, status)
            return

        # 非 IDLE: 运行 VAD
        speech_start = self._vad.check(audio_float)
        speech_end = self._vad.is_speech_end(audio_float)

        if state == State.LISTENING:
            if self._speech_active:
                audio_int16 = (audio_float * 32767).astype(np.int16).tobytes()
                with self._asr_lock:
                    s = self._asr_stream
                if s is not None:
                    try:
                        s.feed(audio_int16)
                    except Exception:
                        pass

            if speech_end and self._silence_start is None:
                self._silence_start = time.perf_counter()
            elif speech_start:
                self._silence_start = None

            if self._speech_active and not self._asr_finishing:
                now = time.perf_counter()
                if (self._silence_start is not None
                        and now - self._silence_start >= self.SILENCE_TIMEOUT):
                    self._speech_active = False
                    self._asr_finishing = True
                    threading.Thread(target=self._finish_asr, daemon=True).start()
                elif (self._listen_start is not None
                        and now - self._listen_start > self.LISTEN_TIMEOUT):
                    self._speech_active = False
                    self._asr_finishing = True
                    threading.Thread(target=self._finish_asr, daemon=True).start()

        elif state == State.WAITING:
            if speech_start:
                print("  🗣️ 继续对话", flush=True)
                self._clear_vad_cache()
                self._set_state(State.LISTENING)
                self._start_asr_listening()

    # ── ASR ───────────────────────────────────────

    def _start_asr_listening(self):
        self._speech_active = True
        self._silence_start = None
        self._listen_start = time.perf_counter()
        # 注意: _interrupted 不在这里重置，由唤醒时或打断时控制
        self.dialog_count += 1
        self._asr_final_texts: list[str] = []

        print(f"  🎙️ 听写 #{self.dialog_count}", flush=True)

        stream = LiveAsrStream(
            sample_rate=SAMPLE_RATE,
            on_partial=lambda t: None,
            on_final=lambda t: self._asr_final_texts.append(t),
            on_error=lambda e: print(f"  ASR: {e}", flush=True),
        )
        try:
            stream.start()
        except Exception as e:
            print(f"  ASR 启动失败: {e}", flush=True)
            self._speech_active = False
            self._set_state(State.IDLE)
            return

        with self._asr_lock:
            self._asr_stream = stream

    def _finish_asr(self):
        with self._asr_lock:
            stream = self._asr_stream
            self._asr_stream = None

        if stream is None:
            self._asr_finishing = False
            return

        t0 = time.perf_counter()
        print("  ⏹️ 处理...", flush=True)
        final = ""
        try:
            t1 = time.perf_counter()
            stream.end()
            t2 = time.perf_counter()
            final = stream.wait(timeout=5)
            t3 = time.perf_counter()
            print(f"  ⏱️ end={t2-t1:.2f}s wait={t3-t2:.2f}s", flush=True)
        except Exception as e:
            print(f"  ASR 异常 ({time.perf_counter()-t0:.1f}s): {e}", flush=True)
        finally:
            try:
                stream.close()
            except Exception:
                pass
            self._asr_finishing = False

        texts = list(getattr(self, '_asr_final_texts', []))
        if final and final not in texts:
            texts.append(final)
        text = "".join(texts).strip()

        if text:
            print(f"  📝 \"{text}\"", flush=True)
            self._on_asr_result(text)
        else:
            print("  (无识别)", flush=True)
            self._set_state(State.IDLE)

    def _on_asr_result(self, text: str):
        # 发送唤醒文本到前端（前端会通过 WebSocket 调 Agent 并显示回复）
        try:
            SESSION.post(self.agent_wakeup_url,
                         json={"text": text, "source": "kws"}, timeout=5)
        except Exception:
            pass

        self._set_state(State.THINKING)
        self._thinking_start = time.perf_counter()
        print("  🤔 ...", flush=True)
        # 回复不在这里获取，由主循环轮询 /api/voice/last-reply

    def _notify_state(self, state: str):
        """通知 agent_server 当前状态变化"""
        try:
            resp = SESSION.post(AGENT_STATE_URL,
                         json={"state": state}, timeout=2)
            resp.raise_for_status()
        except Exception as e:
            print(f"  ⚠️ 状态通知失败 ({state}): {e}", flush=True)

    def _check_interrupt(self) -> bool:
        """检查 agent_server 是否收到打断请求"""
        try:
            resp = SESSION.get(AGENT_INTERRUPT_URL, timeout=2)
            return resp.json().get("interrupt", False)
        except Exception:
            return False

    def _poll_reply(self) -> Optional[str]:
        """轮询 agent_server 获取前端 Agent 生成的回复文本"""
        try:
            resp = SESSION.get(
                f"{AGENT_REPLY_URL}?since={self._last_reply_id_seen}",
                timeout=2,
            )
            data = resp.json()
            reply_id = data.get("reply_id", 0)
            text = data.get("text", "")
            if reply_id > self._last_reply_id_seen:
                self._last_reply_id_seen = reply_id
                return text if text else None
        except Exception:
            pass
        return None

    def _speak_response(self, text: str):
        self._set_state(State.SPEAKING)
        self._interrupted = False
        self._speaking_start = time.perf_counter()
        self._clear_vad_cache()
        self._notify_state("speaking")

        def _tts_play():
            try:
                chunks = self.tts.synthesize_stream(
                    text, sample_rate=SAMPLE_RATE, encoding="raw")
                self.player.play_stream(chunks, sample_rate=SAMPLE_RATE)
                self.player.wait()
            except Exception as e:
                print(f"  TTS 异常: {e}", flush=True)

            if not self._interrupted:
                print("  ✅ 播放完成", flush=True)
                self._clear_vad_cache()
                self._set_state(State.WAITING)
                self._waiting_start = time.perf_counter()
                self._notify_state("waiting")

        threading.Thread(target=_tts_play, daemon=True).start()

    def _reset_agent(self):
        try:
            SESSION.post("http://localhost:9015/api/reset", timeout=5)
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description="KWS Full-Duplex Voice Assistant")
    p.add_argument("--keyword", default="你好小图,小图小图")
    p.add_argument("--cooldown", type=float, default=3.0)
    p.add_argument("--device", type=int, default=None)
    p.add_argument("--no-tts", action="store_true")
    p.add_argument("--list-devices", action="store_true")
    args = p.parse_args()

    if args.list_devices:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                t = "USB" if "usb" in d["name"].lower() else "  "
                print(f"  [{i}] {t} {d['name']} ({int(d['default_samplerate'])}Hz)")
        return

    print(f"🎤 全双工语音助手 | 唤醒词:{args.keyword} | TTS:{'✅' if not args.no_tts else '❌'}")

    a = VoiceAssistant(keyword=args.keyword, cooldown=args.cooldown,
                       enable_tts=not args.no_tts)

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=VAD_CHUNK_SAMPLES,
                            callback=a.audio_callback, device=args.device)

    print("🟢 监听中... Ctrl+C 退出\n")
    try:
        with stream:
            while True:
                time.sleep(0.2)

                if a.state == State.IDLE:
                    if (a._detector._wakeup_flag.is_set()
                            and not a._detector.is_speaking):
                        a.wakeup_count += 1
                        print(f"\n🔔 唤醒 #{a.wakeup_count}!")
                        time.sleep(0.3)
                        a._set_state(State.WAKING)
                        if a.enable_tts:
                            a._play_wozai()
                            time.sleep(0.6)
                        a._reset_agent()
                        a._interrupted = False
                        a._set_state(State.LISTENING)
                        a._start_asr_listening()
                        a._detector._wakeup_flag.clear()

                elif a.state == State.THINKING:
                    reply = a._poll_reply()
                    if reply is not None:
                        if not reply.strip():
                            a._set_state(State.IDLE)
                            a._notify_state("idle")
                        else:
                            print(f"  💬 \"{reply[:60]}...\"", flush=True)
                            if a.enable_tts and a._wozai_pcm is not None:
                                a._speak_response(reply)
                            else:
                                print(f"  📄 {reply}", flush=True)
                                a._set_state(State.WAITING)
                                a._waiting_start = time.perf_counter()
                                a._notify_state("waiting")
                    elif (a._thinking_start is not None
                          and time.perf_counter() - a._thinking_start > 60):
                        print("  ⏰ Agent 超时，回 IDLE\n")
                        a._set_state(State.IDLE)
                        a._notify_state("idle")

                elif a.state == State.SPEAKING:
                    if a._check_interrupt():
                        print("  🗣️ 打断!", flush=True)
                        a._interrupted = True
                        a.player.stop()
                        a._clear_vad_cache()
                        a._set_state(State.LISTENING)
                        a._start_asr_listening()

                elif a.state == State.WAITING:
                    if a._waiting_start:
                        if time.perf_counter() - a._waiting_start >= a.WAITING_TIMEOUT:
                            print(f"  ⏰ 回 IDLE\n")
                            a._set_state(State.IDLE)
                            a._notify_state("idle")

                elif a.state == State.LISTENING:
                    if (a._listen_start and not a._speech_active
                            and time.perf_counter() - a._listen_start > a.LISTEN_TIMEOUT):
                        print("  ⏰ 回 IDLE\n")
                        a._set_state(State.IDLE)
                        a._notify_state("idle")

    except KeyboardInterrupt:
        print(f"\n📊 唤醒:{a.wakeup_count} 对话:{a.dialog_count}")
        print("👋")


if __name__ == "__main__":
    main()
