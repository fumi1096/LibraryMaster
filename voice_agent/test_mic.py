"""
麦克风测试程序
测试语音输入功能，基于 sounddevice 录制音频并保存为 WAV 文件。
硬件: ES8326 (duplex-audio), card 0, device 0
"""

import sounddevice as sd
import numpy as np
import wave
import tempfile
import os
import sys
import time
import threading
from datetime import datetime

# ============ 配置参数 ============
DEVICE_NAME = "duplex-audio"       # 麦克风设备名称关键字
SAMPLE_RATE = 16000                # 采样率 (16kHz，适合语音识别)
CHANNELS = 1                       # 单声道
DTYPE = "int16"                    # 采样位深
RECORD_SECONDS = 5                 # 默认录制时长（秒）
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))  # 输出目录
# ================================


def list_audio_devices():
    """列出所有音频设备，标记输入/输出设备"""
    print("=" * 60)
    print("可用的音频设备列表:")
    print("=" * 60)
    devices = sd.query_devices()
    print(devices)
    print("-" * 60)

    # 找到默认输入设备
    default_input = sd.default.device[0]
    default_output = sd.default.device[1]
    print(f"\n默认输入设备索引: {default_input}")
    print(f"默认输出设备索引: {default_output}")

    # 查找匹配的输入设备
    input_devices = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            input_devices.append((i, dev))
            if DEVICE_NAME in dev["name"]:
                print(f"  ✓ 找到目标设备: [{i}] {dev['name']}")

    if not input_devices:
        print("  ⚠ 未找到任何输入（麦克风）设备!")
    return input_devices


def find_target_device():
    """查找目标麦克风设备，返回设备索引"""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and DEVICE_NAME in dev["name"]:
            print(f"使用设备: [{i}] {dev['name']}")
            return i
    return None


def record_audio(duration=RECORD_SECONDS, device=None):
    """录制音频"""
    print(f"\n🎤 开始录音 {duration} 秒 ...")
    
    # 倒计时
    for i in range(duration, 0, -1):
        print(f"   {i} ...", end="\r")
        time.sleep(1)
    print("   录音中 ...")

    # 录制
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=device,
    )
    sd.wait()  # 等待录制完成

    print(f"✅ 录音完成! 共录制 {duration} 秒")
    return recording


