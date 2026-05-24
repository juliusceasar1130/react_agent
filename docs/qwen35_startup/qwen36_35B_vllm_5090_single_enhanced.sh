#!/bin/bash
# SUCCESS: Proven stable configuration for Qwen3.6-35B-A3B MoE on single RTX 5090
# 
# Verified: Optimized for Blackwell 32GB VRAM & Qwen 3.6 Agentic workflows
# Key fixes:
# - Single GPU TP=1 binding (no NCCL multi-card deadlocks)
# - Custom qwen3.6-enhanced.jinja for stable Tool Calling & Reasoning hidden
# - vLLM Chunked Prefill & Prefix Caching for low TTFT latency under Agent load
# - Marlin FP8 Kernel forcing & FlashInfer MoE backend tuning
#
# Requires: qwen3.6-enhanced.jinja template in /home/julius/models/

# ----------------------------------------------------
#  RTX 5090 单卡极致算力爆发与环境配置
# ----------------------------------------------------
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=0            # 显式锁定单卡运行

export OMP_NUM_THREADS=4                 # CPU 多线程并行调度
export VLLM_USE_FLASHINFER_SAMPLER=1    # 开启 FlashInfer 极速采样（低 TTFT 延迟）
export VLLM_TEST_FORCE_FP8_MARLIN=1     # 强力：对 FP8 激活模型启用 Marlin 极速内核加速
export VLLM_ENABLE_CUDAGRAPH_GC=1       # 垃圾回收 CUDA 图显存，杜绝长期运行的 VRAM 泄露

# 清除 FlashInfer 过期缓存
rm -rf ~/.cache/flashinfer

# 启动推理服务（挂载 Qwen3.6 增强版模板）
vllm serve /home/julius/models/RedHatAIQwen3.6-35B-A3B-NVFP4 \
  --served-model-name gpt-5-nano \
  --chat-template /home/julius/models/qwen3.6-enhanced.jinja \
  --default-chat-template-kwargs '{"preserve_thinking": false}' \
  --attention-backend FLASHINFER \
  --tensor-parallel-size 1 \
  --max-model-len 64072 \
  --max-num-seqs 4 \
  --max-num-batched-tokens 4096 \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.90 \
  --dtype auto \
  --enable-auto-tool-choice \
  --enable-chunked-prefill \
  --enable-prefix-caching \
  --tool-call-parser qwen3_xml \
  --reasoning-parser qwen3 \
  --no-use-tqdm-on-load \
  --moe_backend flashinfer_cutlass \
  --host 0.0.0.0 \
  --port 8089 \
  --language-model-only
