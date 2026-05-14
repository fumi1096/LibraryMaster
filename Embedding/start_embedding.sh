#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"
sglang serve\
  --model-path ~/model/Qwen3_embedding-0.6b \
  --host 0.0.0.0 \
  --port 30000 \
  --is-embedding&
 #model-path要换成你模型的地址