def save_wave_file(data, filename):
    """将录音数据保存为 WAV 文件"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data.tobytes())
    file_size = os.path.getsize(filename)
    print(f"💾 文件已保存: {filename}")
    print(f"   文件大小: {file_size / 1024:.1f} KB")
    return filename


def play_audio(data, device=None):
    """播放音频"""
    print("🔊 播放录音 ...")
    sd.play(data, samplerate=SAMPLE_RATE, device=device)
    sd.wait()
    print("✅ 播放完成")


def print_audio_info(data):
    """打印音频数据信息"""
    if isinstance(data, np.ndarray):
        max_val = np.max(np.abs(data))
        rms = np.sqrt(np.mean(data.astype(np.float64) ** 2))
        print("\n📊 音频信息:")
        print(f"  采样率: {SAMPLE_RATE} Hz")
        print(f"  通道数: {CHANNELS}")
        print(f"  数据长度: {len(data)} 采样点")
        print(f"  最大振幅: {max_val}")
        print(f"  RMS 能量: {rms:.1f}")
        print(f"  时长: {len(data) / SAMPLE_RATE:.2f} 秒")

        if max_val < 100:
            print("\n⚠️  警告: 音频信号非常微弱，麦克风可能没有正常拾音!")
            print("   请检查:")
            print("    - 麦克风是否被静音")
            print("    - 音量设置 (使用 alsamixer 检查)")
            print(f"    - 设备是否正确: hw:{find_target_device() or 0},0")
        elif max_val > 30000:
            print("\n📢 音频信号正常，音量充足")
        else:
            print("\n🔉 音频信号正常，音量适中")


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import sounddevice  # noqa
        import numpy  # noqa
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖库: {e}")
        print("\n请安装依赖:")
        print("  pip install sounddevice numpy")
        return False


def interactive_record(device_idx):
    """交互式录制：允许用户多次录制和回放"""
    while True:
        print("\n" + "=" * 50)
        print("🎙️  麦克风测试菜单")
        print("=" * 50)
        print("1. 录制音频 (5秒)")
        print("2. 录制音频 (3秒)")
        print("3. 录制音频 (10秒)")
        print("4. 列出所有音频设备")
        print("5. 退出")
        print("-" * 50)

        choice = input("请选择操作 (1-5): ").strip()

        if choice == "1":
            data = record_audio(5, device=device_idx)
            print_audio_info(data)
            save_wave_file(data, os.path.join(OUTPUT_DIR, "test_mic_output.wav"))
            play_audio(data, device=None)

        elif choice == "2":
            data = record_audio(3, device=device_idx)
            print_audio_info(data)
            fname = f"test_mic_{datetime.now().strftime('%H%M%S')}.wav"
            save_wave_file(data, os.path.join(OUTPUT_DIR, fname))

        elif choice == "3":
            data = record_audio(10, device=device_idx)
            print_audio_info(data)
            fname = f"test_mic_{datetime.now().strftime('%H%M%S')}.wav"
            save_wave_file(data, os.path.join(OUTPUT_DIR, fname))

        elif choice == "4":
            list_audio_devices()

        elif choice == "5":
            print("👋 退出麦克风测试")
            break

        else:
            print("❌ 无效选择，请输入 1-5")


def quick_test(device_idx):
    """快速测试：录制5秒，保存并播放"""
    print("\n===== 🎤 麦克风快速测试 =====")
    data = record_audio(5, device=device_idx)
    print_audio_info(data)

    # 保存
    output_path = os.path.join(OUTPUT_DIR, "test_mic_output.wav")
    save_wave_file(data, output_path)

    # 播放
    play_audio(data, device=None)

    print(f"\n✅ 快速测试完成! 录音文件: {output_path}")
    return output_path


def main():
    """主函数"""
    print("=" * 60)
    print("  🎤 麦克风测试程序 (Microphone Test)")
    print("  硬件: ES8326 / duplex-audio (card 0, device 0)")
    print("=" * 60)

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 列出设备
    input_devices = list_audio_devices()

    if not input_devices:
        print("\n❌ 未找到输入设备，请检查麦克风连接。")
        sys.exit(1)

    # 查找目标设备
    device_idx = find_target_device()
    if device_idx is None:
        print(f"\n未找到名称包含 '{DEVICE_NAME}' 的设备。")
        print(f"将使用默认输入设备 (索引: {sd.default.device[0]})")
        device_idx = sd.default.device[0]

    try:
        # 打印设备详细信息
        dev_info = sd.query_devices(device_idx)
        print(f"\n设备详情: {dev_info['name']}")
        print(f"  输入通道: {dev_info['max_input_channels']}")
        print(f"  默认采样率: {dev_info['default_samplerate']} Hz")

        # 测试模式选择
        print("\n" + "-" * 50)
        print("请选择测试模式:")
        print("  1. 快速测试 (录制5秒 → 保存 → 播放)")
        print("  2. 交互模式 (菜单式多次测试)")
        print("  3. 仅列出设备信息")
        print("-" * 50)

        mode = input("请选择 (1/2/3): ").strip()

        if mode == "1":
            quick_test(device_idx)
        elif mode == "2":
            interactive_record(device_idx)
        elif mode == "3":
            pass  # 已经列出设备了
        else:
            print("无效选择，执行快速测试")
            quick_test(device_idx)

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("\n调试提示:")
        print("  1. 检查 alsamixer: 按 F6 选择声卡，确保 MIC 未被静音")
        print("  2. 尝试: arecord -d 5 -f cd test.wav")
        print("  3. 确认设备: arecord -l")
        sys.exit(1)


if __name__ == "__main__":
    main()
