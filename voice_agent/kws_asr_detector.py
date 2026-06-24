#!/usr/bin/env python3
"""
KWS 关键词唤醒 — VAD (本地) + 讯飞流式 ASR (云端)

基于讯飞中英识别大模型 spark_zh_iat 流式接口:
  - VAD (fsmn-vad, ~4MB) 检测语音起止
  - 检测到语音后立即打开 WebSocket, 边录边识别
  - 按官方规范: 1280 字节/帧, 40ms 间隔
  - on_partial 实时匹配关键词, 延迟 < 1s

用法:
  python kws_asr_detector.py                          # 默认 "你好小图"
  python kws_asr_detector.py --keyword "小云小云"      # 自定义
  python kws_asr_detector.py --keyword "你好小图,小图小图"  # 多关键词
"""

import argparse
import time
import threading
from collections import deque

import numpy as np
import sounddevice as sd
from funasr import AutoModel

from xunfei_asr import LiveAsrStream

SAMPLE_RATE = 16000
VAD_CHUNK_MS = 200
VAD_CHUNK_SAMPLES = int(VAD_CHUNK_MS * SAMPLE_RATE / 1000)


HOTWORD_RES_ID = "MmNmMWI1OGQxODkxNTMwODkwNGJtYw=="


class ASRWakeupDetector:
    """VAD + 讯飞流式 ASR 唤醒检测 (真正流式, 边录边识别)"""

    def __init__(self, keywords: str = "你好小图", cooldown: float = 3.0):
        self.keywords = [kw.strip() for kw in keywords.split(",")]
        self.cooldown = cooldown

        # VAD 状态
        self.is_speaking = False
        self._speech_start = 0.0

        # 冷却 & 统计
        self._cooldown_until = 0.0
        self.total_wakeups = 0
        self.total_vad_triggers = 0

        # 当前 ASR 流
        self._asr_stream: LiveAsrStream | None = None
        self._asr_lock = threading.Lock()
        self._wakeup_flag = threading.Event()

        # ASR 连接期间的音频缓冲 (避免丢失首帧)
        self._pending_chunks: deque[bytes] = deque()
        self._stream_ready = threading.Event()

        # 预语音缓冲: 保留最近 600ms 音频 (VAD 触发时回补)
        self._pre_speech: deque[np.ndarray] = deque(maxlen=3)  # 3 × 200ms

        self._load_vad()

    # ================================================================
    # VAD 加载
    # ================================================================

    def _load_vad(self) -> None:
        print("📦 加载 VAD (fsmn-vad, ~4MB)...")
        t0 = time.perf_counter()
        self.vad_model = AutoModel(
            model="fsmn-vad", model_revision="v2.0.4",
            disable_pbar=True, disable_update=True,
        )
        self.vad_cache = {}
        print(f"✅ VAD 就绪 ({time.perf_counter() - t0:.1f}s)", flush=True)

    # ================================================================
    # 音频回调 (sounddevice 线程)
    # ================================================================

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            return

        audio_float = indata[:, 0].copy()  # float32 [-1, 1]

        # VAD 检测
        result = self.vad_model.generate(
            input=audio_float, cache=self.vad_cache,
            is_final=False, chunk_size=VAD_CHUNK_MS,
        )
        boundaries = result[0].get("value", []) if result else []

        # 始终保留预语音缓冲 (VAD 触发时回补开头)
        self._pre_speech.append(audio_float)

        # 🔑 先处理 VAD 边界, 再喂音频 (确保当前 chunk 不丢失)
        speech_just_started = False
        for _ts, vad_status in boundaries:
            if vad_status == -1:   # 语音开始
                if not self.is_speaking:
                    self._on_speech_start()
                    speech_just_started = True
            elif vad_status >= 0:  # 语音结束
                if self.is_speaking:
                    self._on_speech_end()

        # 边录边传: VAD 之后 is_speaking 已是最新状态
        # 注意: 如果语音刚刚开始, 当前 chunk 已在 _pre_speech 中被捕获, 不要重复
        if self.is_speaking and not speech_just_started:
            audio_int16 = (audio_float * 32767).astype(np.int16).tobytes()
            with self._asr_lock:
                if self._asr_stream is not None:
                    try:
                        self._asr_stream.feed(audio_int16)
                    except Exception as ex:
                        print(f"  [KWS] feed 异常: {ex}", flush=True)
                elif not self._stream_ready.is_set():
                    self._pending_chunks.append(audio_int16)

        # 首次说话时打印音量诊断
        if self.is_speaking and not self._level_printed:
            self._level_printed = True
            rms = float(np.sqrt(np.mean(audio_float ** 2)))
            peak = float(np.abs(audio_float).max())
            print(f"  🔊 音量: rms={rms:.4f} peak={peak:.4f} "
                  f"({int(rms*32767)}/{int(peak*32767)} int16)", flush=True)

    # ================================================================
    # 语音起止处理
    # ================================================================

    def _on_speech_start(self) -> None:
        if time.perf_counter() < self._cooldown_until:
            return  # 冷却中

        self.is_speaking = True
        self._speech_start = time.perf_counter()
        self._wakeup_flag.clear()
        self._stream_ready.clear()
        self._level_printed = False
        self.total_vad_triggers += 1

        # 将预语音缓冲转 int16 并入 pending (不丢失 VAD 触发前的音频)
        pre_int16: list[bytes] = []
        for chunk in self._pre_speech:
            pre_int16.append((chunk * 32767).astype(np.int16).tobytes())
        self._pending_chunks.clear()
        self._pending_chunks.extend(pre_int16)
        self._pre_speech.clear()

        pre_ms = len(pre_int16) * VAD_CHUNK_MS
        total_pre = sum(len(c) for c in pre_int16)
        print(f"\n🎙️ 检测到语音 (+{pre_ms}ms 预语音, {total_pre}B) (第{self.total_vad_triggers}次)", flush=True)

        # 🔑 在后台线程连接 ASR, 不阻塞音频回调!
        threading.Thread(target=self._connect_asr, daemon=True).start()

    def _connect_asr(self) -> None:
        """后台线程: 连接讯飞 ASR, 连接成功后冲刷缓冲的音频"""
        with self._asr_lock:
            self._asr_stream = LiveAsrStream(
                sample_rate=SAMPLE_RATE,
                res_id=HOTWORD_RES_ID,
                on_partial=self._on_asr_partial,
                on_final=self._on_asr_final,
                on_error=self._on_asr_error,
            )
        try:
            self._asr_stream.start()
        except Exception as e:
            print(f"❌ ASR 启动失败: {e}", flush=True)
            self.is_speaking = False
            with self._asr_lock:
                self._asr_stream = None
            self._stream_ready.set()
            return

        # ASR 就绪 — 冲刷缓冲的音频
        self._stream_ready.set()
        with self._asr_lock:
            chunks = list(self._pending_chunks)
            self._pending_chunks.clear()
        total_bytes = sum(len(c) for c in chunks)
        if total_bytes:
            print(f"  [KWS] ASR 就绪, 冲刷缓冲 {len(chunks)} 块 ({total_bytes}B)", flush=True)
        for chunk in chunks:
            try:
                self._asr_stream.feed(chunk)
            except Exception:
                break

    def _on_speech_end(self) -> None:
        self.is_speaking = False
        dur = time.perf_counter() - self._speech_start

        with self._asr_lock:
            stream = self._asr_stream

        if stream is not None:
            print(f"  [KWS] 语音结束 ({dur:.1f}s), 等待 ASR 结果...", flush=True)
            stream.end()
            # 等待最终结果 (最多等 5 秒)
            try:
                final_text = stream.wait(timeout=5)
            except Exception:
                final_text = stream.latest_text

            if not self._wakeup_flag.is_set():
                if final_text:
                    print(f"📝 [{dur:.1f}s] 最终: \"{final_text}\"", flush=True)
                else:
                    print(f"   [{dur:.1f}s] (无识别结果)", flush=True)
            stream.close()

        with self._asr_lock:
            self._asr_stream = None

    # ================================================================
    # ASR 回调
    # ================================================================

    def _on_asr_partial(self, text: str) -> None:
        """实时中间结果 — 立即检查关键词"""
        if not text or self._wakeup_flag.is_set():
            return
        print(f"  📝 [{time.perf_counter()-self._speech_start:.1f}s] \"{text}\"", flush=True)

        for kw in self.keywords:
            if kw in text:
                self._wakeup_flag.set()
                self._cooldown_until = time.perf_counter() + self.cooldown
                self.total_wakeups += 1
                delay = time.perf_counter() - self._speech_start
                print(f"🔔 唤醒! 关键词: \"{kw}\"  "
                      f"延迟: {delay:.1f}s  累计: {self.total_wakeups}次",
                      flush=True)

                # 立即关闭 ASR 流, 不用等语音结束
                with self._asr_lock:
                    if self._asr_stream is not None:
                        self._asr_stream.close()
                        self._asr_stream = None
                return

    def _on_asr_final(self, text: str) -> None:
        """最终结果"""
        if not self._wakeup_flag.is_set() and text:
            for kw in self.keywords:
                if kw in text:
                    self._wakeup_flag.set()
                    self._cooldown_until = time.perf_counter() + self.cooldown
                    self.total_wakeups += 1
                    print(f"🔔 唤醒! 关键词: \"{kw}\"  "
                          f"累计: {self.total_wakeups}次",
                          flush=True)
                    return

    def _on_asr_error(self, error: str) -> None:
        print(f"⚠️ ASR 错误: {error}", flush=True)

    # ================================================================
    # 统计
    # ================================================================

    @property
    def stats(self) -> str:
        return f"VAD触发: {self.total_vad_triggers}  |  唤醒: {self.total_wakeups}"


