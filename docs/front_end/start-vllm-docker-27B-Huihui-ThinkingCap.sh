#!/bin/bash

LOCAL_MODEL_DIR="/home/julius/models"
MODEL_NAME="Huihui-ThinkingCap-Qwen3.6-27B-abliterated-NVFP4"
JINJA_FILE="qwen3.6-enhanced.jinja"

docker rm -f vllm-27B 2>/dev/null

docker run -d \
  --name vllm-27B \
  --gpus all \
  --ipc=host \
  -p 8089:8089 \
  -v "${LOCAL_MODEL_DIR}:/models" \
  -e HF_HOME=/root/.cache/huggingface \
  -e CUDA_DEVICE_ORDER=PCI_BUS_ID \
  -e CUDA_VISIBLE_DEVICES=0 \
  -e OMP_NUM_THREADS=4 \
  vllm/vllm-openai:v0.26.0 \
  --model "/models/${MODEL_NAME}" \
  --served-model-name gpt-5-nano \
  --chat-template "/models/${JINJA_FILE}" \
  --default-chat-template-kwargs '{"enable_thinking": true}' \
  --attention-backend flashinfer \
  --tensor-parallel-size 1 \
  --max-model-len 81920 \
  --max-num-seqs 4 \
  --max-num-batched-tokens 8192 \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.92 \
  --dtype auto \
  --enable-auto-tool-choice \
  --enable-chunked-prefill \
  --tool-call-parser qwen3_xml \
  --reasoning-parser qwen3 \
  --no-use-tqdm-on-load \
  --host 0.0.0.0 \
  --port 8089 \
  --language-model-only \
  --enable-prefix-caching 
  # --speculative-config '{"method": "mtp", "num_speculative_tokens": 2}' 

 