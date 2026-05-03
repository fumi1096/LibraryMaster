#!/bin/bash

sglang serve\
  --model-path ~/model/Qwen3_embedding-0.6b \
  --host 0.0.0.0 \
  --port 30000 \
  --is-embedding&