# ================================================================
# 入口
# ================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="KWS 唤醒 (VAD + 讯飞流式 ASR)")
    parser.add_argument("--keyword", default="你好小图,小图小图", help="唤醒词(逗号分隔)")
    parser.add_argument("--cooldown", type=float, default=3.0, help="冷却(秒)")
    parser.add_argument("--device", type=int, default=None)
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()

    if args.list_devices:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                tag = "🔌" if "usb" in d["name"].lower() else "  "
                print(f"  [{i}] {tag} {d['name']} ({int(d['default_samplerate'])}Hz)")
        return

    print("=" * 50)
    print("  🎤 KWS 唤醒 (VAD + 讯飞流式 ASR — 边录边识别)")
    print(f"  关键词: {args.keyword}")
    print(f"  内存: ~4MB (仅 VAD)")
    print(f"  接口: wss://iat.xf-yun.com/v1 (中英识别大模型)")
    print("=" * 50)

    detector = ASRWakeupDetector(keywords=args.keyword, cooldown=args.cooldown)
    print("🟢 开始监听... 按 Ctrl+C 退出\n", flush=True)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="float32",
        blocksize=VAD_CHUNK_SAMPLES, callback=detector._audio_callback,
        device=args.device,
    )

    try:
        with stream:
            while True:
                time.sleep(0.3)
    except KeyboardInterrupt:
        print(f"\n📊 {detector.stats}")
        print("👋 再见!")


if __name__ == "__main__":
    main()
