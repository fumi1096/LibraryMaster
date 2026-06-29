#!/usr/bin/env python3
"""
导出 SenseVoiceSmall 到 ONNX (量化) 以降低内存占用。
"""

import os
import sys
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description="导出 FunASR 模型到 ONNX")
    parser.add_argument("--model", type=str, default="iic/SenseVoiceSmall")
    parser.add_argument("--output-dir", type=str, default="./onnx_models")
    parser.add_argument("--quantize", action="store_true", default=True,
                        help="导出 int8 量化模型 (更小更快)")
    parser.add_argument("--no-quantize", action="store_false", dest="quantize")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"📦 导出模型: {args.model}")
    print(f"   输出目录: {args.output_dir}")
    print(f"   量化: {'int8' if args.quantize else 'fp32'}")
    print("=" * 55)

    t0 = time.perf_counter()

    from funasr import AutoModel

    print("🔄 加载 PyTorch 模型...")
    export_model = AutoModel(
        model=args.model,
        output_dir=args.output_dir,
        device="cpu",
    )

    print(f"🔄 导出 ONNX (quantize={args.quantize})...")
    export_model.export(
        quantize=args.quantize,
        type="onnx",
    )

    t1 = time.perf_counter()
    print(f"✅ 导出完成! 耗时: {t1 - t0:.1f} s")

    # 列出导出文件
    onnx_dir = os.path.join(args.output_dir, args.model)
    if os.path.isdir(onnx_dir):
        print(f"\n📁 导出文件:")
        total_size = 0
        for f in sorted(os.listdir(onnx_dir)):
            path = os.path.join(onnx_dir, f)
            size = os.path.getsize(path)
            total_size += size
            print(f"   {f}: {size / 1024 / 1024:.1f} MB")
        print(f"   总大小: {total_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
