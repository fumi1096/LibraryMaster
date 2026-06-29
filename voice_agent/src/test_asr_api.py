#!/usr/bin/env python3
"""快速验证讯飞中英识别大模型 API 是否可用"""
import sys, os, time, wave, numpy as np, sounddevice as sd

# 将上级目录加入 sys.path，使 src/ 中的文件能引用同级模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from xunfei_asr import LiveAsrStream

SAMPLE_RATE = 16000
DURATION = 3

print(f"🎙️ 请说话 ({DURATION}s)...")
# 用 float32 录制 (sounddevice 在 float32 模式下可靠缩放到 [-1, 1])
audio_f32 = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
sd.wait()

# float32 [-1,1] → int16
audio = (audio_f32[:, 0] * 32767).astype(np.int16)

# 音频诊断
print(f"📊 音频: shape={audio.shape} dtype={audio.dtype} "
      f"min={audio.min()} max={audio.max()} "
      f"rms={np.sqrt(np.mean(audio.astype(np.float64)**2)):.0f}", flush=True)

if np.abs(audio).max() < 100:
    print("⚠️ 音量太低! 请检查麦克风是否静音或选错设备", flush=True)
    print("   可用 --list-devices 查看: python test_asr_api.py --list-devices", flush=True)

# 保存 WAV
wav_path = "/tmp/test_asr_audio.wav"
with wave.open(wav_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio.tobytes())
print(f"💾 已保存: {wav_path}", flush=True)

print("✅ 录音完成, 开始识别...\n")

stream = LiveAsrStream(
    sample_rate=SAMPLE_RATE,
    on_partial=lambda t: None,
    on_final=lambda t: None,
    on_error=lambda e: print(f"  ❌ 错误: {e}"),
)

try:
    stream.start()
    raw_bytes = audio.tobytes()
    print(f"📤 发送 {len(raw_bytes)} 字节音频...", flush=True)
    stream.feed(raw_bytes)
    stream.end()
    result = stream.wait(timeout=15)
    print(f"\n📄 最终结果: \"{result}\"")
except Exception as e:
    print(f"❌ 失败: {e}")
    sys.exit(1)
