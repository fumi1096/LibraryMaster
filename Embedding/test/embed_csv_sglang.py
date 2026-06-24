"""
CSV 向量化脚本 — 使用本地 SGLang 嵌入服务给 CSV 文件添加向量列

特点：
  - 分段读取 CSV，防止大文件耗尽内存
  - 批量调用 SGLang（Qwen3-Embedding-0.6B）生成 1024 维向量
  - 逐批写出，内存占用稳定
  - 支持重试，网络抖动时可恢复

用法：
  python embed_csv_sglang.py -i testtable.csv -o testtable_with_vector.csv
  python embed_csv_sglang.py -i testtable.csv --chunk-size 100
  python embed_csv_sglang.py -i testtable.csv --embedding-url http://10.0.0.5:30000/v1
"""

import csv
import json
import argparse
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

# ------------- 默认配置 -------------
DEFAULT_EMBEDDING_URL = "http://127.0.0.1:30000/v1"
DEFAULT_EMBEDDING_MODEL = "Qwen3-Embedding-0.6B"
DEFAULT_EMBEDDING_DIM = 1024
DEFAULT_CHUNK_SIZE = 50       # 每批从 CSV 读取的行数
DEFAULT_RETRY_CNT = 3          # API 调用失败重试次数


def build_text(row):
    """将一行（pandas Series）拼成用于向量化的文本字符串。"""
    parts = []
    for val in row.values:
        s = str(val)
        if s and s != "nan" and s != "None":
            parts.append(s)
    return " ".join(parts)


def embed_batch(client, model, dim, texts, retry=DEFAULT_RETRY_CNT):
    """
    批量向量化，带重试。

    Args:
        client: OpenAI 客户端
        model:   模型名
        dim:     维度（通过前缀 <|dim:N|> 控制）
        texts:   文本列表
        retry:   最大重试次数

    Returns:
        list[list[float]] — 每个文本对应的向量
    """
    # SGLang 通过前缀约定控制输出维度
    prefixed = [f"<|dim:{dim}|>{t}" for t in texts]

    last_err = None
    for attempt in range(retry):
        try:
            resp = client.embeddings.create(model=model, input=prefixed)
            return [d.embedding for d in resp.data]
        except Exception as e:
            last_err = e
            if attempt < retry - 1:
                wait = (attempt + 1) * 2
                print(f"  ⚠ API 失败，{wait}s 后重试 ({attempt + 1}/{retry}): {e}")
                time.sleep(wait)
            else:
                raise last_err


def main():
    parser = argparse.ArgumentParser(
        description="使用本地 SGLang 进行 CSV 向量化（分段读取，内存友好）"
    )
    parser.add_argument("--input", "-i", default="testtable.csv",
                        help="输入 CSV 路径")
    parser.add_argument("--output", "-o", default="testtable_with_vector.csv",
                        help="输出 CSV 路径")
    parser.add_argument("--column-name", default="embedding",
                        help="新增向量列的列名")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                        help=f"每批处理行数（默认 {DEFAULT_CHUNK_SIZE}）")
    parser.add_argument("--embedding-url", default=DEFAULT_EMBEDDING_URL,
                        help=f"SGLang 服务地址（默认 {DEFAULT_EMBEDDING_URL}）")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL,
                        help=f"嵌入模型（默认 {DEFAULT_EMBEDDING_MODEL}）")
    parser.add_argument("--embedding-dim", type=int, default=DEFAULT_EMBEDDING_DIM,
                        help=f"向量维度（默认 {DEFAULT_EMBEDDING_DIM}）")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise SystemExit(f"❌ 输入文件不存在: {input_path}")

    # 仅读取表头，用于确定输出列顺序
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise SystemExit("❌ CSV 没有表头或为空")

    out_columns = list(fieldnames) + [args.column_name]

    # ---------- 初始化 SGLang 客户端 ----------
    print(f"🔗 嵌入服务: {args.embedding_url}")
    print(f"🧠 模型: {args.embedding_model}  (维度: {args.embedding_dim})")
    print(f"📂 输入: {input_path}")
    print(f"📂 输出: {output_path}")
    print(f"📦 分批大小: {args.chunk_size} 行/批")
    print("=" * 60)

    client = OpenAI(base_url=args.embedding_url, api_key="EMPTY")

    # ---------- 分段读取 + 处理 + 写出 ----------
    chunk_iter = pd.read_csv(
        input_path,
        chunksize=args.chunk_size,
        dtype=str,           # 全部按字符串读，避免类型干扰
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    total = 0
    first = True

    for idx, chunk in enumerate(chunk_iter):
        print(f"📦 第 {idx + 1} 批 ({len(chunk)} 行)...")

        # 1) 拼文本
        texts = [build_text(row) for _, row in chunk.iterrows()]

        # 2) 向量化
        try:
            vectors = embed_batch(client, args.embedding_model,
                                  args.embedding_dim, texts)
        except Exception as e:
            print(f"❌ 第 {idx + 1} 批向量化失败: {e}")
            print("   已处理的行已保存，跳过剩余数据。")
            break

        # 3) 加入 DataFrame
        chunk[args.column_name] = [
            json.dumps(v, ensure_ascii=False) for v in vectors
        ]

        # 4) 写出（首批写表头，后续追加）
        chunk.to_csv(
            output_path,
            mode="w" if first else "a",
            header=first,
            index=False,
            encoding="utf-8-sig",
            columns=out_columns,
        )

        total += len(chunk)
        print(f"  ✅ 累计完成 {total} 行")
        first = False

    print("=" * 60)
    print(f"🎉 完成！共处理 {total} 行 → {output_path}")


if __name__ == "__main__":
    main()
